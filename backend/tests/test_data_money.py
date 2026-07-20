"""Endpoint tests for POST /api/data/money — the merged passbook. Both
upstreams (GetPayInTxnRpt / GetPayOutTxnRpt) are mocked with respx — no live
network. Covers: bare-SessionId credential on both directions, the captured
request body (FY window, UserID from session), merge ordering, landed-only
totals, status-casing normalization, Reason passthrough, destination masking,
the PII drop-list, partial degradation, and the error map."""

import datetime
import logging

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import config
from app.main import create_app

HEADERS = {
    "Authorization": "test-sso-jwt",
    "X-Session-Id": "test-session-token",
    "X-User-Id": "X008593",
}

PAYOUT_REASON = (
    "Request rejected due to low funds (Rs 70.61). "
    "Try again with a smaller amount."
)

# Live-captured pay-in shape (SUCCESS casing, ISO-T dates, gateway IDs).
PAYIN_TXNS = [
    {
        "ClientCode": "X008593",
        "ClientName": "RAMESH KUMAR",
        "ModeOfPayment": "UPI",
        "Segment": "NSE_FNO",
        "ClientBankAccNo": "50100218008829",
        "DepositBankName": "ICICI NSE CLIENT A/C - 000405107280",
        "Amount": 50.0,
        "VoucherNo": "BR755189387",
        "JiffyTransactionId": "639641966427013120",
        "AtomReferenceNo": "125033910138477",
        "Status": "SUCCESS",
        "RequestedDateTime": "2026-07-08T16:19:45.29",
        "AccountsDateTime": "2026-07-08T16:19:56.903",
    },
    {   # phantom pending attempt — must never inflate the landed totals
        "ClientCode": "X008593",
        "ClientName": "RAMESH KUMAR",
        "ModeOfPayment": "",
        "Segment": "NSE_CASH",
        "ClientBankAccNo": "50100218008829",
        "DepositBankName": "ICICI NSE CLIENT A/C - 000405107280",
        "Amount": 10149986.0,
        "VoucherNo": "",
        "JiffyTransactionId": "639641966427099999",
        "AtomReferenceNo": "125033910138999",
        "Status": "PENDING",
        "RequestedDateTime": "2026-07-10T09:12:00",
        "AccountsDateTime": "1900-01-01T00:00:00",
    },
]

# Live-captured pay-out shape (mixed casing, space dates, "" sentinels,
# the 'X008593 Excel artifact, the internal Search_All_Levels hierarchy).
PAYOUT_TXNS = [
    {
        "ClientCode": "'X008593",
        "ClientName": "RAMESH KUMAR",
        "Segment": "NSE_CASH",
        "ClientBankName": "",
        "ClientBankAccNo": "50100218008829",
        "Amount": 150.0,
        "Status": "Failure",
        "RequestedDateTime": "2026-06-10 21:01:13",
        "VoucherNo": "",
        "AccountsDateTime": "",
        "Reason": PAYOUT_REASON,
        "Remarks": "PAYOUT REQUESTED",
        "Search_All_Levels": "/Employee//20001//BRANCH/MUMBAI",
    },
    {
        "ClientCode": "'X008593",
        "ClientName": "RAMESH KUMAR",
        "Segment": "NSE_CASH",
        "ClientBankName": "HDFC",
        "ClientBankAccNo": "50100218008829",
        "Amount": 500.0,
        "Status": "Success",  # pay-out casing differs from pay-in's SUCCESS
        "RequestedDateTime": "2026-07-12 10:30:00",
        "VoucherNo": "PV123",
        "AccountsDateTime": "2026-07-12 10:31:02",
        "Reason": "",
        "Remarks": "PAYOUT REQUESTED",
        "Search_All_Levels": "/Employee//20001//BRANCH/MUMBAI",
    },
    {
        "ClientCode": "'X008593",
        "ClientName": "RAMESH KUMAR",
        "Segment": "NSE_CASH",
        "ClientBankName": "",
        "ClientBankAccNo": "50100218008829",
        "Amount": 75.0,
        "Status": "CANCELLED",
        "RequestedDateTime": "2026-07-01 08:00:00",
        "VoucherNo": "",
        "AccountsDateTime": "",
        "Reason": "",
        "Remarks": "",
        "Search_All_Levels": "/Employee//20001//BRANCH/MUMBAI",
    },
]


def _payin_response(txns=None) -> httpx.Response:
    txns = PAYIN_TXNS if txns is None else txns
    return httpx.Response(
        200,
        json={
            "Status": "Success",
            "Response": {
                "PayInTxn": txns,
                "TotalCount": [{"TotalRecords": len(txns)}],
            },
            "Reason": "",
        },
    )


