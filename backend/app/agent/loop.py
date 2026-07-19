"""The agentic tool-use loop behind POST /api/chat (CHO-213 · 4.2/4.4/4.5).

A manual `while stop_reason == "tool_use"` loop over the Anthropic Messages
API (design D1). Every round streams (`client.messages.stream(...)`): text
deltas are forwarded to the SSE response AS THEY ARRIVE, then
`get_final_message()` decides continuation. Assistant and tool messages are
fed back wire-faithfully through the conversation store — `thread.messages()`
IS the messages param, so replay stays byte-identical (and Anthropic prompt
caching warm).

SSE contract (design D9, pinned with the frontend):
  text      {"delta": str}                      — streamed assistant text
  tool      {"name", "status": "started"|"finished", "is_error": bool}
  artifact  file: {"kind":"file","file":{...},"fileToken","flowKey"}
            data: {"kind":"data","tool":<name>, ...envelope fields (its own
                   "kind":"ok" dropped — the artifact kind replaces it)}
  done      {"thread": {"taskTurns": n, "sessionTurns": n}}   — terminal
  error     {"error": "AGENT_UNAVAILABLE"|"AUTH_EXPIRED"}      — terminal
Exactly one terminal event is emitted per stream. AUTH_EXPIRED from a tool is
still fed to the model as an is_error tool_result (it narrates), and then
replaces `done` as the terminal event so the shell can react.

PII: this module logs exception type names, counts, and timings only — never
message text, tool inputs, or envelopes.
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator

from app import config
from app.agent import caps as agent_caps
from app.agent import prompt as agent_prompt
from app.agent import tools as agent_tools
from app.agent.ctx import CODE_AUTH_EXPIRED, ToolCtx
from app.agent.store import ThreadStore

logger = logging.getLogger("app.agent.loop")

# Data-card envelopes worth an artifact event. KB results are NOT artifacts —
# the model narrates them. Contract-note lists are narrated too (the model
# offers the choices); only the downloaded note is a (file) artifact.
_DATA_ARTIFACT_TOOLS = frozenset(
    {"get_holdings", "get_money_transactions", "get_brokerage_rates"}
)

# fileToken envelopes → the existing download-card, keyed for the frontend's
# per-flow copy (password note etc.).
_FILE_FLOW_KEYS = {
    "get_pnl_report": "pnl",
    "get_ledger_report": "ledger",
    "get_capital_gains_report": "tax",
    "download_contract_note": "contract-notes",
}

_ESCALATION_REMINDER = (
    "<system-reminder>Conversation limit reached. Do not ask another "
    "clarifying question. Answer with the information you already have if "
    "you can, and offer to connect the user with a human support agent for "
    "anything unresolved.</system-reminder>"
)

# Session backstop alone (CHO-214 · D6): a long-lived thread is normal use,
# not evidence of struggle — offer a human only when the user seems stuck.
_SOFT_ESCALATION_REMINDER = (
    "<system-reminder>This session has been running a while. If the user "
    "seems stuck, frustrated, or keeps rephrasing the same unresolved "
    "question, offer to connect them with a human support agent. If their "
    "request is clear and answerable, just answer it normally — do not "
    "mention conversation length or suggest escalation.</system-reminder>"
)

_WRAPUP_REMINDER = (
    "<system-reminder>Tool-call limit reached for this message. Do not "
    "request any more tools. Summarize what you found so far, tell the user "
    "plainly what you could not complete, and suggest how to proceed."
    "</system-reminder>"
)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def _reminder_message(text: str) -> dict:
    """A trailing user-role system-reminder block. Appended at the END of the
    messages array (never stored, never edits system) so the prompt-cache
    prefix stays intact."""
    return {"role": "user", "content": [{"type": "text", "text": text}]}


def _block_to_dict(block: Any) -> dict:
    """SDK content block → the wire-faithful plain dict the store persists."""
    if isinstance(block, dict):
        return block
    btype = getattr(block, "type", None)
    if btype == "text":
        return {"type": "text", "text": block.text}
    if btype == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    if btype == "thinking":
        return {
            "type": "thinking",
            "thinking": block.thinking,
            "signature": block.signature,
        }
    if btype == "redacted_thinking":
        return {"type": "redacted_thinking", "data": block.data}
    dump = getattr(block, "model_dump", None)
    return dump(exclude_none=True) if callable(dump) else {"type": str(btype)}


def _usage_dict(usage: Any) -> dict:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return usage
    out: dict = {}
    for key in (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    ):
        value = getattr(usage, key, None)
        if value is not None:
            out[key] = value
    return out


def _artifact_payload(
    name: str, outcome: agent_tools.DispatchOutcome
) -> dict | None:
    """The pinned artifact event for a successful tool result, or None."""
    envelope = outcome.envelope
    if outcome.is_error or not isinstance(envelope, dict):
        return None
    if name == "open_report_form" and envelope.get("kind") == "form":
        # Form handover (CHO-214): the shell boots the guided FlowCard from
        # this seed via startRun(descriptor, seed).
        return {
            "kind": "flow",
            "flowKey": envelope.get("flow"),
            "seed": envelope.get("seed") or {},
        }
    if "fileToken" in envelope:
        return {
            "kind": "file",
            "file": envelope.get("file"),
            "fileToken": envelope["fileToken"],
            "flowKey": _FILE_FLOW_KEYS.get(name),
        }
    if name in _DATA_ARTIFACT_TOOLS and envelope.get("kind") == "ok":
        payload = {k: v for k, v in envelope.items() if k != "kind"}
        return {"kind": "data", "tool": name, **payload}
    return None


async def run_chat_stream(
    *, message: str, ctx: ToolCtx, store: ThreadStore, client: Any
) -> AsyncIterator[str]:
    """The SSE generator for one /api/chat request. Never raises into the
    transport: any unexpected failure becomes a terminal error event."""
    terminal_emitted = False
    try:
        async for chunk in _chat_events(
            message=message, ctx=ctx, store=store, client=client
        ):
            if chunk.startswith("event: done") or chunk.startswith(
                "event: error"
            ):
                terminal_emitted = True
            yield chunk
    except Exception as exc:
        logger.warning("agent chat stream failed error=%s", type(exc).__name__)
        if not terminal_emitted:
            yield _sse("error", {"error": "AGENT_UNAVAILABLE"})


async def _chat_events(
    *, message: str, ctx: ToolCtx, store: ThreadStore, client: Any
) -> AsyncIterator[str]:
    store.register_prompt(agent_prompt.snapshot_text(), agent_tools.tool_schemas())
    thread = await store.get_thread(ctx.session_id, client_code=ctx.client_code)
    store.append_turn(
        thread,
        role="user",
        kind="user_text",
        content=[{"type": "text", "text": message}],
    )

    # Caps are evaluated once per incoming user message (design D5), after
    # the user turn is appended so the current message counts. Injection is
    # trip-specific (CHO-214 · D6): clarify/task trips mandate the offer;
    # the session backstop alone only asks the model to watch for struggle.
    counters = agent_caps.evaluate(thread)
    tripped = set(counters.tripped)
    if tripped & {agent_caps.CAP_CLARIFY, agent_caps.CAP_TASK_TURNS}:
        escalation_reminder: str | None = _ESCALATION_REMINDER
    elif agent_caps.CAP_SESSION_TURNS in tripped:
        escalation_reminder = _SOFT_ESCALATION_REMINDER
    else:
        escalation_reminder = None
    auth_expired = False
    rounds = 0

    while True:
        force_wrapup = rounds >= config.agent_max_tool_rounds()
        messages = agent_prompt.primed_messages() + thread.messages()
        if escalation_reminder is not None:
            messages.append(_reminder_message(escalation_reminder))
        if force_wrapup:
            messages.append(_reminder_message(_WRAPUP_REMINDER))

        model = config.agent_model()
        kwargs: dict = {
            "model": model,
            "max_tokens": config.agent_max_tokens(),
            "system": agent_prompt.system_blocks(),
            "tools": agent_tools.tool_schemas(),
            "messages": messages,
            **config.agent_thinking_params(model, config.agent_thinking()),
        }
        if force_wrapup:
            kwargs["tool_choice"] = {"type": "none"}

        started = time.perf_counter()
        try:
            if client is None:
                raise RuntimeError("anthropic client not configured")
            async with client.messages.stream(**kwargs) as stream:
                async for delta in stream.text_stream:
                    if delta:
                        yield _sse("text", {"delta": delta})
                final = await stream.get_final_message()
        except Exception as exc:
            # SDK retries already happened; the agent is unavailable for this
            # turn. Existing guided flows are unaffected.
            logger.warning(
                "agent model call failed error=%s", type(exc).__name__
            )
            yield _sse("error", {"error": "AGENT_UNAVAILABLE"})
            return
        latency_ms = int((time.perf_counter() - started) * 1000)

        content = [_block_to_dict(block) for block in (final.content or [])]
        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        stop_reason = getattr(final, "stop_reason", None)
        store.append_turn(
            thread,
            role="assistant",
            kind="assistant_tool_use" if tool_uses else "assistant_text",
            content=content,
            meta={
                "model": getattr(final, "model", None),
                "stop_reason": stop_reason,
                "usage": _usage_dict(getattr(final, "usage", None)),
                "latency_ms": latency_ms,
            },
        )

        if stop_reason == "tool_use" and tool_uses:
            rounds += 1
            for block in tool_uses:
                yield _sse(
                    "tool",
                    {"name": block["name"], "status": "started", "is_error": False},
                )
            # Parallel tool_use blocks execute concurrently; all results are
            # answered in ONE user message on the wire (consecutive
            # tool_result turns merge in thread.messages()).
            outcomes = await asyncio.gather(
                *(
                    agent_tools.dispatch_outcome(
                        block["name"], block.get("input") or {}, ctx
                    )
                    for block in tool_uses
                )
            )
            artifacts: list[dict | None] = []
            for block, outcome in zip(tool_uses, outcomes):
                yield _sse(
                    "tool",
                    {
                        "name": block["name"],
                        "status": "finished",
                        "is_error": outcome.is_error,
                    },
                )
                artifact = _artifact_payload(block["name"], outcome)
                artifacts.append(artifact)
                if artifact is not None:
                    yield _sse("artifact", artifact)
                if outcome.error_code == CODE_AUTH_EXPIRED:
                    auth_expired = True
                store.append_turn(
                    thread,
                    role="user",
                    kind="tool_result",
                    content=[
                        {
                            "type": "tool_result",
                            "tool_use_id": block["id"],
                            "content": outcome.content,
                            "is_error": outcome.is_error,
                        }
                    ],
                    meta={
                        "tool_name": block["name"],
                        "is_error": outcome.is_error,
                        "duration_ms": outcome.duration_ms,
                    },
                )
            # CHO-215: the artifact IS the answer. When every call succeeded
            # and every one produced an artifact (form/data/file card), end
            # the turn — no continuation model call, no narration. Any round
            # with an error or a narration-needing success (KB, note list)
            # continues to the model as before. auth_expired is unreachable
            # here (auth expiry is an error result).
            if (
                outcomes
                and all(not o.is_error for o in outcomes)
                and all(a is not None for a in artifacts)
            ):
                counters = agent_caps.evaluate(thread)
                yield _sse(
                    "done",
                    {
                        "thread": {
                            "taskTurns": counters.task_user_turns,
                            "sessionTurns": counters.session_user_turns,
                        }
                    },
                )
                return
            continue

        # Terminal: end_turn (or any non-tool stop). Exactly one terminal
        # event: AUTH_EXPIRED (after the model's narration) when a tool
        # surfaced auth expiry, else done with the derived counters.
        if auth_expired:
            yield _sse("error", {"error": "AUTH_EXPIRED"})
            return
        counters = agent_caps.evaluate(thread)
        yield _sse(
            "done",
            {
                "thread": {
                    "taskTurns": counters.task_user_turns,
                    "sessionTurns": counters.session_user_turns,
                }
            },
        )
        return
