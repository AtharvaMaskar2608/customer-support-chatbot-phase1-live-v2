"""Unit tests for estimated trace cost in INR (CHO-275)."""

from app.agent import trace_cost


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
