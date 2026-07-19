"""`open_report_form` — the form-handover tool core (CHO-214 · tasks 1.1/1.2).

Design D3: the model calls this whenever a report request has missing
parameters. The handler keeps only the fields the named flow declares,
validates each kept value against the flow's canonical options and date
constraints, and SILENTLY DROPS anything invalid — a dropped value simply
means the widget asks for it. The surviving seed rides back in a `form`
envelope; the loop turns it into the `flow` SSE artifact and the frontend
boots the guided FlowCard via `startRun(descriptor, seed)`.

The catalogs below mirror the frontend flow descriptors
(`frontend/src/flow/flows/*.ts`) — chip labels exactly as the UI presents
them, date constraints per descriptor. The frontend re-validates against the
live descriptors, so drift here can only ever produce an unseeded slot,
never a mis-filled form.
"""

import datetime
import re

from pydantic import BaseModel, ConfigDict, field_validator

from app.agent.ctx import ToolCtx, ToolError, parse_params

FLOW_KEYS = ("pnl", "ledger", "tax", "contract-notes")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Per-flow chip fields → canonical values (frontend ChipOption.value).
_CHIP_FIELDS: dict[str, dict[str, tuple[str, ...]]] = {
    "pnl": {"segment": ("Equity", "F&O", "Commodity")},
    "ledger": {"book": ("Normal", "MTF")},
    "tax": {"format": ("PDF", "Excel")},
    "contract-notes": {},
}

# Per-flow date constraints, mirroring the descriptors' DateConstraints.
# (min_date, future_days_cap, max_range_years | None); None = no date slot.
_DATE_RULES: dict[str, tuple[str, int, int | None] | None] = {
    "pnl": ("2018-01-01", 7, 2),
    "ledger": ("2018-01-01", 7, 2),
    "tax": None,
    "contract-notes": ("2018-01-01", 0, None),
}

# Delivery is seedable where the flow has a delivery choice; contract notes
# download per tapped note (no delivery step to seed).
_DELIVERY_FLOWS = frozenset({"pnl", "ledger", "tax"})


class OpenReportFormParams(BaseModel):
    """User-intent fields only; unknown extras are ignored (never errors)."""

    model_config = ConfigDict(extra="ignore")

    flow: str
    segment: str | None = None
    book: str | None = None
    fy: str | None = None
    format: str | None = None
    fromDate: str | None = None
    toDate: str | None = None
    delivery: str | None = None

    @field_validator("flow")
    @classmethod
    def _valid_flow(cls, v: str) -> str:
        if v not in FLOW_KEYS:
            raise ValueError(
                "flow must be one of pnl, ledger, tax, contract-notes"
            )
        return v


def _parse_date(value: str) -> datetime.date | None:
    if not _DATE_RE.match(value):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _fy_values(today: datetime.date) -> tuple[str, ...]:
    """The selectable financial years: current Indian FY + previous two —
    the same dynamic window the tax descriptor computes client-side."""
    start_year = today.year if today.month >= 4 else today.year - 1
    return tuple(f"{start_year - back}-{start_year - back + 1}" for back in (0, 1, 2))


def _validate_dates(
    flow: str, from_raw: str | None, to_raw: str | None, today: datetime.date
) -> dict[str, str]:
    """Both-or-neither; returns {} unless the pair passes the flow's rules."""
    rules = _DATE_RULES[flow]
    if rules is None or from_raw is None or to_raw is None:
        return {}
    min_iso, future_cap, max_years = rules
    from_date, to_date = _parse_date(from_raw), _parse_date(to_raw)
    if from_date is None or to_date is None or from_date > to_date:
        return {}
    if from_date < datetime.date.fromisoformat(min_iso):
        return {}
    if to_date > today + datetime.timedelta(days=future_cap):
        return {}
    if max_years is not None:
        try:
            limit = from_date.replace(year=from_date.year + max_years)
        except ValueError:  # Feb 29 anchor
            limit = from_date.replace(year=from_date.year + max_years, day=28)
        if to_date > limit:
            return {}
    return {"fromDate": from_raw, "toDate": to_raw}


def validate_seed(
    params: OpenReportFormParams, today: datetime.date | None = None
) -> tuple[dict[str, str], list[str]]:
    """(surviving seed, dropped field names) per design D3 — fields the flow
    does not declare are dropped, declared fields with invalid values are
    dropped, and dates survive only as a valid pair."""
    today = today or datetime.date.today()
    flow = params.flow
    provided = {
        key: value
        for key, value in params.model_dump(exclude={"flow"}).items()
        if value is not None
    }
    seed: dict[str, str] = {}

    for field, allowed in _CHIP_FIELDS[flow].items():
        if field in provided and provided[field] in allowed:
            seed[field] = provided[field]

    if flow == "tax" and provided.get("fy") in _fy_values(today):
        seed["fy"] = provided["fy"]

    seed.update(
        _validate_dates(flow, provided.get("fromDate"), provided.get("toDate"), today)
    )

    if flow in _DELIVERY_FLOWS and provided.get("delivery") in ("download", "email"):
        seed["delivery"] = provided["delivery"]

    dropped = sorted(set(provided) - set(seed))
    return seed, dropped


_HANDOFF_NOTE = (
    "The guided form is now open in the chat; the user will fill the "
    "remaining fields and submit it there. Reply with ONE short line handing "
    "off to the form — do not ask for any values and do not list what is "
    "missing."
)


async def run_open_report_form(
    params: OpenReportFormParams | dict, ctx: ToolCtx
) -> dict | ToolError:
    """Form-handover core. Never raises; an invalid flow key is the only
    error (the model must fix it) — invalid seed values are dropped."""
    params = parse_params(OpenReportFormParams, params)
    if isinstance(params, ToolError):
        return params
    seed, dropped = validate_seed(params)
    return {
        "kind": "form",
        "flow": params.flow,
        "seed": seed,
        "prefilled": sorted(seed),
        "dropped": dropped,
        "note": _HANDOFF_NOTE,
    }
