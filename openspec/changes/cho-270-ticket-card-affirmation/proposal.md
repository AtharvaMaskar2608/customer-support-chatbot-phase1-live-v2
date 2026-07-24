# CHO-270: ticket-card-affirmation

## Why

Jam on CHO-270: the bot announced “Let me raise a support ticket…” / “I’m raising a support ticket…”, the user said “Ok”, and the reply was more narration — **no ticket card / ticket number**. The card only renders from a successful `raise_support_ticket` → `ticket` artifact. CHO-241’s affirmation guard only matched the *immediately preceding* assistant turn against exact infinitive offer markers (`raise a support ticket`, …). Gerund narration (“I’m **raising**…”) does not match, so after “Ok” the dispatcher rejects the tool call and the card never appears.

## What Changes

- **Widen** `ticket_call_is_user_initiated` affirmation recovery:
  - Treat gerund / announce-near-offer markers (`raising a ticket`, `raising a support ticket`, `let me raise`, …) as confirmation context — still requires an affirmative user turn; never allows preemptive raises.
  - Scan **all consecutive assistant turns** since the previous user message (not only the last bubble), so an earlier “Let me raise a support ticket…” still counts when a later “I’m raising…” bubble precedes “Ok”.
- **Light prompt hardening**: never claim a ticket is being / was raised unless `raise_support_ticket` was just called; the ticket card is the confirmation.
- **Default model**: switch `AGENT_MODEL_DEFAULT` to `claude-sonnet-4-6` with `AGENT_THINKING=off` (omit thinking — smallest Sonnet config). Haiku remains allowlisted via env.
- Spec delta on `agent-loop` (affirmation recovery + default model). Tests for the screenshot path + default model assertions.
- No frontend TicketCard / Freshdesk payload changes (traces filter model list order only).

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `agent-loop`: affirmative acceptance of escalation SHALL also match recent assistant announce/raise narration (gerunds + multi-bubble lookback), so `raise_support_ticket` can succeed and emit the ticket artifact after “Ok”. Default model SHALL be `claude-sonnet-4-6` with thinking off.

## Impact

- **Owns:** `backend/app/agent/tickets.py` (`ticket_call_is_user_initiated`), light touch in `backend/app/agent/prompt.py` ticket policy, `backend/app/config.py` default model, related tests, OpenSpec `agent-loop` delta, `.env.example` comment, traces FilterBar model order.
- **Does not own:** TicketCard UI, `/api/ticket` help-card path, Freshdesk D1 payload.
- Linear: CHO-270 · branch `cursor/cho-270-ticket-card-affirmation-9d2b`.
