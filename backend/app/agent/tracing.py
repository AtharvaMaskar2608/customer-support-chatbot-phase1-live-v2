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
from app.agent import langfuse_mirror

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


def stable_user_id(client_code: str | None) -> str | None:
    """Public alias of :func:`_stable_id` for callers outside this module."""
    return _stable_id(client_code)


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
    # The mirror's handle for this span (CHO-286). Runtime-only: `_span_dict`
    # builds the persisted shape field by field, so this never reaches Postgres.
    lf: Any = None


@dataclass
class _Trace:
    thread_id: str | None
    user_id: str | None
    input: Any
    start_ms: float
    spans: list[_Span] = field(default_factory=list)
    # CHO-286 context fields (platform / entry point / versions / ticket / seq).
    # Merged onto the root span metadata at end so both sinks see the same bag.
    context: dict = field(default_factory=dict)
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
        # CHO-286: both sinks are opened HERE, in the one place a span comes
        # into existence, so the mirror cannot describe a different shape than
        # the persisted tree — parenting is read from the same `parent_id`.
        # `llm` becomes a Langfuse `generation` so model/usage land in native
        # fields; everything else is a plain span.
        if parent_id is None:
            meta = {k: v for k, v in self.context.items() if v is not None}
            span.lf = langfuse_mirror.start_root(
                name=name,
                input=self.input,
                metadata=meta or None,
                version=meta.get("backend_version"),
            )
        else:
            parent = next((s for s in self.spans if s.id == parent_id), None)
            span.lf = langfuse_mirror.start_child(
                parent.lf if parent is not None else None,
                name=name,
                as_type="generation" if type_ == "llm" else "span",
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
    # CHO-286: the mirror gets THIS module's `redact` as its export mask, so a
    # single definition governs both sinks. It stays inert unless separately
    # flagged on and fully credentialed.
    langfuse_mirror.configure(mask=_mirror_mask)


def _mirror_end_failed(span: _Span, exc: BaseException) -> None:
    """Close a mirror span whose body raised.

    OpenTelemetry exports a span when it ENDS, so one left open is simply
    absent from Langfuse — while Postgres still records it (with a null
    duration). That divergence is the one thing the mirror must never produce,
    and tool/model failures are an ordinary path, not an exotic one. Records
    the exception TYPE only; the message could carry upstream detail.
    """
    langfuse_mirror.end(
        span.lf, level="ERROR", status_message=type(exc).__name__
    )


def _mirror_mask(*, data: Any, **_: Any) -> Any:
    """Adapter for the Langfuse SDK's keyword-only mask hook (CHO-286).

    Runs client-side on the exporter thread, so a credential- or PII-shaped
    value is scrubbed before the span leaves this process — the unredacted form
    never crosses the network, even to self-hosted infrastructure. A mask that
    raises would drop the span, so failure falls back to a fixed marker rather
    than letting the original value through.
    """
    try:
        return redact(data)
    except Exception:
        return "[redaction-failed]"


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


async def lookup_lf_trace_id(
    pool: Any, *, thread_id: str | None, turn_seq: int | None
) -> str | None:
    """Find ``lf_trace_id`` on a persisted root whose ``turn_seq`` matches.

    Used by ``/api/feedback`` to score the Langfuse turn the user rated.
    Best-effort: missing pool/ids or a miss returns None (caller falls back to
    session-level scoring).
    """
    if pool is None or not thread_id or turn_seq is None:
        return None
    try:
        rows = await pool.fetch(
            "SELECT spans FROM agent_traces WHERE thread_id = $1 "
            "ORDER BY created_at DESC LIMIT 30",
            thread_id,
        )
    except Exception as exc:
        logger.warning("lf_trace lookup failed error=%s", type(exc).__name__)
        return None
    for row in rows or []:
        spans = row["spans"] if isinstance(row, dict) else row[0]
        if isinstance(spans, str):
            try:
                spans = json.loads(spans)
            except Exception:
                continue
        if not isinstance(spans, list) or not spans:
            continue
        root = spans[0]
        if not isinstance(root, dict):
            continue
        meta = root.get("metadata") or {}
        if meta.get("turn_seq") == turn_seq:
            lf_id = meta.get("lf_trace_id")
            if isinstance(lf_id, str) and lf_id:
                return lf_id
    return None


# --------------------------------------------------------------------------- #
# Public wrappers — pass-through when off / no pool / no active trace.
# --------------------------------------------------------------------------- #


def bind_conversation_thread(thread_id: str | None) -> None:
    """Point the in-flight trace at the conversation-store Thread.id (CHO-275).

    Main Menu / cold-load ``reset_thread`` mints a new store id; traces that
    previously hashed ``session_id`` kept rolling up after reset. Call this
    right after ``store.get_thread`` so cost buckets match conversation STM.
    No-op when tracing is off or no turn is active.
    """
    trace = _current_trace.get()
    if trace is None or not thread_id:
        return
    trace.thread_id = thread_id
    # CHO-286: the mirror's identity lands here rather than at turn start,
    # because this is the first moment the thread id exists. It still precedes
    # every child span (loop.py binds at :275, the first model round is :392),
    # so the whole tree carries it.
    root = trace.spans[0] if trace.spans else None
    if root is not None:
        langfuse_mirror.set_identity(
            root.lf, user_id=trace.user_id, session_id=thread_id
        )


def bind_turn_context(**fields: Any) -> None:
    """Merge non-None context fields onto the in-flight trace (and open root)."""
    trace = _current_trace.get()
    if trace is None:
        return
    updates = {k: v for k, v in fields.items() if v is not None}
    if not updates:
        return
    trace.context.update(updates)
    root = trace.spans[0] if trace.spans else None
    if root is not None:
        langfuse_mirror.set_metadata(root.lf, updates)


def bind_ticket_id(ticket_id: Any) -> None:
    """Stamp a raised Freshdesk ticket id onto the open turn root."""
    if ticket_id is None:
        return
    bind_turn_context(ticket_id=ticket_id)


def bind_turn_seq(turn_seq: int | None) -> None:
    """Stamp the exchange's last stored seq (feedback anchor) onto the root."""
    if turn_seq is None:
        return
    bind_turn_context(turn_seq=turn_seq)


def _root_context_for_end(trace: _Trace, root: _Span) -> dict:
    """Final root metadata bag shared by Postgres spans and the Langfuse end."""
    meta = {k: v for k, v in trace.context.items() if v is not None}
    if root.end_ms is not None:
        meta["latency_ms"] = int(root.end_ms - root.start_ms)
    lf_id = langfuse_mirror.trace_id(root.lf)
    if lf_id:
        meta["lf_trace_id"] = lf_id
    return meta


async def observe_turn(
    *,
    message: str,
    session_id: str,
    client_code: str,
    pool: Any,
    run: Callable[[], AsyncIterator[str]],
    platform: str | None = None,
    screen_name: str | None = None,
    frontend_version: str | None = None,
) -> AsyncIterator[str]:
    """agent root span for one /api/chat turn. ``user_id`` is a hashed client
    code; ``thread_id`` starts unset and is filled by
    :func:`bind_conversation_thread` once the store thread is known (CHO-275).
    Persists the assembled tree at turn end."""
    if not _ENABLED or pool is None:
        async for chunk in run():
            yield chunk
        return
    # session_id kept on the signature for callers / future fallbacks; thread
    # grouping uses the conversation Thread.id via bind_conversation_thread.
    _ = session_id
    context = {
        k: v
        for k, v in {
            "platform": platform,
            "screen_name": screen_name,
            "frontend_version": frontend_version,
            "backend_version": config.bot_version(),
        }.items()
        if v is not None
    }
    trace = _Trace(
        thread_id=None,
        user_id=_stable_id(client_code),
        input=redact(message),
        start_ms=_now_ms(),
        context=context,
    )
    root = trace.open("agent", "chat_turn", parent_id=None)
    t_tok = _current_trace.set(trace)
    p_tok = _current_parent.set(root.id)
    try:
        async for chunk in run():
            yield chunk
    finally:
        root.end_ms = _now_ms()
        root.metadata = _root_context_for_end(trace, root)
        _current_parent.reset(p_tok)
        _current_trace.reset(t_tok)
        langfuse_mirror.end(
            root.lf,
            metadata=root.metadata or None,
            version=root.metadata.get("backend_version"),
        )
        _schedule_persist(pool, trace)


async def observe_model_round(
    *,
    user_input: str,
    open_stream: Callable[[], Any],
    holder: dict,
    extra: dict | None = None,
) -> AsyncIterator[str]:
    """llm span for one streamed model round; yields text deltas and stashes the
    final message in ``holder['final']`` for the loop to continue.

    `extra` (CHO-271) is merged into the span metadata — COUNTS ONLY (curated
    turns, estimated history tokens). Never message text, tool inputs or
    envelopes: the span already records only redact(user_input) + usage."""
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
    try:
        async with open_stream() as stream:
            async for delta in stream.text_stream:
                if delta:
                    parts.append(delta)
                    yield delta
            final = await stream.get_final_message()
    except BaseException as exc:
        _mirror_end_failed(span, exc)
        raise
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
        # CHO-278: cache writes bill per TTL (5m = 1.25x base input, 1h = 2x),
        # and the aggregate above carries no TTL. Record the split so the cost
        # estimator prices each bucket instead of guessing. None when the SDK
        # omits `usage.cache_creation` — the estimator then prices the aggregate
        # at the 5-minute rate, as it always did.
        "cache_creation_5m_input_tokens": _cache_creation_get(
            usage, "ephemeral_5m_input_tokens"
        ),
        "cache_creation_1h_input_tokens": _cache_creation_get(
            usage, "ephemeral_1h_input_tokens"
        ),
        "stop_reason": getattr(final, "stop_reason", None),
    }
    if extra:
        span.metadata.update(extra)
    # CHO-286: model and token counts ride Langfuse's native generation fields
    # so its own dashboards aggregate them; the full metadata (including the
    # per-TTL cache split CHO-278 tuned) goes alongside, and OUR cost figure
    # stays authoritative — it is what the CHO-262 viewer reports.
    langfuse_mirror.end(
        span.lf,
        input=span.input,
        output=span.output,
        model=span.metadata.get("model"),
        usage_details={
            k: v
            for k, v in (
                ("input", span.metadata.get("input_tokens")),
                ("output", span.metadata.get("output_tokens")),
                ("cache_read_input_tokens",
                 span.metadata.get("cache_read_input_tokens")),
                ("cache_creation_input_tokens",
                 span.metadata.get("cache_creation_input_tokens")),
            )
            if v is not None
        }
        or None,
        metadata=span.metadata,
    )


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
    except BaseException as exc:
        _mirror_end_failed(span, exc)
        raise
    finally:
        _current_parent.reset(p_tok)
        span.end_ms = _now_ms()
    span.input = redact(tool_input)
    span.metadata = {
        "is_error": getattr(outcome, "is_error", None),
        "error_code": getattr(outcome, "error_code", None),
        "duration_ms": getattr(outcome, "duration_ms", None),
    }
    langfuse_mirror.end(span.lf, input=span.input, metadata=span.metadata)
    return outcome


