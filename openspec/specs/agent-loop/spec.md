# agent-loop Specification

## Purpose
TBD - created by archiving change cho-213-agentic-loop. Update Purpose after archive.
## Requirements
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
The system prompt SHALL instruct the model to never invent values for required tool parameters and SHALL include the current date **resolved in IST (`Asia/Kolkata`)** so relative date expressions resolve to `YYYY-MM-DD`. The date MUST be computed from an explicitly named zone, never inherited from the host or container timezone, and the report-form validator MUST resolve "today" on the same clock so the prompt and the validator can never disagree. For the four report flows (P&L, ledger, capital gains, contract notes) the model SHALL NOT ask for parameters in prose: when any parameter is missing it SHALL call `open_report_form` carrying only the values the user actually stated (none stated ⇒ flow key alone), and when every parameter the tool needs is explicitly known in the current message — for P&L/ledger/tax that includes delivery; for `list_contract_notes` both dates — it MAY call that tool directly. When the parameters are instead carried over from a prior flow event in the thread (a follow-up such as "now the same for MTF" or "same for ledger"), the model SHALL call `open_report_form` seeded with those carried-over values rather than executing directly — a follow-up always re-opens the guided form pre-filled and editable, and a report is generated only on the user's delivery tap; the model never silently generates a report from carried-over context. Contract-note date range SHALL NEVER be requested in a free-text question; missing dates SHALL use `open_report_form` with `flow=contract-notes`. The `list_contract_notes` tool description SHALL NOT instruct the model to always call it first when dates are unknown. Prose clarifying questions (all missing values bundled into one question) remain only for non-report tools (e.g. a missing note id after a list), not for report date ranges.

#### Scenario: Nothing mentioned loads the full form
- **WHEN** the user writes "get my P&L" with no parameters
- **THEN** the model calls `open_report_form` with only the flow key, and the widget boots the full guided P&L flow from its first slot — no value assumed, no prose question asked

#### Scenario: Contract notes without dates open the form
- **WHEN** the user writes "get my contract notes" with no date range
- **THEN** the model calls `open_report_form` with `flow=contract-notes` and does not ask for dates in chat text

#### Scenario: Partial mention pre-fills the form
- **WHEN** the user writes "P&L for equity"
- **THEN** the model calls `open_report_form` with the flow key and segment only, and the widget opens with the segment chip filled, asking for the date range next

#### Scenario: Full mention in one message still executes directly
- **WHEN** the user writes "Get my F&O P&L for 1 to 30 June 2026, download it here"
- **THEN** the model calls the P&L report tool directly and the file card is produced with no form

#### Scenario: Follow-up re-opens the seeded form, never auto-generates
- **WHEN** the user completed a Normal ledger for FY 2026-27 and then writes "now the same for MTF"
- **THEN** the model calls `open_report_form` seeded with book MTF and the carried-over range, the guided ledger form re-opens pre-filled and editable, and nothing generates until the user taps delivery

#### Scenario: Cross-report "same" maps onto the target form
- **WHEN** the user completed a P&L for F&O · June 2026 and then writes "now the same for ledger"
- **THEN** the model calls `open_report_form` for ledger carrying the period (dropping the inapplicable segment), and the ledger form opens seeded with the range and asking for the book — nothing generates until the user delivers

