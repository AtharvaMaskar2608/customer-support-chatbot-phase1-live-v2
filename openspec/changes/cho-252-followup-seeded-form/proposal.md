# CHO-252: followup-seeded-form

## Why

On a follow-up report request — the first request generated a report, then the user says "now the same for MTF" — the agent auto-generates the file directly and no setup widget appears. The user can't see or adjust what was carried over before it runs (CHO-252: on follow-up questions the widget should load again, even if pre-filled, still showing an option to edit).

The root cause is a prompt rule, not the frontend. The frontend already renders a seeded, editable FlowCard whenever the agent emits a `flow` artifact ([ChatShell.tsx:363](frontend/src/chat/ChatShell.tsx#L363)). But the current "Slot filling without invention" rule tells the model: when every parameter is known **"from the user's words or from a prior flow event in the thread"** it calls the report tool directly — so a follow-up whose values come from the prior flow-event memo skips the form and produces a `file` artifact.

This also makes cross-report "same for …" safe. Because each flow has a different shape, the model must map the carried-over values onto the target flow — and a seeded form (which the user confirms) plus the form validator (which drops fields the target flow doesn't declare) means a mis-mapped "same" can only ever ask, never silently produce the wrong report. It is the same "detect → offer, confirm before acting" philosophy as the ticket-creation policy (CHO-241).

## What Changes

- Refine the agent's slot-filling rule: the model SHALL execute a report tool **directly only when the user states every parameter (including delivery) in their current message**. When parameters are instead **carried over from a prior flow event** (a follow-up such as "now the same for MTF" or "same for ledger"), the model SHALL call `open_report_form` **seeded** with those values — re-opening the guided form pre-filled and editable — rather than auto-generating.
- Result: every follow-up report request re-shows the widget (pre-filled, still editable), and a report is generated only on the user's explicit delivery tap. Fully-specified single-message requests still execute directly (unchanged).
- Backend/prompt-only: `backend/app/agent/prompt.py`. No frontend change (the seeded-form render path already exists), no API/contract change. The form validator already drops values the target flow doesn't declare, so cross-report "same" degrades to "the widget asks", never a wrong value.

## Capabilities

### Modified Capabilities

- `agent-loop`: a report request whose parameters are carried over from a prior flow event (a follow-up / "same for …") SHALL open the seeded guided form for confirmation, not execute the report tool directly; only a request that states all parameters in the current message executes directly.

## Impact

- Backend only: `backend/app/agent/prompt.py` — reword the report slot-filling instruction so "prior flow event" carry-over routes through `open_report_form` (seeded), and reserve direct execution for all-parameters-in-the-current-message.
- No frontend change: the `flow` artifact → seeded FlowCard path already renders pre-filled, editable forms.
- Verify with an agent transcript/prompt test if one exists for follow-ups; otherwise a manual round-2 check. The prompt-snapshot hash will change (expected).
- Linear: CHO-252 · branch `cho-252-followup-seeded-form`. Relates to CHO-249, CHO-250, CHO-253, CHO-241.
