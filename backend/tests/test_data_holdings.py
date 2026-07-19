"""Endpoint tests for POST /api/data/holdings. Upstream (COTI) is mocked with
respx — no live network. Covers: the Session-prefixed credential, paise
fidelity against FinX's own CSV values, server-side derivation, ranking,
freshness (max LUT), the PII whitelist, the empty-portfolio kind, the error
map, IDOR defense, and PII-safe logging."""

import json
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

# Live-captured shape: LTP/CP in paise, ABP in rupees, LUT day-first.
HOLDINGS_RESPONSE = {
    "Status": "Success",
    "Response": {
        "lDictHoldingData": {
            "INE028A01039": {
                "Sym": "BANKBARODA-EQ",
                "Name": "BANK OF BARODA",
                "Seg": 1,
                "LTP": 24680,
                "CP": 24830.0,
                "ABP": 125.0,
                "Q": 501,
                "LUT": "17-07-2026 15:58:59",
            },
            "INF204KB14I2": {
                "Sym": "NIFTYBEES-EQ",
                "Name": "NIP IND ETF NIFTY BEES",
                "Seg": 1,
                "LTP": 27646,
                "CP": 27399.0,
                "ABP": 177.0,
                "Q": 215,
                "LUT": "17-07-2026 15:49:38",
            },
            "INF204KB17I5": {
                "Sym": "GOLDBEES-EQ",
                "Name": "NIP IND ETF GOLD BEES",
                "Seg": 1,
                "LTP": 11579,
                "CP": 11647.0,
                "ABP": 64.09,
                "Q": 88,
                "LUT": "17-07-2026 15:49:12",
            },
        },
        "BodStatus": 0,
    },
    "Reason": "",
}


@pytest.fixture()
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def _mock_holdings(response: httpx.Response) -> respx.Route:
    return respx.post(config.upstream_holdings_url()).mock(return_value=response)


def _ok() -> httpx.Response:
    return httpx.Response(200, json=HOLDINGS_RESPONSE)


# --- credential + upstream call --------------------------------------------

@respx.mock
def test_sends_session_prefixed_authorization(client):
    route = _mock_holdings(_ok())

    client.post("/api/data/holdings", headers=HEADERS)

    sent = route.calls.last.request
    assert sent.headers["authorization"] == "Session test-session-token"
    assert sent.headers["from"] == config.finx_from_header()


@respx.mock
def test_smuggled_body_never_reaches_upstream(client):
    """The upstream body is built solely from the session headers — a smuggled
    client code cannot even be read, let alone forwarded (IDOR defense by
    construction)."""
    route = _mock_holdings(_ok())

    client.post(
        "/api/data/holdings",
        headers=HEADERS,
        json={"ClientId": "X999999", "accessToken": "evil"},
    )

    sent_content = route.calls.last.request.content.decode()
    assert "X999999" not in sent_content
    assert "evil" not in sent_content


@respx.mock
def test_upstream_body_carries_required_session_fields(client):
    """COTI requires the body fields (empty body → upstream 404, live-verified);
    every value derives from the authenticated session headers."""
    route = _mock_holdings(_ok())

    client.post("/api/data/holdings", headers=HEADERS)

    sent = json.loads(route.calls.last.request.content.decode())
    assert sent["UserId"] == HEADERS["X-User-Id"]
    assert sent["UserCode"] == HEADERS["X-User-Id"]
    assert sent["GroupId"] == "HO"
    assert sent["SessionId"] == HEADERS["X-Session-Id"]
    assert sent["Status"] == ""


# --- derivation (the CSV-verified numbers) ----------------------------------

@respx.mock
def test_rows_ranked_by_current_value_with_csv_verified_derivation(client):
    _mock_holdings(_ok())

    resp = client.post("/api/data/holdings", headers=HEADERS)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["kind"] == "ok"
    assert [r["sym"] for r in payload["rows"]] == [
        "BANKBARODA",  # 123646.80 — exchange suffix stripped
        "NIFTYBEES",  # 59438.90
        "GOLDBEES",  # 10189.52
    ]

    bank = payload["rows"][0]
    # Known values from FinX's own CSV export (docs/prototype/samples/):
    # q=501, abp=125, ltp=246.80 → current 123646.80, pnl 61021.80, 97.44%.
    assert bank["qty"] == 501
    assert bank["abp"] == 125.0
    assert bank["ltp"] == 246.80  # 24680 paise
    assert bank["current"] == pytest.approx(123646.80)
    assert bank["invested"] == pytest.approx(62625.0)
    assert bank["pnl"] == pytest.approx(61021.80)
    assert bank["pnlPct"] == pytest.approx(97.44)
    # 1D move: 501 × (246.80 − 248.30) = −751.50.
    assert bank["day"] == pytest.approx(-751.50)

    gold = payload["rows"][2]
    assert gold["ltp"] == 115.79  # 11579 paise — the CSV fidelity check
    assert gold["current"] == pytest.approx(10189.52)  # CSV "Current Value"

    nifty = payload["rows"][1]
    assert nifty["current"] == pytest.approx(59438.90)
    assert nifty["pnlPct"] == pytest.approx(56.19)


