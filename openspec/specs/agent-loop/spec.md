# agent-loop Specification

## Purpose
TBD - created by archiving change cho-213-agentic-loop. Update Purpose after archive.
## Requirements
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

### Requirement: Tool failures are recoverable, not fatal
A tool handler failure (validation error, upstream failure, unexpected exception) SHALL be returned to the model as a `tool_result` with `is_error: true` and an actionable message; it SHALL NOT abort the loop or surface a 5xx to the user for that turn.

#### Scenario: Missing parameter bounced
- **WHEN** the model calls the P&L tool without a valid `fromDate`
- **THEN** the handler returns `is_error: true` with a message naming the missing/invalid field and the model's next message asks the user for it

#### Scenario: Upstream failure narrated
- **WHEN** a tool's upstream call returns the normalized `NO_DATA` outcome
- **THEN** the model receives it as an error tool_result and explains the outcome to the user in plain language

### Requirement: Credential isolation
Tool input schemas SHALL contain only user-intent parameters. Credentials (SSO JWT, SessionId, client code) SHALL be taken exclusively from the authenticated request headers of `/api/chat` into a per-request context injected by the dispatcher; no value originating from model output SHALL ever be used as a credential or client identifier. Requests missing credentials SHALL return the pinned `MISSING_CREDENTIALS` error without calling the model.

#### Scenario: Model cannot redirect identity
- **WHEN** the model emits a tool call whose input contains an unexpected client-identifier field
- **THEN** the field is ignored and the tool executes against the header-derived client code

#### Scenario: Missing headers
- **WHEN** `/api/chat` is called without the auth headers
- **THEN** the response is HTTP 400 `{"error": "MISSING_CREDENTIALS"}` and no model call is made

### Requirement: Slot filling without invention
The system prompt SHALL instruct the model to never invent values for required tool parameters and SHALL include today's date so relative date expressions resolve to `YYYY-MM-DD`. For the four report flows (P&L, ledger, capital gains, contract notes) the model SHALL NOT ask for parameters in prose: when any parameter is missing it SHALL call `open_report_form` carrying only the values the user actually stated (none stated ⇒ flow key alone), and when every parameter including the delivery method is explicitly known — from the user's words or from a prior flow event in the thread — it SHALL call the report tool directly. Prose clarifying questions (all missing values bundled into one question) remain only for non-report tools.

#### Scenario: Nothing mentioned loads the full form
- **WHEN** the user writes "get my P&L" with no parameters
- **THEN** the model calls `open_report_form` with only the flow key, and the widget boots the full guided P&L flow from its first slot — no value assumed, no prose question asked

#### Scenario: Partial mention pre-fills the form
- **WHEN** the user writes "P&L for equity"
- **THEN** the model calls `open_report_form` with the flow key and segment only, and the widget opens with the segment chip filled, asking for the date range next

#### Scenario: Full mention still executes directly
- **WHEN** the user writes "Get my F&O P&L for 1 to 30 June 2026, download it here"
- **THEN** the model calls the P&L report tool directly and the file card is produced with no form

#### Scenario: Relative dates resolve before seeding
- **WHEN** the user writes "equity P&L for last month"
- **THEN** the `open_report_form` call carries the concrete `YYYY-MM-DD` range for the previous calendar month

#### Scenario: Follow-up reuses flow-event context
- **WHEN** a flow event records a completed June Equity P&L download and the user writes "now the same for F&O"
- **THEN** the model calls `open_report_form` seeded with segment F&O and the June date range, landing the user on the delivery step

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

### Requirement: Compliance-constrained answers
The system prompt SHALL constrain the agent to factual support answers: no investment advice, no contractual commitments or promises on behalf of Choice, and resistance to instruction-override attempts in user text. These constraints SHALL apply to every reply, including tool-result summaries.

#### Scenario: Advice request deflected
- **WHEN** the user asks "should I buy more of this stock?"
- **THEN** the reply declines to advise and redirects to factual account/support capabilities

