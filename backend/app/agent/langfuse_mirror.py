"""Langfuse mirror for the agent span tree (CHO-286) + journey APIs (CHO-288).

A SECOND sink for the tree `tracing.py` assembles for ``agent_traces``, plus
short-lived observations for non-chat journey HTTP APIs. Postgres stays the
system of record for chat turns; the mirror is subordinate in every direction:

* chat-turn spans still originate from the ``observe_*`` helpers;
* journey API observations are explicit best-effort roots (CHO-288) and are
  never required for request success;
* it is OFF unless ``LANGFUSE_TRACING`` is on AND both credentials and a base
  URL are present, so an unconfigured environment constructs no client and
  makes no network call;
* every entry point swallows its own exceptions. A Langfuse instance that is
  down, slow, or misconfigured must not change the chat response, must not
  delay it, and must not prevent the `agent_traces` write.

Identity mapping (CHO-288 / `trace-mirror`):

    Langfuse session_id  <-  HMAC(FinX SessionId)   (never the raw credential)
    Langfuse user_id     <-  client_code            (raw; same as Postgres)
    metadata.thread_id   <-  conversation Thread.id

Chat turns join Postgres via metadata ``thread_id`` + ``user.id``. The FinX
SSO session id is a live credential (report endpoints authenticate with it) and
MUST NOT appear raw in any Langfuse field.

Identity is applied AFTER the root span opens, directly onto the OTel span,
rather than through ``propagate_attributes``. That is deliberate: the thread id
is not known when the turn starts (``bind_conversation_thread`` supplies it a
moment later, still before any child span), and ``propagate_attributes`` is a
context manager that would have to be held open across function boundaries to
cover the whole turn. Setting ``session.id``/``user.id`` on the span directly
achieves the same result without that lifetime problem.
"""

import logging
from typing import Any

from app import config

logger = logging.getLogger(__name__)

_client: Any = None
_ENABLED = False

# Set once at configure(); the OTel attribute keys Langfuse reads trace-level
# identity from. Held as module state so the import stays inside configure().
_ATTR_SESSION = "session.id"
_ATTR_USER = "user.id"


def enabled() -> bool:
    return _ENABLED and _client is not None


def configure(mask: Any = None) -> None:
    """Build the client when the flag and full credentials are present.

    ``mask`` is the same ``tracing.redact`` the Postgres path uses. Passing it
    here is what makes "a second sink inherits the same mask" true by
    construction rather than by convention: one definition governs both sinks,
    so the mirror cannot fall behind as the denylist grows.
    """
    global _client, _ENABLED, _ATTR_SESSION, _ATTR_USER
    _client, _ENABLED = None, False

    if not config.langfuse_tracing_enabled():
        logger.info("langfuse mirror disabled (LANGFUSE_TRACING off)")
        return
    public, secret = config.langfuse_public_key(), config.langfuse_secret_key()
    base_url = config.langfuse_base_url()
    if not (public and secret and base_url):
        logger.warning("langfuse mirror disabled: credentials or base URL missing")
        return

    try:
        from langfuse import Langfuse, LangfuseOtelSpanAttributes

        _ATTR_SESSION = LangfuseOtelSpanAttributes.TRACE_SESSION_ID
        _ATTR_USER = LangfuseOtelSpanAttributes.TRACE_USER_ID
        _client = Langfuse(
            public_key=public,
            secret_key=secret,
            base_url=base_url,
            mask=mask,
        )
        _ENABLED = True
        # Host only — never the keys.
        logger.info("langfuse mirror enabled (%s)", base_url)
    except Exception as exc:
        logger.warning("langfuse mirror init failed error=%s", type(exc).__name__)
        _client, _ENABLED = None, False


def start_root(
    *,
    name: str,
    input: Any = None,
    metadata: dict | None = None,
    version: str | None = None,
) -> Any:
    """Open the trace root. Returns an opaque handle, or None when inert."""
    if not enabled():
        return None
    try:
        kwargs: dict[str, Any] = {"name": name, "as_type": "span"}
        if input is not None:
            kwargs["input"] = input
        if metadata:
            kwargs["metadata"] = metadata
        if version:
            kwargs["version"] = version
        return _client.start_observation(**kwargs)
    except Exception as exc:
        logger.warning("langfuse root failed error=%s", type(exc).__name__)
        return None


def start_child(parent: Any, *, name: str, as_type: str = "span") -> Any:
    """Open a child of `parent`. Explicit parenting off the handle, not OTel
    context: the agent loop hands work between coroutines, so the ambient
    context is not a reliable description of our tree shape."""
    if parent is None or not enabled():
        return None
    try:
        return parent.start_observation(name=name, as_type=as_type)
    except Exception as exc:
        logger.warning("langfuse child failed error=%s", type(exc).__name__)
        return None


def set_identity(handle: Any, *, user_id: str | None, session_id: str | None) -> None:
    """Stamp trace-level identity onto an open span.

    Called when the conversation thread is bound, which happens after the root
    opens but before any child span, so the whole tree carries it.
    """
    if handle is None or not enabled():
        return
    try:
        otel = getattr(handle, "_otel_span", None)
        if otel is None:
            return
        if session_id:
            otel.set_attribute(_ATTR_SESSION, session_id)
        if user_id:
            otel.set_attribute(_ATTR_USER, user_id)
    except Exception as exc:
        logger.warning("langfuse identity failed error=%s", type(exc).__name__)


