# context-routing-evals

## ADDED Requirements

### Requirement: Tracked harness, separate invocation, key-gated skip
The routing evals SHALL live in tracked source under `backend/evals/` (a runner, one module per case, shared assertions, and canned fixtures) so the merge gate is reviewable and repeatable. They SHALL NOT run as part of the default `uv run pytest` invocation: the live cases require `ANTHROPIC_API_KEY` and SHALL be started by their own command. When that key is absent every live case SHALL be reported as **skipped** and the runner SHALL exit successfully — a missing key MUST NOT fail the run.

#### Scenario: Default test run is unaffected
- **WHEN** `uv run pytest` runs
- **THEN** no live model call is made by the eval harness and the suite's pass/fail is independent of it

#### Scenario: No API key present
- **WHEN** the runner is invoked with no `ANTHROPIC_API_KEY`
- **THEN** every live case is recorded as skipped, the report says so, and the process exits 0

### Requirement: Seeded history with a substituted tool layer
Each case SHALL construct its prior conversation by appending turns directly through the conversation store (`store.append_turn`) — user text, assistant text, assistant tool_use, tool_result, and flow-event memos — and SHALL generate only the **probe turn** with a live model call. The tool layer SHALL be substituted with a recording double that returns canned envelopes and records every `(tool name, input)` it is asked for, so probe-turn tool calls never reach the Choice APIs, Freshdesk, or Postgres. Cores that are purely local (`open_report_form`, `get_report_columns`) MAY run their real handlers. Consequently the harness SHALL require **no FinX/SSO credentials and no database** — `ANTHROPIC_API_KEY` alone.

#### Scenario: A fourteen-turn thread costs one model call
- **WHEN** a case seeds thirteen prior turns and probes with the fourteenth message
- **THEN** the seeded turns are written through the store with no model call, and only the probe turn calls the model

#### Scenario: No upstream credentials needed
- **WHEN** the probe turn emits a tool call for a credentialed flow (holdings, money, contract notes)
- **THEN** the recording double answers it from a canned envelope, no upstream request is made, and the case still asserts on the emitted tool input

#### Scenario: Assertions read decisions, not upstream success
- **WHEN** a case checks routing
- **THEN** it asserts on the recorded tool calls and the SSE event stream, never on upstream payload success

### Requirement: Every case asserts no abstention
Every case SHALL apply one shared assertion: the probe turn's assistant text MUST NOT match the abstention family — declining to determine, find, or tell; claiming the information is not provided or not available in the chat/conversation history; or claiming no access to it — whenever the information is in fact present in the seeded thread. This assertion SHALL be a single documented constant reused by all cases.

#### Scenario: Abstention is a failure even when routing was right
- **WHEN** the model calls the correct tool but replies that it cannot determine the answer from the conversation history
- **THEN** the case fails on the abstention assertion

#### Scenario: One definition of the phrase family
- **WHEN** the phrase list changes
- **THEN** it changes in exactly one place and every case picks the change up

### Requirement: The seven gate cases
The harness SHALL implement seven cases covering the routing and recall failures this programme exists to fix, each with explicit pass criteria read from recorded tool calls, the SSE stream, and the assistant text.

#### Scenario: E1 — mid-thread report parameters
- **WHEN** a thread with a completed ledger flow (form result plus its flow-event memo) followed by three noisy turns receives "now the same for MTF"
- **THEN** the first recorded tool call is `open_report_form` with `flow` = ledger and `book` = MTF and the date range carried from the memo, and **no** assistant text asking for a report parameter precedes it

#### Scenario: E2 — follow-up after a spent data card
- **WHEN** a thread whose holdings result is no longer verbatim receives a question about those holdings
- **THEN** `get_holdings` is re-called, and the reply contains no figure from the earlier envelope that is absent from the freshly returned one

#### Scenario: E3 — contract-note id fidelity
- **WHEN** a thread whose `list_contract_notes` result is no longer verbatim receives "download the 14 June one"
- **THEN** `download_contract_note` is called with an id that string-matches an id present in the seeded result, and **no** id is emitted that was never in it

#### Scenario: E4 — a fact from turn two recalled at turn fourteen
- **WHEN** the user stated an amount and date at turn 2 and asks for it again at turn 14, after intervening knowledge-base and data-card turns
- **THEN** the reply carries that exact amount and date, and does not abstain

