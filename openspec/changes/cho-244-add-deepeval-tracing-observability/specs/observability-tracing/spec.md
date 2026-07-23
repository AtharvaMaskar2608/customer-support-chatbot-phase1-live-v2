# observability-tracing

## ADDED Requirements

### Requirement: Config-gated tracing initialization
The backend SHALL initialize DeepEval tracing once at application startup, and only when tracing is configured — a `CONFIDENT_API_KEY` is present, or tracing is explicitly enabled. When tracing is not configured, instrumentation SHALL be a no-op that adds no latency and changes no behavior. Initialization SHALL be fault-isolated: a failure to configure tracing SHALL be logged and SHALL leave the chat path fully functional.

#### Scenario: Enabled when a key is present
- **WHEN** the app starts with a `CONFIDENT_API_KEY` configured
- **THEN** DeepEval tracing is configured once (mask, environment, sampling rate, key) and turns are traced

#### Scenario: No-op when unconfigured
- **WHEN** the app starts with no `CONFIDENT_API_KEY` and tracing not explicitly enabled
- **THEN** the observe wrappers pass through without creating spans and the chat path is byte-for-byte unchanged

#### Scenario: Init failure never breaks chat
- **WHEN** tracing initialization raises for any reason
- **THEN** the error is logged and `/api/chat` continues to serve normally without tracing

### Requirement: Per-turn agent trace with multi-turn thread stitching
Each `POST /api/chat` turn SHALL be captured as one trace whose root is an `agent` span. The trace SHALL set `thread_id` to the session id and `user_id` to the client code so that every turn of one conversation groups into a single thread. The trace input SHALL be the user's message and the trace output SHALL be the assistant's final text.

#### Scenario: Turns of one session group into a thread
- **WHEN** two `/api/chat` turns arrive with the same `X-Session-Id`
- **THEN** both traces carry that `thread_id` and group into one thread, tagged with the `X-User-Id` as `user_id`

### Requirement: Component spans for llm, tool, and retriever steps
Within the agent trace, the backend SHALL record: an `llm` span for each streamed model round carrying the model name and input/output token counts; a `tool` span for each tool dispatch (including parallel tool rounds); and a `retriever` span for a knowledge-base search carrying the retrieved chunks as `retrieval_context`.

#### Scenario: Streamed round produces an llm span with usage
- **WHEN** a model round completes
- **THEN** its `llm` span records the model and the input/output token counts from the final message usage

#### Scenario: KB search produces a retriever span with context
- **WHEN** the `search_knowledge_base` tool runs a hybrid search
- **THEN** a `retriever` span nested under that tool span records the fused chunks as `retrieval_context`

### Requirement: No PII or secrets in traces
Span and trace inputs/outputs SHALL never contain credentials or personal data — the SSO JWT, session id, client code, PAN, DOB, bank details, email, or phone number — nor raw upstream response bodies. This SHALL be enforced by two layers: observed functions receive only safe arguments (credentialed context is passed via closure, never as an observed parameter), and a global mask redacts credential- and PII-shaped values (and denylisted keys) from all span data before export.

#### Scenario: Credentialed context is never captured
- **WHEN** a tool or retriever span is recorded
- **THEN** the span input contains only safe values (tool name, model-supplied parameters, or the search query) and never the `ctx` object, SSO JWT, session id, or client code

#### Scenario: Mask redacts credential- and PII-shaped values
- **WHEN** a value that looks like a JWT, PAN, email, phone, or an opaque token — or sits under a denylisted key — would be exported
- **THEN** the mask replaces it with a redaction marker before the data leaves the process

### Requirement: Tracing never degrades the chat path
Instrumentation SHALL NOT change the SSE event contract or the assistant's output, SHALL NOT add latency to the response (traces export on a background thread), and a tracing-layer error SHALL NOT surface as a chat error.

#### Scenario: Streaming is unaffected
- **WHEN** a turn is traced
- **THEN** the SSE `text`/`tool`/`artifact`/`done` events are identical to the untraced path and text still streams delta-by-delta as it arrives
