"""Freshdesk escalation core (CHO-218 · design D1-D4).

One ticket core, two entry points: the `raise_support_ticket` agent tool and
`POST /api/ticket` (help card) both call `run_raise_ticket`, producing
identical tickets. The parameter set is CLONED from the live prototype
tickets (#7539459/#7529083) in the chatbot-testing group — subject, group,
status/priority/source/type, tags, and custom fields are byte-for-byte the
established contract (design D1), so bot tickets land where the support
workflow already expects them.

Requester identity is the client code only (`unique_external_id` + `name`);
no email or phone ever leaves our system. Credentials (API root/key) come
from server-side config at call time — never logged, never in tool schemas,
never stored in the conversation. Upstream logging is status + timing only
(FinxClient posture): no body, no URL, no credential.

The ticket description carries the conversation transcript (design D2):
user/assistant text and app-event memos only — NEVER tool_use/tool_result
internals — rendered as simple HTML, truncated oldest-first past the caps.
"""

import datetime
import html
import logging
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app import config
from app.agent.ctx import CODE_UPSTREAM_ERROR, ToolCtx, ToolError, parse_params

logger = logging.getLogger("app.agent.tickets")

# --- the D1 "same in every ticket" constants ---------------------------------
# Cloned from the live prototype tickets; the group id lives in config (env
# override FRESHDESK_GROUP_ID) so production routing later is a config flip.
TICKET_STATUS_OPEN = 2
TICKET_PRIORITY_MEDIUM = 2
TICKET_SOURCE_CHAT = 7
TICKET_TYPE = "GENERAL QUERY"
TICKET_TAGS = ("choice-jini", "chatbot-testing", "lang:en")

_TIMEOUT_SECONDS = 10.0

# Transcript caps (design D2): hard turn cap + byte soft cap, both truncating
# oldest-first — a support agent needs the recent tail of the conversation.
MAX_TRANSCRIPT_TURNS = 100
TRANSCRIPT_SOFT_CAP_BYTES = 60_000

_UNREACHABLE_MESSAGE = (
    "couldn't reach the support system — suggest the user try the Help "
    "section in the FinX app, or try again shortly"
)

# Only the human-readable conversation enters the ticket. Tool internals
# (assistant_tool_use inputs, tool_result envelopes) are noise to a support
# agent and are excluded by construction, never by redaction.
_TRANSCRIPT_KINDS = frozenset({"user_text", "assistant_text", "flow_event"})

_SPEAKERS = {"user_text": "Client", "assistant_text": "Jini"}


class RaiseTicketParams(BaseModel):
    """User-intent field only; unknown extras are ignored (never errors)."""

    model_config = ConfigDict(extra="ignore")

    reason: str = Field(min_length=1, max_length=200)


# --- transcript rendering (design D2) ----------------------------------------


def _turn_text(turn: Any) -> str:
    """Join a turn's text blocks; non-text blocks contribute nothing."""
    return "\n".join(
        str(block.get("text", ""))
        for block in turn.content
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()


def _escape(text: str) -> str:
    """HTML-escape + keep the author's line breaks readable in the ticket."""
    return html.escape(text).replace("\n", "<br>")


def _render_entry(kind: str, text: str) -> str:
    if kind == "flow_event":
        return f"<p><i>{_escape(text)}</i></p>"
    return f"<p><b>{_SPEAKERS[kind]}:</b> {_escape(text)}</p>"


def render_transcript(
    thread: Any,
    *,
    reason: str,
    client_code: str,
    max_turns: int = MAX_TRANSCRIPT_TURNS,
) -> str:
    """The ticket description: metadata block + conversation as simple HTML.

    Includes user_text / assistant_text (text blocks joined; empty ones
    skipped) and flow_event memos (italicized app events) — NEVER
    assistant_tool_use or tool_result content. Truncates oldest-first past
    `max_turns` and past the ~60KB soft cap, stating how many turns are
    shown. All conversation text is HTML-escaped.
    """
    entries: list[tuple[str, str]] = []
    for turn in getattr(thread, "turns", None) or []:
        if turn.kind not in _TRANSCRIPT_KINDS:
            continue
        text = _turn_text(turn)
        if text:
            entries.append((turn.kind, text))
    total = len(entries)
    kept = entries[-max_turns:] if max_turns >= 0 else entries

    raised_at = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    )

    def _render(kept_entries: list[tuple[str, str]]) -> str:
        parts = [
            "<p>"
            f"<b>Client ID:</b> {_escape(client_code)}<br>"
            f"<b>Reason:</b> {_escape(reason)}<br>"
            f"<b>Raised at:</b> {raised_at}<br>"
            f"<b>Turns included:</b> {len(kept_entries)} of {total}"
            "</p>"
        ]
        if len(kept_entries) < total:
            parts.append(
                "<p><i>Transcript truncated — showing the last "
                f"{len(kept_entries)} of {total} turns.</i></p>"
            )
        parts.extend(_render_entry(kind, text) for kind, text in kept_entries)
        return "\n".join(parts)

    rendered = _render(kept)
    while (
        len(rendered.encode("utf-8")) > TRANSCRIPT_SOFT_CAP_BYTES and len(kept) > 1
    ):
        kept = kept[1:]  # drop the oldest kept turn and re-render
        rendered = _render(kept)
    return rendered


