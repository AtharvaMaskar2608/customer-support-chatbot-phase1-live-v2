# money-flow

## ADDED Requirements

### Requirement: One merged passbook timeline
The Money flow SHALL render pay-in and pay-out as a single newest-first timeline (no tabs): direction is a per-row attribute — ↓ (green) for money in, ↑ (neutral) for money out. The default period SHALL be financial-year-to-date (FromDate = FY start, ToDate = today + 7 days, matching the FinX app).

#### Scenario: Interleaved stream
- **WHEN** deposits and withdrawals exist in the period
- **THEN** they appear in one list ordered purely by time, distinguished by direction glyphs

### Requirement: Status presentation
Rows SHALL follow the color discipline: `SUCCESS` → quiet green ✓; `PENDING` → amber "● Pending"; `FAILURE` → red "● Failed"; `CANCELLED` → gray "● Cancelled"; failed and cancelled rows dimmed. The card header SHALL show count-chips per status (non-zero only) that act as filters.

#### Scenario: Support scan
- **WHEN** the timeline holds a pending deposit among successes
- **THEN** the pending row is the most prominent element and the chip row shows its count

### Requirement: Row content and detail
Each row SHALL show the amount (paise-safe), and a meta line with date, 12-hour time, mode (when present) and masked destination (when present). Tapping expands a detail grid: direction-labeled request time ("Deposit requested"/"Withdrawal requested"), mode, destination ("To account"/"To your bank"), reference (voucher no or —), and — when upstream provided a `Reason` — a full-width "Why" cell showing it verbatim.

#### Scenario: Failed withdrawal explains itself
- **WHEN** the user expands a failed withdrawal whose Reason is "Request rejected due to low funds (Rs 70.61). Try again with a smaller amount."
- **THEN** that exact text appears in the Why cell

### Requirement: Landed-only footer totals
The footer SHALL read "Landed this period: `<₹in>` in · `<₹out>` out", counting only `SUCCESS` transactions. Pending and failed amounts MUST NOT inflate the totals.

#### Scenario: Phantom pending excluded
- **WHEN** a ₹1,01,49,986 pending attempt exists alongside ₹860 of landed deposits
- **THEN** the footer reports ₹860 in

### Requirement: Progressive disclosure
The list SHALL show the 6 most recent rows with "Show all n" (n from the merged stream; upstream `TotalRecords` governs completeness). Filter changes reset to the first 6.

#### Scenario: Long history
- **WHEN** more than 6 transactions match the current filter
- **THEN** only 6 render with a Show-all affordance carrying the true count

### Requirement: Help copy
The follow-up ("Something not adding up?") SHALL explain, factually: deposits may sit Pending before landing; failed deposits auto-reverse; withdrawals require sufficient free balance and a rejected one carries its reason in the detail.

#### Scenario: Missing money question
- **WHEN** the user opens the help affordance
- **THEN** the explanation covers pending, reversal, and the withdrawal-balance rule without speculative promises
