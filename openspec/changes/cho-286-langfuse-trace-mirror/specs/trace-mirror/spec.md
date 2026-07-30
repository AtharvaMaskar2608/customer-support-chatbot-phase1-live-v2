## ADDED Requirements

### Requirement: The assembled span tree is mirrored to a self-hosted Langfuse instance
Every span the tracing layer opens for a `/api/chat` turn SHALL, when the mirror is enabled, also be emitted to a self-hosted Langfuse instance, with the same nesting the Postgres row records: an `agent` root, `llm` rounds beneath it, `tool` spans, and `retriever` spans beneath their tool. Emission SHALL originate from the same `observe_*` helpers that build the internal span tree, so the two sinks cannot describe different shapes. The Langfuse instance SHALL be self-hosted; trace data SHALL NOT be sent to a third-party hosted service.

#### Scenario: A turn produces a matching tree in both sinks
- **WHEN** a chat turn runs with the mirror enabled and calls a tool that performs a KB search
- **THEN** the Langfuse trace carries the same span names and parent-child relationships as the `agent_traces` row for that turn

#### Scenario: The mirror adds no instrumentation of its own
- **WHEN** a code path has no span in the Postgres trace
- **THEN** it has no observation in Langfuse either — the mirror never observes anything the system of record does not

### Requirement: Identity mapping keeps the two stores joinable
The Langfuse `session_id` SHALL be the conversation-store `Thread.id` — the same value the Postgres row stores as `thread_id` — and the Langfuse `user_id` SHALL be the same salted HMAC of the client code the Postgres row stores. Raw identifiers SHALL NOT be sent. The FinX SSO session id is a live credential (the report endpoints authenticate with it) and SHALL NOT be sent to Langfuse in any form; where correlation to an SSO session is required, a salted HMAC of it MAY be carried in metadata, never the value itself.

#### Scenario: A Langfuse trace can be pivoted to its Postgres row
- **WHEN** an operator opens a trace in Langfuse and reads its session and user identifiers
- **THEN** those identifiers match the `thread_id` and `user_id` of the corresponding `agent_traces` row exactly, so the same query finds it in either store

#### Scenario: Main Menu starts a new Langfuse session
- **WHEN** the user returns to Main Menu and `reset_thread` mints a new conversation thread
- **THEN** subsequent turns carry the new thread id as the Langfuse session id, so a session never rolls up across a reset

#### Scenario: The SSO session token never reaches Langfuse
- **WHEN** any span is exported to Langfuse
- **THEN** the raw SSO session id and raw client code appear nowhere in it — not in the session field, not in inputs or outputs, not in metadata

### Requirement: The mirror is subordinate to the system of record
The mirror SHALL be controlled by an environment flag that is **off by default**, and SHALL be best-effort in every respect. A Langfuse instance that is unreachable, slow, misconfigured, or absent SHALL NOT change the chat response, SHALL NOT delay it, and SHALL NOT prevent or alter the write to `agent_traces`. Failures SHALL be logged by exception type only, never with span contents, and SHALL NOT propagate to the request.

#### Scenario: Langfuse being down does not affect a turn
- **WHEN** every Langfuse export call raises
- **THEN** the chat turn streams its reply normally and the `agent_traces` row is written complete

#### Scenario: The mirror is inert without configuration
- **WHEN** the flag is unset or the credentials are missing
- **THEN** no Langfuse client is constructed, no network call is attempted, and tracing behaves exactly as it did before this change

#### Scenario: Disabling the mirror is a config change, not a deploy
- **WHEN** the flag is set to off and the container is recreated
- **THEN** Postgres tracing continues unchanged with no residual state to unwind
