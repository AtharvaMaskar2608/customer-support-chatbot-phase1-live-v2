# agent-tool-registry

## ADDED Requirements

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
