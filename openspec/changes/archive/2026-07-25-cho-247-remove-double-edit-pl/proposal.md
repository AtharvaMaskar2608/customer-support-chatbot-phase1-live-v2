# CHO-247: remove-double-edit-pl

## Why

On the report setup card (P&L and every guided flow) each **filled** slot shows **two** ways to edit the same value: the chip itself is tap-to-edit (with a ✎ pencil), and the row header ALSO renders a separate **"Edit ✎"** text button. Both call the same `onEdit(slotKey)`, so the header button is pure redundancy — testers flagged it as clutter (CHO-247 screenshot: the F&O row and the FY 2026-27 row each carry a highlighted "Edit ✎" button beside an already-editable chip).

## What Changes

- Remove the redundant row-header **"Edit ✎"** button from filled slots on the flow card. The chip stays the single, self-evident edit affordance — tapping the chip re-opens the slot; the ✎ glyph on the chip signals it.
- No behaviour change: editing still works identically (tap the chip), and the locked/generating state is unchanged (chips already disable when the card locks). Every guided flow (P&L, ledger, capital gains, contract notes) benefits — the card is shared.
- Frontend-only. No backend, API, or descriptor change.

## Capabilities

### Modified Capabilities

- `report-flow-engine`: a filled slot SHALL expose exactly one edit affordance — the chip itself — and SHALL NOT render a second, redundant "Edit" control in the slot's row header.

## Impact

- Frontend only: `frontend/src/chat/FlowCard.tsx` — stop passing `onEdit` to `SlotRow` at the filled-slot branch (~line 283) and drop the now-unused header-button rendering in `SlotRow` (~lines 41–50); keep `FilledChip`'s tap-to-edit + pencil (~lines 56–72, ~285) untouched.
- No test impact expected; `tsc` + lint + build are the gates. Visible UI change → screenshot before deploy.
- Linear: CHO-247 · branch `cho-247-remove-double-edit-pl`.
