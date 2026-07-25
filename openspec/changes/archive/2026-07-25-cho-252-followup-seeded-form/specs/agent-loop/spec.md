# agent-loop

## MODIFIED Requirements

### Requirement: Slot filling without invention
The system prompt SHALL instruct the model to never invent values for required tool parameters and SHALL include the current date **resolved in IST (`Asia/Kolkata`)** so relative date expressions resolve to `YYYY-MM-DD`. The date MUST be computed from an explicitly named zone, never inherited from the host or container timezone, and the report-form validator MUST resolve "today" on the same clock so the prompt and the validator can never disagree. For the four report flows (P&L, ledger, capital gains, contract notes) the model SHALL NOT ask for parameters in prose: when any parameter is missing it SHALL call `open_report_form` carrying only the values the user actually stated (none stated ⇒ flow key alone). The model SHALL call a report tool directly ONLY when the user states every parameter — including the delivery method — in their current message. When the parameters are instead carried over from a prior flow event in the thread (a follow-up such as "now the same for MTF" or "same for ledger"), the model SHALL call `open_report_form` seeded with those carried-over values rather than executing directly — a follow-up always re-opens the guided form pre-filled and editable, and a report is generated only on the user's delivery tap; the model never silently generates a report from carried-over context. Prose clarifying questions (all missing values bundled into one question) remain only for non-report tools.

#### Scenario: Nothing mentioned loads the full form
- **WHEN** the user writes "get my P&L" with no parameters
- **THEN** the model calls `open_report_form` with only the flow key, and the widget boots the full guided P&L flow from its first slot — no value assumed, no prose question asked

#### Scenario: Partial mention pre-fills the form
- **WHEN** the user writes "P&L for equity"
- **THEN** the model calls `open_report_form` with the flow key and segment only, and the widget opens with the segment chip filled, asking for the date range next

#### Scenario: Full mention in one message still executes directly
- **WHEN** the user writes "Get my F&O P&L for 1 to 30 June 2026, download it here"
- **THEN** the model calls the P&L report tool directly and the file card is produced with no form

#### Scenario: Follow-up re-opens the seeded form, never auto-generates
- **WHEN** the user completed a Normal ledger for FY 2026-27 and then writes "now the same for MTF"
- **THEN** the model calls `open_report_form` seeded with book MTF and the carried-over range, the guided ledger form re-opens pre-filled and editable, and nothing generates until the user taps delivery

#### Scenario: Cross-report "same" maps onto the target form
- **WHEN** the user completed a P&L for F&O · June 2026 and then writes "now the same for ledger"
- **THEN** the model calls `open_report_form` for ledger carrying the period (dropping the inapplicable segment), and the ledger form opens seeded with the range and asking for the book — nothing generates until the user delivers

#### Scenario: Date is IST regardless of host timezone
- **WHEN** the backend process runs with `TZ=UTC` at 01:00 IST on 21 July 2026
- **THEN** the prompt states the date as 2026-07-21, not 2026-07-20
