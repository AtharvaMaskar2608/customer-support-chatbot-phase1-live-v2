# holdings-flow

## MODIFIED Requirements

### Requirement: CSV export
The card SHALL offer a prominent, clearly visible **full-width primary button** (filled accent, download icon) to download the holdings CSV — not a quiet footer text link. Its label SHALL include the holding count: "Download CSV — all N holdings" ("holding" when N = 1). The file is generated client-side from data the card already holds, in FinX's own export format: columns `Instrument, Exchange, QTY | LOT, Avg. Price, LTP, Invested Amt., Current Value, Returns, Returns %, Product`, filename `{UserCode}_Holding_Overall_Report_{timestamp}.csv`. Feedback SHALL happen on the button (spinner → green "Saved to downloads" → revert); the filename MUST NOT be echoed into the conversation.

#### Scenario: Prominent CTA
- **WHEN** the holdings card renders with N holdings
- **THEN** a full-width primary "Download CSV — all N holdings" button is clearly visible, not a quiet text link

#### Scenario: Export
- **WHEN** the user taps the Download CSV button
- **THEN** the file saves with the FinX-format name and the button itself confirms — no new chat bubble
