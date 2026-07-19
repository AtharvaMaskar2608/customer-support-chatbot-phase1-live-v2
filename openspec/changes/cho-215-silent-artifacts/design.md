# CHO-215 · Silent Artifacts — Design

## D1 · The short-circuit condition

After a tool round executes, the loop ends the turn (no continuation model call) iff:

1. every `tool_use` in the round dispatched successfully (`is_error: false` for all), and
2. every successful call produced an artifact event (`_artifact_payload(...) is not None`), and
3. at least one artifact was emitted.

Rationale for the strictness: an errored call needs the model to explain; a successful non-artifact call (KB search, contract-note list) exists precisely to be narrated; a mixed round (rare — e.g. parallel KB + brokerage) keeps today's behavior because half the answer is prose. `AUTH_EXPIRED` is an errored call, so its narrate-then-error-event path is untouched.

## D2 · Termination mechanics

On short-circuit the loop emits the terminal event directly after the round's `tool`/`artifact` events and `tool_result` turn writes: `done` with the derived counters (or the `AUTH_EXPIRED` error event — unreachable here since auth expiry is an error result, listed for completeness). The stored thread ends on the `tool_result` turn with no trailing assistant text — a shape the store already replays correctly: the next incoming user message merges beside the tool_result blocks in one user-role message (CHO-214's tool_result-first merge), and the API accepts it. The `open_report_form` synthetic result and every envelope stay stored, so the model retains full context on the next turn.

Pre-tool text in the same round (a preamble the model streamed before its `tool_use` blocks) has already been forwarded and stored by the time the short-circuit decision runs; the prompt now bans such preambles for artifact tools, so this text is normally empty.

## D3 · Deterministic captions (frontend)

The shell, which knows actual layout, renders the connective copy beside agent artifacts:

- **flow artifact** → a short fixed bot line before the seeded FlowCard ("Here you go — fill in the rest and it's on its way." for a seeded form; the descriptor's own `intro` when the seed is empty, matching the sticker experience).
- **file artifact** → the existing download card plus a fixed report-ready line (the password note already renders on the card).
- **data artifact** → no extra line: the card plus its existing `dataFollowup` affordance already close the exchange.

All copy is code, not model output — byte-stable, zero tokens, never spatially wrong.

## D4 · Prompt changes

- Artifact tools (`open_report_form`, `get_holdings`, `get_money_transactions`, `get_brokerage_rates`, and the three report tools when called directly) are called **immediately, with no preamble text** — the app supplies any connective copy.
- Spatial words about UI ("above", "below") are banned — the model cannot know layout.
- Never restate data a card shows (applies to the mixed-round narration that still happens).
- The CHO-214 "reply with ONE short handoff line" instruction and the handoff examples are updated to "call the tool and stop" (the examples' reply text becomes empty/omitted).
- A tax/ITR example is added ("Can you fetch my ITR" → `open_report_form` with flow=tax and nothing else). Live miss: with only P&L/ledger examples, Haiku reverted to a prose interrogation for ITR — example coverage beats rule text at this model size, so every flow family gets one.

## D6 · Cap defaults for 8-hour sessions

`TASK_TURN_CAP` 10 → 100, `SESSION_TURN_CAP` 20 → 100 (code defaults; env still overrides both at call time). The widget session — thread key — lives ~8 hours, so 10-per-task/20-per-session were tripping in ordinary use. `CLARIFY_CAP` stays 2: it bounds repeated questioning quality, not conversation length, and forms have made report clarifies near-extinct anyway. The soft/mandatory trip-specific injection from CHO-214 is unchanged.

## D5 · What deliberately does NOT change

- KB narration quality and length (that is the product's answer).
- Error narration, clarify behavior for non-report tools, caps and escalation semantics (CHO-214).
- The store schema, SSE event vocabulary, and frontend renderers — only who authors the caption text.