#### Scenario: Date is IST regardless of host timezone
- **WHEN** the backend process runs with `TZ=UTC` at 01:00 IST on 21 July 2026
- **THEN** the prompt states the date as 2026-07-21, not 2026-07-20

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
`/api/chat` SHALL respond as a Server-Sent Events stream (`text/event-stream`). Assistant text SHALL be forwarded as `text` events carrying deltas while the model generates (each loop round runs via the Anthropic SDK's streaming interface); tool activity SHALL surface as `tool` events (name + started/finished + error flag); successful tool results SHALL be emitted immediately as `artifact` events — file artifacts referencing the existing `fileToken` delivery mechanism, data artifacts carrying the normalized envelopes, and flow artifacts (`kind: "flow"`) carrying the flow key plus the validated seed for a guided-form handover — and the stream SHALL terminate with a `done` event carrying the thread's turn counters and the exchange's last turn seq (`thread.lastSeq`, the feedback anchor). Only assistant text streams as deltas; tool rounds never leak raw model deltas. Missing credentials SHALL be rejected pre-stream as HTTP 400 `MISSING_CREDENTIALS`; failures after the stream opens (Anthropic unavailable, guard exhaustion without text) SHALL be emitted as an `error` event with the pinned shape (`AGENT_UNAVAILABLE`; `AUTH_EXPIRED` passthrough) so the shell can react.

#### Scenario: Done event anchors the exchange
- **WHEN** any agent exchange terminates with `done`
- **THEN** the event's `thread` object includes `lastSeq` equal to the seq of the thread's final stored turn for that exchange

#### Scenario: Form handover emitted as flow artifact
- **WHEN** the model calls `open_report_form` for a P&L request that mentioned only the segment
- **THEN** the stream carries `artifact {kind: "flow", flowKey: "pnl", seed: {segment: "Equity"}}` followed by the terminal `done` event

#### Scenario: Text streams as it generates
- **WHEN** the agent composes a reply
- **THEN** the widget receives `text` delta events progressively rather than one final payload

#### Scenario: Report produced in chat
- **WHEN** the agent completes a P&L request with delivery "download"
- **THEN** an `artifact` event carries the fileToken, name, size label and format for the existing download card, followed by the terminal `done` event

#### Scenario: Anthropic outage
- **WHEN** the Messages API call fails after retries
- **THEN** the stream emits `error` `{"error": "AGENT_UNAVAILABLE"}` and existing guided flows remain unaffected

### Requirement: Configurable model and thinking
The loop's model SHALL be selected by `AGENT_MODEL` (`claude-sonnet-4-6` default, or `claude-haiku-4-5`) and its reasoning by `AGENT_THINKING` (`off` default, or `minimal`), both env-overridable and read at call time. The thinking parameter SHALL be resolved per model: `off` omits the `thinking` parameter on both models; `minimal` maps to `{type:"enabled", budget_tokens:1024}` on `claude-haiku-4-5` (the API minimum) and to `{type:"adaptive"}` with `output_config.effort:"low"` on `claude-sonnet-4-6` (where `budget_tokens` is deprecated). No other thinking configuration SHALL be sent.

#### Scenario: Default configuration
- **WHEN** no agent env vars are set
- **THEN** requests go to `claude-sonnet-4-6` with no `thinking` parameter

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

### Requirement: Concise, non-refusing knowledge answers
Knowledge-base narration SHALL lead with the direct answer in one to three short sentences, adding detail only when the user asks for it — no headers, lists, or preambles unless steps are requested. User-visible replies SHALL comply with the user-facing voice requirement: no mechanism terms, process narration, retry disclosure, process-tied uncertainty/guessing after a miss, or forbidden self-narration. The system prompt SHALL enumerate the knowledge base's actual topic catalog so the model knows what it covers, and SHALL direct that process/how-to questions — including account closure/deletion — are ALWAYS answered from the knowledge base: the assistant never refuses a how-to as an action it cannot perform. For account actions outside its capabilities it SHALL explain the process and offer to raise a support ticket.

#### Scenario: Account deletion is answered, not refused
- **WHEN** the user asks "how do I delete my account?"
- **THEN** the reply explains the closure process from the knowledge base (and may offer a ticket) — it does not respond that it cannot help with that, and it does not mention searching or the knowledge base

#### Scenario: KB answer is brief
- **WHEN** the user asks "what are AMC charges?"
- **THEN** the reply is a few short sentences leading with the amount/definition, not a multi-section explainer, and contains no banned mechanism or narration wording

### Requirement: The prompt carries a live IST status line
The primed turn SHALL end with a status line stating the current IST time, weekday, and date, together with the market state and — when the market is open — the session's close time. This replaces the date-only line, so the model can answer wall-clock questions such as whether a same-day cutoff has passed, rather than only resolving relative dates.

#### Scenario: Open market with a close time
- **WHEN** a request is made at 14:47 IST on an ordinary trading Monday
- **THEN** the prompt states the current IST time and date, that markets are open, and when the session closes

#### Scenario: Holiday state is explicit
- **WHEN** a request is made on a weekday exchange holiday
- **THEN** the prompt states that the market is closed for a holiday, rather than implying an ordinary closed session

#### Scenario: Cutoff question is answerable
- **WHEN** a customer asks at 15:20 IST whether they can still act before the session ends
- **THEN** the model has the clock and the close time available in its prompt and can answer without guessing

### Requirement: The live status line is the last content block of the primed turn
The primed user turn SHALL be composed of at least two content blocks: the frozen instructions and few-shot examples first, carrying the prompt-cache breakpoint, and the live status line last. No volatile value may appear before a cache breakpoint.

#### Scenario: Frozen prefix stays byte-stable across requests
- **WHEN** two requests are made minutes apart on the same day
- **THEN** every content block up to and including the cache breakpoint is byte-identical between them, and only the final block differs

#### Scenario: Recorded prompt snapshot stays time-stable
- **WHEN** the prompt snapshot is recorded for hashing
- **THEN** it contains the status line's placeholders rather than a rendered time, so the hash does not change from one minute to the next

### Requirement: Tax and capital-gains figures are report-only
The system prompt SHALL forbid the model from computing tax or capital-gains figures, classifying a specific lot's holding period into short- vs long-term for a figure, or stating any tax rate or exemption threshold from general knowledge. Any question involving such figures or rates SHALL route to the capital gains report (via `open_report_form` for tax, or `get_capital_gains_report` when every parameter is known), which is the authoritative statement. This mirrors the brokerage grounding rule: the authoritative source answers, never the model's memory. The model MAY explain the concept in plain terms without producing a figure or a rate.

#### Scenario: User asks for a computed tax figure
- **WHEN** the user provides lot data or asks how much tax they will owe on a sale
- **THEN** the model does not compute a gain, does not apply FIFO/LIFO, does not classify the holding period into a figure, and does not state a tax rate; it explains that the figure comes from the official capital gains statement and offers to open the capital gains report

#### Scenario: No tax rate is ever quoted
- **WHEN** any reply touches capital-gains tax
- **THEN** it contains no tax rate or exemption threshold (e.g. no "10%", no "12.5%", no "₹1 lakh" / "₹1.25 lakh" exemption) — these change with tax law and are not in the system's ground truth

#### Scenario: Concept explanation without figures is allowed
- **WHEN** the user asks what capital gains are or how holding period affects them
- **THEN** the model may explain the concept in plain terms (that gains are computed on sale, that holding period determines short- vs long-term treatment) without producing any specific figure or rate, and offers the report for actual numbers

### Requirement: Report columns are registry-grounded
The agent SHALL answer any question about what a report contains, what a column or field means, or how to read a report ONLY from the column registry via the `get_report_columns` tool — using each label verbatim and the registry's locked gloss for its meaning. It SHALL NOT enumerate, rename, or invent report columns from general knowledge or the knowledge base. The registry is server-side config (`backend/content/column_registry.json`, remote-updatable, no client data) covering the P&L, tax, ledger, contract-note, and holdings reports. When a field name is ambiguous across reports (returned by the tool as `ambiguousLabels`), the agent SHALL ask which report the user means. When a report is not in the registry, the agent SHALL NOT list columns — it offers to pull the report instead.

#### Scenario: P&L columns are grounded, not invented
- **WHEN** the user asks what their P&L report contains
- **THEN** the agent calls `get_report_columns` for `pnl` and describes only the registry's columns (Security, Open, Buy, Sell, Net Qty, CL. Price, Realized P&L, Unrealized P&L) with their locked glosses — never "Short-term / Long-term / Trading P&L / Charges", which are not in the P&L report

#### Scenario: field meaning comes from the locked gloss
- **WHEN** the user asks what a specific column means (e.g. "what is Derv Comm")
- **THEN** the agent answers from the registry's gloss ("derivative and commodity income") without guessing or renaming the label

#### Scenario: ambiguous field asks which report
- **WHEN** the user asks about a field that appears in more than one report (e.g. Net Qty)
- **THEN** the agent asks which report they mean before explaining it

#### Scenario: uncovered surface is not enumerated
- **WHEN** the user asks to explain the columns of something not in the registry
- **THEN** the agent does not list columns and offers to pull the relevant report instead

### Requirement: First-name address is rare
When the live context includes the client's first name (CHO-246), the prompt SHALL instruct the model not to start routine replies with that name, to use it at most once per conversation (e.g. a single greeting), and never to open consecutive messages with the name. The name remains available for identity / self-only grounding; over-familiar repeated vocatives are forbidden.

#### Scenario: Name present but not every reply
- **WHEN** the primed live context includes `You are speaking with <FirstName>`
- **THEN** the same block also instructs "at most once" / do not start routine replies with their name

### Requirement: Ticket creation is user-initiated only
The assistant SHALL offer to raise a support ticket but SHALL NEVER decide to raise one on its own judgement. The model SHALL call `raise_support_ticket` only when the user's latest message is an explicit escalation request (asks for a human, to raise a ticket/complaint, to escalate) or an affirmative acceptance of the assistant's own escalation invite — never preemptively. The prompt SHALL instruct: never announce ticket creation as a plan ("let me raise a ticket"); when a ticket would help, ask "Want me to raise a ticket so the team can take this up?" and stop; never claim a ticket is being or was raised unless `raise_support_ticket` was just called (the ticket confirmation card carries the id); offer at most once per issue (if declined or ignored, do not offer again for that issue); never offer a ticket while refusing a request for security/policy/another client's data (refuse briefly and stop); never narrate retrieval or internal steps.

As a code-level guarantee independent of model behaviour, the orchestrator SHALL reject a model-emitted `raise_support_ticket` call whose triggering user turn is neither an explicit escalation request (allowlist match) nor an affirmative acceptance of the assistant's escalation invite in the preceding exchange: the call SHALL return an error `tool_result` (steering the model to offer instead) and SHALL NOT create a ticket. Affirmative acceptance SHALL match when the user's latest message is affirmative AND any consecutive assistant turn since the previous user message contains an escalation-invite marker — including standard offers ("raise a ticket", "Want me to raise…", "take this up") and announce/gerund forms the model sometimes emits instead of a clean offer ("let me raise", "raising a support ticket"). The help-card entry point (`POST /api/ticket`) is inherently user-initiated and is NOT subject to this check.

#### Scenario: Preemptive ticket call is blocked
- **WHEN** the model emits `raise_support_ticket` on a turn where the user only asked a factual question (no escalation request, no accepted offer)
- **THEN** the orchestrator returns an error tool_result, no ticket is created, and the model offers a ticket instead of raising one

#### Scenario: Explicit request raises a ticket
- **WHEN** the user says "just connect me to a human" or "raise a ticket"
- **THEN** the model's `raise_support_ticket` call passes the check and a real ticket is created

#### Scenario: Affirmative after announce/raise narration is allowed
- **WHEN** the assistant has just narrated raising a ticket (e.g. "Let me raise a support ticket…" and/or "I'm raising a support ticket now…") and the user replies "Ok" / "yes"
- **THEN** the model's `raise_support_ticket` call passes the check so a real ticket and ticket artifact can be produced (confirmation card with the Freshdesk id)

#### Scenario: Affirmative without escalate context stays blocked
- **WHEN** the user says "yes" or "Ok" with no preceding assistant escalation invite or raise narration
- **THEN** the orchestrator rejects `raise_support_ticket` and no ticket is created

#### Scenario: Not offered while refusing
- **WHEN** the user asks for something the assistant must refuse (another client's data, investment advice)
- **THEN** the assistant refuses briefly and does NOT offer a ticket

#### Scenario: Help-card chip is unaffected
- **WHEN** the user taps "Raise a ticket" on a help card
- **THEN** `POST /api/ticket` raises the ticket normally, not subject to the model-call guard

### Requirement: Assistant identity name
The system prompt SHALL identify the assistant to the model as "AskFinX" — its self-identity, the name it uses when referring to itself, and the name it continues under when resisting identity-override or instruction-extraction attempts. The customer-facing product name shown in the widget (chat, launcher, What's new, browser title) SHALL likewise be "AskFinX". Programmatic identifiers — the embed API global and init function, persisted client-side keys, and Freshdesk routing constants (tags and custom-field values) — are NOT part of this name and SHALL remain unchanged for backward compatibility and support routing.

#### Scenario: The bot names itself AskFinX
- **WHEN** the user asks "who are you?" or attempts to change the assistant's identity
- **THEN** the assistant identifies and continues as AskFinX, not Choice Jini

#### Scenario: Programmatic identifiers are unchanged
- **WHEN** a host site initialises the widget or a bot ticket is routed in Freshdesk
- **THEN** the `ChoiceJini.init` embed API and the internal routing constants still work exactly as before — the rename is display-only

### Requirement: Client identity in context and self-only data
The prompt SHALL carry the logged-in user's first name so the assistant can address them and recognise self-reference. The name SHALL be placed in the volatile block after the cache breakpoint (alongside the live status line), never in the cached prefix, so prompt-cache stability is preserved and the recorded prompt snapshot keeps a placeholder (the hash does not churn). The prompt SHALL instruct the assistant that ONLY the logged-in client's own data exists for it: any request for another person's account, reports, or details SHALL be declined briefly ("I can fetch reports only for your account") with no tool call — the assistant never fetches, nor pretends to fetch, a third party's data. This complements the tool-layer credential isolation (which already derives the client code from request headers); it fixes the conversational behaviour.

#### Scenario: Bot can address the user
- **WHEN** the profile provides the first name "Harsha"
- **THEN** the assistant has "Harsha" available in its prompt context and may address the user by name

#### Scenario: Name rides the volatile block
- **WHEN** two requests are made minutes apart in the same session
- **THEN** the cached prompt prefix is byte-identical between them and the first name appears only in the post-breakpoint block; the recorded snapshot stores a placeholder, not the name

#### Scenario: Third-party data request is declined
- **WHEN** the user asks for another person's report (e.g. "provide me <someone else>'s P&L report")
- **THEN** the assistant briefly says it can fetch reports only for the user's own account and makes no report tool call — it does not set up a form as if it would fetch that person's data

### Requirement: User-facing voice conceals intermediary steps
User-visible assistant text SHALL NOT expose retrieval mechanics, internal process, retry loops, guessing after a miss, or self-narration. The system prompt SHALL include a **USER-FACING VOICE** section that forbids, in streamed replies, the following patterns (from CHO-265 / Jam):

- **Mechanism terms:** knowledge base, KB, search results, retrieval, documents, sources, index, process note, vector, embedding, context (when describing lookup), chunk.
- **Process narration (announce-then-act):** I'll search, let me search, searching for, let me look, let me check, let me find, I'm looking into, let me try, let me raise — the model SHALL call tools with no preceding narration and answer directly.
- **Retry disclosure:** let me search more specifically, let me try again, that didn't return, the first search, a different search, more relevant results.
- **Process-tied uncertainty / guessing after miss:** I'm not sure, I think, it seems, this is likely, may involve, might be, possibly, probably, I believe, it appears, as far as I can tell — when used to narrate lookup confidence, paper over an empty/failed lookup, or invent a likely process. Soft language in an otherwise clean factual answer that does not disclose process or mechanism is out of scope for this ban.
- **Self-narration:** based on what I found, according to the information I have, from what I can see, the results indicate, I don't have information on.

When a tool or knowledge-base lookup returns nothing usable, the assistant SHALL reply with a short, factual limitation using allowed phrasing (e.g. "That isn't covered in our support guides", "I can't pull that for your account") and MAY offer a support ticket per ticket policy — without mechanism terms, retry disclosure, process-tied uncertainty/guessing, or forbidden self-narration. The assistant SHALL NOT invent facts or likely causes to avoid sounding uncertain.

Enforcement SHALL be via the system/primed prompt and tool descriptions only; the backend SHALL NOT apply a post-generation regex filter on assistant text in this change.

Internal code, tool names (including `search_knowledge_base`), and specification text MAY continue to refer to the knowledge base; this requirement applies only to user-visible streamed text. Anthropic-facing tool descriptions SHALL NOT prime the model with "knowledge base", "search results", or "summarize the results".

#### Scenario: KB answer hides mechanism
- **WHEN** the user asks a general how-to and the model answers after a successful `search_knowledge_base` call
- **THEN** the streamed reply leads with the direct answer and contains none of the banned mechanism, process-narration, retry-disclosure, process-tied uncertainty, or self-narration phrases

#### Scenario: Tool call is silent
- **WHEN** the model needs to look up a general support answer
- **THEN** it calls `search_knowledge_base` with no preceding assistant text and the reply does not announce searching or looking

#### Scenario: Empty lookup uses allowed miss phrasing
- **WHEN** `search_knowledge_base` returns no usable content for the user's question
- **THEN** the reply states the limitation in plain factual language (and may offer a ticket) without "I don't have information on", "based on what I found", inventing likely causes, or any banned mechanism term

#### Scenario: Retry is invisible
- **WHEN** the model performs a second `search_knowledge_base` call with a refined query in the same turn
- **THEN** the user-visible reply does not mention a first search, a retry, "search results", or "more relevant results"

#### Scenario: Jam-class miss does not guess
- **WHEN** the user asks how to update cost price for shares bought outside FinX and lookups return nothing relevant
- **THEN** the reply does not say "knowledge base", narrate search/retry, hedge with "this is likely" / "may involve", or announce "let me raise a support ticket" — it states the gap plainly and may ask whether to raise a ticket

#### Scenario: Grounded answer stays direct
- **WHEN** a tool returns account or knowledge-base data the model uses in its reply
- **THEN** the reply states the fact directly without process-tied hedges such as "I think" or "it seems" about the lookup

