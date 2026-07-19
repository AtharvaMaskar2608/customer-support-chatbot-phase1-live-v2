# CHO-215 · Silent Artifacts

## Why

Live testing of CHO-214 exposed a structural token leak: after every artifact-producing tool call the loop makes a **second full model call** whose only job is to narrate what is already on screen — "Your form is open above…", a prose recap of the brokerage card the user is looking at, "your P&L is ready below". That call re-reads the entire prompt, duplicates the card's content, guesses at layout it cannot know (it said "below" for a card rendered above — the model has no knowledge of where artifacts sit), and on long threads it is exactly where the escalation offer leaks into otherwise clean replies. The card IS the answer; the narration is waste.

## What Changes

- **Loop short-circuit**: after executing a tool round, if **every successful call produced an artifact** (form handover, data card, file card), **at least one artifact was emitted**, and **no call errored**, the loop ends the turn in code — no continuation model call, straight to the terminal `done` event. This roughly halves model calls (and the continuation's full prompt re-read) on every report and data request, and makes post-artifact narration structurally impossible — wrong "above/below", duplicate card recaps, and the escalation-offer leak all disappear with it.
- **What still narrates**: KB search results (prose is the product), contract-note lists (the model offers the choices), any errored call (the model explains what happened), and mixed rounds (an artifact plus a non-artifact success in parallel) — these continue exactly as today. `AUTH_EXPIRED` handling is unchanged.
- **Deterministic frontend captions**: the connective line beside an artifact is rendered by the chat shell from fixed copy/flow descriptors — zero tokens, and the frontend actually knows the layout. Seeded forms get a short handoff line; agent-produced file cards get the report-ready line (password note already on the card); data cards keep their existing follow-up affordance.
- **Prompt tightening**: artifact tools are called with no preamble text; spatial words ("above"/"below") are banned everywhere; never describe data a card already shows (covers the mixed-round case the short-circuit doesn't). The form-rule examples gain a **tax/ITR case** — live testing showed "Can you fetch my ITR" still drew a prose interrogation instead of the capital-gains form (the examples covered P&L and ledger only; Haiku follows examples more than rules).
- **Cap defaults raised for the 8-hour session reality**: `TASK_TURN_CAP` default 10 → **100** and `SESSION_TURN_CAP` default 20 → **100** (both still env-overridable; `CLARIFY_CAP` stays 2 — it guards quality, not length). The old defaults were sized for short sessions and tripped in normal use of a thread that legitimately lives ~8 hours.
- **Transcript stays wire-valid**: a short-circuited turn ends on the stored `tool_result` turn; the next user message merges beside it in replay (the merge machinery from CHO-214 already handles exactly this shape).

## Capabilities

### Modified Capabilities

- `agent-loop`: the orchestration loop terminates without a continuation call on artifact-only successful rounds; prompt rules extended (no preamble before artifact tools, no spatial language, no card recaps).
- `report-chat-shell`: the shell renders deterministic caption lines for agent artifacts instead of expecting model narration.

## Impact

- Backend: `app/agent/loop.py` (short-circuit + artifact accounting per round), `app/agent/prompt.py` (rules + example tweaks). No schema, store, or config changes.
- Frontend: `src/chat/ChatShell.tsx` / `messages.ts` (caption lines beside artifacts).
- Cost/latency: one model call saved per report/data request; the user's reply latency for those requests drops to the tool round alone.
- Compliance/PII: unchanged (strictly less model output).
