"""Ledger report flow — `POST /api/report/ledger` (CHO-208, Wave 1).

Additive mirror of the Wave-0 P&L route in `app.report`: a per-flow request
model, an endpoint-specific upstream body mapping, the shared `FinxClient`
call, and the shared delivery/PII layer. The download token endpoint
(`GET /api/report/file/{token}`) is owned by `app.report` and reused as-is.

Normalized response envelope (identical to P&L):
  download -> {"delivery": "download", "file": {...}, "fileToken": "<id>"}
  email    -> {"delivery": "email", "emailMasked": "san***@gmail.com"}
  errors   -> 401 {"error": "AUTH_EXPIRED"} · 404 {"error": "NO_DATA"}
              · 502 {"error": "UPSTREAM_ERROR"}
"""

import logging
import re

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator

from app.finx.client import FinxClient, ResultKind
from app.finx.delivery import fetch_artifact, mask_email, size_label
from app.finx.routing import Endpoint

logger = logging.getLogger("app.reports.ledger")

router = APIRouter()

# --- Ledger per-descriptor mapping (design decision 5: never shared) --------
# Customer "book" labels map to the upstream Margin discriminator. GROUP1 is a
# fixed constant for this endpoint (uppercase — the data API's "Group1" differs).
_BOOK_TO_MARGIN = {"Normal": 0, "MTF": 1}
_LEDGER_GROUP = "GROUP1"
# RequestFor is hardcoded per endpoint (the field that lies). Ledger: 0=dl, 1=email.
_LEDGER_REQUESTFOR_DOWNLOAD = 0
_LEDGER_REQUESTFOR_EMAIL = 1

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class LedgerReportRequest(BaseModel):
    # extra="ignore": any client-supplied client code (ClientId/LoginId/...) in
    # the body is silently dropped. The client code we send upstream comes ONLY
    # from the authenticated session header (IDOR defense).
    model_config = ConfigDict(extra="ignore")

    book: str
    fromDate: str
    toDate: str
    delivery: str

    @field_validator("book")
    @classmethod
    def _valid_book(cls, v: str) -> str:
        if v not in _BOOK_TO_MARGIN:
            raise ValueError("book must be one of Normal, MTF")
        return v

    @field_validator("delivery")
    @classmethod
    def _valid_delivery(cls, v: str) -> str:
        if v not in ("download", "email"):
            raise ValueError("delivery must be 'download' or 'email'")
        return v

    @field_validator("fromDate", "toDate")
    @classmethod
    def _valid_date(cls, v: str) -> str:
        if not _DATE_RE.match(v):
            raise ValueError("date must be YYYY-MM-DD")
        return v


def _missing_credentials() -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": "MISSING_CREDENTIALS"})


def _error_response(kind: ResultKind) -> JSONResponse:
    """Map an upstream result kind to the pinned client-facing error shape."""
    if kind is ResultKind.AUTH_EXPIRED:
        return JSONResponse(status_code=401, content={"error": "AUTH_EXPIRED"})
    if kind in (ResultKind.NO_DATA, ResultKind.EMPTY):
        return JSONResponse(status_code=404, content={"error": "NO_DATA"})
    return JSONResponse(status_code=502, content={"error": "UPSTREAM_ERROR"})


@router.post("/api/report/ledger")
async def ledger_report(
    body: LedgerReportRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    if not authorization or not x_session_id or not x_user_id:
        return _missing_credentials()

    # Session-bound: client code comes ONLY from the authenticated session
    # (X-User-Id), never from the request body.
    client_code = x_user_id
    margin = _BOOK_TO_MARGIN[body.book]
    is_email = body.delivery == "email"
    request_for = (
        _LEDGER_REQUESTFOR_EMAIL if is_email else _LEDGER_REQUESTFOR_DOWNLOAD
    )

    upstream_body = {
        "ClientId": client_code,
        "LoginId": client_code,  # the client code — NOT the "JIFFY" literal
        "Group": _LEDGER_GROUP,
        "Margin": margin,
        "FromDate": body.fromDate,
        "ToDate": body.toDate,
        "RequestFor": request_for,
        "SessionId": x_session_id,
    }

    finx = FinxClient(request.app.state.http_client)
    result = await finx.call(
        Endpoint.LEDGER,
        session_id=x_session_id,
        sso_jwt=authorization,
        body=upstream_body,
    )
    if result.kind is not ResultKind.OK:
        return _error_response(result.kind)

    response_value = (result.payload or {}).get("Response")

    if is_email:
        # Never surface the raw confirmation string — mask before returning.
        return {"delivery": "email", "emailMasked": mask_email(response_value)}

    # Download: response_value is a report URL string. Fetch it server-side and
    # hand back only an opaque token — the URL never reaches the client or logs.
    if not isinstance(response_value, str) or not response_value.startswith(
        "http"
    ):
        return _error_response(ResultKind.UPSTREAM_ERROR)

    data = await fetch_artifact(request.app.state.http_client, response_value)
    if data is None:
        return _error_response(ResultKind.UPSTREAM_ERROR)

    filename = f"Ledger_{body.book}_{body.fromDate}_to_{body.toDate}.pdf"
    token = request.app.state.report_files.put(
        data=data,
        filename=filename,
        content_type="application/pdf",
        session_id=x_session_id,
    )
    return {
        "delivery": "download",
        "file": {
            "name": filename,
            "sizeLabel": size_label(len(data)),
            "format": "PDF",
            "passwordProtected": True,  # delivered PDF is PAN-password-protected
        },
        "fileToken": token,
    }
