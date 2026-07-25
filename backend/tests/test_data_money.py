"""Endpoint tests for POST /api/data/money — the merged passbook. Both
upstreams (GetPayInTxnRpt / GetPayOutTxnRpt) are mocked with respx — no live
network. Covers: bare-SessionId credential on both directions, the captured
request body (FY window, UserID from session), merge ordering, landed-only
totals, status-casing normalization, Reason passthrough, destination masking,
the PII drop-list, partial degradation, and the error map."""

import copy
import datetime
import logging

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import config
from app.clock import ist_today
from app.data.money import _MODEL_TXN_CAP, _fy_window, money_model_view
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
    # IST, matching the app — `date.today()` here would make this test pass on an
    # IST dev box and fail on a UTC CI runner inside the 00:00-05:30 window.
    today = ist_today()
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


# --- CHO-277: the model-facing projection ------------------------------------
#
# `money_model_view` bounds what the MODEL reads. Everything the USER sees (the
# route body, the SSE artifact, the card) is built from the unprojected
# envelope, so these tests assert both halves: the projection is small, and the
# thing it was projected from is untouched.

# Byte pin for the route: `POST /api/data/money` must serialize exactly as it
# did before CHO-277 (captured from the pre-change code on the fixtures above).
ROUTE_GOLDEN_BODY = (
    '{"kind":"ok","txns":[{"dir":"out","amt":500.0,"st":"SUCCESS","dt":"2026-07-1'
    '2T10:30:00","mode":null,"dest":"HDFC ••8829","ref":"PV123","rsn":n'
    'ull},{"dir":"in","amt":10149986.0,"st":"PENDING","dt":"2026-07-10T09:12:00",'
    '"mode":null,"dest":"ICICI ••7280","ref":null,"rsn":null},{"dir":"i'
    'n","amt":50.0,"st":"SUCCESS","dt":"2026-07-08T16:19:45","mode":"UPI","dest":'
    '"ICICI ••7280","ref":"BR755189387","rsn":null},{"dir":"out","amt":'
    '75.0,"st":"CANCELLED","dt":"2026-07-01T08:00:00","mode":null,"dest":"Bank '
    '••8829","ref":null,"rsn":null},{"dir":"out","amt":150.0,"st":"FAIL'
    'URE","dt":"2026-06-10T21:01:13","mode":null,"dest":"Bank ••8829","'
    'ref":null,"rsn":"Request rejected due to low funds (Rs 70.61). Try again wit'
    'h a smaller amount."}],"counts":{"SUCCESS":2,"PENDING":1,"CANCELLED":1,"FAIL'
    'URE":1},"landed":{"in":50.0,"out":500.0},"totalRecords":{"in":2,"out":3},"pa'
    'rtial":false}'
)

# One landed deposit and one landed withdrawal, both placed deliberately far
# outside the newest-25 window, so "aggregates are exact" is actually tested.
LANDED_IN_OUTSIDE_CAP = 4242.42
LANDED_OUT_OUTSIDE_CAP = 999.0
_LANDED_IN_INDEX = 60
_LANDED_OUT_INDEX = 65


def _bulk_txns(count: int = 72) -> tuple[list, list]:
    """`count` rows split across both directions on strictly decreasing
    timestamps (index 0 is newest), so the cap boundary is unambiguous. Every
    row is PENDING except the two SUCCESS rows past the cap."""
    base = datetime.datetime(2026, 7, 20, 12, 0, 0)
    payin: list[dict] = []
    payout: list[dict] = []
    for i in range(count):
        stamp = (base - datetime.timedelta(minutes=i)).isoformat()
        if i % 2 == 0:
            payin.append(
                {
                    "Amount": (
                        LANDED_IN_OUTSIDE_CAP
                        if i == _LANDED_IN_INDEX
                        else 100.0 + i
                    ),
                    "Status": "SUCCESS" if i == _LANDED_IN_INDEX else "PENDING",
                    "RequestedDateTime": stamp,
                    "ModeOfPayment": "UPI",
                    "DepositBankName": "ICICI NSE CLIENT A/C - 000405107280",
                    "VoucherNo": f"BR{i}",
                }
            )
        else:
            payout.append(
                {
                    "Amount": (
                        LANDED_OUT_OUTSIDE_CAP
                        if i == _LANDED_OUT_INDEX
                        else 200.0 + i
                    ),
                    "Status": "Success" if i == _LANDED_OUT_INDEX else "PENDING",
                    "RequestedDateTime": stamp,
                    "ClientBankName": "HDFC",
                    "ClientBankAccNo": "50100218008829",
                    "VoucherNo": f"PV{i}",
                    "Reason": "",
                }
            )
    return payin, payout


