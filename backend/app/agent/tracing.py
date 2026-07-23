"""Self-hosted agent tracing in Postgres (replaces the CHO-244 Confident AI /
DeepEval export).

Each POST /api/chat turn is captured as an execution graph — an ``agent`` root
with ``llm`` / ``tool`` / ``retriever`` child spans — and written as ONE JSONB
row to the ``agent_traces`` table of our own Postgres (the KB / conversation
store DB), grouped into multi-turn threads. No external service, no data
egress, no metered cost, no extra dependency.

Design:

* No framework. Parent/child nesting is tracked with ``contextvars`` — async-
  and ``asyncio.gather``-safe: each gathered tool coroutine copies the current
  context and sees the agent span as its parent, and sets itself as the parent
  for anything it calls (so a KB search nests a ``retriever`` span under its
  ``tool`` span).
* The public wrappers (``observe_turn`` / ``observe_model_round`` /
  ``observe_tool`` / ``observe_retrieval``) are tracer-agnostic and unchanged
  from the loop's point of view — a plain pass-through when tracing is off or
  no DB pool is available.
* PII / secret hygiene is kept: span inputs/outputs are masked (:func:`redact`),
  and the session id (a live FinX auth token) and client code are stored only
  as HMAC hashes, so a conversation's turns still group into a thread without a
  raw credential landing in an analytics table.
* Never raises into chat: persistence is fire-and-forget and fully guarded; a
  tracing failure is logged (type only) and dropped.
"""

import asyncio
import contextvars
import hashlib
import hmac
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable

from app import config

logger = logging.getLogger("app.agent.tracing")

_ENABLED = False


# --------------------------------------------------------------------------- #
# Mask — redact credential- and PII-shaped values before anything is stored.
# --------------------------------------------------------------------------- #

_REDACT = "[REDACTED]"

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]*")
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_EMAIL_RE = re.compile(r"[\w.+-]{1,64}@[\w-]{1,255}\.[\w.-]{1,255}")
_PHONE_RE = re.compile(r"\b(?:\+?91[-\s]?)?[6-9]\d{9}\b")
# Opaque tokens / file handles / session ids: long unbroken id-ish runs.
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")

# Dict keys whose value is redacted wholesale, whatever its shape.
_DENY_KEYS = frozenset(
    {
        "authorization", "sso_jwt", "ssojwt", "ssotoken", "sso_token",
        "accesstoken", "access_token", "sessionid", "session_id",
        "x_session_id", "clientcode", "client_code", "clientid", "client_id",
        "userid", "user_id", "user_code", "usercode", "token", "filetoken",
        "file_token", "fileid", "file_id", "pan", "dob", "email", "phone",
        "mobile", "mobile_number", "bank", "accountnumber", "account_number",
        "ifsc", "password",
    }
)


def _redact_str(value: str) -> str:
    value = _JWT_RE.sub(_REDACT, value)
    value = _PAN_RE.sub(_REDACT, value)
    value = _EMAIL_RE.sub(_REDACT, value)
    value = _PHONE_RE.sub(_REDACT, value)
    value = _LONG_TOKEN_RE.sub(_REDACT, value)
    return value


def redact(data: Any) -> Any:
    """Recursively scrub credential/PII-shaped values from a span's input or
    output before it is persisted."""
    if isinstance(data, str):
        return _redact_str(data)
    if isinstance(data, dict):
        out: dict = {}
        for key, val in data.items():
            if isinstance(key, str) and key.lower() in _DENY_KEYS:
                out[key] = _REDACT
            else:
                out[key] = redact(val)
        return out
    if isinstance(data, (list, tuple)):
        return [redact(v) for v in data]
    return data


def _stable_id(value: str | None) -> str | None:
    """HMAC hash of a sensitive identifier (session id / client code) so a
    conversation's turns still group into one thread/user without storing the
    raw credential. Pseudonymisation, not secrecy of the mapping."""
    if not value:
        return None
    key = config.tracing_salt().encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Span model + per-turn collector (held in contextvars for nesting).
# --------------------------------------------------------------------------- #


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


@dataclass
class _Span:
    id: str
    parent_id: str | None
    type: str  # agent | llm | tool | retriever
    name: str
    start_ms: float
    end_ms: float | None = None
    input: Any = None
    output: Any = None
    metadata: dict = field(default_factory=dict)


