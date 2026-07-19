# report-chat-shell

## MODIFIED Requirements

### Requirement: Pinned composer with keyword routing
A composer SHALL remain pinned and usable at every point, including after a flow completes. Submitting text SHALL route by keyword to the matching flow — file flows (P&L, ledger, capital gains, contract notes) and data flows (holdings/portfolio, pay-in/pay-out/deposit/withdraw, brokerage/charges/slab) — or, if unmatched, reply with the available actions including the data flows. (Full natural-language understanding is a later change.)

#### Scenario: Text routes to a flow
- **WHEN** the user types a message matching a known report
- **THEN** that flow starts inline

#### Scenario: Data-flow keywords route
- **WHEN** the user types "my portfolio", "did my deposit land" or "what's my brokerage"
- **THEN** the holdings, money, or brokerage flow starts inline

#### Scenario: Unmatched text
- **WHEN** the user types something with no matching flow
- **THEN** the bot replies with the available report and data actions

## ADDED Requirements

### Requirement: Data-flow stickers
The empty state SHALL include stickers for the three data flows — "My holdings", "Pay in / out", "Brokerage" — using the tinted icon system, alongside the four file-flow stickers.

#### Scenario: Sticker starts a data flow
- **WHEN** the user taps "My holdings" from the empty state
- **THEN** the empty state collapses and the holdings flow runs inline
