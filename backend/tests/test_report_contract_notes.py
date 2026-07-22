"""Endpoint tests for the Contract Notes two-call flow (CHO-210, Wave 1):

  POST /api/report/contract-notes/list
  POST /api/report/contract-notes/download

Both upstream hosts are mocked with respx — no live network. Covers: the
list→client mapping (DDMMYYYY → "DD Mon YYYY", month grouping, sorted), the
same-date badge logic, the 204-empty branch, the download raw-bytes → token
path (no password), the "Session " auth prefix, IDOR defense on both calls,
the sensitive file_id never leaking to the client or the logs, and the shared
file-token endpoint reuse.

The Wave-1 router is wired onto a fresh `create_app()` here (main.py
integration is owned by the orchestrator); the shared file-token endpoint
`GET /api/report/file/{token}` comes from the report router `create_app()`
already includes.
"""

import logging
from datetime import datetime, timezone

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import config
from app.main import create_app
from app.reports import contract_notes
from app.reports.contract_notes import router as contract_notes_router

HEADERS = {
    "Authorization": "test-sso-jwt",
    "X-Session-Id": "test-session-token",
    "X-User-Id": "X008593",
}

# ~88-char opaque download handles — sensitive, must never reach the client.
FILE_ID_EQUITY = "EQ" + "a" * 86
FILE_ID_COMMODITY = "CM" + "b" * 86
FILE_ID_SINGLE = "SG" + "c" * 86

PDF_BYTES = b"%PDF-1.4\n" + b"x" * 4000  # ~4 KB fake contract-note PDF

LIST_BODY = {"fromDate": "2024-09-01", "toDate": "2024-09-30"}


@pytest.fixture()
def client():
    app = create_app()
    # Wave-1 flow: wire the contract-notes router (main.py integration is done
    # later by the orchestrator). The file-token endpoint is already present.
    app.include_router(contract_notes_router)
    with TestClient(app) as test_client:
        yield test_client


def _mock_list(response: httpx.Response) -> respx.Route:
    return respx.post(contract_notes._contract_list_url()).mock(return_value=response)


def _mock_download(response: httpx.Response) -> respx.Route:
    return respx.post(contract_notes._contract_download_url()).mock(
        return_value=response
    )


def _list_ok() -> httpx.Response:
    """Two notes on 16 Sep (Equity + Commodity) + one on 18 Sep (Equity)."""
    return httpx.Response(
        200,
        json={
            "StatusCode": 200,
            "Message": "Success",
            "DevMessage": None,
            "Body": {
                "client_code": "X008593",
                "contractNotes": [
                    {"date": "16092024", "file_id": FILE_ID_EQUITY,
                     "group": "Grp1", "id": "16092024", "invoice_number": "2140106"},
                    {"date": "16092024", "file_id": FILE_ID_COMMODITY,
                     "group": "Grp2", "id": "16092024", "invoice_number": "2140107"},
                    {"date": "18092024", "file_id": FILE_ID_SINGLE,
                     "group": "GRP1", "id": "18092024", "invoice_number": "2140200"},
                ],
            },
        },
    )


def _pdf_response() -> httpx.Response:
    return httpx.Response(
        200, content=PDF_BYTES, headers={"content-type": "application/pdf"}
    )


# --- list mapping -----------------------------------------------------------

@respx.mock
def test_list_maps_notes_sorted_with_month_and_date(client):
    _mock_list(_list_ok())

    resp = client.post(
        "/api/report/contract-notes/list", headers=HEADERS, json=LIST_BODY
    )

    assert resp.status_code == 200
    notes = resp.json()["notes"]
    assert [n["date"] for n in notes] == ["16 Sep 2024", "16 Sep 2024", "18 Sep 2024"]
    assert all(n["month"] == "SEPTEMBER 2024" for n in notes)
    assert {n["segment"] for n in notes} == {"Equity & F&O", "Commodity"}
    # Every note carries an opaque id (not the upstream id which == the date).
    assert all(n["id"] and n["id"] not in ("16092024", "18092024") for n in notes)


@respx.mock
def test_badge_only_when_a_date_has_two_notes(client):
    _mock_list(_list_ok())

    notes = client.post(
        "/api/report/contract-notes/list", headers=HEADERS, json=LIST_BODY
    ).json()["notes"]

    same_day = [n for n in notes if n["date"] == "16 Sep 2024"]
    single = next(n for n in notes if n["date"] == "18 Sep 2024")

    # Two notes on 16 Sep → each gets its exchange badge (Equity vs Commodity).
    badges = {n["segment"]: n["badge"] for n in same_day}
    assert badges == {"Equity & F&O": "NSE·BSE", "Commodity": "MCX"}
    # One note on 18 Sep → no disambiguating badge.
    assert single["segment"] == "Equity & F&O"
    assert single["badge"] is None


@respx.mock
def test_list_never_exposes_file_id(client):
    _mock_list(_list_ok())

    resp = client.post(
        "/api/report/contract-notes/list", headers=HEADERS, json=LIST_BODY
    )

    # The sensitive ~88-char download handles must appear nowhere in the payload.
    for file_id in (FILE_ID_EQUITY, FILE_ID_COMMODITY, FILE_ID_SINGLE):
        assert file_id not in resp.text


