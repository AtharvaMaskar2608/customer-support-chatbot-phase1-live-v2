"""Estimated Anthropic API cost for agent traces (CHO-275).

Pure math: token counts × USD list rates × FX → INR. Not a live billing API.
Rates match Anthropic platform pricing for Sonnet 4.6 / Haiku 4.5 (5-minute
cache writes). Unknown models fall back to Sonnet rates.
"""

from __future__ import annotations

from typing import Any

from app import config

# USD per million tokens (MTok). Cache write = 5-minute ephemeral rate.
_RATES_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    "claude-haiku-4-5": {
        "input": 1.0,
        "output": 5.0,
        "cache_read": 0.10,
        "cache_creation": 1.25,
    },
}


def _rates_for(model: str | None) -> dict[str, float]:
    if model and model in _RATES_USD_PER_MTOK:
        return _RATES_USD_PER_MTOK[model]
    return _RATES_USD_PER_MTOK["claude-sonnet-4-6"]


def _num(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def usd_for_usage(
    *,
    model: str | None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
) -> float | None:
    """USD cost for one LLM usage blob. None when every count is zero."""
    inp = max(input_tokens, 0)
    out = max(output_tokens, 0)
    cread = max(cache_read_input_tokens, 0)
    cwrite = max(cache_creation_input_tokens, 0)
    if inp + out + cread + cwrite == 0:
        return None
    rates = _rates_for(model)
    usd = (
        inp * rates["input"]
        + out * rates["output"]
        + cread * rates["cache_read"]
        + cwrite * rates["cache_creation"]
    ) / 1_000_000.0
    return usd


def inr_from_usd(usd: float | None) -> float | None:
    if usd is None:
        return None
    return round(usd * config.trace_cost_usd_to_inr(), 4)


def cost_inr_from_spans(spans: list | None, *, model: str | None = None) -> float | None:
    """Sum INR cost across LLM spans. Falls back to row-level model when a
    span omits metadata.model."""
    if not spans:
        return None
    total_usd = 0.0
    any_usage = False
    for span in spans:
        if not isinstance(span, dict):
            continue
        if span.get("type") != "llm":
            continue
        meta = span.get("metadata") if isinstance(span.get("metadata"), dict) else {}
        span_model = meta.get("model") if isinstance(meta.get("model"), str) else model
        usd = usd_for_usage(
            model=span_model,
            input_tokens=_num(meta.get("input_tokens")),
            output_tokens=_num(meta.get("output_tokens")),
            cache_read_input_tokens=_num(meta.get("cache_read_input_tokens")),
            cache_creation_input_tokens=_num(meta.get("cache_creation_input_tokens")),
        )
        if usd is not None:
            any_usage = True
            total_usd += usd
    if not any_usage:
        return None
    return inr_from_usd(total_usd)


def cost_inr_from_row(
    *,
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    spans: list | None = None,
) -> float | None:
    """Prefer span-accurate cache split; else row input/output totals."""
    from_spans = cost_inr_from_spans(spans, model=model)
    if from_spans is not None:
        return from_spans
    usd = usd_for_usage(
        model=model,
        input_tokens=_num(input_tokens),
        output_tokens=_num(output_tokens),
    )
    return inr_from_usd(usd)
