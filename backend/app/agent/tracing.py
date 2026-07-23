"""DeepEval tracing for the agent loop (CHO-244).

Config-gated observability: when a CONFIDENT_API_KEY is present (or
DEEPEVAL_TRACING=1) each POST /api/chat turn is captured as a DeepEval trace —
an ``agent`` root span stitched into a multi-turn thread, with ``llm``,
``tool`` and ``retriever`` child spans — and exported to Confident AI. With
nothing configured every wrapper here is a pass-through: no spans, no latency,
no behaviour change.

PII / secret safety (non-negotiable, per CLAUDE.md):

* DeepEval auto-captures a function's ARGUMENTS as the span input. Our cores
  take ``ctx: ToolCtx`` (SSO JWT, session id, client code) and non-serializable
  handles (http client, pg pool). So the observed functions here take only
  SAFE args; the credentialed context rides in the caller's CLOSURE and is
  never a decorated parameter.
* A global ``mask`` (:func:`redact`) is the second layer — it scrubs
  credential- and PII-shaped values from every span input/output before export.
* ``thread_id`` / ``user_id`` are HMAC hashes, never the raw session id (a live
  FinX auth token) or client code (never logged, per CLAUDE.md). Hashing keeps
  a conversation's turns grouped without exporting the credential itself.

This module never raises into the chat path: import is guarded, ``configure``
is fault-isolated, and every wrapper falls back to a plain pass-through.
"""

import hashlib
import hmac
import logging
import re
from typing import Any, AsyncIterator, Awaitable, Callable

from app import config

logger = logging.getLogger("app.agent.tracing")

try:  # deepeval is a declared dep; guard anyway so a broken install can't
    # break import of the loop that pulls this module in.
    from deepeval.tracing import (  # type: ignore
        observe,
        trace_manager,
        update_current_span,
        update_current_trace,
        update_llm_span,
    )

    _IMPORT_OK = True
except Exception:  # pragma: no cover - only when the install is broken
    _IMPORT_OK = False

_ENABLED = False


# --------------------------------------------------------------------------- #
# Mask — redact credential- and PII-shaped values (DeepEval's global `mask`).
# --------------------------------------------------------------------------- #

