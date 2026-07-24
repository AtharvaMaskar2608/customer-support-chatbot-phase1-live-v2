"""Prompt-engineering playground (CHO-272).

Isolated from production `/api/chat`: gated by ``PLAYGROUND_TOKEN`` (404 when
unset), conversation threads namespaced under ``pg:`` via
``thread_session_id``, and prompt overrides accepted only on these endpoints.
``ToolCtx.session_id`` stays the live FinX SessionId so tool/upstream auth
works. Production prompt constants remain the source of truth for the live
agent.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.agent.ctx import ToolCtx
from app.agent.loop import run_chat_stream
from app.agent.prompt import PRIMED_INSTRUCTIONS, SYSTEM_PROMPT
from app.agent.router import _anthropic_client
from app.reports.contract_notes import _ref_store

# Playground threads never share a session key with production chat.
_SESSION_PREFIX = "pg:"


def require_playground(request: Request) -> None:
    """Gate the playground by the shared operator token.

    Unset token => 404 (playground disabled). Set => ``X-Playground-Token``
    must match (constant-time). Token is never logged.
    """
    token = config.playground_token()
    if not token:
        raise HTTPException(status_code=404, detail="not found")
    provided = request.headers.get("X-Playground-Token", "")
    if not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="unauthorized")


router = APIRouter(prefix="/api/playground", dependencies=[Depends(require_playground)])


class PlaygroundChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str = Field(min_length=1, max_length=4000)
    systemPrompt: str | None = Field(default=None, max_length=200_000)
    primedInstructions: str | None = Field(default=None, max_length=200_000)


def _missing_credentials() -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": "MISSING_CREDENTIALS"})


def _pg_session(session_id: str) -> str:
    return f"{_SESSION_PREFIX}{session_id}"


@router.get("/defaults")
async def playground_defaults() -> dict[str, str]:
    """Production prompt constants — the starting draft for the editor."""
    return {
        "systemPrompt": SYSTEM_PROMPT,
        "primedInstructions": PRIMED_INSTRUCTIONS,
    }


@router.post("/chat/reset")
async def playground_chat_reset(
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    if not authorization or not x_session_id or not x_user_id:
        return _missing_credentials()
    await request.app.state.conversation_store.reset_thread(
        _pg_session(x_session_id), client_code=x_user_id
    )
    return {"ok": True}


@router.post("/chat")
async def playground_chat(
    body: PlaygroundChatRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    if not authorization or not x_session_id or not x_user_id:
        return _missing_credentials()

    # ToolCtx.session_id must stay the live FinX SessionId — tools, greeting,
    # and contract-note auth all reuse it. Thread isolation uses a separate
    # namespaced store key so playground chats never collide with production.
    ctx = ToolCtx(
        session_id=x_session_id,
        sso_jwt=authorization,
        client_code=x_user_id,
        http_client=request.app.state.http_client,
        pg_pool=getattr(request.app.state, "pg_pool", None),
        report_files=request.app.state.report_files,
        contract_note_refs=_ref_store(request),
    )
    # Empty override strings mean "use production default".
    system_override = body.systemPrompt if body.systemPrompt else None
    primed_override = body.primedInstructions if body.primedInstructions else None
    return StreamingResponse(
        run_chat_stream(
            message=body.message,
            ctx=ctx,
            store=request.app.state.conversation_store,
            client=_anthropic_client(request),
            system_override=system_override,
            primed_override=primed_override,
            thread_session_id=_pg_session(x_session_id),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
