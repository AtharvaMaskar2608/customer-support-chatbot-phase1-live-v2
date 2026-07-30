"""Langfuse mirror for the agent span tree (CHO-286).

A SECOND sink for the exact tree `tracing.py` already assembles for
``agent_traces``. Postgres stays the system of record; this is a mirror, and it
is subordinate in every direction:

* it never observes anything the Postgres path does not — every call here is
  made from inside the five ``observe_*`` helpers, which are the only places a
  span is opened or closed;
* it is OFF unless ``LANGFUSE_TRACING`` is on AND both credentials and a base
  URL are present, so an unconfigured environment constructs no client and
  makes no network call;
* every entry point swallows its own exceptions. A Langfuse instance that is
  down, slow, or misconfigured must not change the chat response, must not
  delay it, and must not prevent the `agent_traces` write.

Identity mapping (see the `trace-mirror` capability):

    Langfuse session_id  <-  conversation Thread.id   (same value as thread_id)
    Langfuse user_id     <-  _stable_id(client_code)  (same HMAC Postgres holds)

Both are the values Postgres already stores, which is what keeps the two stores
joinable — a Langfuse trace can be pivoted to its `agent_traces` row on either
key. The FinX SSO session id is NOT sent in any form: it is a live credential
(the report endpoints authenticate with it), and `observability-tracing`
forbids storing it.

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


def start_root(*, name: str, input: Any) -> Any:
    """Open the trace root. Returns an opaque handle, or None when inert."""
    if not enabled():
        return None
    try:
        return _client.start_observation(name=name, as_type="span", input=input)
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


def shutdown() -> None:
    """Flush pending spans at app shutdown. Batched export means a short-lived
    process could otherwise exit with spans still queued."""
    if not enabled():
        return
    try:
        _client.shutdown()
    except Exception as exc:
        logger.warning("langfuse shutdown failed error=%s", type(exc).__name__)
