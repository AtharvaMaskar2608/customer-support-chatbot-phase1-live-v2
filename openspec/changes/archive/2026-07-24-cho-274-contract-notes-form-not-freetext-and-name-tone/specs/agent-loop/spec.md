## MODIFIED Requirements

### Requirement: Slot filling without invention
The system prompt SHALL instruct the model to never invent values for required tool parameters and SHALL include the current date **resolved in IST (`Asia/Kolkata`)** so relative date expressions resolve to `YYYY-MM-DD`. The date MUST be computed from an explicitly named zone, never inherited from the host or container timezone, and the report-form validator MUST resolve "today" on the same clock so the prompt and the validator can never disagree. For the four report flows (P&L, ledger, capital gains, contract notes) the model SHALL NOT ask for parameters in prose: when any parameter is missing it SHALL call `open_report_form` carrying only the values the user actually stated (none stated ⇒ flow key alone), and when every parameter the tool needs is explicitly known in the current message — for P&L/ledger/tax that includes delivery; for `list_contract_notes` both dates — it MAY call that tool directly. Contract-note date range SHALL NEVER be requested in a free-text question; missing dates SHALL use `open_report_form` with `flow=contract-notes`. The `list_contract_notes` tool description SHALL NOT instruct the model to always call it first when dates are unknown. Prose clarifying questions (all missing values bundled into one question) remain only for non-report tools (e.g. a missing note id after a list), not for report date ranges.

#### Scenario: Nothing mentioned loads the full form
- **WHEN** the user writes "get my P&L" with no parameters
- **THEN** the model calls `open_report_form` with only the flow key, and the widget boots the full guided P&L flow from its first slot — no value assumed, no prose question asked

#### Scenario: Contract notes without dates open the form
- **WHEN** the user writes "get my contract notes" with no date range
- **THEN** the model calls `open_report_form` with `flow=contract-notes` and does not ask for dates in chat text

#### Scenario: Partial mention pre-fills the form
- **WHEN** the user writes "P&L for equity"
- **THEN** the model calls `open_report_form` with the flow key and segment only, and the widget opens with the segment chip filled, asking for the date range next

#### Scenario: Full mention still executes directly
- **WHEN** the user writes "Get my F&O P&L for 1 to 30 June 2026, download it here"
- **THEN** the model calls the P&L report tool directly and the file card is produced with no form

#### Scenario: Date is IST regardless of host timezone
- **WHEN** the backend process runs with `TZ=UTC` at 01:00 IST on 21 July 2026
- **THEN** the prompt states the date as 2026-07-21, not 2026-07-20

## ADDED Requirements

### Requirement: First-name address is rare
When the live context includes the client's first name (CHO-246), the prompt SHALL instruct the model not to start routine replies with that name, to use it at most once per conversation (e.g. a single greeting), and never to open consecutive messages with the name. The name remains available for identity / self-only grounding; over-familiar repeated vocatives are forbidden.

#### Scenario: Name present but not every reply
- **WHEN** the primed live context includes `You are speaking with <FirstName>`
- **THEN** the same block also instructs "at most once" / do not start routine replies with their name
