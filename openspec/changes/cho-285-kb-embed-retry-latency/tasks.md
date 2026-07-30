## 1. Investigate the healthy-path baseline

- [ ] 1.1 Sample recent traces (or run manual test queries) to measure typical successful `embed_query` latency against `api.openai.com`, to ground the new timeout value in real data rather than a guess.

## 2. Config

- [x] 2.1 Add a dedicated embedding-call timeout setting to `backend/app/config.py` (e.g. `kb_embed_timeout_seconds()`, env `KB_EMBED_TIMEOUT_SECONDS`), independent of `upstream_timeout_seconds()`, with a sensible default requiring no `.env` changes to deploy.

## 3. Bound embed_query's retry latency

- [x] 3.1 In `backend/app/kb/embed.py`, override the per-request `timeout=` on the `http.post(...)` call to the OpenAI embeddings endpoint using the new dedicated timeout instead of inheriting the shared client's `upstream_timeout_seconds()`.
- [x] 3.2 Keep the existing two-attempt retry loop structure, verifying the worst-case total (both attempts at the new timeout) lands in the single-digit-second range instead of ~20s.
- [x] 3.3 Confirm the existing degrade-to-FTS-only behavior (`embed_query` returning `None` on failure, `router.py`'s handling of that) is unchanged.

## 4. Trace visibility

- [x] 4.1 Add a tracing span around the `embed_query()` call in `backend/app/kb/router.py`, mirroring `tracing.observe_retrieval`'s existing pattern (nested under the same `tool` parent span as the `retriever` span), so embedding duration is directly visible rather than inferred from a gap.
- [x] 4.2 Verify the new span doesn't break any existing assumptions in `backend/evals/` or the observability dashboard about span shape/count under a `tool` span.

## 5. Tests

- [x] 5.1 Update/extend `backend/tests/test_kb_search.py` to cover: a slow/timing-out first embedding attempt still completes (via retry or degrade) within the new bounded ceiling; the FTS-only degrade path is unchanged on embedding failure; the new tracing span appears with the expected duration when tracing is enabled.

## 6. Verify

- [x] 6.1 Run the backend test suite (`uv run pytest`) and confirm no regressions.
- [ ] 6.2 If feasible, manually reproduce a slow-embedding scenario (e.g. temporarily point at an unreachable host or inject latency) to confirm the end-to-end KB search now degrades within the new bounded ceiling instead of ~20s.
