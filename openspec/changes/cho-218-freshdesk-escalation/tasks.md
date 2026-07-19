# CHO-218 · Freshdesk Escalation — Tasks

## 1. Backend — ticket core

- [ ] 1.1 Config getters for FRESHDESK_DOMAIN / FRESHDESK_API_KEY / FRESHDESK_API_ROOT (+ group-id constant with env override) via the `_secret` pattern; never logged
- [ ] 1.2 `app/agent/tickets.py`: transcript renderer (user/assistant/flow_event only, metadata block, oldest-first truncation cap, HTML) + `run_raise_ticket(params, ctx)` core building the exact D1 payload and POSTing to Freshdesk (10s timeout; 4xx/5xx/timeout → ToolError UPSTREAM_ERROR); success → `{kind:"ticket", ticketId, status:"Open"}` + flow-event memo append; unit tests incl. transcript-content exclusions and a no-credentials scan of rendered HTML
- [ ] 1.3 Registry entry `raise_support_ticket` (schema: reason only) + loop `ticket` artifact kind (artifact-only short-circuit covers it); prompt: when to escalate, never preemptively, never duplicate a remembered ticket; tests with respx-mocked Freshdesk (payload byte-contract, artifact event, resolution reset, error path narrates)
- [ ] 1.4 `POST /api/ticket` route (auth validation, optional reason, shared core); tests (400 no creds, success shape, upstream failure)

## 2. Frontend — real ticket cards

- [ ] 2.1 Help-card "Raise a ticket" → `/api/ticket` with busy state + graceful failure; delete `makeTicketId`; agent `ticket` artifact renders the same TicketCard; build green

## 3. Verification

- [ ] 3.1 Backend + frontend suites green; live: exactly ONE real test ticket into chatbot-testing (agent path, real conversation transcript), fetched back read-only and checked against the D1 contract (fields, tags, transcript, no credentials); ticket id noted in the PR; flow-event memo confirmed in Postgres; help-card path exercised against the mocked... real endpoint with the same core (no second live ticket)
