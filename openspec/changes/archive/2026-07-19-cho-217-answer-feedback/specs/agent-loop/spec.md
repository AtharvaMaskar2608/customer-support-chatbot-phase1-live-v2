# agent-loop (delta)

## MODIFIED Requirements

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
