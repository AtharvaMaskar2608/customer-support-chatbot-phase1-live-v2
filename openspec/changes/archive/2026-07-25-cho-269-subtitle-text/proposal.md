# CHO-269: subtitle-text

## Why

Product wants a shorter home-screen subtitle that leads with in-chat reports, and wants the “no email verification needed” phrase called out in **green + bold** (Linear CHO-269). This supersedes the two-line CHO-254 copy and its FinX-blue highlight on that phrase.

## What Changes

- **Replace the two subtitle paragraphs** in `frontend/src/chat/EmptyState.tsx` with a single line:
  - `Get your reports in chat, explain charges and processes - no email verification needed`
- **Highlight** only `no email verification needed` with online/green tokens (`text-online` / `text-online-soft`) and `font-bold`, same base font size/leading as the surrounding subtitle.
- Frontend-only. No backend, API, chips, or composer work.

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `home-screen`: subtitle becomes one line with the CHO-269 copy; the verification phrase is green + bold (online tokens), not FinX blue accent.

## Impact

- **Owns:** subtitle markup/classes in `frontend/src/chat/EmptyState.tsx`, and the `home-screen` spec lines for subtitle copy / highlight styling.
- **Does not own:** chip layout (CHO-268), divider placement, greeting template.
- **Related:** supersedes CHO-254 subtitle strings and its blue highlight on this phrase.
- Gates: `npx tsc --noEmit` + `npm run build`.
- Linear: CHO-269 · branch `cursor/cho-269-subtitle-text-0b83`.
