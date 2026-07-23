# CHO-255/256/257: report-rerun-affordances

## Why

Three Triage reports converge on one rule: a report's **re-run / adjust affordance** belongs **only on the no-data result**, never on a successful one — and tapping it should **start a fresh message**, not edit the delivered card in place.

Today:
- A **delivered** report (P&L / ledger / tax file card) shows an "Adjust & run again" pill (CHO-249). **CHO-257**: hide it on success — it belongs on the no-data path only.
- A report that finds **no data** shows only a plain text line ("I couldn't find any P&L for that period. Want to try a different date range?") with **no affordance**. **CHO-256**: give it a card affordance to try a different range, like contract notes — and it should start a new message.
- **Contract notes** show a "Change dates" pill even after a **successful** list (multi-note footer) and single-note delivery ("Other dates"). **CHO-255**: show it only when there's no data, and tapping it should start a new message, not reopen the existing card's date step in place.

## What Changes

- **Reports (CHO-257 + CHO-256):** remove the "Adjust & run again" pill from delivered report cards (download + email). On a **no-data** report result, render a "Try a different range" affordance under the empty-result line; choosing it spawns a fresh seeded flow card below (the CHO-249 spawn-fresh pattern), never mutating the delivered/failed card. `AUTH_EXPIRED` and generic errors keep their text-only remediation (a range change won't fix them).
- **Contract notes (CHO-255):** remove the "Change dates" / "Other dates" affordance from **successful** note results (multi-note list footer + single-note); keep it only on the empty / error paths. Tapping "Change dates" spawns a **fresh** contract-notes flow (a new message asking for a new range) instead of reopening the existing card's date step in place.
- Frontend-only. No backend / API change.

## Capabilities

### Modified Capabilities

- `report-chat-shell`: the report re-run affordance SHALL appear only on a no-data report result (not on a delivered report), and choosing it SHALL spawn a fresh seeded flow below rather than mutating a card in place.
- `contract-notes-report-flow`: the "Change dates" affordance SHALL appear only on the empty / error result (not after a successful list or single-note delivery), and choosing it SHALL start a fresh flow (new message) rather than reopening the existing card in place.

## Impact

- Frontend only: `frontend/src/chat/ChatShell.tsx` (renderResult no-data branch, download/email renderers, `handleChangeDates`, single-note path), `frontend/src/chat/NotesList.tsx` (drop the success-path footer button), `frontend/src/chat/messages.ts` (a no-data report retry message kind).
- Reverses the CHO-249 success-path affordance placement while keeping its spawn-fresh mechanism.
- `tsc` + lint + build gates; visible UI change → screenshots of the no-data (affordance present) and success (affordance absent) states, reports + contract notes.
- Linear: CHO-255, CHO-256, CHO-257 · branch `cho-255-257-report-rerun-affordances`.
