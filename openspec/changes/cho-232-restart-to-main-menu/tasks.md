# CHO-232: restart-to-main-menu — tasks

## 1. Rename the control

- [ ] 1.1 In `frontend/src/App.tsx`, change the engaged-state pill in `FloatingControls` from "↻ Restart" to "🏠 Main Menu" (replace the ↻ glyph with the 🏠 emoji; keep the same black pill so it mirrors the "✨ What's new" sibling)
- [ ] 1.2 Mirror the same "🏠 Main Menu" label in the parked `CHO-229 — HEADER PARKED` block so the recoverable header stays consistent
- [ ] 1.3 Leave the `onRestart` handler, pill styling, position, and the What's-New idle state untouched

## 2. Verification

- [ ] 2.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 2.2 Engage a conversation → the top-right control reads "Main Menu"; tapping it still clears the chat, aborts any stream, and returns to the greeting
- [ ] 2.3 Idle state still shows "✨ What's new" with its unseen dot

## 3. Ship & sync

- [ ] 3.1 `git-sync` with issue key CHO-232
- [ ] 3.2 `linear-connector` — summary comment + state on merge
