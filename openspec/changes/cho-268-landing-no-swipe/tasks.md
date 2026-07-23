## 1. OpenSpec

- [x] 1.1 Confirm proposal, design, and home-screen delta match CHO-268 Jam intent (no pager; divider above composer)

## 2. Stickers — remove pagination

- [x] 2.1 Remove `PAGE_SIZE`, page state, chevron/dot controls, and the `paginate` prop from `Stickers.tsx`
- [x] 2.2 Always render the full non-`hideSticker` wrap row (landing and no-match reply)

## 3. EmptyState — divider placement

- [x] 3.1 Drop `paginate` from the landing `<Stickers>` call
- [x] 3.2 Make EmptyState a flex column that fills the scroll canvas (`flex-1`) and pin the "or ask anything about FinX" divider with `mt-auto` so it sits just above the composer
- [x] 3.3 Preserve existing divider hairline/label classes and collapse transition behaviour

## 4. Verify

- [x] 4.1 Run `npx tsc --noEmit`, `npm run lint`, and `npm run build` in `frontend/`
