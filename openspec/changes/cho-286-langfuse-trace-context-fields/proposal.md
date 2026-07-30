## Why

CHO-286 shipped the Langfuse mirror of the existing Postgres span tree, but the original wishlist still had gaps: platform, entry point, bot versions, ticket ID on the thread, and thumbs feedback were never instrumented. Operators opening Langfuse today can see the execution graph, not *where* the turn came from, *which* bot build produced it, whether a ticket was raised, or how the user rated the answer.

## What Changes

- Forward `platform` and `screenName` (entry point) from the FinX/widget handoff through request headers into each turn's root span metadata (Postgres + Langfuse).
- Stamp `backend_version` (env `BOT_VERSION`) and optional `frontend_version` on every turn root.
- When a support ticket is raised (agent tool or `/api/ticket`), attach `ticket_id` to the active Langfuse session/trace metadata.
- On `/api/feedback`, create a Langfuse score (`user-feedback`) joined to the matching turn via `turn_seq` / Langfuse `trace_id` stored on the root metadata.
- Make turn-wise latency explicit on the root metadata (`latency_ms`) when the root closes.
- Out of scope: raw client code in traces (CHO-287).

## Capabilities

### New Capabilities
- `trace-context-fields`: request/context fields (platform, entry point, bot versions, ticket id, turn seq, latency) and feedback scores on the Langfuse mirror (and the matching Postgres root metadata).

### Modified Capabilities
- `trace-mirror`: root spans carry the context metadata above; feedback becomes a best-effort Langfuse score without changing the never-degrade guarantee.

## Impact

- Frontend `authHeaders` / session handoff — send `X-Platform`, `X-Screen-Name`, `X-Frontend-Version`.
- Backend `router.py`, `ctx.py`, `loop.py`, `tracing.py`, `langfuse_mirror.py`, `config.py`.
- `.env.example` + `docker-compose.yml` — `BOT_VERSION`.
- Tests for mirror metadata, feedback scoring, and header intake.
