# agent-loop

## RENAMED Requirements

- FROM: `### Requirement: The live status line is the last content block of the primed turn`
- TO: `### Requirement: The live status line rides the single trailing volatile message`

## MODIFIED Requirements

### Requirement: The live status line rides the single trailing volatile message
The live IST status line — together with the logged-in client's first name when known — SHALL be carried by a single trailing message that is the LAST message in the array sent to the model, positioned AFTER every message replayed from the conversation store, and that trailing message SHALL be the only place volatile content appears anywhere in the array. The live context SHALL be its first content block; any cap or wrap-up reminders for that round (and any future per-request injection) SHALL ride the same message after it, so the count of trailing volatile messages stays exactly one. The primed user turn SHALL therefore end at the frozen instructions block that carries the prompt-cache breakpoint (a single content block), followed by the frozen acknowledgement. The trailing live context SHALL be framed as app-generated context using the same injected-block convention the loop's reminders already use, so the model does not read it as the user's latest utterance; that framing SHALL NOT be persisted to the conversation store. No volatile value may appear before ANY cache breakpoint — including a breakpoint placed on the conversation history — so for two requests whose stored turns are identical, every message from the primed turn through the newest stored turn SHALL be byte-identical and only the trailing message may differ. The frozen instructions SHALL refer to the live context by its new position (the note at the end of the conversation), and the recorded prompt snapshot SHALL keep the status line's placeholder template rather than a rendered time.

#### Scenario: Frozen prefix stays byte-stable across requests
- **WHEN** two requests are made minutes apart with the same stored turns
- **THEN** every message except the last is byte-identical between them, and only the trailing live-context message differs

#### Scenario: Live context sits after all stored history
- **WHEN** a thread with several stored turns is replayed for a model call
- **THEN** the primed turn is a single frozen instructions block, every stored turn follows it, and the status line is the first content block of the one trailing message that ends the array

#### Scenario: Live context is not read as the user's message
- **WHEN** the trailing message is assembled immediately after the user's own question
- **THEN** the live context is wrapped in the app-generated reminder frame (never typed by the user), and the model answers the user's question rather than responding to the clock line

#### Scenario: Reminders ride the same trailing message
- **WHEN** a cap trip or the wrap-up guard injects a reminder for that round
- **THEN** the reminder is a further block of the same trailing message, after the live context, and is never stored in the thread

#### Scenario: Recorded prompt snapshot stays time-stable
- **WHEN** the prompt snapshot is recorded for hashing
- **THEN** it contains the status line's placeholders rather than a rendered time, so the hash does not change from one minute to the next

#### Scenario: Relative dates still resolve from the relocated line
- **WHEN** the user says "last month" and the model must produce concrete `YYYY-MM-DD` values
- **THEN** the frozen instructions point at the live-context note at the end of the conversation and the dates resolve correctly from it

### Requirement: First-name address is rare
When the trailing live-context note includes the client's first name (CHO-246), the prompt SHALL instruct the model not to start routine replies with that name, to use it at most once per conversation (e.g. a single warm greeting), and never to open consecutive messages with the name. Because the note now sits after the visible conversation, the instruction SHALL be phrased as a check the model can actually perform against what it can see — if the name has already been used earlier in the conversation it SHALL NOT be used again — so the clause's new proximity to the generation point cannot re-introduce the CHO-274 over-use behaviour. The name remains available for identity / self-only grounding; over-familiar repeated vocatives are forbidden.

#### Scenario: Name present but not every reply
- **WHEN** the trailing live-context note includes `You are speaking with <FirstName>`
- **THEN** the same block also instructs "at most once", "do not start routine replies with their name", and not to use the name again if it was already used earlier in the conversation

#### Scenario: Name is used at most once across a long conversation
- **WHEN** a ten-turn conversation runs with the first name available in every request
- **THEN** the first name appears in at most one assistant reply

### Requirement: Configurable model and thinking
The loop's model SHALL be selected by `AGENT_MODEL` (`claude-sonnet-4-6` default, or `claude-haiku-4-5`) and its reasoning by `AGENT_THINKING` (`off` default, or `minimal`), both env-overridable and resolved from the environment at request time — but resolved ONCE PER TURN, not per tool round, so an environment change between rounds cannot split a single turn across two models (which would drop every prompt-cache tier, since cache entries are model-scoped, and would mis-record the turn's model in the stored turn metadata). The thinking parameter SHALL be resolved per model: `off` omits the `thinking` parameter on both models; `minimal` maps to `{type:"enabled", budget_tokens:1024}` on `claude-haiku-4-5` (the API minimum) and to `{type:"adaptive"}` with `output_config.effort:"low"` on `claude-sonnet-4-6` (where `budget_tokens` is deprecated). No other thinking configuration SHALL be sent.

