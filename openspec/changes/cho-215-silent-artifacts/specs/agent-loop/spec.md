# agent-loop (delta)

## MODIFIED Requirements

### Requirement: Tool-use orchestration loop
The backend SHALL expose `POST /api/chat` which appends the user's free-text message to the session's conversation and runs a tool-use loop against the Anthropic Messages API: while the response's `stop_reason` is `tool_use`, every `tool_use` block in that response SHALL be executed, the assistant message SHALL be appended wire-faithfully (content blocks unmodified), and all corresponding `tool_result` blocks SHALL be returned in a single user-role message. After executing a round, the loop SHALL end the turn WITHOUT a continuation model call when every call in the round succeeded, every successful call emitted an artifact event (form handover, data card, or file card), and at least one artifact was emitted — the artifact is the answer; connective copy is the frontend's job and post-artifact narration is structurally prevented. In every other case (any errored call, any successful non-artifact call such as KB search or a contract-note list, or a mixed round) the model SHALL be called again as before. The loop otherwise ends when `stop_reason` is `end_turn` or when the configurable inner-round guard (default 5) is reached. The system prompt SHALL instruct the model to call artifact-producing tools immediately with no preamble text, to never use spatial UI language ("above"/"below" — the model cannot know layout), and to never restate data an artifact already shows.

#### Scenario: Artifact-only round ends the turn silently
- **WHEN** the model's round contains a single successful `open_report_form` (or `get_brokerage_rates`) call
- **THEN** the stream carries the `tool` and `artifact` events followed directly by the terminal `done` event — no further model call is made and no narration text is generated

#### Scenario: KB round still narrates
- **WHEN** the model's round contains a successful `search_knowledge_base` call
- **THEN** the loop calls the model again and the answer streams as text, exactly as before

#### Scenario: Errored round still narrates
- **WHEN** a tool call in the round returns `is_error: true`
- **THEN** the loop calls the model again so it can explain the failure (including the AUTH_EXPIRED narrate-then-error path)

#### Scenario: Mixed round still narrates
- **WHEN** one round contains a successful data-card call AND a successful KB search in parallel
- **THEN** the loop continues to the model, which narrates the KB result without restating the card's contents

#### Scenario: Short-circuited transcript continues cleanly
- **WHEN** a turn ended on a short-circuited form-open and the user sends the next message
- **THEN** the replayed conversation is accepted by the API (the trailing tool_result merges with the new user text) and the model retains the tool context

#### Scenario: ITR request opens the tax form
- **WHEN** the user writes "Can you fetch my ITR" with no parameters
- **THEN** the model calls `open_report_form` with flow `tax` and the capital-gains form loads — no prose questions about FY, format, or delivery

### Requirement: Conversation caps and escalation suggestion
The loop SHALL enforce, in code and independent of model behavior, three env-configurable caps evaluated per incoming user message: (1) at most `CLARIFY_CAP` (default 2) clarifying questions per task window; (2) at most `TASK_TURN_CAP` (default **100**) user turns per task window; (3) at most `SESSION_TURN_CAP` (default **100**) user turns per session — defaults sized for the ~8-hour life of a widget session thread. A task window is the span of conversation since the last resolution event — an assistant turn that completed with at least one successful (`is_error: false`) tool call, which includes a successful `open_report_form` call — and a resolution event SHALL reset the per-task counters. Escalation injection SHALL be trip-specific: a clarify-cap or task-turn trip SHALL instruct the model to stop asking and offer escalation to a human; a session-backstop trip alone SHALL instruct the model to offer a human only if the user appears stuck or unsatisfied, and otherwise answer normally.

#### Scenario: Clarify cap trips
- **WHEN** the model has asked 2 clarifying questions in the current task window and required parameters are still missing
- **THEN** the next reply offers escalation instead of a third question

#### Scenario: Normal-length sessions never trip the backstop
- **WHEN** a user sends their 25th message of an 8-hour session with tasks resolving normally
- **THEN** no cap has tripped and no escalation instruction of any kind is injected

#### Scenario: Session backstop still guards the rephrase loop
- **WHEN** the user is on their 100th message and visibly stuck rephrasing the same unresolved question
- **THEN** the reply includes the escalation offer
