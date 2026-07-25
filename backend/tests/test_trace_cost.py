"""Unit tests for estimated trace cost in INR (CHO-275, CHO-278)."""

import pytest

from app.agent import trace_cost


def _llm_span(**meta):
    return [{"type": "llm", "metadata": meta}]


def test_haiku_row_tokens_fx_96_46(monkeypatch):
    monkeypatch.setattr("app.config.trace_cost_usd_to_inr", lambda: 96.46)
    # (120*1 + 18*5) / 1e6 * 96.46 = 0.00021 * 96.46
    cost = trace_cost.cost_inr_from_row(
        model="claude-haiku-4-5",
        input_tokens=120,
        output_tokens=18,
        spans=None,
    )
    assert cost == round(0.00021 * 96.46, 4)


def test_sonnet_with_cache_tokens(monkeypatch):
    monkeypatch.setattr("app.config.trace_cost_usd_to_inr", lambda: 96.46)
    spans = [
        {
            "type": "llm",
            "metadata": {
                "model": "claude-sonnet-4-6",
                "input_tokens": 1_000_000,
                "output_tokens": 0,
                "cache_read_input_tokens": 1_000_000,
                "cache_creation_input_tokens": 1_000_000,
            },
        }
    ]
    # USD: 3 + 0.30 + 3.75 = 7.05 → INR 7.05 * 96.46
    cost = trace_cost.cost_inr_from_spans(spans)
    assert cost == round(7.05 * 96.46, 4)


