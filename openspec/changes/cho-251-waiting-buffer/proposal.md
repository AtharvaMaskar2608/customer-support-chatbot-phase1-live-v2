## Why

Report and data-flow narration walks a short caption list (~720ms per step), then freezes on the last caption while the fetch continues. Linear CHO-251 screenshot (holdings) shows the pill stuck on **"Valuing at last prices…"** after the sequence ends — the UI looks hung even though work is still in progress. Same freeze pattern exists for report `generate` and data `generateData`.

## What Changes

- **Cycle narration while the fetch is pending.** After one full pass through a flow's narration steps, wrap to the first step and keep rotating at the same ~720ms cadence until the overlapped promise settles. When it resolves, remove the narrate pill and render the result exactly as today.
- **Apply in `ChatShell` to all multi-step narrated waits:** report `generate`, data `generateData`, and contract-notes list fetch `runSelection` (same freeze bug).
- **No copy or descriptor changes.** Per-flow caption strings stay byte-stable; no fake progress bar; no new "Still working…" strings.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `report-chat-shell`: narrated generation SHALL cycle through the flow's caption sequence for the entire pending fetch, instead of freezing on the last step.

## Impact

- **Exclusive ownership:** `frontend/src/chat/ChatShell.tsx` (narration loop in `generate` / `generateData` / `runSelection`) + optional tiny shared helper colocated with the shell + related frontend tests if any exist for this path.
- **Do NOT touch:** `EmptyState`, `Stickers`, `BrokerageCard`, `prompt.py`, backend, flow/dataflow descriptors, or caption copy.
- Frontend-only. Gates: `tsc`, lint, build; manual check with a throttled/slow fetch to confirm cycling.
- Linear: CHO-251 · branch `cho-251-waiting-buffer`.

## Parallel apply

Wave 1 — safe parallel with `cho-259-brokerage-ui` and `cho-265-no-kb-mention` (disjoint file ownership).
