# report-chat-shell

## ADDED Requirements

### Requirement: No-data reports offer a range-recovery affordance
When a report request returns no data (the outcome that renders a "couldn't find …" line for P&L, ledger, or capital gains), the shell SHALL render an actionable recovery affordance beneath the line — a "Try another range" pill, mirroring the contract-notes "Change dates" recovery — not a dead-end text line. Choosing it SHALL re-open the range selection on a fresh seeded flow card below (the prior segment/book retained, the date range or financial year re-opened), so the user can pick a new range and re-run without restarting the flow. The completed no-data card SHALL remain as history (spawn-fresh-below).

#### Scenario: Empty P&L offers recovery
- **WHEN** a P&L request for July 2026 returns no data
- **THEN** the "couldn't find any P&L for that period" line is followed by a "Try another range" pill

#### Scenario: Recovery re-opens the range
- **WHEN** the user taps "Try another range"
- **THEN** a fresh P&L card appears below with the segment kept and the date range re-opened for a new pick, and the earlier no-data card stays as history

#### Scenario: Consistent with contract notes
- **WHEN** any date-bearing report (P&L, ledger) returns no data
- **THEN** the recovery affordance matches the contract-notes "Change dates" pattern rather than each flow inventing its own
