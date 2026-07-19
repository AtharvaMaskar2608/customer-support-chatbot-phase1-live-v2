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
The loop SHALL enforce, in code and independent of model behavior, three env-configurable caps evaluated per incoming user message: (1) at most `CLARIFY_CAP` (default 2) clarifying questions per task window; (2) at most `TASK_TURN_CAP` (default 10) user turns per task window; (3) at most `SESSION_TURN_CAP` (default 20) user turns per session. A task window is the span of conversation since the last resolution event — an assistant turn that completed with at least one successful (`is_error: false`) tool call, which includes a successful `open_report_form` call — and a resolution event SHALL reset the per-task counters. Escalation injection SHALL be trip-specific: a clarify-cap or task-turn trip SHALL instruct the model to stop asking and offer escalation to a human; a session-backstop trip alone SHALL instruct the model to offer a human only if the user appears stuck or unsatisfied, and otherwise answer normally.

#### Scenario: Clarify cap trips
- **WHEN** the model has asked 2 clarifying questions in the current task window and required parameters are still missing
- **THEN** the next reply offers escalation instead of a third question

#### Scenario: Form-open resets the task window
- **WHEN** a report request opens a form after earlier unresolved back-and-forth in the same window
- **THEN** the successful `open_report_form` result is a resolution event and the per-task counters restart from zero

#### Scenario: Fresh query in a long-lived session is not misflagged
- **WHEN** the session backstop alone has tripped and the user sends a clean, fully-answerable new request
- **THEN** the reply answers normally without suggesting the conversation has been going back and forth

#### Scenario: Session backstop still guards the rephrase loop
- **WHEN** the user is on their 20th message and visibly stuck rephrasing the same unresolved question
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

