## 1. Identity + helper

- [x] 1.1 Expose `stable_session_id(finx_session_id)` (HMAC via existing `_stable_id`) and document that Langfuse `session.id` uses it
- [x] 1.2 Remap chat-turn identity: Langfuse `session.id` = hashed FinX SessionId; always stamp metadata `thread_id` = Thread.id; keep `user.id` = raw client code
- [x] 1.3 Generalize `emit_ticket_observation` → `emit_api_observation(name, *, session_id_finx, user_id, thread_id, metadata, output)` (ticket becomes a caller)
- [x] 1.4 Update feedback score session fallback to hashed FinX session (prefer `lf_trace_id` join still)

## 2. Instrument journey routes

- [x] 2.1 `POST /api/ticket`, `POST /api/feedback`, `POST /api/chat/reset` — emit API observations (+ ticket_id on ticket)
- [x] 2.2 `GET /api/greeting`, `GET /api/whats-new` — emit; what's-new identity optional
- [x] 2.3 Report routes (pnl/ledger/tax + contract-notes list/download + file download) — emit
- [x] 2.4 Data routes (holdings/money/brokerage) — emit

## 3. Frontend what's-new

- [x] 3.1 When session credentials exist, forward auth/session/user headers on `GET /api/whats-new` (endpoint remains public without them)

## 4. Tests + verify

- [x] 4.1 Unit tests: hashed session identity, `thread_id` metadata, ticket observation, reset observation, never-degrade when mirror raises
- [x] 4.2 Update CHO-286 tests that asserted Langfuse `session.id` == Thread.id
- [x] 4.3 `uv run pytest` for affected suites; frontend lint if what's-new touched
