# holdings-flow Specification

## Purpose
TBD - created by archiving change cho-211-data-card-flows. Update Purpose after archive.
## Requirements
### Requirement: Zero-slot flow
The Holdings flow SHALL ask no questions: sticker tap (or matched keyword) → narrated fetch ("Fetching your holdings… → Valuing at last prices…") → the portfolio card. There is no slot card and no delivery step.

#### Scenario: Instant portfolio
- **WHEN** the user taps "My holdings"
- **THEN** the portfolio card appears after the narration with no intermediate questions

### Requirement: Portfolio hero and pills
The card SHALL lead with the portfolio's current value (count-up), holding count, an "Invested" subline, and exactly two stat pills: **1D** (last-session move: `Σ Q×(LTP−CP)`) and **Overall** (`current − invested`), each with ▴/▾, ₹ amount and %, green/red by sign. The label MUST be "1D", never "Today".

#### Scenario: Both directions honest
- **WHEN** the portfolio is up 59% overall but down on the last session
- **THEN** the Overall pill is green and the 1D pill is red — both visible together

### Requirement: Time honesty
The hero SHALL carry a freshness line — a gray (non-"online") dot plus "Prices as of `<stamp>` — last fetch, not live", where the stamp derives from the maximum `LUT` in the API response, never a hardcode. The bot copy and narration MUST NOT claim live or real-time prices. The footer SHALL read "Ask again anytime — prices refetch on every request."

#### Scenario: Weekend ask
- **WHEN** the user asks on a non-trading day
- **THEN** the freshness line shows the last trading session's timestamp and no copy says "right now" or "live"

### Requirement: Allocation bar with Other-lump
The card SHALL show an animated allocation bar: the top 5 holdings by current value as colored segments plus one gray "Other (n)" segment aggregating the rest; a legend names the top 2 with percentages plus "+n more". Sub-segment tooltips carry symbol + allocation %.

#### Scenario: Ten holdings
- **WHEN** the portfolio holds 10 scrips
- **THEN** the bar renders 6 segments (top 5 + Other(5)), not 10 slivers

### Requirement: Ranked expandable rows
Rows SHALL be sorted by current value (descending), showing the top 4 with "Show all n" for the rest. Each row: color dot, symbol (exchange suffix stripped), qty + avg buy price, current value, overall P&L % (signed, colored). Tapping expands a detail grid: Invested, Current, Last price, 1D change, Overall P&L, Allocation.

#### Scenario: Expand a holding
- **WHEN** the user taps a row
- **THEN** the six-field detail grid expands inline beneath it

### Requirement: CSV export
The footer SHALL offer "Download CSV" generating — client-side from data the card already holds — FinX's own export format: columns `Instrument, Exchange, QTY | LOT, Avg. Price, LTP, Invested Amt., Current Value, Returns, Returns %, Product`, filename `{UserCode}_Holding_Overall_Report_{timestamp}.csv`. Feedback SHALL happen on the button (spinner → green "Saved to downloads" → revert); the filename MUST NOT be echoed into the conversation.

#### Scenario: Export
- **WHEN** the user taps Download CSV
- **THEN** the file saves with the FinX-format name and the button itself confirms — no new chat bubble

### Requirement: Factual presentation only
The card SHALL present concentrations, losses and gains as numbers only. It MUST NOT generate advice, warnings or recommendations (e.g. about diversification) from the data.

#### Scenario: Concentrated portfolio
- **WHEN** one holding is 51% of the portfolio
- **THEN** the card shows "51%" with no advisory copy