def _payout_response(txns=None) -> httpx.Response:
    txns = PAYOUT_TXNS if txns is None else txns
    return httpx.Response(
        200,
        json={
            "Status": "Success",
            "Response": {
                "PayOutTxn": txns,
                "TotalCount": [{"TotalRecords": len(txns)}],
            },
            "Reason": "",
        },
    )


@pytest.fixture()
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def _mock_both(
    payin: httpx.Response | None = None, payout: httpx.Response | None = None
) -> tuple[respx.Route, respx.Route]:
    in_route = respx.post(config.upstream_payin_url()).mock(
        return_value=payin or _payin_response()
    )
    out_route = respx.post(config.upstream_payout_url()).mock(
        return_value=payout or _payout_response()
    )
    return in_route, out_route


# --- credential + captured request body -------------------------------------

@respx.mock
def test_both_directions_send_bare_session_id(client):
    in_route, out_route = _mock_both()

    client.post("/api/data/money", headers=HEADERS)

    for route in (in_route, out_route):
        assert route.calls.last.request.headers["authorization"] == (
            "test-session-token"
        )


@respx.mock
def test_upstream_body_matches_capture_with_fy_window(client):
    in_route, _ = _mock_both()

    client.post("/api/data/money", headers=HEADERS)

    body = httpx.Response(200, content=in_route.calls.last.request.content).json()
    today = datetime.date.today()
    fy_start = datetime.date(
        today.year if today.month >= 4 else today.year - 1, 4, 1
    )
    assert body == {
        "UserID": "X008593",  # from X-User-Id, never the request body
        "FromDate": fy_start.isoformat(),
        "ToDate": (today + datetime.timedelta(days=7)).isoformat(),
        "Segment": "",
        "Status": "",
        "StartPos": 0,
        "NoOfRecords": 500,
    }


@respx.mock
def test_smuggled_client_code_is_ignored(client):
    in_route, _ = _mock_both()

    client.post(
        "/api/data/money", headers=HEADERS, json={"UserID": "X999999"}
    )

    assert "X999999" not in in_route.calls.last.request.content.decode()


# --- merge, ordering, totals ------------------------------------------------

@respx.mock
def test_merged_stream_is_newest_first(client):
    _mock_both()

    payload = client.post("/api/data/money", headers=HEADERS).json()

    assert payload["kind"] == "ok"
    assert [(t["dir"], t["amt"]) for t in payload["txns"]] == [
        ("out", 500.0),  # 2026-07-12 10:30
        ("in", 10149986.0),  # 2026-07-10 09:12
        ("in", 50.0),  # 2026-07-08 16:19
        ("out", 75.0),  # 2026-07-01 08:00
        ("out", 150.0),  # 2026-06-10 21:01
    ]
    # Both date formats normalized to ISO 8601.
    assert payload["txns"][0]["dt"] == "2026-07-12T10:30:00"
    assert payload["txns"][2]["dt"] == "2026-07-08T16:19:45"


@respx.mock
def test_landed_totals_count_success_only(client):
    _mock_both()

    payload = client.post("/api/data/money", headers=HEADERS).json()

    # The ₹1,01,49,986 pending attempt and the failed/cancelled pay-outs
    # must not inflate the landed totals.
    assert payload["landed"] == {"in": 50.0, "out": 500.0}


@respx.mock
def test_status_counts_and_casing_normalization(client):
    _mock_both()

    payload = client.post("/api/data/money", headers=HEADERS).json()

    assert payload["counts"] == {
        "SUCCESS": 2,  # "SUCCESS" (pay-in) + "Success" (pay-out)
        "PENDING": 1,
        "FAILURE": 1,  # "Failure"
        "CANCELLED": 1,
    }
    assert {t["st"] for t in payload["txns"]} == {
        "SUCCESS", "PENDING", "FAILURE", "CANCELLED",
    }


@respx.mock
def test_total_records_surfaced_per_direction(client):
    _mock_both()

    payload = client.post("/api/data/money", headers=HEADERS).json()

    assert payload["totalRecords"] == {"in": 2, "out": 3}


# --- row content ------------------------------------------------------------

@respx.mock
def test_reason_forwarded_verbatim_and_sentinels_null(client):
    _mock_both()

    payload = client.post("/api/data/money", headers=HEADERS).json()

    failed = next(t for t in payload["txns"] if t["st"] == "FAILURE")
    assert failed["rsn"] == PAYOUT_REASON  # verbatim, display-only
    assert failed["ref"] is None  # "" VoucherNo sentinel
    pending = next(t for t in payload["txns"] if t["st"] == "PENDING")
    assert pending["mode"] is None  # "" ModeOfPayment sentinel
    assert pending["rsn"] is None  # pay-in has no Reason
    success_in = next(
        t for t in payload["txns"] if t["dir"] == "in" and t["st"] == "SUCCESS"
    )
    assert success_in["mode"] == "UPI"
    assert success_in["ref"] == "BR755189387"


