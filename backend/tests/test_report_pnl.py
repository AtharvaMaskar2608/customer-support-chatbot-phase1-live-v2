"""Endpoint tests for POST /api/report/pnl and GET /api/report/file/{token}.

Upstreams (the report API and the report-artifact host) are mocked with respx
— no live network. Covers: segment/RequestFor mapping, download URL never
leaking, file streaming + session binding, email masking, IDOR defense, the
error map, and PII-safe logging.
"""

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

ARTIFACT_URL = "https://client-report.choiceindia.com/PDFReports/PNLReport_9931_X008593.pdf"
PDF_BYTES = b"%PDF-1.4\n" + b"x" * 5000  # ~5 KB fake PDF

DOWNLOAD_BODY = {
    "segment": "Equity",
    "fromDate": "2026-04-01",
    "toDate": "2026-07-21",
    "delivery": "download",
}


@pytest.fixture()
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def _mock_pnl(response: httpx.Response) -> respx.Route:
    return respx.post(config.upstream_pnl_url()).mock(return_value=response)


def _mock_artifact() -> respx.Route:
    return respx.get(ARTIFACT_URL).mock(
        return_value=httpx.Response(
            200, content=PDF_BYTES, headers={"content-type": "application/pdf"}
        )
    )


def _pnl_success(response_value: str) -> httpx.Response:
    return httpx.Response(
        200, json={"Status": "Success", "Response": response_value, "Reason": ""}
    )


# --- download flow ----------------------------------------------------------

@respx.mock
def test_download_returns_token_and_hides_upstream_url(client):
    _mock_pnl(_pnl_success(ARTIFACT_URL))
    _mock_artifact()

    resp = client.post("/api/report/pnl", headers=HEADERS, json=DOWNLOAD_BODY)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["delivery"] == "download"
    assert payload["file"]["format"] == "PDF"
    assert payload["file"]["passwordProtected"] is True
    assert payload["file"]["name"] == "PnL_Equity_2026-04-01_to_2026-07-21.pdf"
    assert payload["file"]["sizeLabel"].endswith("KB")
    assert payload["fileToken"]

    # The raw upstream URL must appear nowhere in the client payload.
    assert ARTIFACT_URL not in resp.text
    assert "client-report.choiceindia.com" not in resp.text
    assert "fileToken" in payload and payload["fileToken"] != ARTIFACT_URL


@respx.mock
def test_download_segment_maps_to_group_cash(client):
    route = _mock_pnl(_pnl_success(ARTIFACT_URL))
    _mock_artifact()

    client.post("/api/report/pnl", headers=HEADERS, json=DOWNLOAD_BODY)

    sent = route.calls.last.request
    body = httpx.Response(200, content=sent.content).json()
    assert body["Group"] == "Cash"  # Equity -> Cash
    assert body["RequestFor"] == 0  # download
    assert body["With_Exp"] is True
    assert body["ClientId"] == "X008593"
    assert body["UserId"] == "X008593"
    assert body["SessionId"] == "test-session-token"
    # SessionId is the authorization for the .NET report endpoint.
    assert sent.headers["authorization"] == "test-session-token"


@pytest.mark.parametrize(
    "segment,group", [("Equity", "Cash"), ("F&O", "Derv"), ("Commodity", "Comm")]
)
@respx.mock
def test_all_segments_map_to_upstream_group(client, segment, group):
    route = _mock_pnl(_pnl_success(ARTIFACT_URL))
    _mock_artifact()

    body = {**DOWNLOAD_BODY, "segment": segment}
    client.post("/api/report/pnl", headers=HEADERS, json=body)

    sent_body = httpx.Response(200, content=route.calls.last.request.content).json()
    assert sent_body["Group"] == group


@respx.mock
def test_file_token_streams_pdf(client):
    _mock_pnl(_pnl_success(ARTIFACT_URL))
    _mock_artifact()
    token = client.post(
        "/api/report/pnl", headers=HEADERS, json=DOWNLOAD_BODY
    ).json()["fileToken"]

    # Token-only: a plain link works, no session header sent.
    resp = client.get(f"/api/report/file/{token}")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content == PDF_BYTES


def test_file_token_unknown_is_404(client):
    resp = client.get("/api/report/file/nope")
    assert resp.status_code == 404


@respx.mock
def test_download_artifact_fetch_failure_is_upstream_error(client):
    _mock_pnl(_pnl_success(ARTIFACT_URL))
    respx.get(ARTIFACT_URL).mock(side_effect=httpx.ConnectError("down"))

    resp = client.post("/api/report/pnl", headers=HEADERS, json=DOWNLOAD_BODY)

    assert resp.status_code == 502
    assert resp.json() == {"error": "UPSTREAM_ERROR"}


# --- email flow -------------------------------------------------------------

