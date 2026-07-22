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

from app.agent.ctx import (
    CODE_UPSTREAM_ERROR,
    ToolCtx,
    ToolError,
    error_json_response,
    parse_params,
    tool_error_from_kind,
)
from app.agent.events import friendly_range, record_flow_event
from app.finx.client import FinxClient, ResultKind
from app.finx.delivery import (
    download_delivery,
    fetch_artifact,
    mask_email,
    size_label,
)
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


async def run_ledger(
    params: LedgerReportRequest | dict, ctx: ToolCtx
) -> dict | ToolError:
    """Ledger flow core — shared by the REST route and the agent tool (CHO-213).

    Same contract as `report.run_pnl`: exact route 200 body on success,
    ToolError otherwise, never raises, download delivery via fileToken only.
    """
    params = parse_params(LedgerReportRequest, params)
    if isinstance(params, ToolError):
        return params

    # Session-bound: client code comes ONLY from the authenticated session
    # (ctx.client_code == X-User-Id), never from the params.
    client_code = ctx.client_code
    margin = _BOOK_TO_MARGIN[params.book]
    is_email = params.delivery == "email"
    request_for = (
        _LEDGER_REQUESTFOR_EMAIL if is_email else _LEDGER_REQUESTFOR_DOWNLOAD
    )

    upstream_body = {
        "ClientId": client_code,
        "LoginId": client_code,  # the client code — NOT the "JIFFY" literal
        "Group": _LEDGER_GROUP,
        "Margin": margin,
        "FromDate": params.fromDate,
        "ToDate": params.toDate,
        "RequestFor": request_for,
        "SessionId": ctx.session_id,
    }

    finx = FinxClient(ctx.http_client)
    result = await finx.call(
        Endpoint.LEDGER,
        session_id=ctx.session_id,
        sso_jwt=ctx.sso_jwt,
        body=upstream_body,
    )
    if result.kind is not ResultKind.OK:
        return tool_error_from_kind(result.kind)

    response_value = (result.payload or {}).get("Response")

    if is_email:
        # Never surface the raw confirmation string — mask before returning.
        return {"delivery": "email", "emailMasked": mask_email(response_value)}

    # Download: response_value is a report URL string. Fetch it server-side and
    # hand back only an opaque token — the URL never reaches the client or logs.
    if not isinstance(response_value, str) or not response_value.startswith(
        "http"
    ):
        return tool_error_from_kind(ResultKind.UPSTREAM_ERROR)
    if ctx.report_files is None:
        return ToolError(CODE_UPSTREAM_ERROR, "report file store not configured")

    data = await fetch_artifact(ctx.http_client, response_value)
    if data is None:
        return tool_error_from_kind(ResultKind.UPSTREAM_ERROR)

    filename = f"Ledger_{params.book}_{params.fromDate}_to_{params.toDate}.pdf"
    token = ctx.report_files.put(
        data=data,
        filename=filename,
        content_type="application/pdf",
        session_id=ctx.session_id,
    )
    return download_delivery(
        {
            "name": filename,
            "sizeLabel": size_label(len(data)),
            "format": "PDF",
            "passwordProtected": False,  # tester-verified: upstream PDFs are not protected (CHO-220)
        },
        token,
    )


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

    ctx = ToolCtx(
        session_id=x_session_id,
        sso_jwt=authorization,
        client_code=x_user_id,
        http_client=request.app.state.http_client,
        report_files=request.app.state.report_files,
    )
    result = await run_ledger(body, ctx)
    if isinstance(result, ToolError):
        return error_json_response(result)
    # Widget completion → agent memory (CHO-214): fire-and-forget.
    record_flow_event(
        request.app,
        session_id=x_session_id,
        client_code=x_user_id,
        flow="ledger",
        details=[f"{body.book} book", friendly_range(body.fromDate, body.toDate)],
        slots={
            "book": body.book,
            "fromDate": body.fromDate,
            "toDate": body.toDate,
        },
        delivery=body.delivery,
    )
    return result
