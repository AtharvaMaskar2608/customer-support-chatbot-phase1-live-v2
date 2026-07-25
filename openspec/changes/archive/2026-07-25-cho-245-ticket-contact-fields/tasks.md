# CHO-245: ticket-contact-fields — tasks

## 1. Fetch + attach email/phone

- [ ] 1.1 In `backend/app/agent/tickets.py`, fetch the client's email + phone from the Profile API server-side (reuse the greeting's `_fetch_profile`; share the per-conversation profile call with CHO-246 if landing together) using `ctx.sso_jwt` + `ctx.client_code`
- [ ] 1.2 Confirm the exact upstream field names for email + mobile from the extended profile response / `docs/api_doc` before wiring
- [ ] 1.3 Add `email` and `phone` to the Freshdesk `payload` (keep `unique_external_id` + `name` = client code); best-effort — omit a field if absent, always raise the ticket
- [ ] 1.4 Update the module docstring (no longer "no email or phone ever leaves our system"); keep logging status+timing only; never log email/phone

## 2. Verification

- [ ] 2.1 `cd backend && uv run pytest` green — assert email/phone present when the profile provides them; a ticket still raises when the profile is unavailable; email/phone never logged
- [ ] 2.2 Both entry points (agent `raise_support_ticket` + `POST /api/ticket`) carry the fields (shared core)

## 3. Ship & sync

- [ ] 3.1 `git-sync` with issue key CHO-245
- [ ] 3.2 `linear-connector` — summary comment + state on merge