@dataclass
class _Trace:
    thread_id: str | None
    user_id: str | None
    input: Any
    start_ms: float
    spans: list[_Span] = field(default_factory=list)
    _counter: int = 0

    def open(self, type_: str, name: str, parent_id: str | None) -> _Span:
        self._counter += 1
        span = _Span(
            id=f"s{self._counter}",
            parent_id=parent_id,
            type=type_,
            name=name,
            start_ms=_now_ms(),
        )
        self.spans.append(span)
        return span


_current_trace: contextvars.ContextVar[_Trace | None] = contextvars.ContextVar(
    "jini_trace", default=None
)
_current_parent: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "jini_parent", default=None
)


# --------------------------------------------------------------------------- #
# Configure + schema.
# --------------------------------------------------------------------------- #


def enabled() -> bool:
    return _ENABLED


def configure() -> None:
    """Set the enabled flag from config (AGENT_TRACING, default on). Cheap and
    idempotent; actual persistence also requires a DB pool at turn time."""
    global _ENABLED
    _ENABLED = config.tracing_enabled()
    logger.info("agent tracing %s (postgres)", "enabled" if _ENABLED else "disabled")


_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS agent_traces (
        id            bigserial PRIMARY KEY,
        created_at    timestamptz NOT NULL DEFAULT now(),
        thread_id     text,
        user_id       text,
        latency_ms    integer,
        model         text,
        input_tokens  integer,
        output_tokens integer,
        tools         text[],
        had_error     boolean,
        input         text,
        output        text,
        spans         jsonb NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS agent_traces_thread_idx "
    "ON agent_traces (thread_id, created_at DESC)",
)


async def ensure_schema(pool: Any) -> None:
    """Create the agent_traces table if needed. Guarded: a failure just leaves
    tracing unable to persist (chat unaffected)."""
    if pool is None or not _ENABLED:
        return
    try:
        for stmt in _SCHEMA:
            await pool.execute(stmt)
    except Exception as exc:
        logger.warning("agent_traces schema init failed error=%s", type(exc).__name__)


# --------------------------------------------------------------------------- #
# Persistence — fire-and-forget, guarded.
# --------------------------------------------------------------------------- #

_pending: set[asyncio.Task] = set()


def _span_dict(trace: _Trace, span: _Span) -> dict:
    dur = None if span.end_ms is None else round(span.end_ms - span.start_ms, 1)
    return {
        "id": span.id,
        "parent_id": span.parent_id,
        "type": span.type,
        "name": span.name,
        "offset_ms": round(span.start_ms - trace.start_ms, 1),
        "duration_ms": dur,
        "input": span.input,
        "output": span.output,
        "metadata": span.metadata,
    }


async def _persist(pool: Any, trace: _Trace) -> None:
    try:
        spans = [_span_dict(trace, s) for s in trace.spans]
        llm = [s for s in trace.spans if s.type == "llm"]
        tools = [s.name for s in trace.spans if s.type == "tool"]
        model = llm[-1].metadata.get("model") if llm else None
        in_tok = sum((s.metadata.get("input_tokens") or 0) for s in llm) or None
        out_tok = sum((s.metadata.get("output_tokens") or 0) for s in llm) or None
        had_error = any(
            s.metadata.get("is_error") for s in trace.spans if s.type == "tool"
        )
        output = " ".join(
            s.output for s in llm if isinstance(s.output, str) and s.output
        )
        root = trace.spans[0] if trace.spans else None
        latency = (
            int(root.end_ms - root.start_ms)
            if root and root.end_ms is not None
            else None
        )
        await pool.execute(
            "INSERT INTO agent_traces (thread_id, user_id, latency_ms, model, "
            "input_tokens, output_tokens, tools, had_error, input, output, spans) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)",
            trace.thread_id,
            trace.user_id,
            latency,
            model,
            in_tok,
            out_tok,
            tools,
            had_error,
            trace.input if isinstance(trace.input, str) else json.dumps(trace.input),
            output or None,
            json.dumps(spans, default=str),
        )
    except Exception as exc:
        logger.warning("trace persist failed error=%s", type(exc).__name__)


def _schedule_persist(pool: Any, trace: _Trace) -> None:
    try:
        task = asyncio.create_task(_persist(pool, trace))
        _pending.add(task)
        task.add_done_callback(_pending.discard)
    except RuntimeError:  # no running loop (shouldn't happen in the async path)
        pass


