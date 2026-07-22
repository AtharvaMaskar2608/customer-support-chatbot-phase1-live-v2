# CHO-223: calendar-year-month-drilldown

## Why

The custom-range calendar navigates one month at a time. `Calendar.tsx` renders the month/year as an inert `<span>` between two chevrons, and `nav(±1)` is the only way to move. Every date flow sets `minDate: '2018-01-01'`, so a customer who wants a range from early 2018 taps the back chevron **102 times** from today. QA flagged this on the P&L flow; it affects Ledger and Contract Notes identically because all three share one component.

## What Changes

- The month/year header becomes a button that opens a **year grid**; picking a year opens a **month grid**; picking a month returns to the day grid. Back-navigation is the header itself (day → month → year).
- Year and month grids respect the **effective** bounds, not just the static ones:
  - Years outside `minDate.getFullYear()`–`maxDate.getFullYear()` are disabled. With `minDate: 2018-01-01` and `futureDaysCap` of 0–7, that is 9 cells (2018–2026) — a 3×3 grid that never scrolls.
  - Once a start date is picked, `maxRangeYears` (2 on P&L and Ledger) shrinks the selectable window to `start.year`–`start.year + 2`; months before `start`'s month in the start year are disabled too.
  - This mirrors the existing `isDisabled()` day logic, so a user can never drill into a month whose every day is greyed out.
- Chevron month-stepping is retained for fine navigation; only the header gains behaviour.
- The two-tap range selection (pick start, then end) is unchanged — drilling to a different year mid-selection keeps the range cap in force.
- Accessibility: the header button carries an `aria-label` describing the current view, year/month cells are real buttons, and the existing focus-visible ring applies.

## Capabilities

### Modified Capabilities

- `report-flow-engine`: the `date` slot's calendar gains a Year → Month → Date drill-down, and the existing per-flow constraint requirement is extended to say the drill-down levels honour the same effective bounds as the day grid.

## Impact

- Frontend only, and only two files: `frontend/src/chat/Calendar.tsx` (the drill-down view state and the year/month grids) and `frontend/src/flow/dates.ts` if a month-label helper is needed — `MONTHS_LONG` already exists.
- One component serves all three date flows (`FlowCard.tsx:151` is the only import site), so this is a single fix with no per-flow work.
- The tax flow's financial-year step is a `chips` slot, not a calendar; it is out of scope.
- No backend, API, or contract change.
- Linear: CHO-223 · branch `cho-223-calendar-year-month-drilldown`.
