# agent-tool-registry (delta)

## ADDED Requirements

### Requirement: Form handover tool with validate-and-drop seeding
The registry SHALL include an `open_report_form` tool whose input schema requires only the flow key (`pnl` | `ledger` | `tax` | `contract-notes`) and accepts every seedable slot value as optional user-intent fields (`segment`, `book`, `fy`, `format`, `fromDate`/`toDate`, `delivery`). The handler SHALL keep only the fields the named flow declares, SHALL validate each kept value against the flow's canonical options and date constraints (chip labels exactly as the UI presents them; dates within 2018-01-01 to today+7 days, span ≤ 2 years, `fromDate ≤ toDate`, both-or-neither), and SHALL silently drop any invalid value — an invalid seed field degrades to the widget asking for it, never to an error and never to a mis-filled form. The contract-notes selection SHALL never be seedable. The handler SHALL return a success envelope carrying the flow key and surviving seed for artifact emission, and the model SHALL receive a synthetic success tool_result describing what was opened and pre-filled so it can close with a brief handoff line.

#### Scenario: Valid partial seed survives
- **WHEN** the model calls `open_report_form` with flow `pnl`, segment "Equity", and a valid June date range
- **THEN** the envelope carries all three fields and the flow artifact seeds the widget accordingly

#### Scenario: Invalid value dropped, not errored
- **WHEN** the seed contains segment "Crypto" or a date range spanning three years
- **THEN** the invalid field is dropped, the remaining valid fields survive, and the tool_result is still a success

#### Scenario: Irrelevant field dropped per flow
- **WHEN** the model calls `open_report_form` with flow `ledger` and a `segment` value
- **THEN** the segment field is dropped and only ledger-declared fields (book, dates, delivery) are considered

#### Scenario: Empty seed is a valid open
- **WHEN** the model calls `open_report_form` with only the flow key
- **THEN** the tool succeeds with an empty seed and the widget boots the full flow from its first slot
