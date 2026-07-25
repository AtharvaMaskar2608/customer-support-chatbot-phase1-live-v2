"""Estimated Anthropic API cost for agent traces (CHO-275, CHO-278).

Pure math: token counts × USD list rates × FX → INR. Not a live billing API.
Rates match Anthropic platform pricing for Sonnet 4.6 / Haiku 4.5. Unknown
models fall back to Sonnet rates.

Cache **writes** are priced per TTL (CHO-278): a 5-minute ephemeral write bills
at 1.25× base input, a 1-hour write at 2×. The per-TTL token split is captured
off the SDK usage object (``cache_creation.ephemeral_{5m,1h}_input_tokens``), so
the estimate never infers a TTL. When only the inclusive aggregate
``cache_creation_input_tokens`` is available — every row written before CHO-278
captured the split — it is priced at the 5-minute rate, keeping historical
figures byte-for-byte unchanged.
"""

from __future__ import annotations

from typing import Any

from app import config

# USD per million tokens (MTok).
_RATES_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_creation_5m": 3.75,
        "cache_creation_1h": 6.00,
    },
    "claude-haiku-4-5": {
        "input": 1.0,
        "output": 5.0,
        "cache_read": 0.10,
        "cache_creation_5m": 1.25,
        "cache_creation_1h": 2.00,
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


def _opt_num(value: Any) -> int | None:
    """Like ``_num`` but keeps "absent" distinguishable from zero — the per-TTL
    split has to be missing, not 0, for the legacy flat fallback to kick in."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _cache_write_buckets(
    *,
    cache_creation_input_tokens: int,
    cache_creation_5m_input_tokens: int | None,
    cache_creation_1h_input_tokens: int | None,
) -> tuple[int, int]:
    """Resolve cache-write tokens into (5m, 1h) buckets.

    Precedence is explicit and never double-counts: the SDK's flat
    ``cache_creation_input_tokens`` is the *inclusive sum* of the per-TTL split,
    so exactly one of the two is charged.

    * split present and non-zero → charge the split, ignore the flat total
    * otherwise                  → charge the flat total at the 5-minute rate
      (legacy rows, and any usage blob the SDK wrote without ``cache_creation``)
    """
    split_5m = max(cache_creation_5m_input_tokens or 0, 0)
    split_1h = max(cache_creation_1h_input_tokens or 0, 0)
    if split_5m + split_1h > 0:
        return split_5m, split_1h
    return max(cache_creation_input_tokens, 0), 0


def usd_for_usage(
    *,
    model: str | None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    cache_creation_5m_input_tokens: int | None = None,
    cache_creation_1h_input_tokens: int | None = None,
) -> float | None:
    """USD cost for one LLM usage blob. None when every count is zero.

    Cache writes are priced per TTL; see ``_cache_write_buckets`` for how the
    split and the legacy aggregate are reconciled.
    """
    inp = max(input_tokens, 0)
    out = max(output_tokens, 0)
    cread = max(cache_read_input_tokens, 0)
    write_5m, write_1h = _cache_write_buckets(
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_creation_5m_input_tokens=cache_creation_5m_input_tokens,
        cache_creation_1h_input_tokens=cache_creation_1h_input_tokens,
    )
    if inp + out + cread + write_5m + write_1h == 0:
        return None
    rates = _rates_for(model)
    usd = (
        inp * rates["input"]
        + out * rates["output"]
        + cread * rates["cache_read"]
        + write_5m * rates["cache_creation_5m"]
        + write_1h * rates["cache_creation_1h"]
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
            # CHO-278: the per-TTL split when the span recorded it; absent (not
            # zero) on every span written before it was captured, which falls
            # the aggregate above back to the 5-minute rate.
            cache_creation_5m_input_tokens=_opt_num(
                meta.get("cache_creation_5m_input_tokens")
            ),
            cache_creation_1h_input_tokens=_opt_num(
                meta.get("cache_creation_1h_input_tokens")
            ),
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
