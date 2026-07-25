# CHO-253: record-no-data-flow-events

## Why

Report generation bypasses the agent: the FlowCard posts to `/api/report/*`, not `/api/chat`. On **success**, the endpoint fires a `flow_event` memo onto the session thread (`record_flow_event`) so the model remembers what the widget did — this is why "now the same for MTF" works. But on a **no-data or failed** report, the endpoint returns before recording (e.g. [report.py:196](backend/app/report.py#L196) returns the `ToolError` first), so the model never learns the attempt happened. It stays blind to the fact that the user asked for, say, P&L F&O July 2026 and got nothing — so its next reply can't reason about it.

This is the agent-memory half of the no-data story: CHO-250 gives the user an immediate in-widget recovery pill; this makes the model's *next* reply no-data-aware (e.g. "there were no F&O trades in July — want the full FY?", or carrying the period to another report). Pairs with CHO-252's follow-up handling.

## What Changes

- Extend flow-event recording to also emit a memo on **no-data** (and other non-success) report outcomes — a new `outcome` value (e.g. `"no_data"`) — wired into the no-data/error branches of the report endpoints, using the same fire-and-forget path.
- Keep the existing framing and hygiene exactly: `role: "user"`, `kind: "flow_event"`, an app-event memo ("[App event …] The user asked for the <flow>: <slot labels> — no records for that period."), `meta` carrying the structured fields with `outcome: "no_data"`. Customer-facing labels + ISO dates only — never credentials, tokens, or upstream fields. Never delays or fails the report response.
- Backend-only.

## Capabilities

### Modified Capabilities

- `conversation-store`: the flow-event recorder SHALL also record no-data / failed report outcomes (not only download/email successes), as an app-event memo with an explicit non-success outcome, so the agent's next turn is aware an attempt was made and returned nothing.

## Impact

- Backend only:
  - `backend/app/agent/events.py` — `render_memo` gains a no-data/failed memo variant; `record_flow_event` accepts the non-success `outcome`.
  - `backend/app/report.py` and `backend/app/reports/{ledger,tax}.py` — record a no-data flow event in the `ToolError` guard when the code is `NO_DATA`, before returning. Contract notes is deferred (its no-data is an empty *list*, a different shape, with existing frontend "Change dates" recovery).
- Fire-and-forget preserved (never awaited, never fails the report response). PII/secret hygiene preserved (labels + ISO dates only).
- Tests: extend `events` / report tests to assert a no-data memo is recorded and the success path is unchanged; `uv run pytest` is the gate.
- Linear: CHO-253 · branch `cho-253-record-no-data-flow-events`. Relates to CHO-250, CHO-252.
