# CHO-247: remove-double-edit-pl — tasks

## 1. Remove the redundant edit button

- [ ] 1.1 In `frontend/src/chat/FlowCard.tsx`, stop rendering the row-header "Edit ✎" button for filled slots: remove the `onEdit` passed to `SlotRow` at the filled-slot branch (~line 283) and drop the now-unused `onEdit` prop + button in the `SlotRow` component (~lines 41–50)
- [ ] 1.2 Keep `FilledChip` exactly as-is — its tap-to-edit (`onClick → onEdit(slot.key)`) and ✎ pencil remain the single edit affordance; the locked state still disables the chip
- [ ] 1.3 Confirm no other caller relies on `SlotRow`'s `onEdit` (it is passed only at the filled-slot branch; active-slot and delivery rows never pass it)

## 2. Verification

- [ ] 2.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 2.2 On a P&L setup with segment + date filled, each row shows ONLY the chip (with ✎) — no separate "Edit" button; tapping a chip still re-opens that slot; after delivery the chips are disabled exactly as before
- [ ] 2.3 Screenshot before deploy (visible UI change), light + dark

## 3. Ship & sync

- [ ] 3.1 `git-sync` with issue key CHO-247
- [ ] 3.2 `linear-connector` — summary comment + state on merge