@respx.mock
def test_totals_and_allocation(client):
    _mock_holdings(_ok())

    payload = client.post("/api/data/holdings", headers=HEADERS).json()

    totals = payload["totals"]
    assert totals["count"] == 3
    assert totals["current"] == pytest.approx(193275.22)
    assert totals["invested"] == pytest.approx(106319.92)
    assert totals["pnl"] == pytest.approx(86955.30)
    assert totals["day"] == pytest.approx(-751.50 + 531.05 - 59.84, abs=0.01)
    # Internal consistency: totals are the sum of the rows they summarize.
    rows = payload["rows"]
    assert totals["current"] == pytest.approx(sum(r["current"] for r in rows))
    assert totals["invested"] == pytest.approx(sum(r["invested"] for r in rows))
    # Allocation covers the whole portfolio and follows the ranking.
    assert sum(r["alloc"] for r in rows) == pytest.approx(100, abs=0.05)
    assert rows[0]["alloc"] > rows[1]["alloc"] > rows[2]["alloc"]


@respx.mock
def test_as_of_is_max_lut_in_iso(client):
    _mock_holdings(_ok())

    payload = client.post("/api/data/holdings", headers=HEADERS).json()

    # Max LUT across scrips (15:58:59 beats the two 15:49 stamps), day-first.
    assert payload["asOf"] == "2026-07-17T15:58:59"


# --- PII whitelist ----------------------------------------------------------

@respx.mock
def test_only_whitelisted_fields_forwarded(client):
    _mock_holdings(_ok())

    resp = client.post("/api/data/holdings", headers=HEADERS)

    row = resp.json()["rows"][0]
    assert set(row.keys()) == {
        "sym", "name", "qty", "abp", "ltp", "current", "invested",
        "pnl", "pnlPct", "day", "dayPct", "alloc",
    }
    # Non-whitelisted upstream fields (Seg, LUT, ISIN keys) never leave.
    assert "Seg" not in resp.text
    assert "INE028A01039" not in resp.text
    assert "BodStatus" not in resp.text


# --- empty portfolio + error map --------------------------------------------

@respx.mock
def test_empty_holdings_dict_is_empty_kind(client):
    _mock_holdings(
        httpx.Response(
            200,
            json={
                "Status": "Success",
                "Response": {"lDictHoldingData": {}, "BodStatus": 0},
                "Reason": "",
            },
        )
    )

    resp = client.post("/api/data/holdings", headers=HEADERS)

    assert resp.status_code == 200
    assert resp.json() == {"kind": "empty"}


@respx.mock
def test_upstream_401_maps_to_auth_expired(client):
    _mock_holdings(
        httpx.Response(401, json={"Status": "Fail", "Reason": "Invalid Session"})
    )

    resp = client.post("/api/data/holdings", headers=HEADERS)

    assert resp.status_code == 401
    assert resp.json() == {"error": "AUTH_EXPIRED"}


@respx.mock
def test_body_failure_status_maps_to_no_data(client):
    _mock_holdings(
        httpx.Response(
            200, json={"Status": "Fail", "Response": None, "Reason": "Data not found."}
        )
    )

    resp = client.post("/api/data/holdings", headers=HEADERS)

    assert resp.status_code == 404
    assert resp.json() == {"error": "NO_DATA"}


@respx.mock
def test_upstream_500_maps_to_upstream_error(client):
    _mock_holdings(httpx.Response(500))

    resp = client.post("/api/data/holdings", headers=HEADERS)

    assert resp.status_code == 502
    assert resp.json() == {"error": "UPSTREAM_ERROR"}


@pytest.mark.parametrize("missing", ["Authorization", "X-Session-Id", "X-User-Id"])
def test_missing_header_is_missing_credentials(client, missing):
    headers = {k: v for k, v in HEADERS.items() if k != missing}
    resp = client.post("/api/data/holdings", headers=headers)
    assert resp.status_code == 400
    assert resp.json() == {"error": "MISSING_CREDENTIALS"}


# --- PII-safe logging -------------------------------------------------------

@respx.mock
def test_logs_carry_no_pii(client, caplog):
    _mock_holdings(_ok())

    with caplog.at_level(logging.DEBUG):
        client.post("/api/data/holdings", headers=HEADERS)

    logtext = "\n".join(r.getMessage() for r in caplog.records)
    assert "X008593" not in logtext
    assert "test-session-token" not in logtext
    assert "test-sso-jwt" not in logtext
    assert "BANKBARODA" not in logtext  # never log upstream bodies
