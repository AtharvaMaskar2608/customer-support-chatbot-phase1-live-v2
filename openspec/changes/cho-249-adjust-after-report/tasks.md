# CHO-249: adjust-after-report — tasks

## 1. Spawn-fresh-below affordance

- [ ] 1.1 In `frontend/src/chat/ChatShell.tsx`, add a handler `handleAdjustRerun(flowKey, values)` that looks up the descriptor and appends `{ id: nextId(), kind: 'flow', run: startRun(descriptor, values) }` below the last message (seeded with the prior run's collected slot values; all slots filled ⇒ lands on the delivery step)
- [ ] 1.2 Render an "Adjust & run again" control under the `download` and `email` result cards in `MessageView`, wired to `handleAdjustRerun(m.flowKey, m.values)`; show it only when `m.values` is non-empty (guided-flow reports), never for agent `file` artifacts (values `{}`)
- [ ] 1.3 Leave the delivered card untouched — the fresh card is a new message; the original stays as history
- [ ] 1.4 Style the control consistently with the existing `ChangeDatesButton` / followup pills

## 2. Verification

- [ ] 2.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 2.2 Deliver a P&L (download), tap "Adjust & run again" → a fresh P&L card appears below pre-filled + editable; change the segment and deliver → new report below; the first card is unchanged
- [ ] 2.3 Confirm an agent-produced file card (free-text "get my June F&O P&L, download") shows NO adjust affordance
- [ ] 2.4 Screenshot before deploy (light + dark)

## 3. Ship & sync

- [ ] 3.1 `git-sync` with issue key CHO-249
- [ ] 3.2 `linear-connector` — summary comment + state on merge
