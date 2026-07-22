# agent-loop

## ADDED Requirements

### Requirement: The prompt carries a live IST status line
The primed turn SHALL end with a status line stating the current IST time, weekday, and date, together with the market state and — when the market is open — the session's close time. This replaces the date-only line, so the model can answer wall-clock questions such as whether a same-day cutoff has passed, rather than only resolving relative dates.

#### Scenario: Open market with a close time
- **WHEN** a request is made at 14:47 IST on an ordinary trading Monday
- **THEN** the prompt states the current IST time and date, that markets are open, and when the session closes

#### Scenario: Holiday state is explicit
- **WHEN** a request is made on a weekday exchange holiday
- **THEN** the prompt states that the market is closed for a holiday, rather than implying an ordinary closed session

#### Scenario: Cutoff question is answerable
- **WHEN** a customer asks at 15:20 IST whether they can still act before the session ends
- **THEN** the model has the clock and the close time available in its prompt and can answer without guessing

### Requirement: The live status line is the last content block of the primed turn
The primed user turn SHALL be composed of at least two content blocks: the frozen instructions and few-shot examples first, carrying the prompt-cache breakpoint, and the live status line last. No volatile value may appear before a cache breakpoint.

#### Scenario: Frozen prefix stays byte-stable across requests
- **WHEN** two requests are made minutes apart on the same day
- **THEN** every content block up to and including the cache breakpoint is byte-identical between them, and only the final block differs

#### Scenario: Recorded prompt snapshot stays time-stable
- **WHEN** the prompt snapshot is recorded for hashing
- **THEN** it contains the status line's placeholders rather than a rendered time, so the hash does not change from one minute to the next

## MODIFIED Requirements

### Requirement: Slot filling without invention
The system prompt SHALL instruct the model to never invent values for required tool parameters and SHALL include the current date **resolved in IST (`Asia/Kolkata`)** so relative date expressions resolve to `YYYY-MM-DD`. The date MUST be computed from an explicitly named zone, never inherited from the host or container timezone, and the report-form validator MUST resolve "today" on the same clock so the prompt and the validator can never disagree. For the four report flows (P&L, ledger, capital gains, contract notes) the model SHALL NOT ask for parameters in prose: when any parameter is missing it SHALL call `open_report_form` carrying only the values the user actually stated (none stated ⇒ flow key alone), and when every parameter including the delivery method is explicitly known — from the user's words or from a prior flow event in the thread — it SHALL call the report tool directly. Prose clarifying questions (all missing values bundled into one question) remain only for non-report tools.

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
- **WHEN** the backend process runs with `TZ=UTC` at 01:00 IST on 21 July 2026
- **THEN** the prompt states the date as 2026-07-21, not 2026-07-20
