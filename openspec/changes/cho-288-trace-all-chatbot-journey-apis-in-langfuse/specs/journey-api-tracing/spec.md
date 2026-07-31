## ADDED Requirements

### Requirement: Journey APIs emit Langfuse observations
When Langfuse tracing is enabled, each in-scope user-journey HTTP API SHALL emit a best-effort Langfuse observation named for that route. In-scope routes are: greeting, what's-new, chat reset (Main Menu), feedback, ticket, report pnl/ledger/tax, contract-notes list/download, report file download, and data holdings/money/brokerage. Out-of-scope routes (health, admin traces/threads, playground) SHALL NOT be instrumented by this capability. Observation failures SHALL NOT change the HTTP status or response body.

#### Scenario: Chip-driven raise ticket is visible in Langfuse
- **WHEN** `POST /api/ticket` succeeds with the mirror enabled
- **THEN** Langfuse receives an observation for that request carrying `ticket_id` in metadata (and compact output), under the journey identity mapping

#### Scenario: Main Menu is traced
- **WHEN** the user triggers Main Menu and `POST /api/chat/reset` completes with the mirror enabled
- **THEN** Langfuse receives an `api.chat_reset` (or equivalent) observation for that request with the prior and/or new `thread_id` in metadata when known

#### Scenario: A data/report chip hit is traced
- **WHEN** a holdings/money/brokerage or report REST route completes with the mirror enabled
- **THEN** Langfuse receives a route-named observation for that request even though no LLM tool span ran

#### Scenario: Instrumentation never breaks the journey
- **WHEN** Langfuse export raises during any journey API
- **THEN** the API still returns its normal success or domain error response

### Requirement: Journey identity uses hashed FinX session and Thread metadata
For journey API observations, Langfuse `session.id` SHALL be a salted HMAC of the FinX SessionId when that header is present. The conversation-store `Thread.id` SHALL appear as metadata `thread_id` when known. Langfuse `user.id` SHALL be the raw client code when present. The raw FinX SessionId SHALL never appear in Langfuse fields, inputs, outputs, or metadata.

#### Scenario: Session is hashed, thread is metadata
- **WHEN** a journey API observation is emitted with both `X-Session-Id` and a resolved Thread
- **THEN** Langfuse `session.id` equals the HMAC of the FinX SessionId, metadata includes `thread_id` equal to `Thread.id`, and the raw SessionId appears nowhere

#### Scenario: What's New without credentials still works
- **WHEN** `GET /api/whats-new` is called without session headers
- **THEN** the endpoint returns content normally; any observation is best-effort and MUST NOT require identity
