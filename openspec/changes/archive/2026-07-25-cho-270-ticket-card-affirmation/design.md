# CHO-270 design: ticket-card affirmation recovery

## Context

Ticket cards are artifact-driven (`kind: ticket` from a successful `raise_support_ticket`). CHO-241 correctly blocks preemptive raises. The jam fails on the *recovery* path: model announces raise → user affirms → guard rejects because markers are too narrow / lookback is one bubble.

## Decision

Keep the user-initiated gate. Broaden only the **affirmative + prior escalate context** arm:

1. **Markers** — add gerund and announce forms that still imply the bot invited/started an escalation (`raising a ticket`, `raising a support ticket`, `let me raise`). Keep existing offer phrases.
2. **Lookback** — after finding the latest user turn, collect consecutive `assistant_text` turns until the prior `user_text`, and match markers against any of them.
3. **Unchanged** — explicit escalation-request allowlist; preemptive block; help-card `/api/ticket` bypass; no fabricated ticket ids.

## Prompt

One-line hardening under TICKET POLICY: do not say a ticket is being/was raised unless the tool just ran; the confirmation card carries the number. Does not replace the code guard.

## Out of scope

- Post-generation text filters for “I’m raising…”
- Changing TicketCard copy or Freshdesk fields
- Auto-raising without user ask/affirm
