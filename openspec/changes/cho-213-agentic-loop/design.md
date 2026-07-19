# CHO-213 · Agentic Loop — Design

## Context

Backend is a FastAPI proxy where every capability is a self-contained route: three report flows (P&L `app/report.py`, Ledger/Tax/Contract-Notes `app/reports/*`), three data-card flows (`app/data/*`), and KB hybrid retrieval (`app/kb/`, CHO-212). Auth is per-request via headers (`authorization` = SSO JWT, `x-session-id`, `x-user-id`); routing/credential selection lives in `app/finx/routing.py`. The frontend chat shell drives guided flows deterministically; free text has no handler.

We studied `docs/agentic_loop_guide.md` (the Anthropic customer-support cookbook). Its prompt architecture (identity in `system`, bulk instructions + few-shot examples in a primed first user turn, guardrails as prompt sections) is adopted; its control flow is **not** — it handles a single tool round with no `stop_reason` handling, no caps, and no auth context, all of which this design supplies.

Constraints: SSO JWTs expire 8h (live testing needs fresh tokens); upstream business failures are HTTP 200 with `Status: "Fail"` (already normalized by the flow cores); PII must stay field-whitelisted; no investment advice; the KB Postgres is reached over an operator-held SSH tunnel (dev).

## Goals / Non-Goals

**Goals:**
- One `/api/chat` endpoint that turns free text into tool-orchestrated answers over the existing flows + KB.
- Zero behavioral change to existing routes (shared-core refactor is contract-preserving).
- Credential isolation: the model can never influence whose data a tool touches.
- Code-enforced conversation caps with escalation suggestion.
- A conversation store whose rows are lossless, replayable, and export-ready as fine-tuning data (function calling included).

**Non-Goals:**
- Escalation tool (Freshdesk raise-ticket) — later change; this change only *suggests* escalation in text.
- Mid-flow free-text breakout with flow-snapshot handover + slot-picker quick replies (frontend) — later change; the store's `flow_event` kind and prompt design leave room for it.
- Training-export/redaction tooling, model fine-tuning, intent-classifier routing.

## Decisions

### D1. Manual while-loop, not the SDK tool runner
`while stop_reason == "tool_use"` per user message, with an env-configurable inner guard (~5 rounds). Rationale: no beta dependency, trivial control flow, and the caps/persistence hooks live naturally between iterations. Alternative (SDK `tool_runner`) rejected for now — its per-turn hooks would work, but the loop is small and owning it keeps the training-data write points explicit. Multiple `tool_use` blocks in one response are all executed and answered in a single user message; tool failures return `tool_result` with `is_error: true` (never raise through the loop).

### D2. Tools are shared-core Python functions, not HTTP self-calls
Each flow's route body is split: `run_<flow>(params, ctx) -> dict` (validation → upstream mapping → FinxClient → normalized envelope) moves to a core module; the route becomes a thin shell (headers → `ctx`; body → params; envelope → JSONResponse). The registry maps tool name → `(schema, handler)`; dispatch is `TOOLS[name].handler(input, ctx)`. Rationale: no duplicated FinX logic, no localhost round-trips, rich error shapes for the model, and the normalized envelopes give the transcript automatic PII whitelisting. Alternative (loop calls own REST endpoints) rejected: credential re-serialization, 3× latency on multi-tool turns, error shape loss.

### D3. `ctx` object for credentials — never tool parameters
`ToolCtx(session_id, sso_jwt, client_code, http_client, pg_pool, report_files)` built once per `/api/chat` request from authenticated headers. Tool schemas contain only user-intent fields (segment, dates, delivery, query…). This preserves the existing IDOR defense (`extra="ignore"` on request models) structurally: the model has no credential fields to fill.

### D4. Slot filling by prompting, enforced by validation
Schemas mark true requirements `required`; the system prompt (a) forbids inventing values, (b) requires bundling all missing fields into one question, (c) carries today's date for relative-date resolution ("last month" → YYYY-MM-DD). Handlers reuse the existing Pydantic validators; invalid/missing input returns `is_error` tool_result with an actionable message ("fromDate must be YYYY-MM-DD — ask the user"), bouncing the model back into asking. Few-shot examples (cookbook pattern) demonstrate the ask-then-call sequence.

