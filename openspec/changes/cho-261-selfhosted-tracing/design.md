# CHO-261 — design

## Why not a framework

DeepEval's tracing is coupled to Confident AI's exporter (metered, external). Our
needs are: an execution graph per turn, grouped by conversation, queryable, in
our own infra. That's a table + a hand-rolled span tree — no framework required,
and no ~60-package dependency.

## Nesting with contextvars (async- and gather-safe)

DeepEval inferred parent/child from the call stack via contextvars; we do the
same explicitly with two `ContextVar`s:

- `_current_trace` — the active `_Trace` collector for this turn.
- `_current_parent` — the span id new children attach to.

`observe_turn` opens the `agent` root and sets both. `observe_model_round`,
`observe_tool`, `observe_retrieval` read `_current_parent` for their parent, and
`observe_tool` sets `_current_parent` to its own id while running, so a KB search
called inside a tool lands its `retriever` span under that `tool` span.

Parallel tool rounds run in `asyncio.gather`, which wraps each coroutine in a
Task that **copies the current context** — so every gathered tool sees the agent
span as its parent, and its own `_current_parent.set()` is isolated to its task.
The `_Trace` object is shared (single-threaded event loop → appends are atomic
between awaits), so all spans collect into one tree. This was verified live: a
KB turn produced `agent → {llm, tool → retriever, llm}` with correct parents.

## Streaming llm span via a holder

`observe_model_round` is an async generator: it yields text deltas (streamed to
SSE) and stashes the final message in a caller-passed `holder` dict, since a
generator can't `return` it. The span records model + input/output tokens **plus
the prompt-cache split** (`cache_read_input_tokens` / `cache_creation…`), which
matters here given the frozen system + primed prefix.

## Zero response impact

Persistence is fire-and-forget: `observe_turn`'s `finally` calls
`asyncio.create_task(_persist(pool, trace))` *after* the last SSE chunk is
yielded, so the DB write never delays the reply. `await pool.execute` yields the
loop, so it doesn't block other requests either (same model the conversation
store already uses). Tasks are kept in a module set to avoid GC; `_persist` is
fully guarded (logs type only, drops on failure).

## PII / secrets

Kept from CHO-244: span inputs/outputs run through `redact()` (JWT / PAN / email
/ phone / opaque-token + denylisted keys). Thread/user ids are HMAC hashes of the
session id (a live FinX auth token) and client code — so a conversation's turns
group without a raw credential landing in an analytics table.

## Schema

`agent_traces` (one JSONB `spans` column + rollup columns for cheap querying)
created idempotently at startup (`ensure_schema`, guarded; no-op without a pool
or when disabled). Indexed on `(thread_id, created_at DESC)`.

## Config

`AGENT_TRACING` (default on) gates it; `TRACING_SALT` keys the id hashing.
Persistence additionally requires the DB pool at request time — no pool ⇒
pass-through.

## Non-goals

- A read UI / dashboard — a follow-up CHO (served via the existing reverse
  proxy). For now: query `agent_traces` in SQL.
- Eval scoring on traces.