@respx.mock
def test_email_returns_masked_address(client):
    confirmation = "PnL Report mail sent successfully to SANTOSH.HARSHA@GMAIL.COM"
    _mock_pnl(_pnl_success(confirmation))

    resp = client.post(
        "/api/report/pnl",
        headers=HEADERS,
        json={**DOWNLOAD_BODY, "delivery": "email"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"delivery": "email", "emailMasked": "san***@gmail.com"}
    # The full (uppercased) address must never appear in the payload.
    assert "SANTOSH.HARSHA@GMAIL.COM" not in resp.text
    assert "santosh.harsha@gmail.com" not in resp.text


@respx.mock
def test_email_sends_requestfor_1(client):
    route = _mock_pnl(_pnl_success("mail sent successfully to A@B.COM"))

    client.post(
        "/api/report/pnl",
        headers=HEADERS,
        json={**DOWNLOAD_BODY, "delivery": "email"},
    )

    body = httpx.Response(200, content=route.calls.last.request.content).json()
    assert body["RequestFor"] == 1


# --- IDOR defense -----------------------------------------------------------

@respx.mock
def test_body_client_code_is_ignored(client):
    """A client code smuggled in the body must NOT reach upstream — the session
    header (X-User-Id) is the only source."""
    route = _mock_pnl(_pnl_success(ARTIFACT_URL))
    _mock_artifact()

    malicious = {
        **DOWNLOAD_BODY,
        "ClientId": "X999999",
        "UserId": "X999999",
        "clientCode": "X999999",
        "SessionId": "attacker-session",
    }
    client.post("/api/report/pnl", headers=HEADERS, json=malicious)

    body = httpx.Response(200, content=route.calls.last.request.content).json()
    assert body["ClientId"] == "X008593"  # from X-User-Id, not the body
    assert body["UserId"] == "X008593"
    assert body["SessionId"] == "test-session-token"  # from X-Session-Id
    assert "X999999" not in route.calls.last.request.content.decode()


# --- error map --------------------------------------------------------------

@respx.mock
def test_upstream_401_maps_to_auth_expired(client):
    _mock_pnl(httpx.Response(401, json={"Status": "Fail", "Reason": "Invalid SessionId"}))

    resp = client.post("/api/report/pnl", headers=HEADERS, json=DOWNLOAD_BODY)

    assert resp.status_code == 401
    assert resp.json() == {"error": "AUTH_EXPIRED"}


@respx.mock
def test_upstream_business_failure_maps_to_no_data(client):
    _mock_pnl(
        httpx.Response(
            200, json={"Status": "Fail", "Response": None, "Reason": "Data not found."}
        )
    )

    resp = client.post("/api/report/pnl", headers=HEADERS, json=DOWNLOAD_BODY)

    assert resp.status_code == 404
    assert resp.json() == {"error": "NO_DATA"}


@respx.mock
def test_upstream_500_maps_to_upstream_error(client):
    _mock_pnl(httpx.Response(500))

    resp = client.post("/api/report/pnl", headers=HEADERS, json=DOWNLOAD_BODY)

    assert resp.status_code == 502
    assert resp.json() == {"error": "UPSTREAM_ERROR"}


# --- validation / credentials ----------------------------------------------

@pytest.mark.parametrize(
    "missing", ["Authorization", "X-Session-Id", "X-User-Id"]
)
def test_missing_header_is_missing_credentials(client, missing):
    headers = {k: v for k, v in HEADERS.items() if k != missing}
    resp = client.post("/api/report/pnl", headers=headers, json=DOWNLOAD_BODY)
    assert resp.status_code == 400
    assert resp.json() == {"error": "MISSING_CREDENTIALS"}


@pytest.mark.parametrize(
    "bad_body",
    [
        {"segment": "Derv", "fromDate": "2026-04-01", "toDate": "2026-07-21", "delivery": "download"},
        {"segment": "Equity", "fromDate": "04-01-2026", "toDate": "2026-07-21", "delivery": "download"},
        {"segment": "Equity", "fromDate": "2026-04-01", "toDate": "2026-07-21", "delivery": "fax"},
    ],
)
def test_invalid_body_is_rejected(client, bad_body):
    resp = client.post("/api/report/pnl", headers=HEADERS, json=bad_body)
    assert resp.status_code == 422


# --- PII-safe logging -------------------------------------------------------

@respx.mock
def test_logs_carry_no_pii(client, caplog):
    _mock_pnl(_pnl_success(ARTIFACT_URL))
    _mock_artifact()

    with caplog.at_level(logging.DEBUG):
        client.post("/api/report/pnl", headers=HEADERS, json=DOWNLOAD_BODY)

    logtext = "\n".join(r.getMessage() for r in caplog.records)
    # No upstream URL, client code, session token, or email in any log line.
    assert ARTIFACT_URL not in logtext
    assert "client-report.choiceindia.com" not in logtext
    assert "X008593" not in logtext
    assert "test-session-token" not in logtext
    assert "test-sso-jwt" not in logtext