### Requirement: Streamed chat response (SSE)
`/api/chat` SHALL respond as a Server-Sent Events stream (`text/event-stream`). Assistant text SHALL be forwarded as `text` events carrying deltas while the model generates (each loop round runs via the Anthropic SDK's streaming interface); tool activity SHALL surface as `tool` events (name + started/finished + error flag); successful tool results SHALL be emitted immediately as `artifact` events — file artifacts referencing the existing `fileToken` delivery mechanism, data artifacts carrying the normalized envelopes, and flow artifacts (`kind: "flow"`) carrying the flow key plus the validated seed for a guided-form handover — and the stream SHALL terminate with a `done` event carrying the thread's turn counters. Only assistant text streams as deltas; tool rounds never leak raw model deltas. Missing credentials SHALL be rejected pre-stream as HTTP 400 `MISSING_CREDENTIALS`; failures after the stream opens (Anthropic unavailable, guard exhaustion without text) SHALL be emitted as an `error` event with the pinned shape (`AGENT_UNAVAILABLE`; `AUTH_EXPIRED` passthrough) so the shell can react.

#### Scenario: Form handover emitted as flow artifact
- **WHEN** the model calls `open_report_form` for a P&L request that mentioned only the segment
- **THEN** the stream carries `artifact {kind: "flow", flowKey: "pnl", seed: {segment: "Equity"}}` followed by a short streamed closing line and the terminal `done` event

#### Scenario: Text streams as it generates
- **WHEN** the agent composes a reply
- **THEN** the widget receives `text` delta events progressively rather than one final payload

#### Scenario: Report produced in chat
- **WHEN** the agent completes a P&L request with delivery "download"
- **THEN** an `artifact` event carries the fileToken, name, size label and format for the existing download card, followed by streamed reply text and a terminal `done` event

#### Scenario: Anthropic outage
- **WHEN** the Messages API call fails after retries
- **THEN** the stream emits `error` `{"error": "AGENT_UNAVAILABLE"}` and existing guided flows remain unaffected

### Requirement: Configurable model and thinking
The loop's model SHALL be selected by `AGENT_MODEL` (`claude-haiku-4-5` default, or `claude-sonnet-4-6`) and its reasoning by `AGENT_THINKING` (`off` default, or `minimal`), both env-overridable and read at call time. The thinking parameter SHALL be resolved per model: `off` omits the `thinking` parameter on both models; `minimal` maps to `{type:"enabled", budget_tokens:1024}` on `claude-haiku-4-5` (the API minimum) and to `{type:"adaptive"}` with `output_config.effort:"low"` on `claude-sonnet-4-6` (where `budget_tokens` is deprecated). No other thinking configuration SHALL be sent.

#### Scenario: Default configuration
- **WHEN** no agent env vars are set
- **THEN** requests go to `claude-haiku-4-5` with no `thinking` parameter

#### Scenario: Sonnet with minimal thinking
- **WHEN** `AGENT_MODEL=claude-sonnet-4-6` and `AGENT_THINKING=minimal`
- **THEN** requests carry `thinking:{type:"adaptive"}` and `output_config:{effort:"low"}` — never `budget_tokens`

### Requirement: Conversation reset endpoint
The backend SHALL expose `POST /api/chat/reset`, authenticated by the same headers as `/api/chat` (missing credentials → HTTP 400 `MISSING_CREDENTIALS`, no side effects). On success it SHALL close the session's current thread in the store and start a fresh one (delegated to the conversation store's reset), make no model call, and return `{"ok": true}`. The endpoint SHALL be idempotent.

#### Scenario: Reset starts a blank slate
- **WHEN** the user resets and then sends "now the same for F&O"
- **THEN** the model sees no prior conversation or flow-event memory, and cap counters have restarted from zero

#### Scenario: Missing credentials
- **WHEN** `/api/chat/reset` is called without the auth headers
- **THEN** the response is HTTP 400 `{"error": "MISSING_CREDENTIALS"}` and no thread is touched

