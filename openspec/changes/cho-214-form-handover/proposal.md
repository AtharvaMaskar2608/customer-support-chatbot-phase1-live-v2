# CHO-214 · Form Handover

## Why

When a free-text report request is missing parameters, the agent currently asks for them in prose ("which dates? download or email?") — the weakest surface we have. The user then types dates as text, the LLM re-parses them, and every exchange burns the clarify caps; live testing showed a fresh, clean query drawing a "we've been going back and forth" escalation because the caps had accumulated across an 8-hour thread with no resolution. Meanwhile the guided widgets already solve parameter collection perfectly — chips, constrained calendar, delivery buttons — and the flow engine's `startRun(descriptor, seed)` was explicitly built "LLM-ready" for seeded entry (CHO-207). This change connects the two: free text in, the *same* guided widget out, pre-filled with whatever the user actually said.

## What Changes

- **`open_report_form` tool**: a new agent tool (`flow` required; every slot value optional) that opens a guided report flow in the widget instead of asking questions. The prompt rule inverts for reports: the agent never asks report parameters in prose — it calls `open_report_form` with only the values the user stated (nothing stated ⇒ empty seed ⇒ the full flow loads, identical to a sticker tap). The handler validates each provided value against the flow's canonical options and **drops** anything invalid — a bad extraction degrades to the widget asking, never to a mis-filled form. The loop emits the validated seed as a new `artifact` event kind (`flow`), returns a synthetic success tool_result so the model closes with one short line, and — because a successful tool call is a resolution event — opening a form resets the task window by construction.
- **Seeded widget boot (frontend)**: the artifact consumer maps the seed to typed `SlotValue`s (re-validating against the descriptor: chip values must match declared options, dates must pass the flow's constraints) and boots the existing `FlowCard` via `startRun(descriptor, seed)` — the engine then asks only the first unfilled gap. A stated delivery preference highlights that delivery button; it never auto-fires — the delivery tap remains the human confirm-and-generate action.
- **Fast path preserved**: when *every* parameter including delivery is explicitly stated (or known from a prior flow event), the agent still calls the report tool directly — "Get my F&O P&L for 1 to 30 June, download it here" keeps producing the PDF in one shot with no form.
- **Flow-event memory**: when a deterministic report endpoint succeeds (widget-driven download or email), the backend appends a `flow_event` turn to the session's thread — the endpoints already carry the session header, which *is* the thread key. The turn's content is a compact, deterministic app-event memo ("The user completed the P&L form in the widget: Equity, 1 Jun–30 Jun 2026, downloaded successfully."), and thread replay now includes `flow_event` turns — so "now the same for F&O" right after a widget-completed report just works.
- **Cap-misfire fix**: escalation injection becomes trip-specific — clarify-cap and task-turn trips still mandate the escalation offer (the current task is genuinely struggling); the session backstop trip now instructs the model to offer a human *only if the user appears stuck*, killing the false "going back and forth" suggestion on fresh queries in long-lived sessions while keeping the KB-rephrase-loop guard.

Out of scope: mid-flow free-text breakout (typing into the composer while a form is open hands over the other way — a later change), the Freshdesk escalation tool, flow events for the data cards (holdings/money/brokerage — trivially addable later), and any cross-session memory.

## Capabilities

### Modified Capabilities

- `agent-loop`: report slot-filling behavior replaced by form handover (prose clarify remains only for non-report tools); `flow` artifact kind added to the SSE contract; escalation injection made trip-specific.
- `agent-tool-registry`: new `open_report_form` entry — validate-and-drop seed semantics, per-flow canonical values, synthetic success result.
- `conversation-store`: `flow_event` turns gain a producer (deterministic report endpoints on success) and enter thread replay as framed app-event memos; wire-faithfulness preserved (the stored memo text is exactly what the model sees).
- `report-chat-shell`: the shell renders `flow` artifacts by booting the existing guided `FlowCard` seeded mid-conversation, with stated delivery highlighted.

## Impact

- Backend: `app/agent/tools.py` (+1 tool), `app/agent/prompt.py` (report routing rules + examples), `app/agent/loop.py` (flow artifact emission), `app/agent/caps.py`/loop (trip-specific injection), report routers (`app/report.py`, `app/reports/*`) append flow events via the existing store (enqueue-only, never blocking the response). No new tables, no new dependencies, no config changes.
- Frontend: `src/chat/agentArtifacts.ts` (flow-seed parsing/validation), `src/chat/ChatShell.tsx` (boot seeded FlowCard from artifact, delivery highlight), `src/flow/dates.ts` (export `rangeLabel`). Engine untouched — `startRun` already takes the seed.
- Security/PII: seed values are user-intent fields only, validated server-side against canonical options before emission; flow-event memos contain only the whitelisted slot labels already shown in the UI; credentials untouched.
- Compliance: unchanged — factual answers only; the form path *reduces* free-prose surface.
