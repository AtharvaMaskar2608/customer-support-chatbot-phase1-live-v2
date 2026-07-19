"""POST /api/chat — the agentic free-text endpoint (CHO-213 · tasks 4.2/4.5).

Thin shell over `app.agent.loop.run_chat_stream`: validates the auth headers
(pre-stream 400 MISSING_CREDENTIALS, matching every other route), builds the
per-request ToolCtx exactly as the flow routes do, and returns an SSE
StreamingResponse. Failures after the stream opens are SSE `error` events
(AGENT_UNAVAILABLE / AUTH_EXPIRED) — never a 5xx.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.agent.ctx import ToolCtx, ToolError, error_json_response
from app.agent.loop import run_chat_stream
from app.agent.tickets import run_raise_ticket, ticket_memo
from app.reports.contract_notes import _ref_store

logger = logging.getLogger("app.agent.router")

router = APIRouter()


class ChatRequest(BaseModel):
    # extra="ignore": nothing but the message is read from the body — any
    # smuggled credential/client-code field is dropped (IDOR posture).
    model_config = ConfigDict(extra="ignore")

    message: str = Field(min_length=1, max_length=4000)


class FeedbackRequest(BaseModel):
    # extra="ignore", same IDOR posture as ChatRequest: only the rating,
    # anchor, and source are read — nothing else in the body is trusted.
    model_config = ConfigDict(extra="ignore")

    rating: Literal["up", "down"]
    anchorSeq: int | None = Field(default=None, ge=1)
    source: str = Field(default="agent", max_length=32)


class TicketRequest(BaseModel):
    # extra="ignore", same IDOR posture: only the reason is read — identity
    # comes from the authenticated headers, never the body.
    model_config = ConfigDict(extra="ignore")

    reason: str = Field(default="General Query", min_length=1, max_length=200)


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


@router.post("/api/feedback")
async def feedback(
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    """Record a 👍/👎 on a completed answer (CHO-217): anchored to the given
    turn seq (agent path) or the thread's latest turn (sticker path). The
    write rides the store's queue — no model call, no DB wait, and degraded
    persistence never surfaces to the user."""
    if not authorization or not x_session_id or not x_user_id:
        return _missing_credentials()
    try:
        body = FeedbackRequest.model_validate(await request.json())
    except Exception:
        # Malformed JSON or invalid rating/anchor — plain 400, no echo of the
        # body (nothing user-supplied is logged or reflected).
        return JSONResponse(status_code=400, content={"error": "INVALID_FEEDBACK"})
    store = request.app.state.conversation_store
    thread = await store.get_thread(x_session_id, client_code=x_user_id)
    anchor_seq = body.anchorSeq or (thread.turns[-1].seq if thread.turns else None)
    if anchor_seq is None:
        return {"ok": True}  # empty thread — nothing to anchor a rating to
    store.record_feedback(
        thread, anchor_seq=anchor_seq, rating=body.rating, source=body.source
    )
    return {"ok": True}


@router.post("/api/ticket")
async def ticket(
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    """Help-card escalation (CHO-218): raise a real Freshdesk ticket through
    the same core the raise_support_ticket agent tool uses — identical
    tickets from both entry points. Success also appends the flow-event memo
    so the agent remembers the escalation; failure is the pinned error JSON
    (the shell shows a graceful line) — never a fabricated ticket id."""
    if not authorization or not x_session_id or not x_user_id:
        return _missing_credentials()
    try:
        body = TicketRequest.model_validate(await request.json())
    except Exception:
        # Absent/malformed body or invalid reason → the default reason (the
        # help-card path has no free text). Nothing user-supplied is echoed.
        body = TicketRequest()

    # Same credential posture as /api/chat: identity from the authenticated
    # headers only. The ticket core needs just the shared http_client plus
    # the conversation thread for the transcript.
    ctx = ToolCtx(
        session_id=x_session_id,
        sso_jwt=authorization,
        client_code=x_user_id,
        http_client=request.app.state.http_client,
    )
    store = request.app.state.conversation_store
    thread = await store.get_thread(x_session_id, client_code=x_user_id)
    ctx.thread = thread

    result = await run_raise_ticket({"reason": body.reason}, ctx)
    if isinstance(result, ToolError):
        return error_json_response(result)

    # The same memo the agent path appends — the thread object is already in
    # hand, so the synchronous append rides the store's writer queue directly.
    ticket_id = result["ticketId"]
    store.append_turn(
        thread,
        role="user",
        kind="flow_event",
        content=[{"type": "text", "text": ticket_memo(ticket_id, body.reason)}],
        meta={"flow": "ticket", "ticketId": ticket_id, "reason": body.reason},
    )
    return {"ticketId": ticket_id, "status": result["status"]}


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
