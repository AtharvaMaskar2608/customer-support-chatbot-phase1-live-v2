# CHO-245: ticket-contact-fields

## Why

Bot-raised Freshdesk tickets currently identify the requester by **client code only** — "no email or phone ever leaves our system" (`tickets.py`). Support can't directly email or call the client back from the ticket. Product wants the client's **email and phone** attached so support can reach them (CHO-245). We already fetch the client's extended profile for the greeting; it carries email + mobile.

## What Changes

- Fetch the logged-in client's **email and phone** from the Profile API (server-side, using the request's SSO JWT) and include them in the Freshdesk ticket's requester `email` and `phone` fields, alongside the existing client-code identity.
- Best-effort: if the profile or a field is unavailable, the ticket is still raised with the client code (reliability unchanged). Email/phone are used only for the requester fields — never logged, never stored in the conversation.
- Reverses the deliberate "client code only" identity choice — update the `tickets.py` docstring and the support-escalation contract accordingly.
- Backend-only. Both ticket entry points (agent tool + `POST /api/ticket`) share `run_raise_ticket`, so both get the fields.

## Open decisions

- **PII confirmation**: this deliberately sends client email + phone to Freshdesk. Confirm product/compliance sign-off (it's the point of the ticket, but it's a posture reversal). CLAUDE.md's "forward only specced fields" rule is satisfied once this spec lands.

## Capabilities

### Modified Capabilities

- `support-escalation`: the ticket requester SHALL additionally carry the client's email and phone (fetched from the Profile API) so support can contact them; best-effort (client code always present), used only for the requester fields, never logged or stored.

## Impact

- Backend: `backend/app/agent/tickets.py` — fetch profile email/phone (reuse the greeting's profile fetch; shares the per-conversation profile call with CHO-246) and add `email` + `phone` to the Freshdesk payload; update the docstring (no longer "no email/phone").
- Confirm the exact upstream profile field names for email + mobile (from the extended profile response / `docs/api_doc`) before wiring.
- PII: email/phone used only for the requester fields; logging stays status+timing only.
- ⚠️ Touches the same support-escalation requirement as CHO-242 IF the ticket subject is rebranded — by default CHO-242 leaves the subject as-is, so no overlap; if that decision flips, ship CHO-242 first and rebase this delta.
- `uv run pytest` gate — assert email/phone present when the profile provides them, and a ticket still raises when it doesn't.
- Linear: CHO-245 · branch `cho-245-ticket-contact-fields`. Relates to CHO-246 (shared profile fetch).
