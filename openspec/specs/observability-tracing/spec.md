# observability-tracing Specification

## Purpose
TBD - created by archiving change cho-275-trace-thread-cost-inr. Update Purpose after archive.
## Requirements
### Requirement: Trace thread_id matches conversation store
Each persisted agent turn SHALL set `agent_traces.thread_id` to the active
conversation-store `Thread.id` (bound after `store.get_thread` during the
turn), not an HMAC of the FinX/session key. A Main Menu or cold-load
`reset_thread` that mints a new store thread SHALL therefore start a new
trace/cost bucket. `user_id` SHALL remain an HMAC-hashed client code (not the
raw FinX client id).

#### Scenario: Reset starts a new trace thread bucket
- **WHEN** the conversation store resets the session and the next chat turn
  loads a new `Thread.id`
- **THEN** the persisted trace for that turn carries the new id, separate from
  prior turns under the old id

#### Scenario: Client code stays hashed
- **WHEN** a turn is persisted
- **THEN** `user_id` is the stable HMAC short-hash of the client code and the
  raw client code is not stored

