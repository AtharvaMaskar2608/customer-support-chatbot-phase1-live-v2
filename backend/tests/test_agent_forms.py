"""Unit tests for the open_report_form seed catalog (CHO-214 · task 1.1).

Validate-and-drop semantics (design D3): fields the flow does not declare are
dropped, declared fields with invalid values are dropped, dates survive only
as a valid pair — and a drop is NEVER an error (the widget just asks).
"""

import asyncio
import datetime

import pytest

from app.agent.ctx import ToolError
from app.agent.forms import (
    OpenReportFormParams,
    run_open_report_form,
    validate_seed,
)

TODAY = datetime.date(2026, 7, 19)


def _seed(flow, today=TODAY, **fields):
    params = OpenReportFormParams(flow=flow, **fields)
    return validate_seed(params, today=today)


# --- chips + irrelevant fields ----------------------------------------------


def test_valid_partial_seed_survives():
    seed, dropped = _seed(
        "pnl", segment="Equity", fromDate="2026-06-01", toDate="2026-06-30"
    )
    assert seed == {
        "segment": "Equity",
        "fromDate": "2026-06-01",
        "toDate": "2026-06-30",
    }
    assert dropped == []


def test_invalid_chip_dropped_not_errored():
    seed, dropped = _seed("pnl", segment="Crypto")
    assert seed == {}
    assert dropped == ["segment"]


def test_irrelevant_field_dropped_per_flow():
    # A segment sent for a ledger request is not a ledger field.
    seed, dropped = _seed("ledger", segment="Equity", book="Normal")
    assert seed == {"book": "Normal"}
    assert dropped == ["segment"]


def test_empty_seed_is_valid():
    seed, dropped = _seed("pnl")
    assert seed == {}
    assert dropped == []


# --- dates -------------------------------------------------------------------


def test_three_year_span_dropped():
    seed, _ = _seed("pnl", fromDate="2023-01-01", toDate="2026-01-02")
    assert seed == {}


def test_one_sided_range_dropped():
    seed, dropped = _seed("pnl", segment="F&O", fromDate="2026-06-01")
    assert seed == {"segment": "F&O"}
    assert "fromDate" in dropped


def test_inverted_range_dropped():
    seed, _ = _seed("pnl", fromDate="2026-06-30", toDate="2026-06-01")
    assert seed == {}


def test_pre_2018_dropped():
    seed, _ = _seed("pnl", fromDate="2017-12-31", toDate="2018-01-31")
    assert seed == {}


def test_future_beyond_cap_dropped():
    # P&L allows today+7 (19 Jul → 26 Jul); +8 is out.
    seed, _ = _seed("pnl", fromDate="2026-07-01", toDate="2026-07-26")
    assert seed == {"fromDate": "2026-07-01", "toDate": "2026-07-26"}
    seed, _ = _seed("pnl", fromDate="2026-07-01", toDate="2026-07-27")
    assert seed == {}


def test_contract_notes_zero_lookahead():
    seed, _ = _seed("contract-notes", fromDate="2026-07-01", toDate="2026-07-19")
    assert seed == {"fromDate": "2026-07-01", "toDate": "2026-07-19"}
    seed, _ = _seed("contract-notes", fromDate="2026-07-01", toDate="2026-07-20")
    assert seed == {}


def test_malformed_date_dropped():
    seed, _ = _seed("pnl", fromDate="June 1", toDate="2026-06-30")
    assert seed == {}


# --- fy / format / delivery --------------------------------------------------


def test_fy_within_window_survives():
    seed, _ = _seed("tax", fy="2025-2026", format="PDF")
    assert seed == {"fy": "2025-2026", "format": "PDF"}


def test_fy_outside_window_dropped():
    seed, dropped = _seed("tax", fy="2020-2021")
    assert seed == {}
    assert dropped == ["fy"]


def test_delivery_seeds_where_flow_has_choice():
    seed, _ = _seed("pnl", delivery="email")
    assert seed == {"delivery": "email"}


def test_contract_notes_delivery_never_seeds():
    seed, dropped = _seed("contract-notes", delivery="download")
    assert seed == {}
    assert dropped == ["delivery"]


# --- handler -----------------------------------------------------------------


def test_handler_returns_form_envelope():
    result = asyncio.run(
        run_open_report_form(
            {"flow": "pnl", "segment": "Equity", "segmentX": "junk"}, ctx=None
        )
    )
    assert not isinstance(result, ToolError)
    assert result["kind"] == "form"
    assert result["flow"] == "pnl"
    assert result["seed"] == {"segment": "Equity"}
    assert result["prefilled"] == ["segment"]
    assert "do not ask" in result["note"]


def test_handler_invalid_flow_is_the_only_error():
    result = asyncio.run(run_open_report_form({"flow": "sip"}, ctx=None))
    assert isinstance(result, ToolError)


@pytest.mark.parametrize("flow", ["pnl", "ledger", "tax", "contract-notes"])
def test_handler_empty_open_succeeds_for_every_flow(flow):
    result = asyncio.run(run_open_report_form({"flow": flow}, ctx=None))
    assert not isinstance(result, ToolError)
    assert result["seed"] == {}
