# CHO-244: add-deepeval-tracing-observability — tasks

## 1. Dependency + config

- [ ] 1.1 `uv add deepeval`; commit `pyproject.toml` + `uv.lock`
- [ ] 1.2 `config.py`: `confident_api_key()` (secret, env or repo-root .env), `deepeval_env()`, `deepeval_sampling_rate()`, `tracing_enabled()`
- [ ] 1.3 `.env.example`: document `CONFIDENT_API_KEY` (+ optional `DEEPEVAL_ENV`, `DEEPEVAL_SAMPLING_RATE`, `DEEPEVAL_TRACING`)

## 2. Tracing module (`app/agent/tracing.py`)

- [ ] 2.1 `redact(data)` mask — JWT/PAN/email/phone/opaque-token + denylisted keys, recursive
- [ ] 2.2 `configure()` — idempotent, try/except, gated on `tracing_enabled()`; passes `mask`, `environment`, `sampling_rate`, `confident_api_key`
- [ ] 2.3 `enabled()` guard + pass-through wrappers when disabled
- [ ] 2.4 `observe_turn`, `observe_model_round` (holder), `observe_tool`, `observe_retrieval` — safe-arg wrappers, ctx via closure

## 3. Wire the loop

- [ ] 3.1 `main.py`: call `tracing.configure()` in the lifespan startup
- [ ] 3.2 `loop.py`: root `observe_turn` around `_chat_events`; `update_current_trace(thread_id, user_id, input, output)`
- [ ] 3.3 `loop.py`: `observe_model_round` around the streamed round; loop reads `holder["final"]`
- [ ] 3.4 `loop.py`: `observe_tool` around each `dispatch_outcome` in the gather
- [ ] 3.5 `kb/router.py`: `observe_retrieval` around `hybrid_search`; `retrieval_context` = fused chunks

## 4. Verification

- [ ] 4.1 `test_agent_tracing.py`: `redact` unit tests (JWT/PAN/email/phone/keys); `configure()` no-op when disabled; wrappers pass-through when disabled and preserve return/stream values
- [ ] 4.2 Existing loop/KB tests still green (`uv run pytest`) — SSE output + behavior unchanged
- [ ] 4.3 Live: run backend with a real `CONFIDENT_API_KEY`, drive one multi-turn conversation, confirm the trace tree + thread appear in Confident AI and carry NO PII/secrets

## 5. Ship & sync

- [ ] 5.1 `git-sync` with issue key CHO-244
- [ ] 5.2 `linear-connector` — In Progress at start, summary + In Review at PR, Done at merge
