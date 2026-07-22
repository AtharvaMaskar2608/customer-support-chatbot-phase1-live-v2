# CHO-233: remove-brokerage-home-chip

## Why

The business team does not want the **Brokerage** quick-action chip shown on the home screen — the rate card is a reference, not a primary entry point, and leading with it upfront misframes the widget. The brokerage *flow* must stay fully functional (typing "what are my brokerage charges", keyword routing, and the rate card itself all unchanged) — only its home-screen chip is removed.

## What Changes

- **Hide the Brokerage chip** from the home-screen quick-action grid. The brokerage data flow stays registered, so composer keyword routing (`/brokerage|my charges|my fees|rate card|slab/i`) and the card render path are untouched — the flow is reachable by typing, just not by a home chip.
- Mechanism: an optional `hideSticker` flag on the flow descriptor; `brokerage` sets it; `Stickers` filters out any flow with `hideSticker`. This keeps the declarative "one descriptor per flow" model — no special-casing by key in the render, and the flow's keyword routing is deliberately independent of its chip.
- Frontend-only. No backend, API, or contract change.

## Capabilities

### Modified Capabilities

- `home-screen`: the quick-action chip set no longer includes a Brokerage chip; the brokerage flow remains reachable by typing / keyword, just not from a home chip.

## Impact

- Frontend only:
  - `frontend/src/flow/dataflow.ts` and `frontend/src/flow/types.ts` — add an optional `hideSticker?: boolean` to the flow descriptor types.
  - `frontend/src/flow/dataflows/brokerage.ts` — set `hideSticker: true`.
  - `frontend/src/chat/Stickers.tsx` — filter `hideSticker` flows out of the chip grid.
- The brokerage flow's keyword routing, `BrokerageCard`, tests, and backend are unchanged.
- No test impact expected; `tsc` + build are the gates.
- Linear: CHO-233 · branch `cho-233-remove-brokerage-home-chip`.
