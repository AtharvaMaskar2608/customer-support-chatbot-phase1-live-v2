# CHO-278: trace-cost-ttl-accuracy — tasks

## 1. Per-TTL cache-write rates

- [x] 1.1 `trace_cost.py:15-28`: replace the single `cache_creation` rate with `cache_creation_5m` / `cache_creation_1h` per model (Sonnet 3.75 / 6.00; Haiku 1.25 / 2.00 USD per MTok); keep the Sonnet fallback for unknown models and update the module docstring (it currently states "Cache write = 5-minute ephemeral rate").
- [x] 1.2 `trace_cost.usd_for_usage`: accept the split (`cache_creation_5m_input_tokens`, `cache_creation_1h_input_tokens`) and price each bucket at its own rate.
- [x] 1.3 Back-compat: when only the flat `cache_creation_input_tokens` is present (every row written before this change), price it at the 5-minute rate so historical `cost_inr` figures do not move. Prefer the split when both are present, and never double-count.
- [x] 1.4 `cost_inr_from_spans`: read the split keys off `span.metadata` with the same precedence.

## 2. Capture the split from the SDK

- [x] 2.1 `loop.py:126-141` `_usage_dict`: read `usage.cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens` (the `anthropic.types.CacheCreation` model) in addition to the four flat keys; tolerate `cache_creation` being absent or a plain dict.
- [x] 2.2 `tracing.py:364-376`: record both split values on the `llm` span metadata beside the existing `cache_read_input_tokens` / `cache_creation_input_tokens`.
- [x] 2.3 Confirm nothing downstream breaks on the extra keys: `turns.meta.usage` consumers, the traces API payloads, and `frontend/src/traces/SpanTree.tsx` (which reads the flat total).

## 3. Tests

- [x] 3.1 `test_trace_cost.py`: a 1h write is priced at 2× base and a 5m write at 1.25× for both models.
- [x] 3.2 `test_trace_cost.py`: a legacy usage blob (flat `cache_creation_input_tokens` only) yields exactly the pre-change INR figure.
- [x] 3.3 `test_trace_cost.py`: unknown model still falls back to Sonnet rates, including the 1h rate.
- [x] 3.4 `test_agent_loop.py` / `test_agent_tracing.py`: a fake usage object exposing `cache_creation` lands both split values in `turns.meta.usage` and on the `llm` span; a usage object without it behaves exactly as today.
- [x] 3.5 Full `uv run pytest` green.

> Implementation notes (sections 1–3, shipped):
> - 3.4 landed entirely in `test_agent_tracing.py` (not `test_agent_loop.py`, which
>   was concurrently owned by another change). `loop._usage_dict` — the function
>   that builds `turns.meta.usage` — is exercised there directly.
> - 2.3 verdict: nothing downstream breaks. `meta` is an opaque `JSONB` blob with
>   no schema/allowlist and no reader in `backend/app`; the traces router has no
>   `response_model` and passes span metadata through verbatim; every token sum is
>   keyed by explicit field name (no generic `usage.items()` anywhere); and
>   `frontend/src/traces/api.ts` types `Span.metadata` as `Record<string, unknown>`,
>   so `SpanTree.tsx` keeps rendering the flat total and simply ignores the new
>   keys. No frontend change required.
> - Sections 4–5 are **gate-blocked, deliberately unticked**: 4.1 needs prod
>   `agent_traces` rows written with CHO-264's rolling cache marker live, which is
>   not deployed yet, so the gap data does not exist. 5.x is conditional on 4.3's
>   verdict. No `"ttl"` key was added anywhere.

## 4. Measure the gap distribution

- [ ] 4.1 Tracked analysis script/query over `agent_traces`: inter-turn gaps keyed by `thread_id` (the conversation thread id bound at `loop.py:258`), over 200+ threads with the CHO-264 marker live.
- [ ] 4.2 From the same data, compute median history size `H` and per-turn delta `d` at turn index ≥8 (derive `H` from `input + cache_read + cache_creation` on the turn's first `llm` span).
- [ ] 4.3 Evaluate the rule: `P(gap > 5 min) > 0.65 · d/H` at turn ≥8. Record the inputs, the verdict, and the sample size in the Linear comment so the decision is auditable.

## 5. Apply the TTL decision (conditional on 4.3)

- [ ] 5.1 If the rule fires: add `"ttl": "1h"` to the **rolling tip marker only** (`store.with_history_breakpoint`), leaving `system`, the primed block, and the insurance marker at 5 minutes.
- [ ] 5.2 Land 5.1 in the same commit as sections 1–2, so no build ever prices a 1h write at the 5m rate.
- [ ] 5.3 Canary after deploy: `cache_read` on the first span of a fresh thread is still ≈6,559 (the 5m frozen entries still read alongside a 1h tip), and `ephemeral_1h_input_tokens` is non-zero on tip writes while `ephemeral_5m_input_tokens` carries the prefix writes.
- [ ] 5.4 If the rule does not fire: record the measured numbers, keep 5 minutes everywhere, and still ship sections 1–3 (the accounting fix stands on its own).

## 6. Ship & sync

- [ ] 6.1 `git-sync` with issue key CHO-278
- [ ] 6.2 `linear-connector` — In Progress at implementation, summary (including the measured gap distribution and the TTL verdict) + In Review at PR, Done at merge