def _envelope_72(client) -> dict:
    payin, payout = _bulk_txns(72)
    _mock_both(_payin_response(payin), _payout_response(payout))
    payload = client.post("/api/data/money", headers=HEADERS).json()
    assert len(payload["txns"]) == 72  # the fixture really is 72 rows
    return payload


@respx.mock
def test_route_body_is_byte_identical_to_pre_cho_277(client):
    """The projection lives in the dispatcher, not the flow core: the route's
    200 body must not move by a single byte."""
    _mock_both()
    assert client.post("/api/data/money", headers=HEADERS).text == ROUTE_GOLDEN_BODY


@respx.mock
def test_model_view_caps_rows_and_reports_shown_out_of_total(client):
    envelope = _envelope_72(client)

    view = money_model_view(envelope)

    assert len(view["txns"]) == _MODEL_TXN_CAP == 25
    assert view["txnsShown"] == 25
    assert view["txnsTotal"] == 72
    # A prefix of the newest-first stream — a slice, never a re-sort.
    assert view["txns"] == envelope["txns"][:25]
    dates = [t["dt"] for t in view["txns"]]
    assert dates == sorted(dates, reverse=True)


@respx.mock
def test_model_view_does_not_mutate_the_envelope_it_projects(client):
    """The card is rendered from the same object — the projection must be pure."""
    envelope = _envelope_72(client)
    before = copy.deepcopy(envelope)

    money_model_view(envelope)

    assert envelope == before
    assert len(envelope["txns"]) == 72


@respx.mock
def test_model_view_aggregates_are_exact_over_every_row(client):
    """A landed deposit outside the capped rows must still be in `landed` — this
    is the whole reason the aggregates are passed through instead of recomputed
    from the shown rows."""
    envelope = _envelope_72(client)

    view = money_model_view(envelope)

    shown_dates = {t["dt"] for t in view["txns"]}
    landed_in = next(
        t for t in envelope["txns"] if t["amt"] == LANDED_IN_OUTSIDE_CAP
    )
    landed_out = next(
        t for t in envelope["txns"] if t["amt"] == LANDED_OUT_OUTSIDE_CAP
    )
    assert landed_in["dt"] not in shown_dates, "fixture must place it past the cap"
    assert landed_out["dt"] not in shown_dates

    assert view["landed"] == {
        "in": LANDED_IN_OUTSIDE_CAP,
        "out": LANDED_OUT_OUTSIDE_CAP,
    }
    assert view["counts"] == {"SUCCESS": 2, "PENDING": 70}
    assert view["totalRecords"] == {"in": 36, "out": 36}
    assert view["partial"] is False
    # ...and none of the capped rows is one of the SUCCESS rows.
    assert {t["st"] for t in view["txns"]} == {"PENDING"}


@respx.mock
def test_model_view_omission_note_states_what_is_true(client):
    envelope = _envelope_72(client)

    note = money_model_view(envelope)["note"]

    assert "25 most recent of 72" in note
    assert "all 72 transactions and are exact" in note
    assert "card in front of them" in note


@respx.mock
def test_model_view_omission_note_never_invites_a_re_call(client):
    """`get_money_transactions` is zero-slot: a repeat call returns this same
    bounded view, so an invitation to retry would be an invitation to loop."""
    envelope = _envelope_72(client)

    note = money_model_view(envelope)["note"].lower()

    for invitation in (
        "again",
        "re-call",
        "recall",
        "retry",
        "call the tool",
        "call this tool for",
        "more rows",
        "request the",
    ):
        assert invitation not in note, f"note invites a re-call: {invitation!r}"
    assert "takes no parameters" in note


