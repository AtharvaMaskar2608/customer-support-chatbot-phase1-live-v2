## MODIFIED Requirements

### Requirement: The assembled span tree is mirrored to a self-hosted Langfuse instance
Every span the tracing layer opens for a `/api/chat` turn SHALL, when the mirror is enabled, also be emitted to a self-hosted Langfuse instance, with the same nesting the Postgres row records: an `agent` root, `llm` rounds beneath it, `tool` spans, and `retriever` spans beneath their tool. Emission SHALL originate from the same `observe_*` helpers that build the internal span tree, so the two sinks cannot describe different shapes. The Langfuse instance SHALL be self-hosted; trace data SHALL NOT be sent to a third-party hosted service. Root metadata (platform, entry point, bot versions, turn_seq, latency_ms, ticket_id, lf_trace_id) SHALL be mirrored with the root span when present on the assembled tree.

#### Scenario: A turn produces a matching tree in both sinks
- **WHEN** a chat turn runs with the mirror enabled and calls a tool that performs a KB search
- **THEN** the Langfuse trace carries the same span names and parent-child relationships as the `agent_traces` row for that turn

#### Scenario: The mirror adds no instrumentation of its own
- **WHEN** a code path has no span in the Postgres trace
- **THEN** it has no observation in Langfuse either — the mirror never observes anything the system of record does not

#### Scenario: Root context metadata is mirrored
- **WHEN** the assembled root carries context metadata keys
- **THEN** the Langfuse root observation carries the same keys
