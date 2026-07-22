# agent-loop

## MODIFIED Requirements

### Requirement: Slot filling without invention
The system prompt SHALL instruct the model to never invent values for required tool parameters and SHALL include today's date **resolved in IST (`Asia/Kolkata`)** so relative date expressions resolve to `YYYY-MM-DD`. The date MUST be computed from an explicitly named zone, never inherited from the host or container timezone, and the report-form validator MUST resolve "today" on the same clock so the prompt and the validator can never disagree. For the four report flows (P&L, ledger, capital gains, contract notes) the model SHALL NOT ask for parameters in prose: when any parameter is missing it SHALL call `open_report_form` carrying only the values the user actually stated (none stated ⇒ flow key alone), and when every parameter including the delivery method is explicitly known — from the user's words or from a prior flow event in the thread — it SHALL call the report tool directly. Prose clarifying questions (all missing values bundled into one question) remain only for non-report tools.

#### Scenario: Nothing mentioned loads the full form
- **WHEN** the user writes "get my P&L" with no parameters
- **THEN** the model calls `open_report_form` with only the flow key, and the widget boots the full guided P&L flow from its first slot — no value assumed, no prose question asked

#### Scenario: Partial mention pre-fills the form
- **WHEN** the user writes "P&L for equity"
- **THEN** the model calls `open_report_form` with the flow key and segment only, and the widget opens with the segment chip filled, asking for the date range next

#### Scenario: Full mention still executes directly
- **WHEN** the user writes "Get my F&O P&L for 1 to 30 June 2026, download it here"
- **THEN** the model calls the P&L report tool directly and the file card is produced with no form

#### Scenario: Date is IST regardless of host timezone
- **WHEN** the backend process runs with `TZ=UTC` (as the deployed container does) at 01:00 IST on 21 July 2026
- **THEN** the prompt states the date as 2026-07-21, not 2026-07-20

#### Scenario: Validator agrees with the prompt across the UTC rollover
- **WHEN** the user asks at 01:00 IST for a report bounded by a zero-day future cap on today's date
- **THEN** the form validator accepts today's IST date rather than rejecting it as a future date
