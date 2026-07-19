# CHO-218 · Freshdesk Escalation — Tasks

## 1. Backend — ticket core

- [x] 1.1 Config getters for FRESHDESK_DOMAIN / FRESHDESK_API_KEY / FRESHDESK_API_ROOT (+ group-id constant with env override) via the `_secret` pattern; never logged
- [x] 1.2 `app/agent/tickets.py`: transcript renderer (user/assistant/flow_event only, metadata block, oldest-first truncation cap, HTML) + `run_raise_ticket(params, ctx)` core building the exact D1 payload and POSTing to Freshdesk (10s timeout; 4xx/5xx/timeout → ToolError UPSTREAM_ERROR); success → `{kind:"ticket", ticketId, status:"Open"}` + flow-event memo append; unit tests incl. transcript-content exclusions and a no-credentials scan of rendered HTML
- [x] 1.3 Registry entry `raise_support_ticket` (schema: reason only) + loop `ticket` artifact kind (artifact-only short-circuit covers it); prompt: when to escalate, never preemptively, never duplicate a remembered ticket; tests with respx-mocked Freshdesk (payload byte-contract, artifact event, resolution reset, error path narrates)
- [x] 1.4 `POST /api/ticket` route (auth validation, optional reason, shared core); tests (400 no creds, success shape, upstream failure)

## 2. Frontend — real ticket cards

- [x] 2.1 Help-card "Raise a ticket" → `/api/ticket` with busy state + graceful failure; delete `makeTicketId`; agent `ticket` artifact renders the same TicketCard; build green

## 3. Verification

- [x] 3.1 Backend 343 passed / 2 skipped, frontend builds green; LIVE: one real ticket #7541521 created via the agent path on a fresh thread (KB answer → "connect me to a person") — fetched back read-only: group 22000168676, status 2, source 7 Chat, type GENERAL QUERY, tags choice-jini/chatbot-testing/lang:en, all five custom fields exact, transcript carries the Client/Jini exchange, zero credential leak; request priority is 2 per the byte-contract test (a Freshdesk instance automation raises it to 4 post-create — instance-side, not ours); ticket flow-event memo confirmed in Postgres; help-card path exercised via the shared-core route tests (no second live ticket)
