# agent-loop

## MODIFIED Requirements

### Requirement: Tool-use orchestration loop
The backend SHALL expose `POST /api/chat` which appends the user's free-text message to the session's conversation and runs a tool-use loop against the Anthropic Messages API: while the response's `stop_reason` is `tool_use`, every `tool_use` block in that response SHALL be executed, the assistant message SHALL be appended wire-faithfully (content blocks unmodified), and all corresponding `tool_result` blocks SHALL be returned in a single user-role message. After executing a round, the loop SHALL end the turn WITHOUT a continuation model call when every call in the round succeeded, every successful call emitted an artifact event (form handover, data card, or file card), and at least one artifact was emitted — the artifact is the answer; connective copy is the frontend's job and post-artifact narration is structurally prevented. When any call in the round surfaces `AUTH_EXPIRED`, the loop SHALL instead end the turn immediately by emitting the terminal `AUTH_EXPIRED` error event with NO continuation model call — auth expiry is a deterministic, security-sensitive state the model never narrates (the auth-expired `tool_result` is still recorded for byte-faithful replay; the frontend shows fixed session-expired copy and signals the host). In every other case (any errored call that is not auth expiry, any successful non-artifact call such as KB search or a contract-note list, or a mixed round) the model SHALL be called again as before. The loop otherwise ends when `stop_reason` is `end_turn` or when the configurable inner-round guard (default 5) is reached. The system prompt SHALL instruct the model to call artifact-producing tools immediately with no preamble text, to never use spatial UI language ("above"/"below" — the model cannot know layout), and to never restate data an artifact already shows.

#### Scenario: Artifact-only round ends the turn silently
- **WHEN** the model's round contains a single successful `open_report_form` (or `get_brokerage_rates`) call
- **THEN** the stream carries the `tool` and `artifact` events followed directly by the terminal `done` event — no further model call is made and no narration text is generated

#### Scenario: KB round still narrates
- **WHEN** the model's round contains a successful `search_knowledge_base` call
- **THEN** the loop calls the model again and the answer streams as text, exactly as before

#### Scenario: Non-auth errored round still narrates
- **WHEN** a tool call in the round returns `is_error: true` for a non-auth failure (`NO_DATA` or `UPSTREAM_ERROR`)
- **THEN** the loop calls the model again so it can explain the failure to the user in plain language

#### Scenario: Auth expiry short-circuits without narration
- **WHEN** a tool call in the round returns the `AUTH_EXPIRED` error result
- **THEN** the loop emits the terminal `AUTH_EXPIRED` error event immediately, makes no further model call, and generates no narration text

#### Scenario: Mixed round still narrates
- **WHEN** one round contains a successful data-card call AND a successful KB search in parallel
- **THEN** the loop continues to the model, which narrates the KB result without restating the card's contents

#### Scenario: Short-circuited transcript continues cleanly
- **WHEN** a turn ended on a short-circuited form-open and the user sends the next message
- **THEN** the replayed conversation is accepted by the API (the trailing tool_result merges with the new user text) and the model retains the tool context

#### Scenario: ITR request opens the tax form
- **WHEN** the user writes "Can you fetch my ITR" with no parameters
- **THEN** the model calls `open_report_form` with flow `tax` and the capital-gains form loads — no prose questions about FY, format, or delivery
