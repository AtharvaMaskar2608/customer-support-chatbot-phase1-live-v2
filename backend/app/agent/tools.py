"""Agent tool registry + dispatcher (CHO-213 · tasks 2.1/2.2, design D2/D3).

Each entry maps a tool name to (JSON schema of USER-INTENT parameters only,
async handler). Handlers are the exact flow cores the REST routes call —
never duplicated, never invoked over HTTP — so both entry points produce the
same normalized envelope. Schemas carry NO credential fields (SessionId, SSO
JWT, client code, ...): credentials travel only in the per-request `ToolCtx`,
so the model has no field to redirect identity through (the structural IDOR
defense from D3).

The spec's "8 capabilities" map to 9 tool entries: contract notes is a
two-step chain (list → download), mirrored as two tools over its two cores.
CHO-214 added open_report_form (form handover) and CHO-218 added
raise_support_ticket (Freshdesk escalation) — 11 entries total.

Dispatch contract (task 2.2):
  - unknown tool          -> is_error, "unknown tool ..."
  - core ToolError        -> is_error with the core's actionable message
  - unexpected exception  -> caught; is_error with a generic message
                             (log carries the exception TYPE only)
  - success               -> compact sorted-key JSON of the envelope
Duration is measured per call and returned for the tool_result meta.
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.agent.ctx import ToolCtx, ToolError
from app.agent.forms import run_open_report_form
from app.agent.tickets import run_raise_ticket, ticket_call_is_user_initiated
from app.columns import run_report_columns
from app.data.brokerage import run_brokerage
from app.data.holdings import run_holdings
from app.data.money import run_money
from app.kb.router import run_kb_search
from app.report import run_pnl
from app.reports.contract_notes import (
    run_contract_notes_download,
    run_contract_notes_list,
)
from app.reports.ledger import run_ledger
from app.reports.tax import run_tax

logger = logging.getLogger("app.agent.tools")

Handler = Callable[[Any, ToolCtx], Awaitable[dict | ToolError]]

_DATE = {"type": "string", "description": "Date in YYYY-MM-DD format."}
_DELIVERY = {
    "type": "string",
    "enum": ["download", "email"],
    "description": (
        "How the report is delivered: 'download' (in-chat file) or 'email' "
        "(sent to the registered email)."
    ),
}

# Zero-slot flows: no user-intent parameters exist at all.
_EMPTY_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    handler: Handler


async def _run_tax_fy(params: Any, ctx: ToolCtx) -> dict | ToolError:
    """Adapter: the tool exposes `fy` (user intent); the core model expects
    `finYear`. Everything else passes through untouched."""
    if isinstance(params, dict) and "fy" in params:
        remapped = dict(params)  # never mutate the stored tool_use input
        remapped["finYear"] = remapped.pop("fy")
        params = remapped
    return await run_tax(params, ctx)


_TOOL_LIST = [
    Tool(
        name="open_report_form",
        description=(
            "Open a guided report form in the chat, pre-filled with the "
            "values the user has stated. THIS is how report requests with "
            "missing parameters are handled — never ask for report "
            "parameters in a text question. Pass only values the user "
            "actually said (resolve relative dates to YYYY-MM-DD first); "
            "pass nothing beyond `flow` when they gave no details. The "
            "widget asks for whatever is missing."
        ),
        schema={
            "type": "object",
            "properties": {
                "flow": {
                    "type": "string",
                    "enum": ["pnl", "ledger", "tax", "contract-notes"],
                    "description": (
                        "Which report form to open: pnl (P&L statement), "
                        "ledger (account statement), tax (capital gains), "
                        "contract-notes (trade confirmations)."
                    ),
                },
                "segment": {
                    "type": "string",
                    "enum": ["Equity", "F&O", "Commodity"],
                    "description": "P&L only: trading segment, if stated.",
                },
                "book": {
                    "type": "string",
                    "enum": ["Normal", "MTF"],
                    "description": "Ledger only: ledger book, if stated.",
                },
                "fy": {
                    "type": "string",
                    "description": (
                        "Tax only: financial year as YYYY-YYYY (e.g. "
                        "'2025-2026'), if stated."
                    ),
                },
                "format": {
                    "type": "string",
                    "enum": ["PDF", "Excel"],
                    "description": "Tax only: file format, if stated.",
                },
                "fromDate": _DATE,
                "toDate": _DATE,
                "delivery": _DELIVERY,
            },
            "required": ["flow"],
            "additionalProperties": False,
        },
        handler=run_open_report_form,
    ),
    Tool(
        name="get_pnl_report",
        description=(
            "Generate the client's Profit & Loss (P&L) statement for one "
            "trading segment over a date range, as a PDF "
            "(download or email). Call this when the user asks for their "
            "P&L, profit/loss statement, or realized trading performance. "
            "All four parameters are required — call this ONLY when every "
            "one of them is explicitly known (from the user's words or a "
            "completed form earlier in this conversation); otherwise call "
            "open_report_form instead."
        ),
        schema={
            "type": "object",
            "properties": {
                "segment": {
                    "type": "string",
                    "enum": ["Equity", "F&O", "Commodity"],
                    "description": "Trading segment the P&L covers.",
                },
                "fromDate": _DATE,
                "toDate": _DATE,
                "delivery": _DELIVERY,
            },
            "required": ["segment", "fromDate", "toDate", "delivery"],
            "additionalProperties": False,
        },
        handler=run_pnl,
    ),
    Tool(
        name="get_ledger_report",
        description=(
            "Generate the client's ledger (account statement of debits and "
            "credits) for the Normal or MTF book over a date range, as a PDF "
            "(download or email). Call this when the "
            "user asks for their ledger, account statement, or fund "
            "debit/credit history. All four parameters are required — call "
            "this ONLY when every one is explicitly known; otherwise call "
            "open_report_form instead."
        ),
        schema={
            "type": "object",
            "properties": {
                "book": {
                    "type": "string",
                    "enum": ["Normal", "MTF"],
                    "description": (
                        "Ledger book: 'Normal' (regular trading account) or "
                        "'MTF' (Margin Trading Facility)."
                    ),
                },
                "fromDate": _DATE,
                "toDate": _DATE,
                "delivery": _DELIVERY,
            },
            "required": ["book", "fromDate", "toDate", "delivery"],
            "additionalProperties": False,
        },
        handler=run_ledger,
    ),
    Tool(
        name="get_capital_gains_report",
        description=(
            "Generate the client's capital gains (tax) report for one "
            "financial year, as PDF or Excel (download or email). Call this "
            "when the user asks for capital gains, their tax report, or "
            "documents for ITR filing. All three parameters are required — "
            "call this ONLY when every one is explicitly known; otherwise "
            "call open_report_form instead."
        ),
        schema={
            "type": "object",
            "properties": {
                "fy": {
                    "type": "string",
                    "description": (
                        "Financial year span in YYYY-YYYY format, e.g. "
                        "'2025-2026' for FY starting April 2025."
                    ),
                },
                "format": {
                    "type": "string",
                    "enum": ["PDF", "Excel"],
                    "description": "Report file format.",
                },
                "delivery": _DELIVERY,
            },
            "required": ["fy", "format", "delivery"],
            "additionalProperties": False,
        },
        handler=_run_tax_fy,
    ),
    Tool(
        name="list_contract_notes",
        description=(
            "List the client's contract notes (trade confirmations) over a "
            "date range. ALWAYS call this first when the user wants a "
            "contract note — it returns the note ids that "
            "download_contract_note requires. Both dates are required."
        ),
        schema={
            "type": "object",
            "properties": {
                "fromDate": _DATE,
                "toDate": _DATE,
            },
            "required": ["fromDate", "toDate"],
            "additionalProperties": False,
        },
        handler=run_contract_notes_list,
    ),
    Tool(
        name="download_contract_note",
        description=(
            "Download one contract note as a PDF. `id` MUST be a note id "
            "returned by list_contract_notes earlier in this conversation — "
            "never invent or guess an id. Call list_contract_notes first if "
            "you do not have one."
        ),
        schema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": (
                        "Opaque note id from a list_contract_notes result."
                    ),
                },
            },
            "required": ["id"],
            "additionalProperties": False,
        },
        handler=run_contract_notes_download,
    ),
    Tool(
        name="get_holdings",
        description=(
            "Fetch the client's current stock holdings (portfolio) with live "
            "valuations, invested value, P&L, and day change. Call this when "
            "the user asks what they hold, their portfolio value, or how "
            "their investments are doing. Takes no parameters."
        ),
        schema=_EMPTY_SCHEMA,
        handler=run_holdings,
    ),
    Tool(
        name="get_money_transactions",
        description=(
            "Fetch the client's money movements — pay-in (deposits) and "
            "pay-out (withdrawals) — for the current financial year, as one "
            "merged passbook. Call this when the user asks about funds "
            "added, withdrawals, transfer status, or missing money. Takes "
            "no parameters."
        ),
        schema=_EMPTY_SCHEMA,
        handler=run_money,
    ),
    Tool(
        name="get_brokerage_rates",
        description=(
            "Fetch the client's personalized brokerage rate card (charges "
            "per segment and order type). Call this when the user asks what "
            "brokerage or charges they pay. Takes no parameters. For "
            "questions about what a charge MEANS (definition or how-to), "
            "call search_knowledge_base instead."
        ),
        schema=_EMPTY_SCHEMA,
        handler=run_brokerage,
    ),
    Tool(
        name="search_knowledge_base",
        description=(
            "Fetch factual support answers for general product, process, "
            "charges, and how-to questions (e.g. account opening, fund "
            "transfer steps, what a term means). Call this for general "
            "questions that are NOT about the client's own account data. "
            "Answer the user directly from what the tool returns."
        ),
        schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query, in plain language.",
                },
                "top_k": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "description": "How many results to return (default 10).",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=run_kb_search,
    ),
    Tool(
        name="get_report_columns",
        description=(
            "Return the exact columns and what each one means for a Choice "
            "report: pnl, tax, ledger, contract-note, or holdings. Call this "
            "whenever the user asks what a report contains, what a column or "
            "field means, or how to read it. Answer ONLY from the result — use "
            "the labels verbatim and never describe report columns from general "
            "knowledge. See the report-columns rule."
        ),
        schema={
            "type": "object",
            "properties": {
                "report": {
                    "type": "string",
                    "enum": [
                        "pnl",
                        "tax",
                        "ledger",
                        "contract-note",
                        "holdings",
                    ],
                    "description": (
                        "Which report's columns to fetch: pnl (P&L), tax "
                        "(capital gains), ledger, contract-note, or holdings."
                    ),
                },
            },
            "required": ["report"],
            "additionalProperties": False,
        },
        handler=run_report_columns,
    ),
    Tool(
        name="raise_support_ticket",
        description=(
            "Raise a real support ticket with Choice's support team, with "
            "this conversation attached. Call this when the user asks for a "
            "human, asks to raise a ticket or complaint, or accepts your "
            "offer to escalate — NEVER preemptively. If an App event earlier "
            "in this conversation already records a ticket for this issue, "
            "reference that ticket instead of calling this again."
        ),
        schema={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": (
                        "Short summary of the user's issue in their own words."
                    ),
                },
            },
            "required": ["reason"],
            "additionalProperties": False,
        },
        handler=run_raise_ticket,
    ),
]


TOOLS: dict[str, Tool] = {tool.name: tool for tool in _TOOL_LIST}


def tool_schemas() -> list[dict]:
    """The Anthropic-facing tool definitions, in stable registry order (the
    order is part of the prompt-cache prefix — never reorder per request)."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.schema,
        }
        for tool in _TOOL_LIST
    ]


