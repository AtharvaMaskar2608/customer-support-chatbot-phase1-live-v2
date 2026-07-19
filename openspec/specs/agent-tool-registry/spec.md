# agent-tool-registry Specification

## Purpose
TBD - created by archiving change cho-213-agentic-loop. Update Purpose after archive.
## Requirements
### Requirement: Registry of function tools over shared flow cores
The backend SHALL provide a tool registry mapping each tool name to a JSON-Schema input definition and an async Python handler. Handlers SHALL be the same core functions the existing REST routes call — extracted from the route bodies, never duplicated and never invoked over HTTP. The registry SHALL cover, at minimum: P&L report, Ledger report, Tax (capital gains) report, Contract Notes report, Holdings, Pay-in/Pay-out, Brokerage slab, and KB search.

#### Scenario: One core, two entry points
- **WHEN** the P&L flow is exercised via `POST /api/report/pnl` and via the agent's `get_pnl_report` tool with identical parameters and credentials
- **THEN** both paths execute the same core function and produce the same normalized envelope

#### Scenario: Dispatch by name
- **WHEN** the loop receives a `tool_use` block naming a registered tool
- **THEN** the registry resolves and invokes its handler with the block's input and the request context

#### Scenario: Unknown tool
- **WHEN** the model emits a tool name not present in the registry
- **THEN** the dispatcher returns `is_error: true` ("unknown tool") instead of raising

### Requirement: Route contracts preserved through extraction
Extracting core functions SHALL NOT change any existing route's request schema, response shape, status codes, credential handling, or logging behavior. The existing route test suites SHALL pass unchanged after the refactor.

#### Scenario: Regression gate
- **WHEN** the backend test suite runs after the core extraction
- **THEN** all pre-existing flow and route tests pass without modification

### Requirement: Handlers return model-consumable results
Each handler SHALL return the flow's normalized, field-whitelisted envelope on success, and a structured error (mapped from the existing `ResultKind` outcomes and validation failures) on failure — never raw upstream bodies, never raised exceptions across the dispatch boundary, and never credentialed URLs. Report-producing handlers SHALL deliver files via the existing token store and return the `fileToken` reference, not file bytes.

#### Scenario: Whitelisted payload in transcript
- **WHEN** the Holdings tool succeeds
- **THEN** its tool_result contains only the fields the Holdings route already exposes to the frontend

#### Scenario: Report file via token
- **WHEN** the P&L tool succeeds with delivery "download"
- **THEN** the tool_result carries the fileToken and file metadata, and the artifact is downloadable through the existing `/api/report/file/{token}` endpoint

### Requirement: Context injection
Handlers SHALL receive a per-request context object carrying the authenticated credentials (SessionId, SSO JWT, client code) and shared resources (HTTP client, Postgres pool, report file store). Tool schemas SHALL NOT define parameters for any of these values.

#### Scenario: KB tool uses pool from context
- **WHEN** the KB search tool executes
- **THEN** it queries through the pool provided in context, and returns the degraded FTS-only or unavailable outcome exactly as the `/api/kb/search` route would

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

### Requirement: Escalation tool
The registry SHALL include a `raise_support_ticket` tool whose input schema carries only the user-intent field `reason` (short required string summarizing the issue in the user's terms). The system prompt SHALL direct the model to call it when the user asks for a human, accepts an escalation offer, or is unresolvable after clarification — never preemptively, and never twice for the same issue when a flow-event memo already records a raised ticket. Credentials and client identity are ctx-injected server-side per the registry's standing contract.

#### Scenario: Reason is the only model-controlled field
- **WHEN** the model calls `raise_support_ticket` with extra fields injected into the input
- **THEN** only `reason` is honored; identity and routing come from the request context and code constants

#### Scenario: No duplicate raise
- **WHEN** a flow-event memo already records ticket #N for the current issue and the user repeats the complaint
- **THEN** the model references the existing ticket instead of calling the tool again

