# CHO-250: no-data-another-range — tasks

## 1. Range-recovery pill on no-data

- [ ] 1.1 In `frontend/src/chat/ChatShell.tsx` `renderResult`, on the no-data outcome (the `NO_DATA` code that maps to the "couldn't find …" line in `messages.ts:105`), append a recovery-action message beneath the bot line
- [ ] 1.2 Wire the pill to spawn a fresh seeded flow card below (`startRun(descriptor, priorValues without the date)` so the engine re-opens the date slot; for capital gains re-open the FY slot), reusing / generalising the `notesAction` → `ChangeDatesButton` pattern
- [ ] 1.3 Keep the prior segment/book seeded; leave the no-data card as history (spawn-fresh-below, consistent with CHO-249)
- [ ] 1.4 Label the pill "Try another range"; reuse the contract-notes pill styling for consistency

## 2. Verification

- [ ] 2.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 2.2 Force a no-data P&L (a period with no trades) → the "couldn't find …" line is followed by a "Try another range" pill; tapping it opens a fresh P&L card with the segment kept and the range re-opened; picking a new range generates below
- [ ] 2.3 Screenshot before deploy (light + dark)

## 3. Ship & sync

- [ ] 3.1 `git-sync` with issue key CHO-250
- [ ] 3.2 `linear-connector` — summary comment + state on merge
