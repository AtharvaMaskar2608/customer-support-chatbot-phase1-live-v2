# CHO-218 · Freshdesk Escalation

## Why

Since CHO-213 the bot can only *suggest* a human; the help card's "Raise a ticket" produces a fake id. This change makes escalation real: a Freshdesk ticket in the existing **chatbot-testing** group, carrying the full conversation, using byte-for-byte the parameter set the prototype tickets already established (verified by fetching live tickets #7539459/#7529083 read-only) — so tickets land where the support workflow already expects them, tagged and typed identically.

## What Changes

- **One ticket core, two entry points**: a shared `create_ticket(ctx, reason)` core called by (1) a new `raise_support_ticket` agent tool — the model calls it when the user asks for a human or accepts the escalation offer, with `reason` as its only user-intent param — and (2) the help card's "Raise a ticket" button via a new `POST /api/ticket` endpoint (same auth headers; the stub `makeTicketId` dies).
- **Cloned parameter set** (the "same in every ticket" contract, from the live prototype tickets): subject `[Choice Jini] <reason> — Client <code>`; group `chatbot-testing` (22000168676); status Open (2); priority Medium (2); source Chat (7); type `GENERAL QUERY`; tags `choice-jini`, `chatbot-testing`, `lang:en`; custom fields `cf_client_id=<code>`, `cf_source="chat box"`, `cf_product="finx"`, `cf_query_type149508="finx-bot"`, `cf_query_sub_type="finx-bot-test"`. Requester identified by **client code only** (as the existing tickets are) — no email or phone pushed to Freshdesk.
- **Conversation in the ticket**: the description is a metadata block (client id, reason, raised-at, turns included) plus the transcript rendered as readable HTML — user and bot messages and completed-form/app-event notes only; never tool internals; transcripts are already credential-clean by store construction. Long conversations truncate oldest-first with a "showing last N turns" note.
- **Ticket lands back in the conversation**: the loop emits a `ticket` artifact (id + status) rendered by the existing TicketCard; a flow-event memo ("support ticket #N raised") lands in the thread so the bot remembers and never re-raises for the same issue; a successful raise is a resolution event for the caps.
- **Config/secrets**: Freshdesk domain/API key/root read from the untracked `.env` via the established `_secret` pattern; never logged, never in tool schemas or the store; upstream calls log status + timing only. Freshdesk unreachable ⇒ `is_error` tool_result / endpoint error — the model apologizes and falls back to suggesting the app's support channels; chat never breaks.

Out of scope: ticket status lookup in chat ("what's my ticket status" — later change), attachments, CSAT, email/phone enrichment of the requester, and any non-testing group routing (switching the group id to a production group is a config change when the team is ready).

## Capabilities

### New Capabilities

- `support-escalation`: the ticket core — parameter contract, transcript rendering, requester identity, failure posture — and the `/api/ticket` entry point.

### Modified Capabilities

- `agent-tool-registry`: `raise_support_ticket` tool entry (user-intent: `reason` only).
- `report-chat-shell`: the help card's ticket action goes through the backend; TicketCard renders real ids; the ticket artifact joins the artifact-rendering contract.

## Impact

- Backend: new `app/agent/tickets.py` (core + Freshdesk client + transcript renderer), `app/agent/tools.py` (+1 tool), `app/agent/loop.py` (ticket artifact kind; artifact-only short-circuit covers it), `app/agent/router.py` (+`/api/ticket`), config getters for the Freshdesk env keys. New test module with respx-mocked Freshdesk.
- Frontend: help-card ticket action calls `/api/ticket`; TicketCard unchanged visually; agent-path ticket artifact wiring; `makeTicketId` removed.
- Verification includes exactly ONE real ticket created in the chatbot-testing group live (it is the designated testing group), then inspected and referenced in the PR.
