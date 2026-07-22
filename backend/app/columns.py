"""Report column registry (CHO-228) — the grounding contract for report
explanations.

Content lives in backend/content/column_registry.json (server-side, remote-
updatable like whats_new.json). It is the ONLY subject matter the agent may use
to explain what a report contains: `get_report_columns` returns a report's
columns plus their locked glosses verbatim, and the CHO-228 prompt rule forbids
the model from enumerating or renaming report columns from general knowledge.
That closes the grounding gap where the bot described P&L columns the report
never had (it bled in tax-report columns like Short Term / Long Term).

No credentials: the registry is static config, identical for every client.
"""

import json
from pathlib import Path
from typing import Any

from app.agent.ctx import ToolCtx, ToolError

CODE_UNKNOWN_REPORT = "UNKNOWN_REPORT"

REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent / "content" / "column_registry.json"
)


def _normalize(label: str) -> str:
    """Matching key for the ambiguity index (light normalization, per the
    grounding contract): drop a trailing "(...)" annotation so a grouped label
    matches its plain sibling across reports ("Net Qty (Qty / Price / Amount)" ~
    "Net Qty"), then lowercase and collapse whitespace. The registry keeps the
    label VERBATIM for display; this key is only for cross-report matching."""
    core = label
    if core.rstrip().endswith(")") and "(" in core:
        core = core[: core.rindex("(")]
    return " ".join(core.lower().split())


def load_registry() -> dict:
    """Read the registry per call so config edits go live without a restart
    (same posture as whats_new.json)."""
    with REGISTRY_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _columns(report: dict) -> list[dict]:
    return report.get("columns") or []


def ambiguity_index(registry: dict) -> dict[str, list[str]]:
    """Normalized label -> sorted report keys it appears in. Labels mapping to
    more than one report are ambiguous and drive disambiguation (a user asking
    "what's Net Qty" must be told which report they mean)."""
    index: dict[str, set[str]] = {}
    for key, report in (registry.get("reports") or {}).items():
        for col in _columns(report):
            index.setdefault(_normalize(col["label"]), set()).add(key)
    return {label: sorted(keys) for label, keys in index.items()}


async def run_report_columns(params: Any, ctx: ToolCtx) -> dict | ToolError:
    """Return the grounded columns + locked glosses for one report (CHO-228).

    The registry is the sole source of truth for report structure — no client
    data, no credentials. Unknown report -> ToolError naming the valid set so
    the model does not invent columns for surfaces the registry does not cover.
    """
    registry = load_registry()
    reports = registry.get("reports") or {}
    report_key = params.get("report") if isinstance(params, dict) else None
    if report_key not in reports:
        valid = ", ".join(sorted(reports))
        return ToolError(
            code=CODE_UNKNOWN_REPORT,
            message=(
                f"No column registry for report '{report_key}'. The registry "
                f"covers only: {valid}. For anything else, do not list columns "
                "— offer to pull the report instead."
            ),
        )
    report = reports[report_key]
    amb = ambiguity_index(registry)
    ambiguous = sorted(
        {
            col["label"]
            for col in _columns(report)
            if len(amb.get(_normalize(col["label"]), [])) > 1
        }
    )
    return {
        "report": report_key,
        "title": report.get("title"),
        "note": report.get("note"),
        "columns": _columns(report),
        "ambiguousLabels": ambiguous,
    }
