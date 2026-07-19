# CHO-215 · Silent Artifacts — Tasks

## 1. Backend — loop short-circuit

- [ ] 1.1 Track per-round outcomes in `loop.py`; end the turn (terminal `done` after tool/artifact events + turn writes) when all calls succeeded, all successful calls emitted artifacts, and ≥1 artifact was emitted; tests: form-only round, data-only round, parallel two-artifact round
- [ ] 1.2 Non-short-circuit paths regression: KB round narrates, errored round narrates (incl. AUTH_EXPIRED path), mixed artifact+KB round narrates; existing loop tests pass with expectations updated only where continuation calls disappear
- [ ] 1.3 Transcript continuity test: short-circuited turn then a follow-up message → replayed messages array is valid (tool_result-first merge) and the loop answers normally

## 2. Backend — prompt + config

- [ ] 2.1 Update rules/examples: call artifact tools immediately with no preamble; ban "above"/"below"; never restate card data; handoff examples end at the tool call; ADD the tax/ITR example ("Can you fetch my ITR" → open_report_form flow=tax) so every flow family has one
- [ ] 2.2 Cap defaults: `TASK_TURN_CAP` 10→100, `SESSION_TURN_CAP` 20→100 in `config.py` (env-overridable unchanged); update any tests asserting the old defaults

## 3. Frontend — deterministic captions

- [ ] 3.1 Flow artifact: bot caption line before the FlowCard (descriptor intro when seed empty; fixed seeded-handoff line otherwise); file artifact: fixed report-ready line; data artifact: unchanged (card + followup only)
- [ ] 3.2 Frontend build green (`tsc -b` + both vite entries)

## 4. Verification

- [ ] 4.1 Backend suite green; live smoke: brokerage question → card only, zero narration tokens after the tool round; "P&L for equity" → seeded form + deterministic caption; KB question unchanged; model-call count per request verified down to one for artifact requests
- [ ] 4.2 Store inspection: short-circuited turns end on tool_result and the next exchange replays cleanly
