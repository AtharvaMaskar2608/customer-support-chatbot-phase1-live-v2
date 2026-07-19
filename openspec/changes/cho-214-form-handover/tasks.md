# CHO-214 · Form Handover — Tasks

## 1. Backend — `open_report_form` tool

- [ ] 1.1 Per-flow canonical seed catalog (declared fields, chip labels, date constraints) + validate-and-drop function with unit tests (invalid chip, 3-year span, one-sided range, irrelevant field per flow, empty seed)
- [ ] 1.2 Registry entry: schema (flow required, all seed fields optional user-intent only), handler returning the flow-key + surviving-seed envelope; synthetic success tool_result text ("Form opened … pre-filled: …")
- [ ] 1.3 Loop emission: successful `open_report_form` emits `artifact {kind:"flow", flowKey, seed}`; tests for event shape and for form-open acting as a resolution event (cap counters reset)

## 2. Backend — prompt routing

- [ ] 2.1 Rewrite report routing rules: never ask report parameters in prose; anything missing → `open_report_form` with only stated values; everything incl. delivery explicitly known (user words or flow-event context) → direct report tool; update few-shot examples (nothing-mentioned, partial, full-mention, follow-up-from-memo)
- [ ] 2.2 Live prompt sanity pass on all four flows: "get my P&L" (empty seed), "P&L for equity" (segment only), "ledger for last month" (dates resolved), full-mention direct call still fires

## 3. Backend — flow-event memory

- [ ] 3.1 Memo renderer: deterministic app-event text from flow + slot labels + delivery + outcome; unit tests (byte-stable output, no tokens/credentials/upstream fields)
- [ ] 3.2 Report endpoints (P&L, ledger, tax, contract-notes download; download and email outcomes) enqueue the `flow_event` turn on success via the existing store — never awaited, never failing the response, silently skipped when the store is absent/degraded; tests incl. store-down path
- [ ] 3.3 `Thread.messages()` includes `flow_event` turns (merge into adjacent user message when roles would collide); replay round-trip test + regression: existing threads without flow events replay unchanged

## 4. Backend — cap tuning

- [ ] 4.1 Trip-specific escalation injection: clarify/task trips keep the mandatory offer; session-backstop-only trip switches to the conditional offer-if-stuck instruction; tests for the fresh-query-no-misfire and stuck-at-20 cases

## 5. Frontend — seeded form boot

- [ ] 5.1 Export `rangeLabel` from `src/flow/dates.ts`; flow-artifact parser in `agentArtifacts.ts`: validate seed against descriptor (chip options, DateConstraints), build typed SlotValues with deterministic date label, drop invalid; unit tests mirroring backend drop cases
- [ ] 5.2 ChatShell: `flow` artifact appends a flow message via `startRun(descriptor, seedValues)`; seeded delivery renders highlighted, still tap-to-fire; verify edit/narration/result behave identically to sticker-started flows
- [ ] 5.3 Frontend suite green; keyword-fallback path unaffected

## 6. Verification & live check

- [ ] 6.1 Full backend + frontend suites green; existing sticker flows spot-checked unchanged
- [ ] 6.2 Live smoke matrix: "get my P&L" → full form; "P&L for equity" → seeded form; "email me my equity P&L for June" → form on delivery step, email highlighted, tap fires; full-mention → direct PDF; complete a form then "now the same for F&O" → seeded via flow-event memo; fresh query after long session → no escalation misfire
- [ ] 6.3 Store inspection: flow_event turns present, memo framed, credential-clean; counters derive correctly around form-opens
