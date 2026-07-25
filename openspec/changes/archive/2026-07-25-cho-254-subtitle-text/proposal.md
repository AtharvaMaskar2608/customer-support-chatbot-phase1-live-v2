# CHO-254: subtitle-text

## Why

The home-screen subtitle still promises **ticket status**, but ticket-status lookup is Phase 2 — not live yet. Product supplied refreshed copy that focuses on reports, charges, processes, and in-chat file delivery (Linear CHO-254). While touching that same highlight span, fold in archived CHO-238: stop painting "no email verification needed." in online/green and use FinX blue accent tokens instead.

## What Changes

- **Replace the two subtitle lines** in `frontend/src/chat/EmptyState.tsx`:
  - Line 1: `Reports, charges, processes, ticket status.` → `Fetch your reports instantly, explain charges and processes.`
  - Line 2: `Files land right here — no email verification needed.` → `Files land right here in chat — no email verification needed.`
- **Retheme the highlight** on `no email verification needed.` from `text-online` / `text-online-soft` (green) to `text-accent` / `text-accent-soft` (FinX blue), matching the hero name accent (CHO-221) and absorbing archived CHO-238.
- Frontend-only. No backend, API, routing, chip layout, or pagination work.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `home-screen`: subtitle copy drops the ticket-status promise; second line adds "in chat"; the highlighted phrase uses FinX blue accent tokens instead of online/green.

## Impact

- **Owns (this PR only):** subtitle strings + highlight class in `frontend/src/chat/EmptyState.tsx`, and the `home-screen` spec lines for those subtitles / highlight colour.
- **Does not own:** Stickers pagination, chip pager controls, or the "or ask anything about FinX" divider (CHO-260).
- **Related:** archived CHO-238 (green → blue on the same phrase) — **included** here; still relevant after the copy change because the phrase remains.
- Frontend-only; gates: `npx tsc --noEmit` + `npm run build`. Visible copy/colour change → screenshot before deploy.
- Linear: CHO-254 · branch `cho-254-subtitle-text`.

## Parallel apply

**Wave 2a — sequenced ahead of CHO-260.** Do **not** parallel-apply with `cho-260-landing-pagination` (both touch `EmptyState` / home-screen). Safe after or alongside Wave 1 (`cho-251-waiting-buffer`, `cho-259-brokerage-ui`, `cho-265-no-kb-mention`) because those own disjoint files. Land this change **before** CHO-260.
