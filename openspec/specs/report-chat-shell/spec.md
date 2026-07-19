# report-chat-shell Specification

## Purpose
TBD - created by archiving change cho-207-report-flows. Update Purpose after archive.
## Requirements
### Requirement: One continuous conversation
The widget SHALL present a single scrolling conversation. The greeting + quick-action stickers are the empty state; on first engagement (a sticker tap or a composer submit) that empty state SHALL collapse away and the conversation SHALL own the canvas.

#### Scenario: Collapse on engage
- **WHEN** the user taps a sticker or sends a message from the empty state
- **THEN** the greeting + stickers animate away and the flow continues inline as messages

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

### Requirement: Narrated generation
While a report is being produced, the shell SHALL show a sequence of short progress captions specific to the flow (e.g. "Pulling your trades… → Tallying charges… → Sealing with your PAN…") rather than a generic spinner.

#### Scenario: Narrated wait
- **WHEN** a report is generating
- **THEN** the progress caption advances through the flow's narration steps, then the result appears

### Requirement: Tinted icon system
All widget iconography SHALL use tinted inline SVG icons (colored via `currentColor`) — not native multi-color emoji — so icons match the tile/button color context.

#### Scenario: Delivery button icons
- **WHEN** the delivery step renders
- **THEN** the primary button shows a document/download glyph in its text color and the email option shows a mail glyph in the accent color

### Requirement: Download feedback
Tapping a download action SHALL give immediate in-place feedback: a brief busy state, then a success check, then revert — so the click is never silent.

#### Scenario: Download tapped
- **WHEN** the user taps a file card's download button
- **THEN** the button shows a spinner, then a green check, then returns to the download icon

### Requirement: Help resolves to an actionable ticket card
A result's help affordance ("Tell me") SHALL open an actionable card (context-appropriate options plus "Raise a ticket"), and raising a ticket SHALL produce a ticket-confirmation card with an id and open status.

#### Scenario: Raise a ticket
- **WHEN** the user opens help on a delivered report and taps "Raise a ticket"
- **THEN** a ticket-confirmation card appears with a ticket id and Open status

### Requirement: Data-flow stickers
The empty state SHALL include stickers for the three data flows — "My holdings", "Pay in / out", "Brokerage" — using the tinted icon system, alongside the four file-flow stickers.

#### Scenario: Sticker starts a data flow
- **WHEN** the user taps "My holdings" from the empty state
- **THEN** the empty state collapses and the holdings flow runs inline

