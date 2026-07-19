"""POST /api/chat — the agentic free-text endpoint (CHO-213 · tasks 4.2/4.5).

Thin shell over `app.agent.loop.run_chat_stream`: validates the auth headers
(pre-stream 400 MISSING_CREDENTIALS, matching every other route), builds the
per-request ToolCtx exactly as the flow routes do, and returns an SSE
StreamingResponse. Failures after the stream opens are SSE `error` events
(AGENT_UNAVAILABLE / AUTH_EXPIRED) — never a 5xx.
"""

import logging

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.agent.ctx import ToolCtx
from app.agent.loop import run_chat_stream
from app.reports.contract_notes import _ref_store

logger = logging.getLogger("app.agent.router")

router = APIRouter()


class ChatRequest(BaseModel):
    # extra="ignore": nothing but the message is read from the body — any
    # smuggled credential/client-code field is dropped (IDOR posture).
    model_config = ConfigDict(extra="ignore")

    message: str = Field(min_length=1, max_length=4000)


def _missing_credentials() -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": "MISSING_CREDENTIALS"})


def _anthropic_client(request: Request):
    """App-level AsyncAnthropic, lazily created. Returns None when the client
    cannot be built (e.g. no API key) — the loop then emits AGENT_UNAVAILABLE
    on the open stream instead of the route 500ing."""
    client = getattr(request.app.state, "anthropic_client", None)
    if client is None:
        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=config.anthropic_api_key())
        except Exception as exc:
            logger.warning(
                "anthropic client unavailable error=%s", type(exc).__name__
            )
            return None
        request.app.state.anthropic_client = client
    return client


@router.post("/api/chat/reset")
async def chat_reset(
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    """Restart the session's conversation (CHO-216): the current thread is
    closed (rows retained), a fresh one becomes active — the agent forgets,
    cap counters restart. No model call, idempotent."""
    if not authorization or not x_session_id or not x_user_id:
        return _missing_credentials()
    await request.app.state.conversation_store.reset_thread(
        x_session_id, client_code=x_user_id
    )
    return {"ok": True}


@router.post("/api/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    if not authorization or not x_session_id or not x_user_id:
        return _missing_credentials()

    # Same ctx construction as the flow routes: credentials from the
    # authenticated headers only; shared resources from app.state (the
    # contract-note ref store is lazily created, as its own routes do).
    ctx = ToolCtx(
        session_id=x_session_id,
        sso_jwt=authorization,
        client_code=x_user_id,
        http_client=request.app.state.http_client,
        pg_pool=getattr(request.app.state, "pg_pool", None),
        report_files=request.app.state.report_files,
        contract_note_refs=_ref_store(request),
    )
    return StreamingResponse(
        run_chat_stream(
            message=body.message,
            ctx=ctx,
            store=request.app.state.conversation_store,
            client=_anthropic_client(request),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
