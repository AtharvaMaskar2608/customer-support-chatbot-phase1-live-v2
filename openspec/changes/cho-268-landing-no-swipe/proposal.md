# CHO-268: landing-no-swipe

## Why

CHO-260 shipped a four-per-page chip pager plus an **"or ask anything about FinX"** divider under the chip block. Product feedback (Jam screenshots on CHO-268): the second-page swipe/pager is poor UX, and the divider sits too high — leaving empty space above the composer while hiding two chips behind pagination. Revert the pager and show every chip on one screen; park the divider immediately above the chat input so the landing fits without swipe.

## What Changes

- **Remove landing chip pagination** — drop `PAGE_SIZE` / prev-next / dots from `Stickers`; the home screen renders **all** non-`hideSticker` chips in the existing wrap row (same as the conversation no-match fallback).
- **Reposition the divider** — keep **"or ask anything about FinX"** (hairline + centred label), but place it **just above the chat composer**, not mid-stack under the chips (per Jam red-box intent).
- **Keep fonts/CSS** — no chip, greeting, subtitle, or composer restyle; FinX tokens unchanged.
- Frontend-only. No backend, API, or flow-descriptor change.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `home-screen`: remove the CHO-260 pagination requirement; chips SHALL render as a single wrap row of every non-`hideSticker` flow; the **"or ask anything about FinX"** divider SHALL sit immediately above the composer (not under mid-stack chip chrome).

## Impact

- **Owns:** `frontend/src/chat/Stickers.tsx` (remove pager), `frontend/src/chat/EmptyState.tsx` (drop `paginate`; divider placement), and the `home-screen` spec delta. Minor flex layout in `EmptyState` / scroll column so the divider can sit at the bottom of the landing canvas.
- **Does not own:** traces UI, KB retrieval, subtitle copy (CHO-254), flow registry / `hideSticker`.
- **Sequence:** applies on top of CHO-260 (pager + divider already present). Rebases onto latest `main` that includes CHO-260.
- Gates: `cd frontend && npx tsc --noEmit`, `npm run lint`, `npm run build`.
- Linear: **CHO-268** · branch `cho-268-landing-no-swipe`.
