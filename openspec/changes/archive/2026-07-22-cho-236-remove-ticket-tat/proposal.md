# CHO-236: remove-ticket-tat

## Why

When a ticket is raised, the confirmation card promises a turnaround time — "Usually resolved within 24 hours — you can check progress anytime by asking 'my ticket status'." Two problems: (1) it commits to a 24-hour TAT the support org hasn't agreed to, and (2) it tells the user a live "my ticket status" self-service check exists, when it doesn't yet. Product wants no TAT commitment and the status check framed as "coming soon".

## What Changes

- Rewrite the ticket-confirmation card copy (`TicketCard`):
  - Drop the **"Status: Open ·"** prefix — the subline reads just **"We'll email you updates"**.
  - Drop the **"resolved within 24 hours"** TAT commitment.
  - Replace the helper line with: **"We're on it — updates will reach your registered email. ✨ Coming soon: ask me 'my ticket status' to track it right here."** — framing the status check as a future feature, not an available action.
- Sweep the agent system prompt for any instruction that tells users to "ask 'my ticket status'" as if it works today; neutralise if present (no live status-check tool exists).
- Frontend-first (copy). No backend contract change; the prompt is touched only if it over-promises status.

## Capabilities

### Modified Capabilities

- `support-escalation`: the ticket confirmation makes no turnaround-time commitment and presents the "my ticket status" self-service check as "coming soon" rather than as an available action.

## Impact

- Frontend: `frontend/src/chat/ResultCards.tsx` (`TicketCard` copy).
- Possibly `backend/app/agent/prompt.py` — verify it does not direct users to a live "my ticket status" check; edit only if it over-promises.
- No API / contract change; ticket creation, transcript, and entry points are unchanged.
- Linear: CHO-236 · branch `cho-236-remove-ticket-tat`.
