# CHO-278: trace-cost-ttl-accuracy

## Why

The cost estimator is blind to cache-write TTL. `trace_cost.py:17-22` hardcodes the **5-minute** write rate ($3.75/MTok Sonnet, $1.25 Haiku), and `_usage_dict` (`loop.py:126-141`) reads only the four flat usage keys even though the SDK's `Usage.cache_creation` exposes `ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens` separately. A 1-hour TTL writes at **2×** base, not 1.25× — so the moment anyone sets `"ttl":"1h"` on any breakpoint, every `cost_inr` figure on traces and threads silently under-reports by ~60%, including the per-turn cost gate CHO-264 relies on to prove itself.

Fix the accounting first, then decide the TTL from data instead of opinion: `agent_traces` already carries per-turn timestamps keyed by `thread_id`, so the inter-turn gap distribution is measurable once CHO-264's rolling marker exists.

## What Changes

- **Per-TTL rate table.** `_RATES_USD_PER_MTOK` gains distinct `cache_creation_5m` / `cache_creation_1h` rates per model (Sonnet 3.75 / 6.00; Haiku 1.25 / 2.00 per MTok), replacing the single hardcoded write rate. Unknown models still fall back to Sonnet.
- **Read the SDK split.** `_usage_dict` captures `usage.cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens` alongside the existing flat keys, and `tracing.observe_model_round` records both on the `llm` span metadata.
- **Price each bucket at its own rate**, with a back-compatible fallback: rows written before this change (and any usage blob without the split) keep pricing the flat `cache_creation_input_tokens` at the 5-minute rate, so historical `cost_inr` figures do not move.
- **THEN decide the TTL from measured gaps.** Compute the inter-turn gap distribution from `agent_traces` keyed by `thread_id` (200+ threads, turn index ≥8) together with the median history size `H` and per-turn delta `d`. **Decision rule:** move ONLY the rolling tip marker to `"ttl":"1h"` iff `P(gap > 5 min) > 0.65 · d/H` at turn ≥8. The frozen prefix stays 5m regardless — it is byte-identical across all clients, so concurrent traffic keeps it warm and 1h would just double its write cost.
- **Ship together.** If the rule fires, the TTL move lands in the **same commit** as the rate table and the split capture, so no build ever prices a 1h write at the 5m rate.

## Open decisions

- **Whether the tip marker moves to 1h at all.** Decided by the rule above, not in advance. Crossover is sensitive to history size: 1h wins above a 5.9% slow-turn rate when `H`≈20k but needs 33% when `H`≈3.6k — and CHO-271's curation collapses `H` from ~12.6k to ~3k, which drops the whole stake below ₹0.10 per conversation. If the measurement lands near the boundary, staying at 5m is the correct answer (its miss floor is 1.25× versus 1h's 2.0×).

## Capabilities

### Modified Capabilities

- `observability-dashboard`: estimated INR cost prices cache writes at per-TTL rates (5-minute vs 1-hour) instead of one hardcoded rate, from a usage split captured off the SDK.

## Impact

- Depends on **CHO-264** shipping first: the rolling history marker must exist before there is any cross-turn gap behaviour to measure, and it is CHO-264's own prod cost gate that this change protects.
- Backend: `backend/app/agent/trace_cost.py` (per-TTL rate table + bucket pricing), `backend/app/agent/loop.py` (`_usage_dict` reads `usage.cache_creation`), `backend/app/agent/tracing.py` (`llm` span records the split).
- Tests: `backend/tests/test_trace_cost.py` (per-TTL pricing, legacy rows unchanged, unknown model fallback), `backend/tests/test_agent_tracing.py` / `test_agent_loop.py` (usage split captured from a fake usage object exposing `cache_creation`).
- Analysis (tracked, not scratch): a query/script over `agent_traces` producing the inter-turn gap distribution, median `H` and `d` at turn ≥8, and the rule's verdict — recorded in the Linear comment so the decision is auditable.
- Frontend: none required; `frontend/src/traces/SpanTree.tsx` already renders `cache_creation_input_tokens` and continues to work off the flat total.
- Gates: `uv run pytest` green; a test asserting a 1h write is priced at 2× base and a 5m write at 1.25×; historical `cost_inr` for an existing trace unchanged.
- Deploy: backend-only ⇒ one new `backendvX.Y.Z`; frontend tag untouched.
- Linear: CHO-278 · branch `cho-278-trace-cost-ttl-accuracy`
