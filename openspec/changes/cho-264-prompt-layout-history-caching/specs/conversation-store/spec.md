# conversation-store

## MODIFIED Requirements

### Requirement: Wire-faithful persistent transcript
Conversations SHALL be persisted in Postgres as `threads` (one per widget session: session id, client code, status `active|resolved|escalated|expired`, prompt hash, timestamps) and `turns` (strictly ordered by per-thread `seq`; role `user|assistant` faithful to the wire — tool results ride in user-role turns; kind `user_text|assistant_text|assistant_tool_use|tool_result|flow_event`; `content` as the exact Anthropic content-block array in JSONB; `meta` carrying model id, stop_reason, token usage and latency for assistant turns, tool name / is_error / duration for tool results). Replaying a thread's turns in `seq` order SHALL reconstruct the LOSSLESS messages array byte-identically to the stored turns — that array is the training/audit artifact and the thread's canonical content. The array actually sent to the model MAY differ from the lossless array ONLY by additive, non-semantic request metadata (prompt-cache `cache_control` markers) and, when that capability is enabled, by a deterministic curated projection of spent tool results specified in its own requirement. The store SHALL NEVER be mutated to produce either: request-time additions SHALL be applied to copies, so a thread's stored turns, its persisted `turns` rows, the ticket transcript, and a post-restart rehydrate all stay byte-faithful to the content they recorded, and replaying the same thread before and after a model call yields identical bytes. This requirement owns the lossless-replay invariant; the curation rules themselves belong to their own requirement.

#### Scenario: Lossless replay
- **WHEN** a thread with tool calls is loaded from the store after a backend restart
- **THEN** the reconstructed messages array continues the conversation without the model losing any tool_use/tool_result context

#### Scenario: Tool call captured for training
- **WHEN** an assistant message containing a `tool_use` block is received from the model
- **THEN** it is stored as its own turn with kind `assistant_tool_use` and the unmodified block content

#### Scenario: Cache markers never reach the store
- **WHEN** a model call places a prompt-cache breakpoint on the conversation tip
- **THEN** no `cache_control` key appears in the thread's stored turns, in the persisted `turns` rows, or in the ticket transcript, and a replay taken after the call is byte-identical to one taken before it

#### Scenario: The model-facing array differs only additively
- **WHEN** the model-facing array is compared block by block with the lossless replay of the same turns
- **THEN** the only differences are additive request metadata (and, when curation is enabled, its deterministic projection) — no stored block's recorded content is altered in place