#### Scenario: E5 — the ticket-affirmation guard still rejects
- **WHEN** the model emits `raise_support_ticket` on a thread where the user's latest message neither asks to escalate nor affirms an escalation offer
- **THEN** the call is rejected as an error result that instructs the model to offer instead, and no ticket is filed

#### Scenario: E6 — report columns are never described from memory
- **WHEN** a thread whose `get_report_columns` result is no longer verbatim receives a question about a column's meaning
- **THEN** `get_report_columns` is re-called before any column is described, and the reply uses no column label absent from the fresh result

#### Scenario: E7 — pronoun follow-up after a knowledge-base answer
- **WHEN** a thread with a knowledge-base exchange followed by one intervening turn receives "tell me more about that"
- **THEN** `search_knowledge_base` is re-issued with a query containing a content word from that earlier exchange rather than a bare pronoun, and the reply does not abstain

### Requirement: The contract-note id case states its expiry precondition
Contract-note ids are session-bound capability tokens that expire after **600 seconds**. The id case SHALL therefore assert **id fidelity only** — every emitted id matches a seeded id, and no id is invented — and SHALL NOT be read as evidence that the download path works. The report SHALL record the elapsed seconds between seeding the note list and issuing the probe, so a reviewer can tell whether a run against real (non-synthetic) ids fell inside the window. The harness SHALL also cover the recovery path: a bounced download caused by an expired id must lead the model to re-list the notes rather than invent an id.

#### Scenario: Elapsed time is recorded, not assumed
- **WHEN** the id case completes
- **THEN** the report carries the seed→probe elapsed seconds for that attempt

#### Scenario: Expired id recovers by re-listing
- **WHEN** a download bounces because its id has expired
- **THEN** the model calls `list_contract_notes` again and never emits an id that was not returned to it

### Requirement: The ticket guard is proven by unit test, never by a live raise
Because ticket creation has **no dry-run mode**, the ticket-affirmation case SHALL run in the normal test suite against a mocked helpdesk, never as a live eval. It SHALL assert both that the unaffirmed call is rejected as an error result **and** that zero ticket-creation requests were issued, in both curation-flag states.

#### Scenario: Zero helpdesk requests on rejection
- **WHEN** the unaffirmed `raise_support_ticket` case runs
- **THEN** the mocked ticket-creation endpoint records no requests at all

#### Scenario: Identical behaviour in both flag states
- **WHEN** the case runs with context curation off and on
- **THEN** the rejection and the zero-request assertion hold identically

### Requirement: Flag-matrix sweep with cost delta and a written report
The runner SHALL execute every case in **both** curation-flag states with **3 attempts** each, and SHALL capture per-attempt model usage in-process (input, output, cache-read and cache-creation tokens, priced to INR by the existing cost model) without requiring a live trace database. It SHALL write a machine-readable report plus a readable markdown twin per sweep, carrying per-case pass rate, first-failure detail, and the flag-on versus flag-off cost delta. When the curation flag does not yet exist, both arms SHALL still run and the sweep SHALL be recorded as a baseline.

#### Scenario: Both arms, three attempts
- **WHEN** a full sweep runs
- **THEN** each case has three recorded attempts per flag state, with the per-arm token and INR totals

#### Scenario: Report is a file, not terminal output
- **WHEN** a sweep finishes
- **THEN** a timestamped JSON report and a markdown twin exist on disk and are attachable to the change's Linear issue

#### Scenario: Baseline before curation exists
- **WHEN** the sweep runs before the curation flag is implemented
- **THEN** both arms produce identical results and the report is labelled a baseline rather than a comparison

### Requirement: Explicit merge gate thresholds
The sweep SHALL be evaluated against fixed thresholds rather than reviewer judgement: the id case and the ticket-guard case SHALL pass **3 of 3** attempts; every other case SHALL pass at least **2 of 3** and SHALL NOT regress against the flag-off arm; and **zero** abstention matches SHALL occur in any case or arm. The runner SHALL exit non-zero when any threshold is missed.

#### Scenario: A hard-fail case at two of three
- **WHEN** the id case passes only 2 of 3 attempts
- **THEN** the gate fails and the runner exits non-zero

#### Scenario: A regression against the baseline arm
- **WHEN** a case passes 2 of 3 with curation on but 3 of 3 with curation off
- **THEN** the report flags a regression and the gate fails
