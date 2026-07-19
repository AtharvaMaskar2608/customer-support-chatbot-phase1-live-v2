# agent-loop Specification

## Purpose
TBD - created by archiving change cho-213-agentic-loop. Update Purpose after archive.
## Requirements
### Requirement: Tool-use orchestration loop
The backend SHALL expose `POST /api/chat` which appends the user's free-text message to the session's conversation and runs a tool-use loop against the Anthropic Messages API: while the response's `stop_reason` is `tool_use`, every `tool_use` block in that response SHALL be executed, the assistant message SHALL be appended wire-faithfully (content blocks unmodified), all corresponding `tool_result` blocks SHALL be returned in a single user-role message, and the model SHALL be called again. The loop SHALL end when `stop_reason` is `end_turn` (reply returned to the user) or when a configurable inner-round guard (default 5 tool rounds per user message) is reached, in which case the loop SHALL stop calling tools and return the best available text reply.

#### Scenario: Single tool round
- **WHEN** the user asks a question the model answers via one KB search
- **THEN** the loop executes the search, feeds the result back, and returns the model's final text with `stop_reason` `end_turn`

#### Scenario: Parallel tool calls answered together
- **WHEN** one assistant response contains two `tool_use` blocks
- **THEN** both tools execute and both `tool_result` blocks are sent back in one user-role message

#### Scenario: Inner guard trips
- **WHEN** the model requests a sixth consecutive tool round for one user message
- **THEN** the loop stops executing tools and returns a text reply without erroring the request

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
The system prompt SHALL instruct the model to never invent values for required tool parameters, to bundle all missing parameters into a single clarifying question, and SHALL include today's date so relative date expressions resolve to `YYYY-MM-DD`.

#### Scenario: Partial info pre-fills
- **WHEN** the user writes "P&L for F&O"
- **THEN** the model's next message asks for the date range and delivery method in one question, without re-asking the segment

#### Scenario: Nothing mentioned runs the entire flow of questions
- **WHEN** the user writes "get my P&L" with no parameters
- **THEN** no value is assumed — the model asks for all required parameters (bundled into one question), exactly as if the guided flow ran from the start

#### Scenario: Relative dates resolve
- **WHEN** the user writes "ledger for last month"
- **THEN** the eventual tool call carries the correct concrete `YYYY-MM-DD` range for the previous calendar month

### Requirement: Conversation caps and escalation suggestion
The loop SHALL enforce, in code and independent of model behavior, three env-configurable caps evaluated per incoming user message: (1) at most `CLARIFY_CAP` (default 2) clarifying questions per task window — once reached the model SHALL be instructed to stop asking and offer escalation; (2) at most `TASK_TURN_CAP` (default 10) user turns per task window; (3) at most `SESSION_TURN_CAP` (default 20) user turns per session. A task window is the span of conversation since the last resolution event — an assistant turn that completed with at least one successful (`is_error: false`) tool call — and a resolution event SHALL reset the per-task counters. When any cap trips, the reply SHALL offer escalation to a human while remaining able to answer.

#### Scenario: Clarify cap trips
- **WHEN** the model has asked 2 clarifying questions in the current task window and required parameters are still missing
- **THEN** the next reply offers escalation instead of a third question

#### Scenario: Resolution resets counters
- **WHEN** a report is successfully generated after 1 clarifying question
- **THEN** the clarify and task-turn counters reset, and a new request from the user starts a fresh task window

#### Scenario: Session backstop
- **WHEN** the user sends their 20th message of the session without regard to task outcomes
- **THEN** the reply includes an escalation suggestion

### Requirement: Compliance-constrained answers
The system prompt SHALL constrain the agent to factual support answers: no investment advice, no contractual commitments or promises on behalf of Choice, and resistance to instruction-override attempts in user text. These constraints SHALL apply to every reply, including tool-result summaries.

#### Scenario: Advice request deflected
- **WHEN** the user asks "should I buy more of this stock?"
- **THEN** the reply declines to advise and redirects to factual account/support capabilities

### Requirement: Streamed chat response (SSE)
`/api/chat` SHALL respond as a Server-Sent Events stream (`text/event-stream`). Assistant text SHALL be forwarded as `text` events carrying deltas while the model generates (each loop round runs via the Anthropic SDK's streaming interface); tool activity SHALL surface as `tool` events (name + started/finished + error flag), successful tool results SHALL be emitted immediately as `artifact` events — file artifacts referencing the existing `fileToken` delivery mechanism and data artifacts carrying the normalized envelopes — and the stream SHALL terminate with a `done` event carrying the thread's turn counters. Only assistant text streams as deltas; tool rounds never leak raw model deltas. Missing credentials SHALL be rejected pre-stream as HTTP 400 `MISSING_CREDENTIALS`; failures after the stream opens (Anthropic unavailable, guard exhaustion without text) SHALL be emitted as an `error` event with the pinned shape (`AGENT_UNAVAILABLE`; `AUTH_EXPIRED` passthrough) so the shell can react.

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

