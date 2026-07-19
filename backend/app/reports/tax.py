"""Capital Gains / Tax report flow — `POST /api/report/tax` (CHO-209, Wave 1).

Additive mirror of the Wave-0 P&L route in `app.report`, and the ONE flow with
a **format** step (PDF / Excel). A per-flow request model, an endpoint-specific
upstream body mapping, the shared `FinxClient` call, and the shared delivery/PII
layer. The download token endpoint (`GET /api/report/file/{token}`) is owned by
`app.report` and reused as-is.

Two Tax-only traps encoded here (see docs/finx_android_api_reference.html §Tax):
  - RequestFor forks from P&L/Ledger: **2 = download · 1 = email** (NOT 0).
    Hardcoded per endpoint — never centralized behind one shared constant.
  - FileFormat: **1 = PDF · 2 = Excel**. The chosen format drives the upstream
    FileFormat, the download filename extension (.pdf / .xlsx), the streamed
    content type, and the `file.format` label handed back to the client.

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
from app.agent.events import record_flow_event
from app.finx.client import FinxClient, ResultKind
from app.finx.delivery import fetch_artifact, mask_email, size_label
from app.finx.routing import Endpoint

logger = logging.getLogger("app.reports.tax")

router = APIRouter()

# --- Tax per-descriptor mapping (design decision 5: never shared) -----------
# RequestFor is hardcoded per endpoint (the field that lies). Tax forks from
# P&L/Ledger: 2 = download, 1 = email (NOT 0). Never share this constant.
_TAX_REQUESTFOR_DOWNLOAD = 2
_TAX_REQUESTFOR_EMAIL = 1

# Chosen format → upstream FileFormat code, download filename extension, and the
# content type streamed back to the browser. FileFormat: 1 = PDF, 2 = Excel.
_FORMAT_SPEC = {
    "PDF": {
        "file_format": 1,
        "ext": "pdf",
        "content_type": "application/pdf",
    },
    "Excel": {
        "file_format": 2,
        "ext": "xlsx",
        "content_type": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    },
}

# Financial year is a "YYYY-YYYY" span (not a date range). The selectable window
# is dynamic (current + last 2 FYs) and owned by the frontend descriptor; here we
# only assert the shape.
_FINYEAR_RE = re.compile(r"^\d{4}-\d{4}$")


class TaxReportRequest(BaseModel):
    # extra="ignore": any client-supplied client code (ClientId/SessionId/...) in
    # the body is silently dropped. The client code we send upstream comes ONLY
    # from the authenticated session header (IDOR defense).
    model_config = ConfigDict(extra="ignore")

    finYear: str
    format: str
    delivery: str

    @field_validator("finYear")
    @classmethod
    def _valid_fin_year(cls, v: str) -> str:
        if not _FINYEAR_RE.match(v):
            raise ValueError("finYear must be YYYY-YYYY")
        return v

    @field_validator("format")
    @classmethod
    def _valid_format(cls, v: str) -> str:
        if v not in _FORMAT_SPEC:
            raise ValueError("format must be 'PDF' or 'Excel'")
        return v

    @field_validator("delivery")
    @classmethod
    def _valid_delivery(cls, v: str) -> str:
        if v not in ("download", "email"):
            raise ValueError("delivery must be 'download' or 'email'")
        return v


def _missing_credentials() -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": "MISSING_CREDENTIALS"})


async def run_tax(
    params: TaxReportRequest | dict, ctx: ToolCtx
) -> dict | ToolError:
    """Tax flow core — shared by the REST route and the agent tool (CHO-213).

    Same contract as `report.run_pnl`: exact route 200 body on success,
    ToolError otherwise, never raises, download delivery via fileToken only.
    The Tax-only RequestFor/FileFormat traps stay encoded here.
    """
    params = parse_params(TaxReportRequest, params)
    if isinstance(params, ToolError):
        return params

    # Session-bound: client code comes ONLY from the authenticated session
    # (ctx.client_code == X-User-Id), never from the params.
    client_code = ctx.client_code
    fmt = _FORMAT_SPEC[params.format]
    is_email = params.delivery == "email"
    request_for = _TAX_REQUESTFOR_EMAIL if is_email else _TAX_REQUESTFOR_DOWNLOAD

    upstream_body = {
        "ClientId": client_code,
        "FinYear": params.finYear,
        "RequestFor": request_for,
        "FileFormat": fmt["file_format"],
        "SessionId": ctx.session_id,
    }

    finx = FinxClient(ctx.http_client)
    result = await finx.call(
        Endpoint.TAX,
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

    # Filename extension follows the chosen format: .pdf for PDF, .xlsx for Excel.
    filename = f"CapitalGains_{params.finYear}.{fmt['ext']}"
    token = ctx.report_files.put(
        data=data,
        filename=filename,
        content_type=fmt["content_type"],
        session_id=ctx.session_id,
    )
    return {
        "delivery": "download",
        "file": {
            "name": filename,
            "sizeLabel": size_label(len(data)),
            "format": params.format,  # "PDF" | "Excel" — the chosen format
            "passwordProtected": True,  # delivered file is PAN-password-protected
        },
        "fileToken": token,
    }


@router.post("/api/report/tax")
async def tax_report(
    body: TaxReportRequest,
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
    result = await run_tax(body, ctx)
    if isinstance(result, ToolError):
        return error_json_response(result)
    # Widget completion → agent memory (CHO-214): fire-and-forget.
    record_flow_event(
        request.app,
        session_id=x_session_id,
        client_code=x_user_id,
        flow="tax",
        details=[f"FY {body.finYear}", body.format],
        slots={"finYear": body.finYear, "format": body.format},
        delivery=body.delivery,
    )
    return result
