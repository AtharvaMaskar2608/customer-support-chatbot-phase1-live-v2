## Context

CHO-286 mirrored `/api/chat` spans to Langfuse with `session.id` = `Thread.id`. Chip/shell REST routes (except a short `raise_ticket` observation and feedback scores) are not mirrored. Analysis that expects tool-like visibility for "Raise a ticket" and other journey actions therefore misses them.

Product identity (confirmed for CHO-288):

| Concept | Value | Role in Langfuse |
|---|---|---|
| FinX SessionId (`X-Session-Id`) | Live credential | Langfuse `session.id` = salted HMAC only (never raw) |
| Conversation Thread.id | uuid4 per conversation | Metadata `thread_id` on every observation |
| Client code (`X-User-Id`) | Internal account id | Langfuse `user.id` raw (CHO-287) |

Main Menu (`reset_thread`) closes the current Thread and opens a new one under the same FinX session — so Langfuse session continues; `thread_id` metadata changes. That is intentional: one FinX login = one Langfuse session; conversations split via `thread_id`.

## Goals / Non-Goals

**Goals:**
- Every in-scope journey API emits a best-effort Langfuse root observation with shared identity + route name + status/error summary (no PII/credential bodies).
- Chat turns keep today's nested LLM/tool/retriever tree; their root identity uses the new session mapping and always includes `thread_id`.
- Ticket raises (chip + agent) continue to expose `ticket_id` on the observation/turn metadata.
- Never degrade request success/latency when Langfuse is down; same redaction mask as today.

**Non-Goals:**
- Persisting every REST call into Postgres `agent_traces` (chat turns remain SoR there).
- Tracing health, admin, or playground.
- Changing Freshdesk / FinX upstream contracts.
- Migrating historical Langfuse sessions keyed by Thread.id.

## Decisions

**1. Generalized `emit_api_observation` (replaces ad-hoc `emit_ticket_observation`).**  
One helper opens a short-lived Langfuse root (`as_type=span`), sets identity (hashed FinX session + raw user id), merges metadata (`thread_id`, `route`, `method`, optional `ticket_id` / `reason` / platform fields), and ends with compact `output` (status code / ok / error_code). Ticket path becomes a caller of this helper with `name=raise_ticket` (or `api.ticket`).

**2. Identity remap in `set_identity` / bind paths.**  
- Langfuse `session.id` ← `_stable_id(finx_session_id)` via a public alias (e.g. `stable_session_id`).  
- Metadata always includes `thread_id` when known.  
- Chat `observe_turn` / `bind_conversation_thread` updated accordingly; feedback score `session_id` fallback uses the hashed FinX session (not Thread.id). Lookup of `lf_trace_id` via Postgres `turn_seq` stays primary.

**3. Instrumentation sites (middleware rejected).**  
Per-route / thin wrapper calls keep never-degrade local and avoid tracing auth failures for out-of-scope noise. In scope:

| Observation name | Route |
|---|---|
| `api.greeting` | `GET /api/greeting` |
| `api.whats_new` | `GET /api/whats-new` |
| `chat_turn` | `POST /api/chat` (existing tree; identity only changes) |
| `api.chat_reset` | `POST /api/chat/reset` (Main Menu) |
| `api.feedback` | `POST /api/feedback` (score stays; add observation) |
| `api.ticket` / `raise_ticket` | `POST /api/ticket` |
| `api.report.pnl` / `ledger` / `tax` | report POSTs |
| `api.report.contract_notes.list` / `.download` | contract-note POSTs |
| `api.report.file` | `GET /api/report/file/{token}` (session/user may be absent — emit with whatever identity is available) |
| `api.data.holdings` / `money` / `brokerage` | data POSTs |

**4. What's New headers are optional.**  
Endpoint remains public. When the shell has a session, frontend forwards `Authorization` / `X-Session-Id` / `X-User-Id` so the observation can join the journey; without them, emit a session-less observation (or skip identity) — still never fail the response.

**5. Dual-path tools stay as-is.**  
When the model calls a tool inside `/api/chat`, the existing `tool` span covers it. When the UI hits the REST route directly, the new API observation covers it. No attempt to nest REST under a prior chat turn (separate HTTP requests).

## Risks / Trade-offs

- **Analysis migration:** dashboards that grouped by Thread.id as Langfuse session must switch to `metadata.thread_id` or accept FinX-session rollups. Document in PR.
- **Feedback join:** session-level score fallback must use hashed FinX session; prefer `lf_trace_id` when present.
- **File download:** often token-only — may lack session headers; best-effort observation without full identity is acceptable.
- **Volume:** more roots per login; keep outputs tiny (no upstream bodies).

## Migration Plan

1. Ship behind existing `LANGFUSE_TRACING` flag (still off by default).
2. Deploy backend (+ frontend what's-new header pass-through).
3. Update analysis queries to group journeys by Langfuse session (hashed FinX) and filter conversations by `metadata.thread_id`.
4. Rollback = set `LANGFUSE_TRACING=0` or revert; Postgres chat traces unchanged.
