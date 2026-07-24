# CHO-275: trace-thread-cost-inr

## Why

Operators reviewing `/traces` see token counts but not spend. They need a
quick INR estimate per turn and per conversation, and those conversation
buckets must reset when Main Menu / `reset_thread` starts a new STM thread
(today traces hash `session_id` and keep rolling up across resets).

## What Changes

- **Read-time INR estimate** on every trace (`cost_inr`) and thread rollup
  (`total_cost_inr`): tokens × Anthropic list USD rates × FX
  (`TRACE_COST_USD_TO_INR`, default **96.46**). No new DB columns; historical
  rows get cost immediately. Span-accurate when `spans` are available (cache
  read/write split); else row `input_tokens`/`output_tokens`.
- **Traces UI** shows “est. ₹…” next to tokens on list + detail for traces
  and threads.
- **Trace `thread_id` = conversation-store `Thread.id`** (bound after
  `store.get_thread`), so a reset starts a new cost bucket. `user_id`
  remains an HMAC of the client code.

## Capabilities

### Modified Capabilities

- `observability-dashboard`: estimated INR cost on API + UI; FX config note.
- `observability-tracing`: persist conversation Thread.id as `thread_id`
  (not hashed session).

## Impact

- Backend: `trace_cost.py`, `traces_router.py`, `tracing.bind_conversation_thread`,
  `loop.py`, `config.trace_cost_usd_to_inr`, `.env.example`.
- Frontend: `src/traces/*` types, `fmtInr`, list/detail chips.
- Out of scope: persisted cost columns, live Anthropic Admin Cost API,
  CHO-273 UI reset / CHO-274 prompt work.