# --------------------------------------------------------------------------- #
# Public wrappers — pass-through when off / no pool / no active trace.
# --------------------------------------------------------------------------- #


async def observe_turn(
    *, message: str, session_id: str, client_code: str, pool: Any,
    run: Callable[[], AsyncIterator[str]],
) -> AsyncIterator[str]:
    """agent root span for one /api/chat turn; stitches the multi-turn thread by
    hashed session/client. Persists the assembled tree at turn end."""
    if not _ENABLED or pool is None:
        async for chunk in run():
            yield chunk
        return
    trace = _Trace(
        thread_id=_stable_id(session_id),
        user_id=_stable_id(client_code),
        input=redact(message),
        start_ms=_now_ms(),
    )
    root = trace.open("agent", "chat_turn", parent_id=None)
    t_tok = _current_trace.set(trace)
    p_tok = _current_parent.set(root.id)
    try:
        async for chunk in run():
            yield chunk
    finally:
        root.end_ms = _now_ms()
        _current_parent.reset(p_tok)
        _current_trace.reset(t_tok)
        _schedule_persist(pool, trace)


async def observe_model_round(
    *, user_input: str, open_stream: Callable[[], Any], holder: dict,
) -> AsyncIterator[str]:
    """llm span for one streamed model round; yields text deltas and stashes the
    final message in ``holder['final']`` for the loop to continue."""
    trace = _current_trace.get()
    if trace is None:
        async with open_stream() as stream:
            async for delta in stream.text_stream:
                if delta:
                    yield delta
            holder["final"] = await stream.get_final_message()
        return
    span = trace.open("llm", "model_round", parent_id=_current_parent.get())
    parts: list[str] = []
    async with open_stream() as stream:
        async for delta in stream.text_stream:
            if delta:
                parts.append(delta)
                yield delta
        final = await stream.get_final_message()
    holder["final"] = final
    span.end_ms = _now_ms()
    span.input = redact(user_input)
    span.output = "".join(parts)
    usage = getattr(final, "usage", None)
    span.metadata = {
        "model": getattr(final, "model", None),
        "input_tokens": _usage_get(usage, "input_tokens"),
        "output_tokens": _usage_get(usage, "output_tokens"),
        # Prompt caching matters a lot here (frozen system + primed prefix) —
        # capture the cache split DeepEval's auto-patch dropped.
        "cache_read_input_tokens": _usage_get(usage, "cache_read_input_tokens"),
        "cache_creation_input_tokens": _usage_get(
            usage, "cache_creation_input_tokens"
        ),
        "stop_reason": getattr(final, "stop_reason", None),
    }


async def observe_tool(
    *, name: str, tool_input: Any, run: Callable[[], Awaitable[Any]],
) -> Any:
    """tool span for one dispatch; sets itself as the parent so a nested KB
    search lands a retriever span underneath it."""
    trace = _current_trace.get()
    if trace is None:
        return await run()
    span = trace.open("tool", name, parent_id=_current_parent.get())
    p_tok = _current_parent.set(span.id)
    try:
        outcome = await run()
    finally:
        _current_parent.reset(p_tok)
        span.end_ms = _now_ms()
    span.input = redact(tool_input)
    span.metadata = {
        "is_error": getattr(outcome, "is_error", None),
        "error_code": getattr(outcome, "error_code", None),
        "duration_ms": getattr(outcome, "duration_ms", None),
    }
    return outcome


async def observe_retrieval(
    *, query: str, run: Callable[[], Awaitable[list]],
) -> list:
    """retriever span for a KB hybrid search; records the fused chunks as
    retrieval_context."""
    trace = _current_trace.get()
    if trace is None:
        return await run()
    span = trace.open("retriever", "kb_search", parent_id=_current_parent.get())
    results = await run()
    span.end_ms = _now_ms()
    chunks = [
        f"{r.get('question', '')} — {r.get('answer', '')}".strip(" —")
        for r in results
        if isinstance(r, dict)
    ]
    span.input = redact(query)
    span.output = {"count": len(results)}
    span.metadata = {
        "retrieval_context": chunks,
        "embedder": config.kb_embed_model(),
    }
    return results


def _usage_get(usage: Any, key: str) -> Any:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage.get(key)
    return getattr(usage, key, None)
