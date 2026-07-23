# CHO-259: brokerage-ui

## Why

The brokerage rate card still renders as a flat, cross-segment rate-cluster list with percentage-primary values — the approved FinX mock calls for a single answer card with a **segment accordion** (Equity → Derivative → Commodity → Currency), ₹-first rate phrasing, FinX segment colours, and two post-card follow-up chips ("Get my contract note" and "Raise a ticket"). Product wants the card to match the mock before Wave 1 ships alongside CHO-251 and CHO-265.

## What Changes

- Replace the flat clustered-row layout with a **segment accordion**: one API fetch, one card; segments always appear in fixed order (Equity → Derivative → Commodity → Currency); **Equity expanded by default**, others collapsed.
- Each segment panel shows a **22px rounded icon tile** in the FinX four-colour family (Equity blue, Derivative purple, Commodity amber, Currency green) and lists that segment's line items with rates.
- **Rate display** switches to ₹ phrasing as the primary visible line (`₹{amount} per ₹10,000 traded` for value-based; `₹{amount} flat per order` for options) — drop or demote the percentage-primary line that conflicts with the mock.
- Keep parse/fallback honesty: unparseable `desc` or oversized slabs still render upstream text verbatim, but inside the accordion shell (never a misleading cross-segment "All futures" summary).
- Statutory disclaimer stays always visible at the card footer (existing copy is fine).
- Post-card follow-ups become **two pill chips**: "Get my contract note" (starts Contract Notes flow) and "Raise a ticket" (escalation, with ticket emoji) — wired through the existing data-flow follow-up mechanism, not a bespoke brokerage-only path.
- Brokerage remains `hideSticker` (keyword/agent reachable only); no backend or API change.

## Capabilities

### New Capabilities

<!-- none — all behaviour lives under the existing brokerage-flow capability -->

### Modified Capabilities

- `brokerage-flow`: segment accordion layout (fixed order, default expand), FinX segment visual identity, ₹-primary rate phrasing, accordion-wrapped fallback, and post-card follow-up chips (contract note + ticket).

## Impact

## Parallel apply

Wave 1 — **safe with `cho-251-waiting-buffer` / `cho-265-no-kb-mention`** (no shared narration-loop or prompt ownership; only additive follow-up type + thin `dataFollowup` chip dispatch).

- Frontend only.
- **Exclusive touch:** `frontend/src/chat/datacards/BrokerageCard.tsx`, `frontend/src/chat/datacards/brokerageCluster.ts`, `frontend/src/flow/dataflows/brokerage.ts`, shared follow-up rendering (`DataFollowup` / descriptor follow-up shape in `frontend/src/flow/dataflow.ts`), related unit tests, and this change's `brokerage-flow` delta spec.
- **Do NOT touch:** `EmptyState` subtitle, `ChatShell` narration loop (except minimal shared follow-up chip wiring if the existing `dataFollowup` path is extended), `backend/app/agent/prompt.py`.
- Gates: `cd frontend && npx tsc --noEmit`, `npm run lint`, `npm run build`; visible UI change → screenshots (light + dark) before deploy.
- Linear: CHO-259 · branch `cho-259-brokerage-ui`.