### D5. Caps and task-window semantics — code, not prompt
- *Resolution event*: an assistant turn that ended with ≥1 successful (`is_error: false`) tool call. Resets the per-task counters.
- *Task window*: turns since the last resolution event.
- Counters (derived from in-memory turns each request, never stored): clarifying questions this window (assistant turns with no tool call that end in a question) ≥ **CLARIFY_CAP=2** → stop asking, suggest escalation; user turns this window ≥ **TASK_TURN_CAP=10** → suggest escalation; user turns this session ≥ **SESSION_TURN_CAP=20** (dumb backstop, catches the KB-rephrase loop where each "successful" answer resets the task window) → suggest escalation.
- Trip behavior: inject an instruction into the final model call so the reply offers escalation naturally; thread `status` unchanged until the user accepts (status transitions to `escalated` become meaningful when the ticket tool lands).
- All caps + inner-round guard + model id are `config.py` getters reading env at call time (existing pattern).

### D6. Conversation store — wire-faithful JSONB, training-grade
Tables in the KB Postgres (empty `threads`/`turns` already provisioned; `prompt_snapshots` added):

```
threads:  id, session_id, client_code, status(active|resolved|escalated|expired),
          prompt_hash → prompt_snapshots, created_at, last_active_at
turns:    id, thread_id, seq (strict per-thread order), role(user|assistant),
          kind(user_text|assistant_text|assistant_tool_use|tool_result|flow_event),
          content JSONB  ← exact Anthropic content-block array as sent/received,
          meta JSONB     ← assistant: {model, stop_reason, usage, latency_ms}
                           tool_result: {tool_name, is_error, duration_ms}
                           flow_event: {flow, action, slots},
          created_at
prompt_snapshots: hash PK, system TEXT, tools JSONB
```

Principles: store exactly what went over the wire (lossless ⇒ any training format is a mechanical export; byte-stable replay preserves Anthropic prompt caching); `role` stays faithful (tool_results ride in user-role messages), `kind` disambiguates; a training example is `{system, tools, messages}` so every thread points at its prompt snapshot; thread `status` + derived task windows double as quality labels for filtering demonstrations. Retention: keep everything, redact at export time (export script is a later change).

### D7. Persistence path — bounded queue, single writer, in-memory authoritative
The hot path holds active threads in an in-memory dict keyed by session_id (source of truth; DB read only on cache miss/restart, tolerating loss of the in-flight step). Every step boundary — user text received, each model message (including intermediate tool_use messages), each tool_result — assigns `seq` synchronously and `put_nowait`s the turn onto a bounded `asyncio.Queue` (~1000). **One** long-lived asyncio task (started/drained in `lifespan`, before pool close) consumes FIFO and inserts via the existing `pg_pool`. Rationale: chat never awaits the DB; strict ordering without cross-thread machinery; one place for retries/metrics; a stalled tunnel degrades persistence (log + dropped-write counter on full queue) instead of freezing chat. Alternatives rejected: per-write `asyncio.create_task` (unordered, loses exceptions, GC hazard); inline awaits (a wedged tunnel would hang every conversation); OS thread (needs its own loop/sync driver, buys nothing over an asyncio task).

### D8. Prompt architecture (from the cookbook, adapted)
Short identity in `system` + compliance rules (factual only, no investment advice, no contractual commitments, jailbreak resistance); bulk instructions, tool-usage guidance, few-shot slot-filling examples in a primed first user turn ("Understood"); today's date injected at a stable position. Prompt + tool schemas hashed at startup → `prompt_snapshots` upsert; threads record the hash they ran under.