_REDACT = "[REDACTED]"

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]*")
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
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
    """Recursively scrub credential/PII-shaped values. Used as DeepEval's
    global ``mask`` and safe to call directly on values we hand to
    ``update_current_span``/``update_current_trace``."""
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
    conversation's turns still group into one thread/user without exporting the
    raw credential. Keyed on the Confident key when present (else a constant) —
    the goal is pseudonymisation, not secrecy of the mapping."""
    if not value:
        return None
    key = (config.confident_api_key() or "jini-tracing").encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Configure — once, at startup, fault-isolated, gated on config.
# --------------------------------------------------------------------------- #


def enabled() -> bool:
    return _ENABLED


def configure() -> None:
    """Initialise DeepEval tracing once. Idempotent; a no-op unless configured
    (key present or DEEPEVAL_TRACING); never raises."""
    global _ENABLED
    if _ENABLED:
        return
    if not _IMPORT_OK:
        logger.warning("deepeval not importable — tracing off")
        return
    if not config.tracing_enabled():
        logger.info("deepeval tracing disabled (no CONFIDENT_API_KEY)")
        return
    try:
        trace_manager.configure(
            mask=redact,
            environment=config.deepeval_env(),
            sampling_rate=config.deepeval_sampling_rate(),
            confident_api_key=config.confident_api_key(),
            tracing_enabled=True,
        )
        _ENABLED = True
        logger.info(
            "deepeval tracing enabled env=%s sampling=%s",
            config.deepeval_env(),
            config.deepeval_sampling_rate(),
        )
    except Exception as exc:
        logger.warning("deepeval tracing init failed error=%s", type(exc).__name__)


# --------------------------------------------------------------------------- #
# Observed inner functions (defined once). SAFE ARGS ONLY — every credentialed
# dependency rides in the caller's closure, never a parameter here.
# --------------------------------------------------------------------------- #

if _IMPORT_OK:

    @observe(type="agent", name="chat_turn")
    async def _observed_turn(
        *, message: str, thread_id: str | None, user_id: str | None,
        run: Callable[[], AsyncIterator[str]],
    ) -> AsyncIterator[str]:
        update_current_trace(
            thread_id=thread_id, user_id=user_id,
            input=redact(message), tags=["chat"],
        )
        async for chunk in run():
            yield chunk

    @observe(type="llm", name="model_round")
    async def _observed_round(
        *, user_input: str, open_stream: Callable[[], Any], holder: dict,
    ) -> AsyncIterator[str]:
        parts: list[str] = []
        async with open_stream() as stream:
            async for delta in stream.text_stream:
                if delta:
                    parts.append(delta)
                    yield delta
            final = await stream.get_final_message()
        holder["final"] = final
        usage = getattr(final, "usage", None)
        update_current_span(input=redact(user_input), output="".join(parts))
        update_llm_span(
            model=getattr(final, "model", None),
            input_token_count=getattr(usage, "input_tokens", None),
            output_token_count=getattr(usage, "output_tokens", None),
        )

    @observe(type="tool")
    async def _observed_tool(
        *, name: str, tool_input: Any, run: Callable[[], Awaitable[Any]],
    ) -> Any:
        outcome = await run()
        update_current_span(
            name=name,
            input=redact(tool_input),
            output={
                "is_error": getattr(outcome, "is_error", None),
                "error_code": getattr(outcome, "error_code", None),
                "duration_ms": getattr(outcome, "duration_ms", None),
            },
        )
        return outcome

    @observe(type="retriever", name="kb_search")
    async def _observed_retrieval(
        *, query: str, run: Callable[[], Awaitable[list]],
    ) -> list:
        results = await run()
        chunks = [
            f"{r.get('question', '')} — {r.get('answer', '')}".strip(" —")
            for r in results
            if isinstance(r, dict)
        ]
        update_current_span(
            input=redact(query),
            retrieval_context=chunks,
            metadata={"count": len(results)},
        )
        return results


# --------------------------------------------------------------------------- #
# Public wrappers — pass-through when tracing is off (no span objects created).
# --------------------------------------------------------------------------- #


async def observe_turn(
    *, message: str, session_id: str, client_code: str,
    run: Callable[[], AsyncIterator[str]],
) -> AsyncIterator[str]:
    """agent root span for one /api/chat turn; stitches the multi-turn thread
    via hashed session/client ids. `run` is the SSE generator closure."""
    if not _ENABLED:
        async for chunk in run():
            yield chunk
        return
    async for chunk in _observed_turn(
        message=message,
        thread_id=_stable_id(session_id),
        user_id=_stable_id(client_code),
        run=run,
    ):
        yield chunk


async def observe_model_round(
    *, user_input: str, open_stream: Callable[[], Any], holder: dict,
) -> AsyncIterator[str]:
    """llm span for one streamed model round; yields text deltas and stashes
    the final message in `holder['final']` for the loop to continue."""
    if not _ENABLED:
        async with open_stream() as stream:
            async for delta in stream.text_stream:
                if delta:
                    yield delta
            holder["final"] = await stream.get_final_message()
        return
    async for delta in _observed_round(
        user_input=user_input, open_stream=open_stream, holder=holder
    ):
        yield delta


async def observe_tool(
    *, name: str, tool_input: Any, run: Callable[[], Awaitable[Any]],
) -> Any:
    """tool span for one dispatch. `run` closes over the credentialed ctx."""
    if not _ENABLED:
        return await run()
    return await _observed_tool(name=name, tool_input=tool_input, run=run)


async def observe_retrieval(
    *, query: str, run: Callable[[], Awaitable[list]],
) -> list:
    """retriever span for a KB hybrid search; records the fused chunks as
    retrieval_context. `run` closes over the pg pool."""
    if not _ENABLED:
        return await run()
    return await _observed_retrieval(query=query, run=run)
