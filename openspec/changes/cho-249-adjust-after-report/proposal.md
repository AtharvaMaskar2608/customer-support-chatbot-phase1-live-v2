# CHO-249: adjust-after-report

## Why

Once a guided report is delivered, its setup card locks (delivery chosen → `active = LOCKED`), so the segment/date chips disable and there is no way to tweak an input and run the report again — the user must restart the flow from scratch. Other surfaces already let you re-open inputs after acting (contract notes offers "Change dates"); reports should too (CHO-249: after "give report" there is no option to edit the segment so the flow can be triggered again).

## What Changes

- After a guided report is **delivered** (download or email), the shell SHALL show an **"Adjust & run again"** affordance beneath the result card. Choosing it appends a FRESH guided flow card below the last message, pre-seeded with the completed run's collected slot values — every slot editable, landing on the delivery step. The delivered card stays above as history; nothing is mutated in place ("spawn fresh below", per the CHO-249 decision).
- The fresh card behaves exactly like any seeded flow: the user edits a chip (e.g. segment F&O → Equity) or a date, taps a delivery option, and a new report generates below.
- Scoped to reports produced by a **guided flow run** (which carries slot values). Agent-produced `file` artifacts carry no slot values to seed, so they keep sending parameter/delivery changes back through chat (consistent with their existing "no Email it" treatment).
- Frontend-only. No backend, API, or descriptor change. The **no-data** terminal gets its own recovery affordance under **CHO-250**; this change covers the successful-delivery case.

## Capabilities

### Modified Capabilities

- `report-chat-shell`: after a guided report is delivered, the shell offers an "Adjust & run again" affordance that spawns a fresh seeded flow card below (pre-filled with the prior run's values, fully editable), leaving the delivered card intact as history.

## Impact

- Frontend only: `frontend/src/chat/ChatShell.tsx` — a new handler that appends `{ kind: 'flow', run: startRun(descriptor, priorValues) }` below the last message, wired to an affordance rendered under the `download`/`email` result cards in `MessageView` (those messages already carry `flowKey` + `values`).
- Applies to sticker/keyword/flow-artifact-produced reports; agent `file` artifacts (values `{}`) do not show it.
- No test impact expected; `tsc` + lint + build are the gates. Visible UI change → screenshot before deploy.
- Linear: CHO-249 · branch `cho-249-adjust-after-report`. Relates to CHO-250, CHO-252.
