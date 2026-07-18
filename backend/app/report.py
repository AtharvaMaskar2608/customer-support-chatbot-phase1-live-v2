"""Report flows — the backend-for-frontend proxy. The browser never calls FinX.

Wave 0 implements P&L (`POST /api/report/pnl`) end-to-end plus the shared
delivery endpoint (`GET /api/report/file/{file_token}`). Ledger / Tax / Contract
Notes are Wave-1 additions: a routing entry (already present) + a per-flow
request model and upstream body mapping like the P&L pair below.

Normalized response envelope returned to the frontend:
  download -> {"delivery": "download", "file": {...}, "fileToken": "<id>"}
  email    -> {"delivery": "email", "emailMasked": "san***@gmail.com"}
  errors   -> 401 {"error": "AUTH_EXPIRED"} · 404 {"error": "NO_DATA"}
              · 502 {"error": "UPSTREAM_ERROR"}
"""

import logging
import re

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, field_validator

from app.finx.client import FinxClient, ResultKind
from app.finx.delivery import fetch_artifact, mask_email, size_label
from app.finx.routing import Endpoint

logger = logging.getLogger("app.report")

router = APIRouter()

# --- P&L per-descriptor mapping (design decision 5: never shared) -----------
# Customer labels map to upstream Group codes. "Derv" etc. are backend-only and
# must never reach the customer.
_SEGMENT_TO_GROUP = {"Equity": "Cash", "F&O": "Derv", "Commodity": "Comm"}
# RequestFor is hardcoded per endpoint (the field that lies). P&L: 0=dl, 1=email.
_PNL_REQUESTFOR_DOWNLOAD = 0
_PNL_REQUESTFOR_EMAIL = 1
_PNL_WITH_EXP = True  # charges included, surfaced in the result copy

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class PnlReportRequest(BaseModel):
    # extra="ignore": any client-supplied client code (ClientId/UserId/...) in
    # the body is silently dropped. The client code we send upstream comes ONLY
    # from the authenticated session header (IDOR defense).
    model_config = ConfigDict(extra="ignore")

    segment: str
    fromDate: str
    toDate: str
    delivery: str

    @field_validator("segment")
    @classmethod
    def _valid_segment(cls, v: str) -> str:
        if v not in _SEGMENT_TO_GROUP:
            raise ValueError("segment must be one of Equity, F&O, Commodity")
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


def _safe_header_filename(name: str) -> str:
    """ASCII-safe filename for the Content-Disposition header."""
    return re.sub(r'[^A-Za-z0-9._-]', "_", name)


@router.post("/api/report/pnl")
async def pnl_report(
    body: PnlReportRequest,
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
    group = _SEGMENT_TO_GROUP[body.segment]
    is_email = body.delivery == "email"
    request_for = _PNL_REQUESTFOR_EMAIL if is_email else _PNL_REQUESTFOR_DOWNLOAD

    upstream_body = {
        "ClientId": client_code,
        "UserId": client_code,  # == ClientId per the upstream contract
        "Group": group,
        "FromDate": body.fromDate,
        "ToDate": body.toDate,
        "RequestFor": request_for,
        "With_Exp": _PNL_WITH_EXP,
        "SessionId": x_session_id,
    }

    finx = FinxClient(request.app.state.http_client)
    result = await finx.call(
        Endpoint.PNL,
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

    filename = f"PnL_{body.segment}_{body.fromDate}_to_{body.toDate}.pdf"
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


@router.get("/api/report/file/{file_token}")
async def report_file(file_token: str, request: Request):
    """Return a previously generated report file by its opaque token.

    Token-only: the token is unguessable and short-TTL, so a plain download
    link works (no session header needed). The upstream URL is never persisted
    — only the fetched bytes are held server-side.
    """
    entry = request.app.state.report_files.get(file_token)
    if entry is None:
        # Unknown or expired — indistinguishable.
        return JSONResponse(status_code=404, content={"error": "NOT_FOUND"})

    filename = _safe_header_filename(entry.filename)
    return Response(
        content=entry.data,
        media_type=entry.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
