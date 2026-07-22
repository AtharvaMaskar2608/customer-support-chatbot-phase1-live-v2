# CHO-233: remove-brokerage-home-chip — tasks

## 1. Descriptor flag

- [ ] 1.1 Add an optional `hideSticker?: boolean` to the flow descriptor types — `DataFlowDescriptor` (`frontend/src/flow/dataflow.ts`) and `FlowDescriptor` (`frontend/src/flow/types.ts`) — documented as "registered + keyword-routable, but not shown as a home chip"
- [ ] 1.2 Set `hideSticker: true` on the brokerage descriptor (`frontend/src/flow/dataflows/brokerage.ts`), leaving `keywords`, `trigger`, `stickerLabel`, and the card wiring intact

## 2. Filter the grid

- [ ] 2.1 In `frontend/src/chat/Stickers.tsx`, filter `ALL_FLOWS` to drop any flow with `hideSticker` before rendering the chip row
- [ ] 2.2 The no-match composer reply reuses `Stickers` — confirm it also omits the Brokerage chip (intended: it is no longer a promoted action)

## 3. Verification

- [ ] 3.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 3.2 Home screen shows the chip grid with **no Brokerage chip**
- [ ] 3.3 Typing "what are my brokerage charges" (or "my brokerage") still routes to the brokerage flow and renders the rate card

## 4. Ship & sync

- [ ] 4.1 `git-sync` with issue key CHO-233
- [ ] 4.2 `linear-connector` — summary comment + state on merge
