"""Endpoint tests for POST /api/report/tax (Capital Gains / Tax, CHO-209).

Mirrors test_report_pnl.py, adding the Tax-only surface: the PDF/Excel **format**
step (FileFormat 1/2 + .pdf/.xlsx filename), the forked RequestFor (2 = download,
1 = email), the "Data not available." no-data wording, and reuse of the shared
GET /api/report/file/{token} download endpoint. Upstreams are respx-mocked — no
live network.
"""

import logging

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import config
from app.main import create_app
from app.reports.tax import router as tax_router

HEADERS = {
    "Authorization": "test-sso-jwt",
    "X-Session-Id": "test-session-token",
    "X-User-Id": "X008593",
}

# URL shapes by format (see the reference § Tax): PDF ends .pdf, Excel .xlsx.
PDF_URL = "https://client-report.choiceindia.com/PDFReports/TAX_9931_X008593.pdf"
XLSX_URL = "https://client-report.choiceindia.com/PDFReports/TAX_9931_X008593_1718000000.xlsx"
PDF_BYTES = b"%PDF-1.4\n" + b"x" * 5000  # ~5 KB fake PDF
XLSX_BYTES = b"PK\x03\x04" + b"x" * 6000  # ~6 KB fake xlsx (zip magic)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

DOWNLOAD_BODY = {
    "finYear": "2025-2026",
    "format": "PDF",
    "delivery": "download",
}


@pytest.fixture()
def client():
    # Parallel-agent safety: mounting the tax router into app.main is owned by a
    # sibling agent and may land separately. Mount it here if it isn't already
    # present so this suite is self-contained. No-op once main.py includes it.
    app = create_app()
    if not any(getattr(r, "path", None) == "/api/report/tax" for r in app.routes):
        app.include_router(tax_router)
    with TestClient(app) as test_client:
        yield test_client


def _mock_tax(response: httpx.Response) -> respx.Route:
    return respx.post(config.upstream_tax_url()).mock(return_value=response)


def _mock_artifact(url: str, content: bytes, content_type: str) -> respx.Route:
    return respx.get(url).mock(
        return_value=httpx.Response(
            200, content=content, headers={"content-type": content_type}
        )
    )


def _tax_success(response_value: str) -> httpx.Response:
    return httpx.Response(
        200, json={"Status": "Success", "Response": response_value, "Reason": ""}
    )


# --- download flow: PDF -----------------------------------------------------

@respx.mock
def test_download_pdf_returns_token_and_hides_upstream_url(client):
    _mock_tax(_tax_success(PDF_URL))
    _mock_artifact(PDF_URL, PDF_BYTES, "application/pdf")

    resp = client.post("/api/report/tax", headers=HEADERS, json=DOWNLOAD_BODY)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["delivery"] == "download"
    assert payload["file"]["format"] == "PDF"
    assert payload["file"]["passwordProtected"] is True
    assert payload["file"]["name"] == "CapitalGains_2025-2026.pdf"
    assert payload["file"]["name"].endswith(".pdf")
    assert payload["file"]["sizeLabel"].endswith("KB")
    assert payload["fileToken"]

    # The raw upstream URL must appear nowhere in the client payload.
    assert PDF_URL not in resp.text
    assert "client-report.choiceindia.com" not in resp.text
    assert payload["fileToken"] != PDF_URL


@respx.mock
def test_download_pdf_sends_fileformat_1_and_requestfor_2(client):
    route = _mock_tax(_tax_success(PDF_URL))
    _mock_artifact(PDF_URL, PDF_BYTES, "application/pdf")

    client.post("/api/report/tax", headers=HEADERS, json=DOWNLOAD_BODY)

    sent = httpx.Response(200, content=route.calls.last.request.content).json()
    assert sent["FileFormat"] == 1  # PDF
    assert sent["RequestFor"] == 2  # Tax download forks to 2 (NOT 0)
    assert sent["FinYear"] == "2025-2026"
    assert sent["ClientId"] == "X008593"
    assert sent["SessionId"] == "test-session-token"
    # SessionId is the authorization for the .NET report endpoint.
    assert route.calls.last.request.headers["authorization"] == "test-session-token"


# --- download flow: Excel ---------------------------------------------------

@respx.mock
def test_download_excel_uses_xlsx_name_and_fileformat_2(client):
    route = _mock_tax(_tax_success(XLSX_URL))
    _mock_artifact(XLSX_URL, XLSX_BYTES, XLSX_MIME)

    body = {**DOWNLOAD_BODY, "format": "Excel"}
    resp = client.post("/api/report/tax", headers=HEADERS, json=body)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["file"]["format"] == "Excel"
    assert payload["file"]["name"] == "CapitalGains_2025-2026.xlsx"
    assert payload["file"]["name"].endswith(".xlsx")
    assert payload["file"]["passwordProtected"] is True

    sent = httpx.Response(200, content=route.calls.last.request.content).json()
    assert sent["FileFormat"] == 2  # Excel
    assert sent["RequestFor"] == 2  # download


@respx.mock
def test_download_excel_streams_xlsx_content_type(client):
    _mock_tax(_tax_success(XLSX_URL))
    _mock_artifact(XLSX_URL, XLSX_BYTES, XLSX_MIME)

    token = client.post(
        "/api/report/tax", headers=HEADERS, json={**DOWNLOAD_BODY, "format": "Excel"}
    ).json()["fileToken"]

    resp = client.get(f"/api/report/file/{token}")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == XLSX_MIME
    assert "attachment" in resp.headers["content-disposition"]
    assert ".xlsx" in resp.headers["content-disposition"]
    assert resp.content == XLSX_BYTES


