## 1. Config + mirror helpers

- [x] 1.1 `config.bot_version()` from `BOT_VERSION` (optional); document in `.env.example`; set on `docker-compose.yml` backend service to the image tag.
- [x] 1.2 `langfuse_mirror`: accept metadata/version on `start_root`; add `set_metadata`, `trace_id`, `create_feedback_score` (BOOLEAN user-feedback); keep never-degrade guards.

## 2. Tracing + loop

- [x] 2.1 `_Trace` context bag + `bind_turn_context` / `bind_ticket_id` / `bind_turn_seq`; stamp on root metadata + Langfuse at end (incl. `latency_ms`, `lf_trace_id`).
- [x] 2.2 `observe_turn` accepts platform / screen_name / frontend_version; backend version from config.
- [x] 2.3 `loop.py`: bind ticket_id after successful `raise_support_ticket`; bind turn_seq before each `done` emit.

## 3. Router + frontend intake

- [x] 3.1 Read `X-Platform`, `X-Screen-Name`, `X-Frontend-Version` on chat/feedback/ticket; put on `ToolCtx` / `observe_turn`.
- [x] 3.2 `/api/feedback`: after store write, best-effort Langfuse score via turn_seq→lf_trace_id lookup (session fallback).
- [x] 3.3 `/api/ticket`: best-effort short Langfuse `raise_ticket` observation with ticket_id + session identity.
- [x] 3.4 Frontend `authHeaders` (agent + shared call sites as needed) forward platform, screenName, optional VITE_APP_VERSION.

## 4. Tests

- [x] 4.1 Root metadata includes context fields when provided.
- [x] 4.2 Ticket bind lands on root; feedback score called with trace id when joinable / session fallback otherwise.
- [x] 4.3 Mirror-off and raising score path never degrade chat/feedback HTTP.