#### Scenario: Default configuration
- **WHEN** no agent env vars are set
- **THEN** requests go to `claude-sonnet-4-6` with no `thinking` parameter

#### Scenario: Sonnet with minimal thinking
- **WHEN** `AGENT_MODEL=claude-sonnet-4-6` and `AGENT_THINKING=minimal`
- **THEN** requests carry `thinking:{type:"adaptive"}` and `output_config:{effort:"low"}` — never `budget_tokens`

#### Scenario: Mid-turn env change cannot split a turn
- **WHEN** `AGENT_MODEL` changes between two tool rounds of the same user turn
- **THEN** every model call of that turn still uses the model resolved at the start of the turn, and the stored turn metadata records that same model

## ADDED Requirements

### Requirement: Rolling prompt-cache breakpoint on the conversation history
Every model call SHALL place an ephemeral `cache_control` breakpoint on the last content block of the last message replayed from the conversation store, so the conversation prefix bills as cache reads instead of fresh input, and SHALL re-place it on each round of the turn (the marker rolls forward with the tip). The marker SHALL be applied by copy-on-mark — the marked block is replaced by a copy carrying `cache_control` — and the conversation store SHALL NOT be mutated: no `cache_control` may appear in a thread's stored turns, in a persisted turn row, or in the ticket transcript. The breakpoint SHALL be placed on the last block of the last STORED message, never on the trailing volatile message and never on the primed prefix.

Because the API searches only a bounded window of recent content blocks (20) for a readable cache entry, when the tip is more than 19 content blocks past the last still-valid entry the loop SHALL also place a second, conditional breakpoint on the deepest message that is still within 19 blocks OF THAT ENTRY — anchored to the last valid entry, never to the tip — so a multi-round turn (up to the round guard, which every wrap-up turn reaches by definition) can still be bridged. Below that distance the second breakpoint SHALL NOT be placed.

The marker SHALL be skipped on the wrap-up round, where `tool_choice: {"type":"none"}` changes the messages-tier cache key so the write could not be read back, and SHALL be skipped when a playground prompt override is in force (drafts stay uncached). One request SHALL never carry more than four `cache_control` breakpoints in total — `system`, the primed instructions block, the rolling tip, and the conditional insurance marker — and the tool schemas SHALL carry none. All breakpoints SHALL use the 5-minute ephemeral TTL. The marker SHALL be gated by `AGENT_HISTORY_CACHE` (default on), which gates ONLY the breakpoint and never the message layout, so turning it off restores the previous two-breakpoint request without a rebuild.

#### Scenario: Marker rides the conversation tip
- **WHEN** a model call is assembled for a thread with stored turns
- **THEN** the last content block of the last stored message carries `cache_control: {"type": "ephemeral"}`, and the trailing volatile message carries none

#### Scenario: Stored turns are never mutated
- **WHEN** a request has marked the conversation tip
- **THEN** no `cache_control` key appears anywhere in the thread's stored turns, and replaying the thread afterwards yields the same bytes as before the request

#### Scenario: The marker rolls once per round
- **WHEN** a turn makes several tool rounds
- **THEN** each model call of that turn carries exactly one history breakpoint, always on the last stored message at that moment

#### Scenario: A deep cross-turn gap gets a second breakpoint
- **WHEN** the previous turn ran the maximum tool rounds with parallel tool calls, so the new tip is more than 19 content blocks past the last valid cache entry
- **THEN** a second breakpoint is placed on the deepest message within 19 blocks of that entry, and a short single-round turn produces only one breakpoint

#### Scenario: Wrap-up round carries no history breakpoint
- **WHEN** the round guard forces the wrap-up call with `tool_choice: {"type": "none"}`
- **THEN** that request carries no history breakpoint, while the round before it did

#### Scenario: Playground drafts stay uncached
- **WHEN** a playground request supplies a system or primed prompt override
- **THEN** no history breakpoint is placed, matching the existing behaviour that override requests drop the prompt breakpoints

#### Scenario: Never more than four breakpoints
- **WHEN** any request is assembled, including a deep-gap round
- **THEN** the total number of `cache_control` markers across `system`, `tools` and `messages` is at most four, and `tools` carry none

#### Scenario: Flag off restores the previous layout
- **WHEN** `AGENT_HISTORY_CACHE` is set to a falsy value
- **THEN** the request carries only the `system` and primed breakpoints, the relocated live-context layout is unchanged, and no other difference appears in the array