def test_unknown_model_falls_back_to_sonnet(monkeypatch):
    monkeypatch.setattr("app.config.trace_cost_usd_to_inr", lambda: 100.0)
    # 1M input @ Sonnet $3 → $3 → ₹300
    cost = trace_cost.cost_inr_from_row(
        model="claude-mystery-9",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert cost == 300.0


def test_zero_usage_returns_none():
    assert (
        trace_cost.cost_inr_from_row(
            model="claude-haiku-4-5",
            input_tokens=0,
            output_tokens=0,
            spans=None,
        )
        is None
    )
    assert trace_cost.cost_inr_from_spans([]) is None
    assert trace_cost.cost_inr_from_spans([{"type": "tool"}]) is None


def test_spans_preferred_over_row_totals(monkeypatch):
    monkeypatch.setattr("app.config.trace_cost_usd_to_inr", lambda: 100.0)
    spans = [
        {
            "type": "llm",
            "metadata": {
                "model": "claude-haiku-4-5",
                "input_tokens": 1_000_000,
                "output_tokens": 0,
            },
        }
    ]
    # Span: $1 → ₹100; row tokens would be huge if used
    cost = trace_cost.cost_inr_from_row(
        model="claude-haiku-4-5",
        input_tokens=9_000_000,
        output_tokens=0,
        spans=spans,
    )
    assert cost == 100.0


# --- CHO-278: per-TTL cache-write rates --------------------------------------


@pytest.mark.parametrize("model", ["claude-sonnet-4-6", "claude-haiku-4-5"])
def test_rate_table_ttl_multipliers_are_1_25x_and_2x(model):
    """A 5-minute write bills at 1.25x base input, a 1-hour write at 2x."""
    rates = trace_cost._RATES_USD_PER_MTOK[model]
    assert rates["cache_creation_5m"] == pytest.approx(rates["input"] * 1.25)
    assert rates["cache_creation_1h"] == pytest.approx(rates["input"] * 2.0)


@pytest.mark.parametrize(
    ("model", "usd_5m", "usd_1h"),
    [("claude-sonnet-4-6", 3.75, 6.00), ("claude-haiku-4-5", 1.25, 2.00)],
)
def test_one_hour_write_priced_at_2x_and_five_minute_at_1_25x(
    monkeypatch, model, usd_5m, usd_1h
):
    monkeypatch.setattr("app.config.trace_cost_usd_to_inr", lambda: 100.0)
    # 1M cache-write tokens, all 5-minute. The flat aggregate is the SDK's
    # inclusive sum of the split, so it is present too and must not be charged.
    at_5m = trace_cost.cost_inr_from_spans(
        _llm_span(
            model=model,
            cache_creation_input_tokens=1_000_000,
            cache_creation_5m_input_tokens=1_000_000,
            cache_creation_1h_input_tokens=0,
        )
    )
    assert at_5m == round(usd_5m * 100.0, 4)
    # The same 1M tokens written under a 1-hour TTL costs strictly more.
    at_1h = trace_cost.cost_inr_from_spans(
        _llm_span(
            model=model,
            cache_creation_input_tokens=1_000_000,
            cache_creation_5m_input_tokens=0,
            cache_creation_1h_input_tokens=1_000_000,
        )
    )
    assert at_1h == round(usd_1h * 100.0, 4)
    assert at_1h > at_5m


def test_mixed_ttl_buckets_priced_separately_and_never_double_counted(monkeypatch):
    monkeypatch.setattr("app.config.trace_cost_usd_to_inr", lambda: 100.0)
    # Sonnet: 400k @ 3.75 + 600k @ 6.00 = 1.50 + 3.60 = $5.10.
    # Charging the flat 1M aggregate as well would give $8.85 — the split wins.
    cost = trace_cost.cost_inr_from_spans(
        _llm_span(
            model="claude-sonnet-4-6",
            cache_creation_input_tokens=1_000_000,
            cache_creation_5m_input_tokens=400_000,
            cache_creation_1h_input_tokens=600_000,
        )
    )
    assert cost == round(5.10 * 100.0, 4)


def test_legacy_flat_only_blob_keeps_its_pre_change_figure(monkeypatch):
    """Every agent_traces row written before CHO-278 carries only the flat
    aggregate. It must price at the 5-minute rate and reproduce the old figure
    exactly, so historical dashboard numbers do not move."""
    monkeypatch.setattr("app.config.trace_cost_usd_to_inr", lambda: 96.46)
    # Same span as test_sonnet_with_cache_tokens, i.e. what the pre-change code
    # priced: 3 + 0.30 + 3.75 = $7.05. Literal, not derived from the rate table.
    legacy_span = _llm_span(
        model="claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=0,
        cache_read_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
    )
    assert trace_cost.cost_inr_from_spans(legacy_span) == round(7.05 * 96.46, 4)
    # Haiku legacy: 1 + 0.10 + 1.25 = $2.35
    legacy_haiku = _llm_span(
        model="claude-haiku-4-5",
        input_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
    )
    assert trace_cost.cost_inr_from_spans(legacy_haiku) == round(2.35 * 96.46, 4)
    # And via the usage-blob entry point, with the split keyword absent entirely.
    assert trace_cost.usd_for_usage(
        model="claude-sonnet-4-6", cache_creation_input_tokens=1_000_000
    ) == pytest.approx(3.75)


def test_all_zero_split_falls_back_to_the_flat_aggregate():
    """Defensive: a blob whose split is present but empty while the aggregate is
    not must still bill the aggregate — never silently drop the write."""
    assert trace_cost.usd_for_usage(
        model="claude-sonnet-4-6",
        cache_creation_input_tokens=1_000_000,
        cache_creation_5m_input_tokens=0,
        cache_creation_1h_input_tokens=0,
    ) == pytest.approx(3.75)


def test_split_alone_is_priced_when_the_aggregate_is_missing():
    """Span metadata without the flat key still prices off the split."""
    assert trace_cost.usd_for_usage(
        model="claude-haiku-4-5", cache_creation_1h_input_tokens=1_000_000
    ) == pytest.approx(2.00)


def test_unknown_model_falls_back_to_sonnet_including_the_1h_rate(monkeypatch):
    monkeypatch.setattr("app.config.trace_cost_usd_to_inr", lambda: 100.0)
    # Sonnet 1h = $6/MTok → ₹600; 5m = $3.75/MTok → ₹375
    assert trace_cost.cost_inr_from_spans(
        _llm_span(
            model="claude-mystery-9",
            cache_creation_input_tokens=1_000_000,
            cache_creation_1h_input_tokens=1_000_000,
        )
    ) == 600.0
    assert trace_cost.cost_inr_from_spans(
        _llm_span(
            model="claude-mystery-9",
            cache_creation_input_tokens=1_000_000,
            cache_creation_5m_input_tokens=1_000_000,
        )
    ) == 375.0
    # …and with no model on the span at all.
    assert trace_cost.usd_for_usage(
        model=None, cache_creation_1h_input_tokens=1_000_000
    ) == pytest.approx(6.00)


def test_zero_usage_with_empty_split_is_still_none():
    assert (
        trace_cost.usd_for_usage(
            model="claude-sonnet-4-6",
            cache_creation_input_tokens=0,
            cache_creation_5m_input_tokens=0,
            cache_creation_1h_input_tokens=0,
        )
        is None
    )
    assert trace_cost.cost_inr_from_spans(
        _llm_span(
            model="claude-sonnet-4-6",
            cache_creation_5m_input_tokens=0,
            cache_creation_1h_input_tokens=0,
        )
    ) is None


def test_non_numeric_split_values_are_ignored(monkeypatch):
    """A malformed span must fall back to the aggregate, not crash."""
    monkeypatch.setattr("app.config.trace_cost_usd_to_inr", lambda: 100.0)
    assert trace_cost.cost_inr_from_spans(
        _llm_span(
            model="claude-sonnet-4-6",
            cache_creation_input_tokens=1_000_000,
            cache_creation_5m_input_tokens="lots",
            cache_creation_1h_input_tokens=None,
        ),
    ) == 375.0
