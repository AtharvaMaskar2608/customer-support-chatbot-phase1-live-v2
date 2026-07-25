# observability-tracing Specification

## Purpose
TBD - created by archiving change cho-275-trace-thread-cost-inr. Update Purpose after archive.
## Requirements
### Requirement: Per-turn execution graph persisted to our own Postgres
Each `POST /api/chat` turn SHALL be captured as an execution graph — an `agent`
root with `llm` / `tool` / `retriever` child spans — and persisted as one row in
an `agent_traces` table in the backend's own Postgres. No trace data SHALL be
sent to any external service. The row SHALL carry the full span tree plus rollup
fields for querying (thread id, user id, model, input/output token counts, tool
names, error flag, latency, and the turn's input and output). Turns of one
conversation SHALL group into a thread via a stable `thread_id`.

#### Scenario: A turn is stored as one row
- **WHEN** a chat turn completes
- **THEN** one `agent_traces` row exists holding the agent/llm/tool/retriever spans and the rollup fields for that turn

#### Scenario: Turns of one conversation share a thread id
- **WHEN** two turns arrive in the same conversation thread (same session, no intervening `reset_thread`)
- **THEN** both rows carry the same `thread_id`, so the conversation can be reconstructed by querying that id

### Requirement: Component spans with correct nesting
The stored graph SHALL nest spans by call structure: `llm` and `tool` spans under
the `agent` root, and a `retriever` span under the `tool` span that triggered it
(a knowledge-base search). Each `llm` span SHALL record the model and the
input/output token counts including the prompt-cache split; each `tool` span the
tool name, masked input, error flag and duration; each `retriever` span the
retrieved chunks as retrieval context and the embedder. Every span SHALL record
its latency.

#### Scenario: KB search nests under its tool span
- **WHEN** the `search_knowledge_base` tool runs a hybrid search
- **THEN** the `retriever` span's parent is that `tool` span, and it carries the fused chunks as retrieval context

#### Scenario: llm span carries the cache split
- **WHEN** a streamed model round completes
- **THEN** its `llm` span records the model plus input, output, and cache-read/cache-creation token counts

### Requirement: No PII or secrets in stored traces
Span inputs/outputs SHALL never contain credentials or personal data (SSO JWT,
session id, client code, PAN, DOB, bank details, email, phone) nor raw upstream
bodies. Credentialed context SHALL never be an observed argument (it rides in a
closure), and a mask SHALL redact credential- and PII-shaped values and
denylisted keys before persistence. The `user_id` SHALL be an HMAC hash of the
client code, and the `thread_id` SHALL be the internal conversation-store
`Thread.id` (see "Trace thread_id matches conversation store"); the raw session
token and the raw client code SHALL never be stored.

#### Scenario: The raw session token is never stored
- **WHEN** a trace row is written
- **THEN** grouping uses the internal conversation `Thread.id` and the hashed client code — the raw session token (a live auth credential) never appears in the table

#### Scenario: Credential- and PII-shaped values are masked
- **WHEN** a span input would contain a JWT, PAN, email, phone, opaque token, or a denylisted key
- **THEN** the mask replaces it with a redaction marker before the row is written

### Requirement: Tracing never degrades the chat path
Instrumentation SHALL NOT change the SSE contract or the assistant's output, and
SHALL add no latency to the response: the row is written by a fire-and-forget
background task created after the turn's final SSE chunk. A tracing or
persistence failure SHALL be logged and dropped, never surfaced as a chat error.
Tracing SHALL be config-gated (default on) and a no-op when disabled or when no
DB pool is available.

#### Scenario: The reply is not delayed by persistence
- **WHEN** a turn is traced
- **THEN** the SSE events and streaming are identical to the untraced path, and the DB write happens after the reply has been sent

#### Scenario: A persistence failure does not break chat
- **WHEN** writing the trace row raises
- **THEN** the error is logged (type only) and the chat response is unaffected

#### Scenario: No-op without a pool
- **WHEN** the DB pool is unavailable
- **THEN** the observe wrappers pass through and the turn behaves exactly as untraced

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