def ticket_memo(ticket_id: Any, reason: str) -> str:
    """The flow-event memo both entry points append on success — framed like
    the events.py app-event memos so the model reads it as data, remembers
    the escalation, and never re-raises for the same issue."""
    return (
        "[App event — generated by the app, not typed by the user] "
        f"Support ticket #{ticket_id} raised — {reason}."
    )


# --- the ticket core (design D1/D3/D4) ---------------------------------------


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


async def run_raise_ticket(
    params: RaiseTicketParams | dict, ctx: ToolCtx
) -> dict | ToolError:
    """Create one Freshdesk ticket carrying the conversation. Never raises.

    Success -> {"kind": "ticket", "ticketId": <id>, "status": "Open"}
    Timeout / 4xx / 5xx / 429 / unconfigured -> ToolError(UPSTREAM_ERROR)
    — never a fabricated ticket id (design D4).
    """
    params = parse_params(RaiseTicketParams, params)
    if isinstance(params, ToolError):
        return params

    root = config.freshdesk_api_root()
    api_key = config.freshdesk_api_key()
    if not root or not api_key:
        logger.warning("freshdesk not configured — ticket not raised")
        return ToolError(code=CODE_UPSTREAM_ERROR, message=_UNREACHABLE_MESSAGE)

    # The exact D1 payload — identity and routing come from the authenticated
    # ctx and code/config constants, never from model-controlled fields.
    payload = {
        "subject": f"[Choice Jini] {params.reason} — Client {ctx.client_code}",
        "description": render_transcript(
            ctx.thread, reason=params.reason, client_code=ctx.client_code
        ),
        "unique_external_id": ctx.client_code,
        "name": ctx.client_code,
        "status": TICKET_STATUS_OPEN,
        "priority": TICKET_PRIORITY_MEDIUM,
        "source": TICKET_SOURCE_CHAT,
        "type": TICKET_TYPE,
        "group_id": config.freshdesk_group_id(),
        "tags": list(TICKET_TAGS),
        "custom_fields": {
            "cf_client_id": ctx.client_code,
            "cf_source": "chat box",
            "cf_product": "finx",
            "cf_query_type149508": "finx-bot",
            "cf_query_sub_type": "finx-bot-test",
        },
    }

    started = time.perf_counter()
    try:
        resp = await ctx.http_client.post(
            f"{root}/tickets",
            json=payload,
            auth=(api_key, "X"),
            timeout=_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # timeout / connect failure — never raises out
        logger.warning(
            "freshdesk call failed error=%s elapsed_ms=%d",
            type(exc).__name__,
            _elapsed_ms(started),
        )
        return ToolError(code=CODE_UPSTREAM_ERROR, message=_UNREACHABLE_MESSAGE)

    # Status + timing only — no body, no URL, no credential (FinxClient posture).
    logger.info(
        "freshdesk upstream status=%d elapsed_ms=%d",
        resp.status_code,
        _elapsed_ms(started),
    )
    if resp.status_code != 201:
        return ToolError(code=CODE_UPSTREAM_ERROR, message=_UNREACHABLE_MESSAGE)
    try:
        ticket_id = resp.json().get("id")
    except Exception:
        ticket_id = None
    if ticket_id is None:  # a 201 without an id is not a success we can show
        return ToolError(code=CODE_UPSTREAM_ERROR, message=_UNREACHABLE_MESSAGE)
    return {"kind": "ticket", "ticketId": ticket_id, "status": "Open"}