@respx.mock
def test_list_204_returns_empty(client):
    _mock_list(httpx.Response(204))

    resp = client.post(
        "/api/report/contract-notes/list", headers=HEADERS, json=LIST_BODY
    )

    assert resp.status_code == 200
    assert resp.json() == {"notes": []}


@respx.mock
def test_list_body_status_nodata_returns_empty(client):
    # 200 transport with a non-200 body StatusCode is "no notes", not an error.
    _mock_list(
        httpx.Response(
            200,
            json={"StatusCode": 204, "Message": "No valid contract notes", "Body": {}},
        )
    )

    resp = client.post(
        "/api/report/contract-notes/list", headers=HEADERS, json=LIST_BODY
    )

    assert resp.status_code == 200
    assert resp.json() == {"notes": []}


@respx.mock
def test_list_sends_sessionid_auth_without_prefix(client):
    route = _mock_list(_list_ok())

    client.post("/api/report/contract-notes/list", headers=HEADERS, json=LIST_BODY)

    sent = route.calls.last.request
    # Go list endpoint authenticates with the RAW SessionId (no "Session " prefix).
    assert sent.headers["authorization"] == "test-session-token"
    body = httpx.Response(200, content=sent.content).json()
    assert body["client_id"] == "X008593"
    assert body["from_date"] == "2024-09-01"
    assert body["to_date"] == "2024-09-30"


# --- IDOR defense (list) ----------------------------------------------------

@respx.mock
def test_list_body_client_id_is_ignored(client):
    route = _mock_list(_list_ok())

    malicious = {**LIST_BODY, "client_id": "X999999", "clientCode": "X999999"}
    client.post("/api/report/contract-notes/list", headers=HEADERS, json=malicious)

    body = httpx.Response(200, content=route.calls.last.request.content).json()
    assert body["client_id"] == "X008593"  # from X-User-Id, never the body
    assert "X999999" not in route.calls.last.request.content.decode()


# --- download ---------------------------------------------------------------

def _opaque_id_for(client, segment: str, badge_present: bool = True) -> str:
    """List, then return the opaque id of the first note matching `segment`."""
    notes = client.post(
        "/api/report/contract-notes/list", headers=HEADERS, json=LIST_BODY
    ).json()["notes"]
    return next(n for n in notes if n["segment"] == segment)["id"]


