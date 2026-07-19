"""Per-request tool context + tool-facing result convention (CHO-213, D2/D3).

`ToolCtx` carries the authenticated credentials and shared app resources that
the route shells read from headers / `request.app.state` today. It is built
once per request — by a route shell or by the agent's `/api/chat` endpoint —
and handed to the flow cores. Tool schemas never define parameters for any of
these values: the model has no credential fields to fill (the structural IDOR
defense from D3).

Result convention across the core boundary (D2):

  success -> the flow's normalized envelope dict — exactly the route's 200 body
  failure -> ToolError(code, message) — `code` maps 1:1 onto the pinned
             client-facing error shapes; `message` is actionable for the model
             ("... — ask the user.").

Cores NEVER raise across this boundary and NEVER return a JSONResponse; route
shells map a ToolError back to the exact same JSONResponse the route returned
before the extraction (`error_json_response`), so the HTTP contract is
byte-identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

import httpx
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from app.finx.client import ResultKind
from app.finx.delivery import FileTokenStore

if TYPE_CHECKING:  # runtime import would be circular (contract_notes imports us)
    from app.reports.contract_notes import ContractNoteRefStore


@dataclass
class ToolCtx:
    """Authenticated credentials + shared resources for one request.

    Credentials come ONLY from the authenticated session headers
    (`authorization` = SSO JWT, `x-session-id`, `x-user-id` = client code) —
    never from a request body and never from tool parameters.

    Resource requirements per core: `pg_pool` for `run_kb_search` (None is the
    degraded KB_UNAVAILABLE state); `report_files` for the download paths of
    the report cores; `contract_note_refs` for both contract-note cores.
    """

    session_id: str
    sso_jwt: str
    client_code: str
    http_client: httpx.AsyncClient
    pg_pool: Any | None = None
    report_files: FileTokenStore | None = None
    contract_note_refs: "ContractNoteRefStore | None" = None


# --- tool-facing error codes -------------------------------------------------
# The first three are the pinned client-facing error strings the routes already
# return; VALIDATION covers bad/missing tool params (routes never see it — the
# FastAPI/pydantic layer 422s first); the KB_* pair preserves the KB route's
# degraded outcomes.
CODE_AUTH_EXPIRED = "AUTH_EXPIRED"
CODE_NO_DATA = "NO_DATA"
CODE_UPSTREAM_ERROR = "UPSTREAM_ERROR"
CODE_VALIDATION = "VALIDATION"
CODE_KB_UNAVAILABLE = "KB_UNAVAILABLE"
CODE_KB_ERROR = "KB_ERROR"


@dataclass
class ToolError:
    """Structured failure a core hands back instead of raising.

    `code` is one of the CODE_* constants; `message` tells the model what to
    do next (never a raw upstream body, never a credentialed URL).
    """

    code: str
    message: str


_KIND_TO_CODE = {
    ResultKind.AUTH_EXPIRED: CODE_AUTH_EXPIRED,
    # Report flows collapse both no-data shapes to the pinned NO_DATA error
    # (data flows turn EMPTY into a success envelope before reaching this map).
    ResultKind.NO_DATA: CODE_NO_DATA,
    ResultKind.EMPTY: CODE_NO_DATA,
}

_CODE_MESSAGES = {
    CODE_AUTH_EXPIRED: (
        "The FinX session has expired — the user must sign in again before "
        "this can be retried."
    ),
    CODE_NO_DATA: "No data found for the requested parameters.",
    CODE_UPSTREAM_ERROR: (
        "The upstream service failed — suggest trying again shortly."
    ),
}


def tool_error_from_kind(kind: ResultKind) -> ToolError:
    """Map an upstream ResultKind to the tool-facing error (default: upstream)."""
    code = _KIND_TO_CODE.get(kind, CODE_UPSTREAM_ERROR)
    return ToolError(code=code, message=_CODE_MESSAGES[code])


def validation_tool_error(exc: ValidationError) -> ToolError:
    """Pydantic failure → actionable VALIDATION error naming each bad field."""
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "params"
        msg = str(err["msg"]).removeprefix("Value error, ")
        parts.append(f"{loc}: {msg}")
    return ToolError(
        code=CODE_VALIDATION, message="; ".join(parts) + " — ask the user."
    )


_M = TypeVar("_M", bound=BaseModel)


def parse_params(model: type[_M], params: object) -> _M | ToolError:
    """Validate tool params against a flow's existing request model.

    Route shells pass the already-parsed pydantic model straight through (no
    double validation, and the FastAPI 422 contract for invalid bodies is
    untouched); the agent passes a raw dict, which is validated here so both
    entry points share one validation source.
    """
    if isinstance(params, model):
        return params
    try:
        return model.model_validate(params if params is not None else {})
    except ValidationError as exc:
        return validation_tool_error(exc)


# --- route-shell mapping back to the pinned HTTP shapes ----------------------

_ERROR_STATUS = {
    CODE_AUTH_EXPIRED: 401,
    CODE_NO_DATA: 404,
    CODE_UPSTREAM_ERROR: 502,
}


def error_json_response(err: ToolError) -> JSONResponse:
    """The exact pre-refactor error response for a ToolError.

    401 {"error": "AUTH_EXPIRED"} · 404 {"error": "NO_DATA"} ·
    502 {"error": "UPSTREAM_ERROR"} — identical to the `_error_response` /
    `envelope.error_response` mapping the routes used before extraction.
    (Codes outside the map cannot reach a route shell; 502 is the backstop.)
    """
    return JSONResponse(
        status_code=_ERROR_STATUS.get(err.code, 502),
        content={"error": err.code},
    )
