# CHO-234: remove-popular-right-now

## Why

The quick-action chip grid on the home screen is topped by a **"POPULAR RIGHT NOW"** eyebrow label. Product doesn't want to editorialise the chips as "popular" — they are the standard entry points, not a trend list. Remove the label; keep the chips.

## What Changes

- **Remove the "POPULAR RIGHT NOW" eyebrow** (`<h3>`) above the chip grid in `EmptyState`. The chips render directly under the subtitle lines, with the section spacing adjusted so it reads cleanly without a heading.
- Frontend-only. No backend, API, or contract change.

## Capabilities

### Modified Capabilities

- `home-screen`: the quick-action chip section no longer shows a "POPULAR RIGHT NOW" label; the chips render without an eyebrow heading.

## Impact

- Frontend only: `frontend/src/chat/EmptyState.tsx` (drop the `<h3>` label; keep `<Stickers>`; adjust the section's top spacing).
- No test impact expected; `tsc` + build are the gates.
- Linear: CHO-234 · branch `cho-234-remove-popular-right-now`.
