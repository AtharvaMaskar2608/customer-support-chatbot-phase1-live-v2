# CHO-260: landing-pagination — tasks

## 0. Prerequisites

- [x] 0.1 Confirm **CHO-254** (`cho-254-subtitle-text`) is merged to `main`; rebase `cho-260-landing-pagination` onto `main` before implementation
- [x] 0.2 Do **not** start while CHO-254 is still open on the same files — both touch `EmptyState.tsx`
- [x] 0.3 Do **not** edit subtitle strings or the highlight class (owned by CHO-254)

## 1. Paginated landing chips

- [x] 1.1 In `frontend/src/chat/Stickers.tsx`, add `paginate?: boolean` (default `false`) and `PAGE_SIZE = 4`; when `paginate`, slice `ALL_FLOWS` by current page index
- [x] 1.2 Render prev/next controls and dot indicators below the chip row when `paginate && totalPages > 1`; disable prev on page 0 and next on last page; style with existing zinc/accent tokens (no new font sizes)
- [x] 1.3 In `frontend/src/chat/EmptyState.tsx`, pass `paginate` to `<Stickers>`; leave the no-match reply path on default (non-paginated)
- [x] 1.4 Confirm Brokerage (`hideSticker`) never appears on any page

## 2. "or ask anything about FinX" divider

- [x] 2.1 In `frontend/src/chat/EmptyState.tsx`, add the hairline + centred **"or ask anything about FinX"** divider below the chip/pagination section (`text-sm` muted zinc; `border-zinc-200` / dark pair for hairlines)
- [x] 2.2 Adjust section spacing so the divider reads cleanly against the fixed composer footer in `ChatShell.tsx` (tweak padding only if needed — do not restyle composer)
- [x] 2.3 Divider collapses with the empty state on first engagement (same transition as greeting/chips)

## 3. Verification

- [x] 3.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 3.2 Home screen page 1 shows four chips + navigation; page 2 shows remaining chips; tapping any chip still submits the trigger phrase
- [ ] 3.3 Divider text visible between chips and composer on home screen; absent after empty state collapses
- [ ] 3.4 Screenshot page 1 and page 2 in light + dark before deploy

## 4. Ship & sync

- [ ] 4.1 `git-sync` with issue key **CHO-260** (branch `cho-260-landing-pagination`)
- [ ] 4.2 `linear-connector` — summary comment + state on merge
