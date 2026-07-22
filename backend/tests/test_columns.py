"""CHO-228 — report column registry, the grounding contract for report
explanations (app/columns.py + content/column_registry.json)."""

import asyncio

from app import columns
from app.agent.ctx import ToolError

REPORT_KEYS = {"pnl", "tax", "ledger", "contract-note", "holdings"}


def _get(report: str):
    return asyncio.run(columns.run_report_columns({"report": report}, None))


def test_registry_loads_with_all_report_keys():
    reg = columns.load_registry()
    assert set(reg["reports"]) == REPORT_KEYS


def test_every_column_has_a_verbatim_label_and_a_gloss():
    reg = columns.load_registry()
    for key, report in reg["reports"].items():
        cols = report["columns"]
        assert cols, f"{key} has no columns"
        for col in cols:
            assert col["label"].strip(), f"{key} has an empty label"
            assert col["meaning"].strip(), f"{key}:{col['label']} missing gloss"


def test_pnl_columns_are_the_real_ones_not_the_hallucinated_set():
    # The bug: the bot said the P&L report has Short-term / Long-term / Trading
    # P&L / Charges columns. It has none of those.
    result = _get("pnl")
    labels = [c["label"] for c in result["columns"]]
    assert labels == [
        "Security",
        "Open (Qty / Price / Amount)",
        "Buy (Qty / Price)",
        "Sell (Qty / Price)",
        "Net Qty (Qty / Price / Amount)",
        "CL. Price",
        "Realized P&L",
        "Unrealized P&L",
    ]
    joined = " ".join(labels).lower()
    for hallucinated in ("short term", "long term", "trading", "charge"):
        assert hallucinated not in joined
    # Short Term / Long Term actually live in the TAX report — the mixup's source.
    tax_labels = {c["label"] for c in _get("tax")["columns"]}
    assert {"Short Term", "Long Term"} <= tax_labels


def test_unknown_report_is_a_toolerror_naming_the_valid_set():
    result = _get("brokerage")
    assert isinstance(result, ToolError)
    assert "pnl" in result.message and "holdings" in result.message


def test_ambiguity_index_matches_grouped_labels_across_reports():
    idx = columns.ambiguity_index(columns.load_registry())
    # "Net Qty" is grouped in P&L, plain in Tax / Contract Note — one key.
    assert set(idx["net qty"]) == {"pnl", "tax", "contract-note"}
    assert set(idx["isin"]) == {"tax", "contract-note"}


def test_result_flags_ambiguous_labels_for_the_report():
    result = _get("pnl")
    assert "Net Qty (Qty / Price / Amount)" in result["ambiguousLabels"]
    # A P&L-only label is not flagged.
    assert "CL. Price" not in result["ambiguousLabels"]
