# data-card-system Specification

## Purpose
TBD - created by archiving change cho-211-data-card-flows. Update Purpose after archive.
## Requirements
### Requirement: Answer-in-chat card anatomy
A data card SHALL render the answer directly in the conversation using the shared anatomy: a hero fact (the single number or list answering the user's question), qualifying context beside it (never buried), a ranked or filtered list, depth on tap, and at most one quiet footer action. Download/export SHALL be a secondary affordance, never the hero.

#### Scenario: Data never gated behind a file
- **WHEN** a data flow completes
- **THEN** the answer is visible in the card itself without any download step

#### Scenario: Depth on demand
- **WHEN** the user taps a list row
- **THEN** an inline detail area expands with the full breakdown, and tapping again collapses it

### Requirement: Paise-safe Indian currency formatting
All monetary values SHALL use Indian digit grouping (₹1,01,49,986) and SHALL preserve paise when present (₹0.10, ₹612.10) while rendering whole rupees without decimals. Values SHALL use tabular numerals.

#### Scenario: Sub-rupee amount
- **WHEN** a ₹0.10 transaction renders
- **THEN** it shows "₹0.10", not "₹0"

#### Scenario: Large amount
- **WHEN** ₹10,149,986 renders
- **THEN** it shows "₹1,01,49,986" (Indian grouping)

### Requirement: Color discipline — success is quiet, exceptions carry the color
Expected/successful states SHALL render minimally (a small green ✓, no pill, no word beyond the chip vocabulary); exception states SHALL carry the color and the word (pending amber, failed red, cancelled gray). Rows for transactions that did not happen (failed, cancelled) SHALL be visually dimmed.

#### Scenario: Mixed-status list
- **WHEN** a list holds successful, pending and failed entries
- **THEN** the pending/failed entries are the most visually prominent and the successful ones the quietest

### Requirement: Count-chips double as filters
Where a card summarizes statuses, the summary chips (dot + count + label) SHALL be the filter controls: tapping filters the list to that status, tapping again clears; chips with a zero count SHALL NOT render.

#### Scenario: Filter by chip
- **WHEN** the user taps the "4 pending" chip
- **THEN** the list shows only pending entries and the chip shows a pressed state; tapping it again restores the full list

### Requirement: Animated reveal
Hero values SHALL count up to their final value on first render, and bar segments SHALL grow to their widths — the data reveal is earned, not dumped. Animations SHALL be one-shot and short (<1s).

#### Scenario: Hero count-up
- **WHEN** a card with a hero value first renders
- **THEN** the value animates from ₹0 to the final amount in under a second

### Requirement: Theme fidelity
Every data-card primitive SHALL render correctly in both light and dark themes using the existing token system.

#### Scenario: Dark theme
- **WHEN** the widget is in dark theme
- **THEN** cards, chips, dimming and status colors remain legible with the dark token values

