# observability-tracing

## ADDED Requirements

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

#### Scenario: Turns of one session share a thread id
- **WHEN** two turns arrive with the same `X-Session-Id`
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
denylisted keys before persistence. The `thread_id` and `user_id` SHALL be HMAC
hashes of the session id and client code, never the raw values.

#### Scenario: Thread id is a hash, not the raw session token
- **WHEN** a trace row is written
- **THEN** its `thread_id` is a hash of the session id — the raw session token (a live auth credential) never appears in the table

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
