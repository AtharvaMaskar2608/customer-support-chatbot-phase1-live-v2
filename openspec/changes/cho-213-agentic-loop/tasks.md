# CHO-213 · Agentic Loop — Tasks

## 1. Shared-core extraction (contract-preserving refactor)

- [x] 1.1 Define `ToolCtx` (session_id, sso_jwt, client_code, http_client, pg_pool, report_files) and a shared `ToolError` result shape mapped from `ResultKind` + validation failures
- [x] 1.2 Extract `run_pnl(params, ctx)` from `app/report.py`; route becomes a thin shell over it
- [x] 1.3 Extract cores for Ledger, Tax, Contract Notes (`app/reports/*`) the same way
- [x] 1.4 Extract cores for Holdings, Pay-in/Pay-out, Brokerage (`app/data/*`)
- [x] 1.5 Extract `run_kb_search(params, ctx)` from `app/kb/` (reuse hybrid_search + embed; preserve degraded FTS-only and unavailable outcomes)
- [x] 1.6 Regression gate: full existing test suite passes with zero test modifications

## 2. Tool registry

- [x] 2.1 Build the registry (`app/agent/tools.py`): name → (JSON schema of user-intent params only, handler); entries for all 8 tools
- [x] 2.2 Dispatcher: resolve name → handler(input, ctx); unknown tool and handler exceptions → `is_error` tool_result; success → normalized envelope; measure duration per call
- [x] 2.3 Unit tests: schema/credential-isolation invariant (no credential fields in any schema), dispatch, error mapping, one-core-two-entry-points equivalence for P&L

## 3. Conversation store

- [x] 3.1 Verify existing empty `threads`/`turns` DDL against design; write migration SQL for deltas + new `prompt_snapshots` table
- [x] 3.2 Turn/thread models + in-memory thread cache keyed by session_id (rehydrate from DB on miss)
- [x] 3.3 Bounded asyncio queue + single writer task (`app/agent/store.py`): FIFO batch inserts via pg_pool, dropped-write counter + length-only logging on full queue/DB down, lifespan startup + drain-before-pool-close shutdown
- [x] 3.4 Prompt snapshot hashing + upsert at startup; threads record the hash
- [x] 3.5 Tests: seq ordering, wire-faithful replay round-trip, degraded mode (fake pool down), restart rehydration losing ≤ one in-flight step

## 4. Agent loop

- [x] 4.1 System prompt + primed first turn: identity, compliance rules (no investment advice, no commitments, jailbreak resistance), tool guidance, slot-filling rules (never invent, bundle questions), few-shot examples, today's date
- [x] 4.2 `POST /api/chat` (`app/agent/router.py`): auth-header validation → ctx; the while-loop on `stop_reason == "tool_use"` with inner-round guard, each round via SDK `messages.stream()` (text deltas forwarded, `get_final_message()` to continue); SSE response (`text`/`tool`/`artifact`/`done`/`error` events); parallel tool_use handling; per-step turn writes (user text, each model message, each tool_result)
- [x] 4.3 Config getters: `CLARIFY_CAP`(2), `TASK_TURN_CAP`(10), `SESSION_TURN_CAP`(20), inner guard(5), `AGENT_MODEL`(claude-haiku-4-5 | claude-sonnet-4-6) + `AGENT_THINKING`(off | minimal) with the per-model thinking mapping (Haiku: budget_tokens 1024; Sonnet 4.6: adaptive + effort low) — env-overridable, read at call time
- [x] 4.4 Cap engine: derive counters from turns (resolution event = assistant turn ending with ≥1 successful tool call); on trip inject escalation-offer instruction into the final model call
- [x] 4.5 SSE event assembly: `text` deltas, `tool` status, `artifact` (fileToken cards, data envelopes) emitted per successful tool, terminal `done` with counters; `MISSING_CREDENTIALS` pre-stream 400, `AGENT_UNAVAILABLE`/`AUTH_EXPIRED` as `error` events post-open; `anthropic` dependency added; wire router into `create_app`
- [x] 4.6 Tests with mocked Anthropic client: loop termination, parallel tools in one result message, is_error bounce on bad params, all three caps (incl. reset-on-resolution and session backstop), credential isolation end-to-end, SSE event sequence (text→artifact→done) + error-event paths, model/thinking config mapping

## 5. Frontend wiring

- [x] 5.1 Composer submits to `/api/chat` with session auth headers; consume SSE (fetch + ReadableStream), render text deltas incrementally into the bot message; typing/progress state before first delta and during `tool` events; verify SSE passes the Vite dev proxy unbuffered
- [x] 5.2 Render artifacts through existing download-card (fileToken) and data-card renderers
- [x] 5.3 Keyword routing demoted to `AGENT_UNAVAILABLE` fallback path (existing behavior preserved for degraded mode)

## 6. Verification & live check

- [x] 6.1 Full backend + frontend test suites green; existing guided flows manually spot-checked unchanged
- [x] 6.2 Live smoke with fresh SSO token: free-text P&L request end-to-end (clarify → tool → download card), a KB question, one cap-trip escalation suggestion; confirm turns + snapshot rows landed in Postgres
- [x] 6.3 Review stored transcripts: wire-faithful blocks, no credentials/raw bodies in `content`/`meta`; token usage recorded in meta
