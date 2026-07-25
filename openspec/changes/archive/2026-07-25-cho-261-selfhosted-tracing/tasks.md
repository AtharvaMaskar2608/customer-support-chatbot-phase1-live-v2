# CHO-261: self-hosted-tracing — tasks

## 1. Rewrite the tracer (Postgres, no framework)

- [x] 1.1 `tracing.py`: contextvar-based `_Trace`/`_Span` model + parent/child nesting
- [x] 1.2 Keep `redact()` mask + `_stable_id()` (now keyed by `TRACING_SALT`)
- [x] 1.3 `observe_turn/model_round/tool/retrieval` build spans; pass-through when off / no pool / no active trace
- [x] 1.4 llm span records model + tokens + the prompt-cache split
- [x] 1.5 `ensure_schema` (agent_traces) + fire-and-forget `_persist` (guarded)

## 2. Config + wiring + drop DeepEval

- [x] 2.1 `config.py`: `tracing_enabled()` (AGENT_TRACING, default on) + `tracing_salt()`; remove Confident/DeepEval knobs
- [x] 2.2 `main.py`: `configure()` + `ensure_schema(pool)` at startup
- [x] 2.3 `loop.py`: pass `pool=ctx.pg_pool` to `observe_turn`
- [x] 2.4 `.env.example`: AGENT_TRACING / TRACING_SALT (drop CONFIDENT_API_KEY)
- [x] 2.5 `uv remove deepeval` (pyproject + uv.lock)

## 3. Verification

- [x] 3.1 `tests/test_agent_tracing.py` rewritten: mask, hashed ids, gating, full nested tree + persist via a fake pool, schema
- [x] 3.2 Full suite green (`uv run pytest`) — 468 passed, 2 skipped
- [x] 3.3 Live: a KB turn persisted the full `agent → llm → tool → retriever` graph to `agent_traces` (incl. cache tokens), thread/user hashed

## 4. Ship & sync

- [ ] 4.1 `git-sync` with issue key CHO-261
- [ ] 4.2 `linear-connector` — In Progress at start, summary + In Review at PR, Done at merge
