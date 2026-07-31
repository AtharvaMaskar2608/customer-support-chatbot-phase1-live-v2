## Why

Langfuse today mostly mirrors the `/api/chat` LLM/tool span tree. Chip-driven and shell API calls that make up the rest of a user's journey (greeting, reports/data cards, contract notes, raise-ticket, what's-new, Main Menu) are invisible or only partially covered — so session analysis cannot reconstruct what the user actually did. We need journey-level tracing: every user-facing API observation plus the existing LLM tree, grouped under one FinX login.

## What Changes

- **BREAKING (Langfuse identity):** Langfuse `session.id` becomes a salted HMAC of the FinX `SessionId` (not `Thread.id`). Our conversation `Thread.id` rides as metadata `thread_id` on every observation. `user.id` stays raw client code (CHO-287).
- Emit a best-effort Langfuse observation for every in-scope journey API (not only chat turns), with shared identity + route metadata.
- Keep existing LLM/`tool`/`retriever` nesting under `chat_turn`; unify help-card `/api/ticket` under the same journey helper (still stamps `ticket_id`).
- Trace Main Menu (`POST /api/chat/reset`) and What's New (`GET /api/whats-new`, with optional session headers from the frontend when available).
- Out of scope: `/api/health`, admin traces/threads, playground. Postgres `agent_traces` remains chat-turn SoR (no requirement to persist every REST call there).

## Capabilities

### New Capabilities
- `journey-api-tracing`: Langfuse observations for every in-scope user-journey HTTP API, with FinX-session-hashed Langfuse session identity and `thread_id` metadata.

### Modified Capabilities
- `trace-mirror`: identity mapping — Langfuse `session.id` = hashed FinX SessionId; `thread_id` metadata = conversation Thread.id; Main Menu no longer implies a new Langfuse session (new Thread.id appears in metadata instead).

## Impact

- Backend: `langfuse_mirror.py`, `tracing.py`, `router.py` (chat/ticket/feedback/reset), greeting, whats-new, report/data routers, contract-notes, report file download (best-effort).
- Frontend: What's New fetch may forward auth/session headers when a session exists (endpoint stays usable without them).
- Tests for identity remap, journey helper, and representative route instrumentation.
- Existing Langfuse sessions keyed by Thread.id will not join to new hashed-session traces — operators filter by `thread_id` metadata / client code after deploy.
