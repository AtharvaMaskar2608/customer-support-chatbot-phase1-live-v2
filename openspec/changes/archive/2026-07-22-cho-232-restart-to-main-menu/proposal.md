# CHO-232: restart-to-main-menu

## Why

Mid-conversation, the top-right control reads "↻ Restart" (CHO-216 / CHO-229). Product wants the wording softened to **"Main Menu"** — the same action, but framed as "go back to the start screen" rather than "restart", which testers read as destructive/data-losing. Functionality is unchanged: it still clears the conversation, aborts any in-flight stream, and requests a fresh agent thread.

## What Changes

- Rename the engaged-state control label from **"↻ Restart"** to **"🏠 Main Menu"** in the floating top-right cluster (`FloatingControls`, CHO-229). The refresh (↻) glyph is replaced with a 🏠 home emoji — mirroring the ✨ that leads the "What's new" pill — so the control reads as "go home", not "reload". Same black pill; styling, position, and the idle "✨ What's new" state are unchanged.
- Update the parked `CHO-229 — HEADER PARKED` block's Restart pill to match, so the recoverable header stays consistent.
- No behavioural change: same `onRestart` handler (conversation clear + stream abort + `POST /api/chat/reset`).
- Frontend-only. No backend, API, or contract change.

## Capabilities

### Modified Capabilities

- `whats-new`: the conversation-state control that takes over the What's-New slot is labelled "Main Menu" instead of "↻ Restart"; its behaviour is unchanged.

## Impact

- Frontend only: `frontend/src/App.tsx` (the live `FloatingControls` label + the parked header block).
- No test impact (no test asserts the label text); `tsc` + build are the gates. The frontend has no unit-test runner.
- Ships in the next frontend image. Visible copy change.
- Linear: CHO-232 · branch `cho-232-restart-to-main-menu`.