# --- shared download endpoint reuse -----------------------------------------

@respx.mock
def test_file_token_streams_pdf(client):
    _mock_tax(_tax_success(PDF_URL))
    _mock_artifact(PDF_URL, PDF_BYTES, "application/pdf")
    token = client.post(
        "/api/report/tax", headers=HEADERS, json=DOWNLOAD_BODY
    ).json()["fileToken"]

    # Token-only: a plain link works, no session header sent.
    resp = client.get(f"/api/report/file/{token}")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content == PDF_BYTES


@respx.mock
def test_download_artifact_fetch_failure_is_upstream_error(client):
    _mock_tax(_tax_success(PDF_URL))
    respx.get(PDF_URL).mock(side_effect=httpx.ConnectError("down"))

    resp = client.post("/api/report/tax", headers=HEADERS, json=DOWNLOAD_BODY)

    assert resp.status_code == 502
    assert resp.json() == {"error": "UPSTREAM_ERROR"}


# --- email flow -------------------------------------------------------------

@respx.mock
def test_email_returns_masked_address(client):
    confirmation = "Tax Report mail sent successfully to SANTOSH.HARSHA@GMAIL.COM"
    _mock_tax(_tax_success(confirmation))

    resp = client.post(
        "/api/report/tax",
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
    route = _mock_tax(_tax_success("mail sent successfully to A@B.COM"))

    client.post(
        "/api/report/tax",
        headers=HEADERS,
        json={**DOWNLOAD_BODY, "delivery": "email"},
    )

    body = httpx.Response(200, content=route.calls.last.request.content).json()
    assert body["RequestFor"] == 1  # email is the cross-endpoint constant


# --- IDOR defense -----------------------------------------------------------

@respx.mock
def test_body_client_code_is_ignored(client):
    """A client code smuggled in the body must NOT reach upstream — the session
    header (X-User-Id) is the only source."""
    route = _mock_tax(_tax_success(PDF_URL))
    _mock_artifact(PDF_URL, PDF_BYTES, "application/pdf")

    malicious = {
        **DOWNLOAD_BODY,
        "ClientId": "X999999",
        "clientCode": "X999999",
        "SessionId": "attacker-session",
    }
    client.post("/api/report/tax", headers=HEADERS, json=malicious)

    body = httpx.Response(200, content=route.calls.last.request.content).json()
    assert body["ClientId"] == "X008593"  # from X-User-Id, not the body
    assert body["SessionId"] == "test-session-token"  # from X-Session-Id
    assert "X999999" not in route.calls.last.request.content.decode()


# --- error map --------------------------------------------------------------

@respx.mock
def test_upstream_401_maps_to_auth_expired(client):
    _mock_tax(httpx.Response(401, json={"Status": "Fail", "Reason": "Invalid SessionId"}))

    resp = client.post("/api/report/tax", headers=HEADERS, json=DOWNLOAD_BODY)

    assert resp.status_code == 401
    assert resp.json() == {"error": "AUTH_EXPIRED"}


@respx.mock
def test_upstream_business_failure_maps_to_no_data(client):
    # Tax's no-data Reason is "Data not available." (vs P&L's "Data not found.").
    # We branch on Status, never the Reason wording.
    _mock_tax(
        httpx.Response(
            200,
            json={"Status": "Fail", "Response": None, "Reason": "Data not available."},
        )
    )

    resp = client.post("/api/report/tax", headers=HEADERS, json=DOWNLOAD_BODY)

    assert resp.status_code == 404
    assert resp.json() == {"error": "NO_DATA"}


@respx.mock
def test_upstream_500_maps_to_upstream_error(client):
    _mock_tax(httpx.Response(500))

    resp = client.post("/api/report/tax", headers=HEADERS, json=DOWNLOAD_BODY)

    assert resp.status_code == 502
    assert resp.json() == {"error": "UPSTREAM_ERROR"}


# --- validation / credentials ----------------------------------------------

@pytest.mark.parametrize("missing", ["Authorization", "X-Session-Id", "X-User-Id"])
def test_missing_header_is_missing_credentials(client, missing):
    headers = {k: v for k, v in HEADERS.items() if k != missing}
    resp = client.post("/api/report/tax", headers=headers, json=DOWNLOAD_BODY)
    assert resp.status_code == 400
    assert resp.json() == {"error": "MISSING_CREDENTIALS"}


@pytest.mark.parametrize(
    "bad_body",
    [
        {"finYear": "2025-2026", "format": "CSV", "delivery": "download"},
        {"finYear": "2025", "format": "PDF", "delivery": "download"},
        {"finYear": "04-2026", "format": "PDF", "delivery": "download"},
        {"finYear": "2025-2026", "format": "PDF", "delivery": "fax"},
    ],
)
def test_invalid_body_is_rejected(client, bad_body):
    resp = client.post("/api/report/tax", headers=HEADERS, json=bad_body)
    assert resp.status_code == 422


# --- PII-safe logging -------------------------------------------------------

@respx.mock
def test_logs_carry_no_pii(client, caplog):
    _mock_tax(_tax_success(PDF_URL))
    _mock_artifact(PDF_URL, PDF_BYTES, "application/pdf")

    with caplog.at_level(logging.DEBUG):
        client.post("/api/report/tax", headers=HEADERS, json=DOWNLOAD_BODY)

    logtext = "\n".join(r.getMessage() for r in caplog.records)
    # No upstream URL, client code, session token, or SSO JWT in any log line.
    assert PDF_URL not in logtext
    assert "client-report.choiceindia.com" not in logtext
    assert "X008593" not in logtext
    assert "test-session-token" not in logtext
    assert "test-sso-jwt" not in logtext