@respx.mock
def test_download_returns_token_and_no_password(client):
    _mock_list(_list_ok())
    _mock_download(_pdf_response())

    note_id = _opaque_id_for(client, "Commodity")
    resp = client.post(
        "/api/report/contract-notes/download",
        headers=HEADERS,
        json={"id": note_id},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["delivery"] == "download"
    assert payload["file"]["format"] == "PDF"
    assert payload["file"]["passwordProtected"] is False  # never PAN-protected
    assert payload["file"]["name"] == "Contract_Note_16Sep2024.pdf"
    assert payload["file"]["sizeLabel"].endswith(("KB", "B"))
    assert payload["fileToken"]


@respx.mock
def test_download_envelope_carries_token_expiry(client):
    """CHO-230: additive token-expiry fields on the download envelope."""
    _mock_list(_list_ok())
    _mock_download(_pdf_response())

    note_id = _opaque_id_for(client, "Commodity")
    payload = client.post(
        "/api/report/contract-notes/download",
        headers=HEADERS,
        json={"id": note_id},
    ).json()

    ttl = config.report_file_ttl_seconds()
    assert payload["ttlSeconds"] == ttl
    expires_at = datetime.fromisoformat(payload["expiresAt"])
    assert expires_at.tzinfo is not None  # timezone-aware UTC timestamp
    delta = (expires_at - datetime.now(timezone.utc)).total_seconds()
    assert 0 < delta <= ttl + 5


@respx.mock
def test_download_resolves_opaque_id_to_file_id_server_side(client):
    _mock_list(_list_ok())
    dl = _mock_download(_pdf_response())

    # The Equity note on the 2-note date maps to FILE_ID_EQUITY.
    notes = client.post(
        "/api/report/contract-notes/list", headers=HEADERS, json=LIST_BODY
    ).json()["notes"]
    equity_id = next(
        n["id"] for n in notes
        if n["segment"] == "Equity & F&O" and n["badge"] == "NSE·BSE"
    )

    client.post(
        "/api/report/contract-notes/download",
        headers=HEADERS,
        json={"id": equity_id},
    )

    sent = dl.calls.last.request
    body = httpx.Response(200, content=sent.content).json()
    assert body["file_id"] == FILE_ID_EQUITY  # resolved from the opaque token
    assert body["client_code"] == "X008593"  # from the session header
    # Download authenticates with the "Session " prefix.
    assert sent.headers["authorization"] == "Session test-session-token"


@respx.mock
def test_download_streams_pdf_via_shared_file_endpoint(client):
    _mock_list(_list_ok())
    _mock_download(_pdf_response())

    note_id = _opaque_id_for(client, "Equity & F&O")
    token = client.post(
        "/api/report/contract-notes/download",
        headers=HEADERS,
        json={"id": note_id},
    ).json()["fileToken"]

    resp = client.get(f"/api/report/file/{token}")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content == PDF_BYTES


# --- IDOR defense (download) ------------------------------------------------

@respx.mock
def test_download_body_client_code_and_file_id_are_ignored(client):
    _mock_list(_list_ok())
    dl = _mock_download(_pdf_response())

    note_id = _opaque_id_for(client, "Equity & F&O")
    malicious = {
        "id": note_id,
        "client_code": "X999999",
        "file_id": "attacker-supplied-file-id",
        "SessionId": "attacker-session",
    }
    client.post(
        "/api/report/contract-notes/download", headers=HEADERS, json=malicious
    )

    sent = dl.calls.last.request.content.decode()
    body = httpx.Response(200, content=sent.encode()).json()
    assert body["client_code"] == "X008593"  # from X-User-Id, not the body
    assert body["file_id"] == FILE_ID_EQUITY  # from the token, not the body
    assert "X999999" not in sent
    assert "attacker-supplied-file-id" not in sent


@respx.mock
def test_download_unknown_id_is_404(client):
    _mock_list(_list_ok())  # not called, but keeps host mocked
    resp = client.post(
        "/api/report/contract-notes/download",
        headers=HEADERS,
        json={"id": "not-a-real-token"},
    )
    assert resp.status_code == 404
    assert resp.json() == {"error": "NO_DATA"}


@respx.mock
def test_download_token_is_session_bound(client):
    _mock_list(_list_ok())
    _mock_download(_pdf_response())

    note_id = _opaque_id_for(client, "Equity & F&O")
    other_session = {**HEADERS, "X-Session-Id": "someone-elses-session"}
    resp = client.post(
        "/api/report/contract-notes/download",
        headers=other_session,
        json={"id": note_id},
    )
    # A token minted for one session is useless to another → indistinguishable 404.
    assert resp.status_code == 404


# --- error map --------------------------------------------------------------

@respx.mock
def test_list_upstream_401_maps_to_auth_expired(client):
    _mock_list(httpx.Response(401, json={"StatusCode": 401, "Message": "bad session"}))

    resp = client.post(
        "/api/report/contract-notes/list", headers=HEADERS, json=LIST_BODY
    )

    assert resp.status_code == 401
    assert resp.json() == {"error": "AUTH_EXPIRED"}


@respx.mock
def test_list_upstream_500_maps_to_upstream_error(client):
    _mock_list(httpx.Response(500))

    resp = client.post(
        "/api/report/contract-notes/list", headers=HEADERS, json=LIST_BODY
    )

    assert resp.status_code == 502
    assert resp.json() == {"error": "UPSTREAM_ERROR"}


@respx.mock
def test_download_upstream_401_maps_to_auth_expired(client):
    _mock_list(_list_ok())
    _mock_download(httpx.Response(401))

    note_id = _opaque_id_for(client, "Equity & F&O")
    resp = client.post(
        "/api/report/contract-notes/download",
        headers=HEADERS,
        json={"id": note_id},
    )

    assert resp.status_code == 401
    assert resp.json() == {"error": "AUTH_EXPIRED"}


# --- validation / credentials -----------------------------------------------

@pytest.mark.parametrize("missing", ["Authorization", "X-Session-Id", "X-User-Id"])
def test_list_missing_header_is_missing_credentials(client, missing):
    headers = {k: v for k, v in HEADERS.items() if k != missing}
    resp = client.post(
        "/api/report/contract-notes/list", headers=headers, json=LIST_BODY
    )
    assert resp.status_code == 400
    assert resp.json() == {"error": "MISSING_CREDENTIALS"}


@pytest.mark.parametrize(
    "bad_body",
    [
        {"fromDate": "09-01-2024", "toDate": "2024-09-30"},
        {"fromDate": "2024-09-01"},  # missing toDate
    ],
)
def test_list_invalid_body_is_rejected(client, bad_body):
    resp = client.post(
        "/api/report/contract-notes/list", headers=HEADERS, json=bad_body
    )
    assert resp.status_code == 422


def test_download_missing_id_is_rejected(client):
    resp = client.post(
        "/api/report/contract-notes/download", headers=HEADERS, json={}
    )
    assert resp.status_code == 422


# --- PII-safe logging -------------------------------------------------------

@respx.mock
def test_logs_carry_no_pii(client, caplog):
    _mock_list(_list_ok())
    _mock_download(_pdf_response())

    with caplog.at_level(logging.DEBUG):
        note_id = _opaque_id_for(client, "Equity & F&O")
        client.post(
            "/api/report/contract-notes/download",
            headers=HEADERS,
            json={"id": note_id},
        )

    logtext = "\n".join(r.getMessage() for r in caplog.records)
    assert FILE_ID_EQUITY not in logtext  # the sensitive handle
    assert "X008593" not in logtext
    assert "test-session-token" not in logtext
    assert "test-sso-jwt" not in logtext