# --- dispatch ----------------------------------------------------------------

_UNEXPECTED_FAILURE_MESSAGE = (
    "The tool failed unexpectedly — apologize briefly and suggest trying "
    "again in a moment."
)


@dataclass
class DispatchOutcome:
    """One tool execution, loop-facing.

    `content` is what goes into the tool_result block; `envelope` is the
    parsed success envelope (for artifact events); `error_code` is the
    ToolError code (for AUTH_EXPIRED passthrough)."""

    content: str
    is_error: bool
    duration_ms: int
    envelope: dict | None = None
    error_code: str | None = None


async def dispatch_outcome(
    name: str, tool_input: Any, ctx: ToolCtx
) -> DispatchOutcome:
    """Resolve name → handler(input, ctx); never raises across this boundary."""
    started = time.perf_counter()

    def _ms() -> int:
        return int((time.perf_counter() - started) * 1000)

    tool = TOOLS.get(name)
    if tool is None:
        return DispatchOutcome(
            content=f"unknown tool: {name}", is_error=True, duration_ms=_ms()
        )
    # CHO-241: ticket creation is user-initiated only. Reject a model-emitted
    # raise_support_ticket the user did not ask for (or accept) — the model must
    # offer, not decide. The help-card /api/ticket path bypasses the dispatcher.
    if name == "raise_support_ticket" and not ticket_call_is_user_initiated(
        ctx.thread
    ):
        return DispatchOutcome(
            content=(
                "Do NOT raise a ticket unless the user explicitly asks to escalate "
                "or accepts your offer. Instead ask 'Want me to raise a ticket so "
                "the team can take this up?' and stop."
            ),
            is_error=True,
            duration_ms=_ms(),
        )
    try:
        result = await tool.handler(tool_input, ctx)
    except Exception as exc:  # cores never raise — this is the last-resort net
        logger.warning(
            "agent tool failed tool=%s error=%s", name, type(exc).__name__
        )
        return DispatchOutcome(
            content=_UNEXPECTED_FAILURE_MESSAGE, is_error=True, duration_ms=_ms()
        )
    if isinstance(result, ToolError):
        return DispatchOutcome(
            content=result.message,
            is_error=True,
            duration_ms=_ms(),
            error_code=result.code,
        )
    return DispatchOutcome(
        content=json.dumps(result, sort_keys=True, separators=(",", ":")),
        is_error=False,
        duration_ms=_ms(),
        envelope=result,
    )


async def dispatch(
    name: str, tool_input: Any, ctx: ToolCtx
) -> tuple[str, bool, int]:
    """(content, is_error, duration_ms) — the task-2.2 dispatcher surface."""
    outcome = await dispatch_outcome(name, tool_input, ctx)
    return outcome.content, outcome.is_error, outcome.duration_ms
