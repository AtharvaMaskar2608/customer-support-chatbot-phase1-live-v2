# CHO-223: calendar-year-month-drilldown — tasks

## 1. Drill-down state

- [x] 1.1 In `frontend/src/chat/Calendar.tsx`, add a `view` state (`'day' | 'month' | 'year'`), defaulting to `'day'`
- [x] 1.2 Turn the `{MONTHS_LONG[viewMonth]} {viewYear}` span into a button: from `day` it opens `year`; from `month` it opens `year`; give it an `aria-label` naming the current view
- [x] 1.3 Hide the prev/next chevrons while in `month` or `year` view (they have no meaning there)

## 2. Effective bounds

- [x] 2.1 Add `yearDisabled(y)` — true when `y < minDate.getFullYear()`, `y > maxDate.getFullYear()`, or (with a `start` picked) outside `start.getFullYear()`–`rangeCapFor(start).getFullYear()`
- [x] 2.2 Add `monthDisabled(y, m)` — true when the whole month falls before `minDate`, after `maxDate`, or outside the `maxRangeYears` window from `start`
- [x] 2.3 Verify both reuse the same `rangeCapFor()` the day grid already uses, so no third source of truth appears

## 3. Grids

- [x] 3.1 Year grid: 3-column grid over `minDate.getFullYear()`–`maxDate.getFullYear()`, disabled cells styled like disabled days; picking a year sets `viewYear` and moves to `month`
- [x] 3.2 Month grid: 3-column grid of the 12 short month labels; picking one sets `viewMonth` and returns to `day`
- [x] 3.3 If the selected year makes the current `viewMonth` invalid, clamp it to the nearest selectable month rather than landing on a fully-disabled grid

## 4. Verification

- [x] 4.1 From today, reach January 2018 in three taps (header → 2018 → Jan) on the P&L flow
- [x] 4.2 Pick a start date, then confirm the year grid disables years beyond `start + 2` on P&L and Ledger
- [x] 4.3 Contract Notes (no `maxRangeYears`, `futureDaysCap: 0`): confirm years 2018–2026 are selectable and no future date is reachable
- [x] 4.4 Keyboard: header and every enabled cell are reachable by Tab and activate on Enter/Space; focus ring visible
- [ ] 4.5 Light and dark themes; `npm run build` passes

## 5. Ship & sync

- [ ] 5.1 `git-sync` with issue key CHO-223
- [ ] 5.2 `linear-connector` — summary comment + state to Done on merge
