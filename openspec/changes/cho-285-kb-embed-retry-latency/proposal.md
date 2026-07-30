## Why

A live trace (2026-07-28, query "When does intraday square off happen") showed a single `search_knowledge_base` tool call taking 20.02s end-to-end while the actual vector retrieval inside it (`kb_search`) took 4ms. The gap is `embed_query()` (`backend/app/kb/embed.py`): it retries the OpenAI embeddings call twice, each attempt bounded by the shared client's 10s default timeout (`backend/app/config.py:21-23`, `UPSTREAM_TIMEOUT_SECONDS`) — so one slow/timed-out first attempt plus a full-length second attempt costs up to ~20s, matching the observed duration almost exactly. That's a ~20-second user-visible stall for what the `kb-retrieval` spec already promises should "degrade gracefully" on embedding failure — the promise holds, but the timeline to get there is far too long. This is not the previously-fixed FinX IPv6/AAAA DNS-hang (that fix already applies to this same shared client); it looks like a genuine transient slowdown against `api.openai.com` made worse by retrying at full timeout budget with no backoff/shortening.

## What Changes

- Bound the embedding call's total retry budget to a small fraction of what it costs today, so a single KB search can no longer stall for anywhere near 20s before degrading to FTS-only.
- Give the embedding call its own timeout distinct from `upstream_timeout_seconds()` (which is tuned for FinX upstream calls, a different latency profile) rather than sharing that budget.
- Preserve existing degrade-to-FTS-only behavior on embedding failure (`embed_query` returning `None`) — this change is about bounding *how long* that path takes, not changing whether it happens.
- Make the embedding call's own duration visible in tracing (today only inferable from the gap between the tool-level span and the `kb_search` sub-span), so a future regression here is visible directly instead of requiring manual arithmetic on a trace.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `kb-retrieval`: the "Query embedding at request time" requirement's degrade-gracefully guarantee gets a bounded latency budget — an embedding failure/timeout SHALL be resolved (either succeed or degrade to FTS-only) within a short, explicit ceiling rather than the current ~20s worst case.

## Impact

- `backend/app/kb/embed.py` — `embed_query()`'s retry loop and per-attempt timeout.
- `backend/app/config.py` — a new embedding-specific timeout setting, separate from `upstream_timeout_seconds()`.
- Possibly `backend/app/main.py` if a dedicated client (vs. a per-call timeout override on the shared client) turns out to be the right shape.
- `backend/app/agent/tracing.py` (or wherever tool/sub-span timing is recorded) if embedding duration is added as its own traced span.
- Existing tests: `backend/tests/test_kb_search.py` (retry/timeout behavior coverage).
- No frontend or prompt changes — backend-only, independent of CHO-282/283/284.
