# conversation-store Specification

## Purpose
TBD - created by archiving change cho-213-agentic-loop. Update Purpose after archive.
## Requirements
### Requirement: Wire-faithful persistent transcript
Conversations SHALL be persisted in Postgres as `threads` (one per widget session: session id, client code, status `active|resolved|escalated|expired`, prompt hash, timestamps) and `turns` (strictly ordered by per-thread `seq`; role `user|assistant` faithful to the wire — tool results ride in user-role turns; kind `user_text|assistant_text|assistant_tool_use|tool_result|flow_event`; `content` as the exact Anthropic content-block array in JSONB; `meta` carrying model id, stop_reason, token usage and latency for assistant turns, tool name / is_error / duration for tool results). Replaying a thread's turns in `seq` order SHALL reconstruct the messages array byte-identically to what was sent to the model.

#### Scenario: Lossless replay
- **WHEN** a thread with tool calls is loaded from the store after a backend restart
- **THEN** the reconstructed messages array continues the conversation without the model losing any tool_use/tool_result context

#### Scenario: Tool call captured for training
- **WHEN** an assistant message containing a `tool_use` block is received from the model
- **THEN** it is stored as its own turn with kind `assistant_tool_use` and the unmodified block content

### Requirement: Prompt snapshots make threads self-contained
The active system prompt and tool schemas SHALL be hashed at startup and upserted into a `prompt_snapshots` table (hash → full system text + tool schema JSON); every thread SHALL record the hash it ran under, so that any thread can later be exported as a complete `{system, tools, messages}` training example without external context.

#### Scenario: Prompt version change
- **WHEN** the backend deploys with a changed system prompt
- **THEN** a new snapshot row exists and new threads reference the new hash while old threads keep the old one

### Requirement: Per-step asynchronous writes through a single owner
A turn SHALL be enqueued for persistence at every step boundary — user message received, every model message (including intermediate tool-use messages), every tool result — with `seq` assigned synchronously at enqueue time. Writes SHALL be performed exclusively by one long-lived background asyncio task consuming a bounded queue FIFO; the chat request path SHALL never await a database write. On graceful shutdown the queue SHALL be drained before the pool closes.

#### Scenario: Chat unaffected by DB latency
- **WHEN** a database insert takes arbitrarily long
- **THEN** in-flight chat requests complete without waiting on it

#### Scenario: Ordered rows
- **WHEN** four turns of one exchange are enqueued in wire order
- **THEN** they persist with strictly increasing `seq` reflecting that order

### Requirement: In-memory authoritative hot path with degraded persistence
The active thread SHALL be served from an in-memory store keyed by session id; the database is read only on cache miss (e.g. restart). If the queue is full or the database is unreachable, the enqueue SHALL not block or fail the chat request: the event SHALL be counted and logged (no verbatim user text in logs) and chat SHALL continue with persistence degraded to best-effort.

#### Scenario: DB outage
- **WHEN** the Postgres tunnel is down mid-conversation
- **THEN** the user conversation continues normally and dropped-write metrics increment

#### Scenario: Restart recovery
- **WHEN** the backend restarts and the user sends the next message
- **THEN** the thread rehydrates from the store, losing at most the single in-flight step from before the restart

### Requirement: Retention and content hygiene
The store SHALL retain threads indefinitely (redaction/anonymization happens at training-export time, out of scope here). Stored content SHALL never include credentials, credentialed URLs, or raw upstream response bodies — tool_result content is limited to the normalized envelopes the routes already expose. Counters (clarify, task-turn, session-turn) SHALL be derived from turns, never stored as columns.

#### Scenario: No credentials at rest
- **WHEN** any thread's turns are inspected
- **THEN** no SSO JWT, SessionId, or upstream URL appears in `content` or `meta`