@respx.mock
def test_model_view_leaves_a_short_stream_whole_and_unnoted(client):
    """Under the cap there is nothing to omit — no note, and every row kept."""
    _mock_both()
    envelope = client.post("/api/data/money", headers=HEADERS).json()

    view = money_model_view(envelope)

    assert view["txns"] == envelope["txns"]
    assert (view["txnsShown"], view["txnsTotal"]) == (5, 5)
    assert "note" not in view


@respx.mock
def test_model_view_passes_empty_and_partial_shapes_through(client):
    no_data = httpx.Response(
        200, json={"Status": "Fail", "Response": None, "Reason": "No data found."}
    )
    _mock_both(payin=no_data, payout=no_data)
    empty = client.post("/api/data/money", headers=HEADERS).json()
    assert money_model_view(empty) == {"kind": "empty"} == empty

    respx.reset()
    _mock_both(payout=httpx.Response(500))
    partial = client.post("/api/data/money", headers=HEADERS).json()
    view = money_model_view(partial)
    assert partial["partial"] is True
    assert view["partial"] is True  # verbatim — degradation is never hidden
    assert view["txns"] == partial["txns"]
    assert "note" not in view


def test_model_view_bounds_the_page_size_ceiling():
    """`_PAGE_SIZE = 500` is per direction, so the merged stream can hold ~1,000
    rows (measured at ~64,000 tokens uncapped). The cap makes the tail risk flat:
    the model payload is the same size at 1,000 rows as at 26."""
    row = {"dir": "in", "amt": 1500.0, "st": "SUCCESS", "dt": "2026-07-20T12:00:00",
           "mode": "UPI", "dest": "ICICI ••7280", "ref": "BR1", "rsn": None}
    envelope = {
        "kind": "ok",
        "txns": [dict(row) for _ in range(1000)],
        "counts": {"SUCCESS": 1000},
        "landed": {"in": 1500000.0, "out": 0.0},
        "totalRecords": {"in": 500, "out": 500},
        "partial": False,
    }

    view = money_model_view(envelope)

    assert len(view["txns"]) == _MODEL_TXN_CAP
    assert (view["txnsShown"], view["txnsTotal"]) == (25, 1000)
    assert view["landed"] == {"in": 1500000.0, "out": 0.0}
    assert len(envelope["txns"]) == 1000, "the card still gets the whole stream"


def test_model_view_introduces_no_field_outside_the_pii_whitelist():
    """The projection may only ADD non-PII counts and one sentence."""
    envelope = {
        "kind": "ok",
        "txns": [{"dir": "in", "amt": 1.0, "st": "SUCCESS", "dt": None,
                  "mode": None, "dest": None, "ref": None, "rsn": None}],
        "counts": {"SUCCESS": 1},
        "landed": {"in": 1.0, "out": 0.0},
        "totalRecords": {"in": 1, "out": 0},
        "partial": False,
    }
    added = set(money_model_view(envelope)) - set(envelope)
    assert added == {"txnsShown", "txnsTotal"}
    envelope["txns"] = envelope["txns"] * (_MODEL_TXN_CAP + 1)
    assert set(money_model_view(envelope)) - set(envelope) == {
        "txnsShown", "txnsTotal", "note",
    }


def test_fy_window_uses_the_ist_clock_across_the_new_financial_year(monkeypatch):
    """1 April, 01:00 IST — the UTC clock still reads 31 March, which would
    anchor the pay-in/pay-out window to the *previous* financial year and
    request a full wrong year of transactions. Regression for CHO-224."""
    import app.clock

    # 2027-03-31 19:30 UTC == 2027-04-01 01:00 IST
    monkeypatch.setattr(
        app.clock,
        "_utc_now",
        lambda: datetime.datetime(2027, 3, 31, 19, 30, tzinfo=datetime.timezone.utc),
    )
    monkeypatch.setenv("TZ", "UTC")

    from_date, to_date = _fy_window(ist_today())
    assert from_date == "2027-04-01", "window anchored to the previous FY"
    assert to_date == "2027-04-08"

    # And the bug being guarded against, spelled out: host-local would give this.
    stale_from, _ = _fy_window(datetime.date(2027, 3, 31))
    assert stale_from == "2026-04-01"