async def observe_embedding(
    *, query: str, run: Callable[[], Awaitable[list | None]],
) -> list | None:
    """retriever span for the query-embedding call — a sibling of the
    ``kb_search`` span under the same ``tool`` parent (CHO-285).

    Typed ``retriever`` rather than a new span type on purpose: the embedding
    IS the vector leg's first half, and reusing the type keeps the persisted
    graph to the agent/llm/tool/retriever shape the dashboard and the
    observability-tracing spec pin. Records whether a vector came back (``None``
    is the FTS-only degrade), never the vector itself — 3072 floats are noise in
    a trace.
    """
    trace = _current_trace.get()
    if trace is None:
        return await run()
    span = trace.open("retriever", "kb_embed", parent_id=_current_parent.get())
    try:
        embedding = await run()
    except BaseException as exc:
        _mirror_end_failed(span, exc)
        raise
    span.end_ms = _now_ms()
    span.input = redact(query)
    span.output = {"dims": len(embedding) if embedding else None}
    span.metadata = {
        "embedder": config.kb_embed_model(),
        "degraded": embedding is None,
    }
    langfuse_mirror.end(
        span.lf, input=span.input, output=span.output, metadata=span.metadata
    )
    return embedding


async def observe_retrieval(
    *, query: str, run: Callable[[], Awaitable[list]],
) -> list:
    """retriever span for a KB hybrid search; records the fused chunks as
    retrieval_context."""
    trace = _current_trace.get()
    if trace is None:
        return await run()
    span = trace.open("retriever", "kb_search", parent_id=_current_parent.get())
    try:
        results = await run()
    except BaseException as exc:
        _mirror_end_failed(span, exc)
        raise
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
    langfuse_mirror.end(
        span.lf, input=span.input, output=span.output, metadata=span.metadata
    )
    return results


def _usage_get(usage: Any, key: str) -> Any:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage.get(key)
    return getattr(usage, key, None)


def _cache_creation_get(usage: Any, key: str) -> Any:
    """One field of the nested per-TTL cache-write split (CHO-278).

    ``usage.cache_creation`` is an ``anthropic.types.CacheCreation`` model, but
    tolerate a plain dict and a missing/None block — older SDK payloads and test
    doubles have no split at all.
    """
    creation = _usage_get(usage, "cache_creation")
    if creation is None:
        return None
    if isinstance(creation, dict):
        return creation.get(key)
    return getattr(creation, key, None)
