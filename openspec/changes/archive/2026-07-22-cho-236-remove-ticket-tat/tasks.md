# CHO-236: remove-ticket-tat — tasks

## 1. Confirmation copy

- [ ] 1.1 In `frontend/src/chat/ResultCards.tsx` (`TicketCard`), change the status subline from "Status: Open · we'll email you updates" to "We'll email you updates"
- [ ] 1.2 Replace the helper line "Usually resolved within 24 hours — you can check progress anytime by asking 'my ticket status'." with: "We're on it — updates will reach your registered email. ✨ Coming soon: ask me 'my ticket status' to track it right here." (real ✨ glyph; keep quote style consistent with the file)
- [ ] 1.3 Keep the "Ticket #{id} raised" line, the ticket icon, and the card frame unchanged

## 2. Prompt sweep (no live status check)

- [ ] 2.1 Grep `backend/app/agent/prompt.py` for any "my ticket status" / status-check instruction implying a live lookup; if present, reword so the bot does not claim it can check status today (it's coming soon). If absent, no change

## 3. Verification

- [ ] 3.1 Raise a ticket → the confirmation card shows the new copy: no "24 hours" TAT, no "Status: Open", and "my ticket status" framed as coming soon
- [ ] 3.2 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes; if the prompt changed, `cd backend && uv run pytest` green
- [ ] 3.3 Screenshot the confirmation card (light + dark)

## 4. Ship & sync

- [ ] 4.1 `git-sync` with issue key CHO-236
- [ ] 4.2 `linear-connector` — summary comment + state on merge