@respx.mock
def test_destinations_are_masked(client):
    _mock_both()

    payload = client.post("/api/data/money", headers=HEADERS).json()

    success_in = next(
        t for t in payload["txns"] if t["dir"] == "in" and t["st"] == "SUCCESS"
    )
    assert success_in["dest"] == "ICICI ••7280"
    failed = next(t for t in payload["txns"] if t["st"] == "FAILURE")
    assert failed["dest"] == "Bank ••8829"  # empty ClientBankName → "Bank"
    success_out = next(
        t for t in payload["txns"] if t["dir"] == "out" and t["st"] == "SUCCESS"
    )
    assert success_out["dest"] == "HDFC ••8829"


@respx.mock
def test_pii_drop_list_never_leaves_the_backend(client):
    _mock_both()

    resp = client.post("/api/data/money", headers=HEADERS)

    for dropped in (
        "RAMESH KUMAR",  # ClientName
        "ClientName",
        "50100218008829",  # full account number
        "000405107280",  # full account number inside DepositBankName
        "639641966427013120",  # JiffyTransactionId
        "125033910138477",  # AtomReferenceNo
        "Search_All_Levels",  # internal branch/employee hierarchy
        "/Employee//20001",
        "X008593",  # client code (incl. the 'X008593 Excel artifact)
    ):
        assert dropped not in resp.text


# --- degraded modes ---------------------------------------------------------

@respx.mock
def test_one_direction_failing_returns_partial(client):
    _mock_both(payout=httpx.Response(500))

    resp = client.post("/api/data/money", headers=HEADERS)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["kind"] == "ok"
    assert payload["partial"] is True
    assert all(t["dir"] == "in" for t in payload["txns"])
    assert payload["totalRecords"] == {"in": 2, "out": 0}


@respx.mock
def test_both_directions_failing_is_upstream_error(client):
    _mock_both(payin=httpx.Response(500), payout=httpx.Response(500))

    resp = client.post("/api/data/money", headers=HEADERS)

    assert resp.status_code == 502
    assert resp.json() == {"error": "UPSTREAM_ERROR"}


@respx.mock
def test_auth_expired_wins_when_both_fail(client):
    _mock_both(
        payin=httpx.Response(401, json={"Status": "Fail"}),
        payout=httpx.Response(500),
    )

    resp = client.post("/api/data/money", headers=HEADERS)

    assert resp.status_code == 401
    assert resp.json() == {"error": "AUTH_EXPIRED"}


@respx.mock
def test_no_transactions_either_side_is_empty_kind(client):
    # Business no-data on a transaction report means "no transactions",
    # not a failure (Status gate is field-based — Reason never inspected).
    no_data = httpx.Response(
        200, json={"Status": "Fail", "Response": None, "Reason": "No data found."}
    )
    _mock_both(payin=no_data, payout=no_data)

    resp = client.post("/api/data/money", headers=HEADERS)

    assert resp.status_code == 200
    assert resp.json() == {"kind": "empty"}


@pytest.mark.parametrize("missing", ["Authorization", "X-Session-Id", "X-User-Id"])
def test_missing_header_is_missing_credentials(client, missing):
    headers = {k: v for k, v in HEADERS.items() if k != missing}
    resp = client.post("/api/data/money", headers=headers)
    assert resp.status_code == 400
    assert resp.json() == {"error": "MISSING_CREDENTIALS"}


# --- PII-safe logging -------------------------------------------------------

@respx.mock
def test_logs_carry_no_pii(client, caplog):
    _mock_both()

    with caplog.at_level(logging.DEBUG):
        client.post("/api/data/money", headers=HEADERS)

    logtext = "\n".join(r.getMessage() for r in caplog.records)
    assert "X008593" not in logtext
    assert "RAMESH KUMAR" not in logtext
    assert "50100218008829" not in logtext
    assert "test-session-token" not in logtext
    assert "test-sso-jwt" not in logtext


@respx.mock
def test_full_success_includes_partial_false(client):
    """CHO-220 regression: `partial` must ALWAYS be present — omitting it on
    full success made the frontend reject every healthy payload (the real
    pay-in/pay-out tester bug)."""
    _mock_both()
    payload = client.post("/api/data/money", headers=HEADERS, json={}).json()
    assert payload["kind"] == "ok"
    assert payload["partial"] is False
