# CHO-255/256/257: report-rerun-affordances — tasks

## 1. Reports — re-run affordance only on no-data (CHO-257 + CHO-256)

- [ ] 1.1 Remove the "Adjust & run again" pill from delivered report cards (download + email renderers) in `ChatShell`
- [ ] 1.2 On a no-data report result (`NO_DATA` only), append a "Try a different range" affordance under the empty line; wire it to the spawn-fresh seeded flow (reuse `handleAdjustRerun`)
- [ ] 1.3 Keep `AUTH_EXPIRED` / generic errors text-only (no range affordance)
- [ ] 1.4 Add the no-data report retry message kind to `messages.ts`

## 2. Contract notes — change-dates only on no-data + new message (CHO-255)

- [ ] 2.1 Remove the "Change dates" footer from `NotesList` (multi-note success) and the single-note "Other dates" pill
- [ ] 2.2 Keep "Change dates" on the empty / error paths
- [ ] 2.3 `handleChangeDates` spawns a FRESH contract-notes flow (new message), not `handleEdit` in place

## 3. Verification

- [ ] 3.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 3.2 Manual: delivered P&L → no pill; no-data P&L → "Try a different range" → fresh card; contract-notes list → no change-dates; empty notes → change-dates → fresh card
- [ ] 3.3 Screenshots of success (affordance absent) + no-data (affordance present), reports + contract notes

## 4. Ship & sync

- [ ] 4.1 `git-sync` with issue key CHO-255 (Fixes CHO-255 / CHO-256 / CHO-257)
- [ ] 4.2 `linear-connector` — summary comment + state on merge for all three