### D9. `/api/chat` contract — SSE stream (frontend-facing)
Request: free text + the same auth headers the flows already send. Response: `text/event-stream`. Events:
- `text` `{delta}` — assistant text as it generates (forwarded from the SDK stream's text deltas)
- `tool` `{name, status: started|finished, is_error}` — tool-round activity (renders as progress/typing state)
- `artifact` `{kind: file|data, ...envelope}` — emitted the moment a tool succeeds (file cards via existing `fileToken`, data cards via normalized envelopes)
- `done` `{thread: {taskTurns, sessionTurns}}` — terminal event
- `error` `{error: CODE}` — pinned shapes (`MISSING_CREDENTIALS` pre-stream as HTTP 400; `AUTH_EXPIRED` passthrough, `AGENT_UNAVAILABLE` as an SSE event when the stream is already open)

Loop mechanics: each round uses the SDK streaming helper (`client.messages.stream(...)` — the supported form of `stream=True`), forwarding `text_stream` deltas to the SSE response as they arrive, then `get_final_message()` to decide `tool_use` continuation. Only assistant text streams; tool rounds surface as `tool` events, not raw deltas. The store is unaffected (it persists the final wire-faithful content blocks per step, identical to non-streaming).

### D10. Model + thinking are two env knobs
`AGENT_MODEL` ∈ {`claude-haiku-4-5` (default), `claude-sonnet-4-6`}; `AGENT_THINKING` ∈ {`off` (default), `minimal`}. The thinking request-param mapping is per-model, resolved in one config function:
| | `off` | `minimal` |
|---|---|---|
| `claude-haiku-4-5` | omit `thinking` | `{type:"enabled", budget_tokens:1024}` (1024 = API minimum; must be < `max_tokens`) |
| `claude-sonnet-4-6` | omit `thinking` | `{type:"adaptive"}` + `output_config:{effort:"low"}` (`budget_tokens` deprecated on 4.6; `effort` unsupported on Haiku) |

Rationale: the two models straddle the thinking-API generation change, so "minimal" cannot be one literal. The mapping lives in `config.py` so the loop code is model-agnostic; prompt-cache note — switching `AGENT_MODEL` mid-session invalidates the Anthropic prompt cache (model-scoped), acceptable for a config change.

## Risks / Trade-offs

- [Model invents parameter values despite prompt] → `is_error` validation bounce is the hard stop; few-shot examples reduce frequency; monitored via stored transcripts.
- [KB-rephrase loop never trips per-task caps] → 20-message session backstop; real fix is the later escalation tool (model recognizes dissatisfaction).
- [Store DB (tunnel) down] → bounded queue + drop-with-metrics; chat unaffected; thread resumability degraded until DB returns. Production launch requires a managed connection — flagged in proposal.
- [Backend restart loses in-memory tail] → per-step writes cap the loss at one in-flight step; thread rehydrates from DB on next message.
- [Token cost/latency of agent turns] → inner-round guard + concise prompt; SSE streaming hides time-to-full-answer (first tokens render immediately); measure from `meta.usage` before optimizing.
- [SSE through the Vite dev proxy / prod ingress buffers] → verify `text/event-stream` passes unbuffered in both (disable proxy buffering if needed); fall back is chunked flushing.
- [Refactor regressions in existing flows] → cores extracted verbatim; existing route tests must pass unchanged (the contract-preservation gate).
- [Prompt cache misses from unstable serialization] → transcript replayed from stored JSONB byte-identically; prompt content frozen per snapshot hash.

## Migration Plan

1. Ship refactor (cores + unchanged routes) first — green tests prove contract preservation.
2. Add store tables (`prompt_snapshots`; confirm `threads`/`turns` DDL matches design, migrate if not) — additive.
3. Ship `/api/chat` + registry + writer behind the frontend wiring; widget change is last.
Rollback: remove frontend wiring (guided flows never depended on the agent); tables are additive and inert.

## Open Questions

- Exact DDL of the pre-existing empty `threads`/`turns` tables vs. this design (verify at implementation; migrate if they diverge).
- Whether Holdings' large payloads need truncation/summarization before entering the transcript as tool_results (measure token sizes during implementation).