def set_metadata(handle: Any, metadata: dict | None) -> None:
    """Merge metadata onto an open span (best-effort)."""
    if handle is None or not enabled() or not metadata:
        return
    try:
        handle.update(metadata=metadata)
    except Exception as exc:
        logger.warning("langfuse metadata failed error=%s", type(exc).__name__)


def trace_id(handle: Any) -> str | None:
    """Hex Langfuse/OTel trace id for an open (or just-ended) root handle."""
    if handle is None:
        return None
    try:
        otel = getattr(handle, "_otel_span", None)
        if otel is None:
            return None
        get_ctx = getattr(otel, "get_span_context", None)
        if not callable(get_ctx):
            # Test doubles may stash the id directly.
            direct = getattr(otel, "trace_id", None)
            return format(direct, "032x") if isinstance(direct, int) else (
                str(direct) if direct else None
            )
        ctx = get_ctx()
        tid = getattr(ctx, "trace_id", None)
        if isinstance(tid, int) and tid:
            return format(tid, "032x")
        return str(tid) if tid else None
    except Exception as exc:
        logger.warning("langfuse trace_id failed error=%s", type(exc).__name__)
        return None


def end(handle: Any, **fields: Any) -> None:
    """Update and close a span. Unset fields are dropped so we never overwrite
    something with None."""
    if handle is None or not enabled():
        return
    try:
        payload = {k: v for k, v in fields.items() if v is not None}
        if payload:
            handle.update(**payload)
        handle.end()
    except Exception as exc:
        logger.warning("langfuse end failed error=%s", type(exc).__name__)


def create_feedback_score(
    *,
    rating: str,
    trace_id: str | None = None,
    session_id: str | None = None,
    anchor_seq: int | None = None,
    source: str | None = None,
) -> None:
    """BOOLEAN ``user-feedback`` score (1=up, 0=down). Best-effort only."""
    if not enabled():
        return
    if not trace_id and not session_id:
        return
    try:
        value = 1 if rating == "up" else 0
        meta = {}
        if anchor_seq is not None:
            meta["anchor_seq"] = anchor_seq
        if source:
            meta["source"] = source
        _client.create_score(
            name="user-feedback",
            value=value,
            data_type="BOOLEAN",
            trace_id=trace_id,
            session_id=session_id if not trace_id else None,
            comment=f"rating={rating}",
            metadata=meta or None,
        )
    except Exception as exc:
        logger.warning("langfuse score failed error=%s", type(exc).__name__)


def emit_api_observation(
    *,
    name: str,
    lf_session_id: str | None = None,
    user_id: str | None = None,
    thread_id: str | None = None,
    metadata: dict | None = None,
    output: Any = None,
    input: Any = None,
    version: str | None = None,
) -> None:
    """Short-lived Langfuse root for a journey HTTP API (CHO-288).

    ``lf_session_id`` must already be the hashed FinX SessionId (callers use
    ``tracing.stable_session_id``). Never pass the raw SessionId here.
    """
    if not enabled():
        return
    handle = None
    try:
        meta = {k: v for k, v in (metadata or {}).items() if v is not None}
        if thread_id:
            meta["thread_id"] = thread_id
        handle = start_root(
            name=name,
            input=input,
            metadata=meta or None,
            version=version or meta.get("backend_version"),
        )
        set_identity(handle, user_id=user_id, session_id=lf_session_id)
        end(handle, metadata=meta or None, output=output)
    except Exception as exc:
        logger.warning("langfuse api obs failed error=%s", type(exc).__name__)
        end(handle)


def emit_ticket_observation(
    *,
    session_id: str | None,
    user_id: str | None,
    ticket_id: Any,
    reason: str | None = None,
    platform: str | None = None,
    screen_name: str | None = None,
    backend_version: str | None = None,
    thread_id: str | None = None,
) -> None:
    """Help-card ``/api/ticket`` observation (wraps :func:`emit_api_observation`).

    ``session_id`` is the Langfuse session id (hashed FinX SessionId), not the
    raw credential and not Thread.id.
    """
    if ticket_id is None:
        return
    meta: dict[str, Any] = {"ticket_id": ticket_id}
    if reason:
        meta["reason"] = reason
    if platform:
        meta["platform"] = platform
    if screen_name:
        meta["screen_name"] = screen_name
    if backend_version:
        meta["backend_version"] = backend_version
    emit_api_observation(
        name="raise_ticket",
        lf_session_id=session_id,
        user_id=user_id,
        thread_id=thread_id,
        metadata=meta,
        output={"ticketId": ticket_id},
        version=backend_version,
    )

def shutdown() -> None:
    """Flush pending spans at app shutdown. Batched export means a short-lived
    process could otherwise exit with spans still queued."""
    if not enabled():
        return
    try:
        _client.shutdown()
    except Exception as exc:
        logger.warning("langfuse shutdown failed error=%s", type(exc).__name__)
