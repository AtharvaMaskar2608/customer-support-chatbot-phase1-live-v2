# CHO-214 · Form Handover — Tasks

## 1. Backend — `open_report_form` tool

- [x] 1.1 Per-flow canonical seed catalog (declared fields, chip labels, date constraints) + validate-and-drop function with unit tests (invalid chip, 3-year span, one-sided range, irrelevant field per flow, empty seed)
- [x] 1.2 Registry entry: schema (flow required, all seed fields optional user-intent only), handler returning the flow-key + surviving-seed envelope; synthetic success tool_result text ("Form opened … pre-filled: …")
- [x] 1.3 Loop emission: successful `open_report_form` emits `artifact {kind:"flow", flowKey, seed}`; tests for event shape and for form-open acting as a resolution event (cap counters reset)

## 2. Backend — prompt routing

- [x] 2.1 Rewrite report routing rules: never ask report parameters in prose; anything missing → `open_report_form` with only stated values; everything incl. delivery explicitly known (user words or flow-event context) → direct report tool; update few-shot examples (nothing-mentioned, partial, full-mention, follow-up-from-memo)
- [x] 2.2 Live prompt sanity pass: "get my P&L" → empty seed; "P&L for equity" → `{segment: Equity}`; "ledger for last month" → June 2026 dates resolved; follow-up-from-memo verified in 6.2 (the direct-call path is unchanged code, regression-covered)

## 3. Backend — flow-event memory

- [x] 3.1 Memo renderer: deterministic app-event text from flow + slot labels + delivery + outcome; unit tests (byte-stable output, no tokens/credentials/upstream fields)
- [x] 3.2 Report endpoints (P&L, ledger, tax, contract-notes download; download and email outcomes) enqueue the `flow_event` turn on success via the existing store — never awaited, never failing the response, silently skipped when the store is absent/degraded; tests incl. store-down path
- [x] 3.3 `Thread.messages()` includes `flow_event` turns (merge into adjacent user message when roles would collide, tool_result blocks kept first); replay round-trip test + regression: existing threads without flow events replay unchanged

## 4. Backend — cap tuning

- [x] 4.1 Trip-specific escalation injection: clarify/task trips keep the mandatory offer; session-backstop-only trip switches to the conditional offer-if-stuck instruction; tests for the fresh-query-no-misfire and stuck-at-20 cases

## 5. Frontend — seeded form boot

- [x] 5.1 Flow-artifact parser in `agentArtifacts.ts`: validate seed against descriptor (chip options, DateConstraints), build typed SlotValues with the existing `customRangeValue` deterministic date label (already exported — no `rangeLabel` export needed), drop invalid; drop-case coverage lives in the backend seed tests (no frontend test runner exists) + `tsc` type gate
- [x] 5.2 ChatShell: `flow` artifact appends a flow message via `startRun(descriptor, seedValues)`; seeded delivery renders highlighted, still tap-to-fire; edit/narration/result run through the identical FlowCard path as sticker-started flows (selection fetch effect covers seeded contract-notes)
- [x] 5.3 Frontend build green (`tsc -b` + both vite entries); keyword-fallback path untouched

## 6. Verification & live check

- [x] 6.1 Backend suite green (302 passed, 2 skipped; all pre-existing tests pass — only the two deliberate tool-count assertions updated 9→10); frontend `tsc -b` + both vite builds green; sticker flows share the identical FlowCard path (additive optional prop only)
- [x] 6.2 Live smoke matrix passed: "get my P&L" → full form (empty seed); "Can you get me my P&L report for equity?" (the CHO-214 motivating query) → seeded form, no prose questions; "ledger for last month" → June 2026 dates seeded; widget-completed P&L (200, real PDF) → "now the same for F&O" → form seeded `{segment: F&O, 2026-06-01→2026-06-30}` from the flow-event memo; clean KB query on the >20-turn thread → normal answer, no "going back and forth" misfire
- [x] 6.3 Store inspected in Postgres: flow_event turn persisted with the framed memo directly before the follow-up that consumed it; last-10-turn scan credential-clean (no session id / JWT); counters derived correctly (form-open resolution asserted in tests)
