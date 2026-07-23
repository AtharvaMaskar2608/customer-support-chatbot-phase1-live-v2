# CHO-261: self-hosted-tracing

## Why

CHO-244 added agent tracing that exported to Confident AI via DeepEval. Confident's free credits are exhausted and it's a **metered external cloud**, and we handle financial PII — so an ongoing, egressing dependency is the wrong fit. Replace the external export with **self-hosted tracing persisted to our own Postgres** (the KB / conversation-store DB): each `/api/chat` turn becomes an execution graph stored as one row, queryable in SQL, grouped into multi-turn threads — no external service, no data egress, no cost. This also lets us **drop the `deepeval` dependency** (~60 packages), reversing the backend-image bloat CHO-244 introduced.

## What Changes

- **Persist to Postgres, not Confident.** New `agent_traces` table (one JSONB row per turn: the span tree + rollup columns — thread/user, model, token counts, tool names, error flag, latency, input/output). Created at startup (`ensure_schema`, guarded).
- **Drop DeepEval entirely.** `tracing.py` is rewritten with no framework: parent/child span nesting is tracked with `contextvars` (async- and `asyncio.gather`-safe), so the same agent → llm → tool → retriever tree is assembled by hand. The **public wrapper interface is unchanged** (`observe_turn` / `observe_model_round` / `observe_tool` / `observe_retrieval` / `configure`), so the loop, KB router, and startup barely change.
- **Feature parity + more.** Same spans, thread stitching (hashed session/client), masked inputs, retrieval_context, per-span latency — plus the **prompt-cache token split** (`cache_read` / `cache_creation`) DeepEval's auto-patch dropped.
- **Zero response impact.** The row is written by a **fire-and-forget background task** created after the turn's last SSE chunk — it never blocks the reply; a persist failure is logged and dropped.
- **Config:** `AGENT_TRACING` (default on) replaces `CONFIDENT_API_KEY`; `TRACING_SALT` pseudonymises the thread/user ids. No secret required.

## Capabilities

### Added Capabilities

- `observability-tracing`: self-hosted agent tracing — each turn persisted as an execution graph to our own Postgres, grouped into multi-turn threads, with PII/secret masking and zero impact on the chat path. (Supersedes the CHO-244 Confident AI export.)

## Impact

- Rewritten: `backend/app/agent/tracing.py`, `backend/tests/test_agent_tracing.py`, `backend/tests/conftest.py`.
- Edited: `backend/app/config.py` (AGENT_TRACING / TRACING_SALT; removed the Confident/DeepEval knobs), `backend/app/main.py` (`ensure_schema` at startup), `backend/app/agent/loop.py` (pass `pool`), `.env.example`.
- Dependency: **removed** `deepeval` from `pyproject.toml` + `uv.lock` (smaller backend image again).
- New DB object: `agent_traces` table in the KB/conversation Postgres (idempotent create).
- Verified: full suite (468 passed) + a live KB turn persisted the full nested graph incl. cache tokens.
- Linear: CHO-261 · branch `cho-261-selfhosted-tracing`. Supersedes CHO-244.
- Follow-up (separate CHO): a read UI (trace viewer) served via the existing reverse proxy.
