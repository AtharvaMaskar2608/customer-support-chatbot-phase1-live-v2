## 1. Domain helpers (cluster → order + ₹ display)

- [x] 1.1 In `frontend/src/chat/datacards/brokerageCluster.ts`, change `rateDisplay` so `per10k` → primary `₹{amt} per ₹10,000 traded` and `order` → `₹{amt} flat per order` (reuse `formatRateInr`; stop returning percentage-primary / `formatRatePct` for the card)
- [x] 1.2 Add `orderBrokerageGroups(groups)` (or equivalent) that returns non-empty groups in fixed order Equity → Derivative → Commodity → Currency, appending unknown titles after
- [x] 1.3 Remove card-path usage of `brokerageClusters` / `clusterLabel`; delete those helpers (and `MAX_CLUSTERS`) if nothing else imports them; keep `parseRate` + formatters
- [x] 1.4 Add unit tests for `orderBrokerageGroups` + new `rateDisplay` shapes (including trailing-zero trim and unparseable handled at call site)

## 2. Accordion card UI

- [x] 2.1 Rewrite `frontend/src/chat/datacards/BrokerageCard.tsx` as a segment accordion: coloured 22px icon tiles (Equity/Derivative/Commodity/Currency hexes from design D5), UPPERCASE title, "`N` rates", chevron; Equity expanded by default
- [x] 2.2 Expanded panel rows: item title left, `rateDisplay` (or verbatim `desc` if parse fails) right; hairline dividers
- [x] 2.3 Drop the "Your brokerage rates / grouped by rate" header; keep the existing statutory disclaimer footer always visible
- [x] 2.4 Independent expand/collapse state; dark-mode check on tile contrast

## 3. Descriptor intro + follow-up chips

- [x] 3.1 In `frontend/src/flow/dataflows/brokerage.ts`, set `intro` to "Here's your brokerage plan — tap a segment to expand."
- [x] 3.2 Widen `DataFlowDescriptor['followup']` in `frontend/src/flow/dataflow.ts` to allow a chips variant (additive; holdings/money unchanged)
- [x] 3.3 Set brokerage `followup` to two chips: "Get my contract note" → `startFlow`/`contractNotes`; "Raise a ticket" with 🎫 → `raiseTicket`
- [x] 3.4 Minimal shared render: extend `DataFollowup` (or sibling) + `ChatShell` `dataFollowup` case only — wire chip actions to existing contract-notes start path and `handleRaiseTicket`; do not touch narration loop

## 4. Verification

- [x] 4.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 4.2 Manual: ask brokerage — Equity open, others collapsed, fixed order, ₹ phrasing (no %), disclaimer visible, both chips present
- [ ] 4.3 Manual: tap "Get my contract note" → contract-notes flow; tap "🎫 Raise a ticket" → escalation
- [ ] 4.4 Screenshots light + dark (accordion + chips) before deploy

## 5. Ship & sync

- [x] 5.1 Branch `cho-259-brokerage-ui` + local commit (push/PR deferred — not requested)
- [x] 5.2 Linear CHO-259 → In Progress + assignee + project at start (In Review at PR / Done at merge — deferred until push)
