# CHO-260: landing-pagination

## Why

The home-screen quick-action chips currently render as a single flex-wrapped grid of every non-`hideSticker` flow (six today). That layout reads like a closed, exhaustive menu and understates how much the bot can do. Product wants a **paginated** chip set plus the missing **"or ask anything about FinX"** divider above the composer — signalling open-ended chat without rewriting greeting or subtitle copy (subtitle is owned by **CHO-254**).

## What Changes

- **Paginate the home-screen chip row** — show **four chips per page** (matching the original mock's visible-chip density), with prev/next + dot controls styled in existing FinX chip typography/colours. All non-`hideSticker` flows remain reachable across pages; chip tap behaviour is unchanged.
- **Implement the missing divider** — render **"or ask anything about FinX"** (hairline + centred label, per the attachment mock) between the chip section and the chat composer on the home screen. The layout spec already requires it; the frontend never shipped it (`EmptyState` → composer gap is empty today).
- **Keep existing font/CSS language** — reuse current chip pill classes, subtitle/greeting styling, and theme tokens; no greeting or subtitle rewrite (CHO-254 lands first).
- **Brokerage stays off the home grid** — `hideSticker` unchanged; keyword routing untouched.
- Frontend-only. No backend, API, or flow-descriptor change.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `home-screen`: home-screen chips SHALL paginate (four per page with navigation controls); the **"or ask anything about FinX"** divider SHALL render between chips and the composer on the landing screen.

## Impact

- **Owns:** `frontend/src/chat/Stickers.tsx` (pagination state + controls), divider + `paginate` wiring in `frontend/src/chat/EmptyState.tsx`, and the `home-screen` spec delta for pager + divider. Possibly minor spacing in `ChatShell.tsx` if the fixed composer needs padding — padding only, no composer restyle.
- **Does not own:** subtitle copy or highlight colour (CHO-254). Assume 254's strings are already on `main` when this applies.
- **Sequence — Wave 2b:** implement **after `cho-254-subtitle-text` merges to `main`**. Rebase this branch onto main once 254 is in.
- Gates: `cd frontend && npx tsc --noEmit`, `npm run lint`, `npm run build`; visible UI change → screenshot page 1 + page 2 (light + dark) before deploy.
- Linear: **CHO-260** · branch `cho-260-landing-pagination`.

## Parallel apply

**Wave 2 sequenced — NOT parallel with CHO-254.** Both touch `EmptyState.tsx` / home-screen. Apply **after** `cho-254-subtitle-text` lands. **CAN** run after or alongside Wave 1 (`cho-251-waiting-buffer`, `cho-259-brokerage-ui`, `cho-265-no-kb-mention`) once 254 is merged (Wave 1 owns disjoint files).
