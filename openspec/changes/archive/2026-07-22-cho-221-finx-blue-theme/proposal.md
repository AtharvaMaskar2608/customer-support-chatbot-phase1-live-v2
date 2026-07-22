# CHO-221: finx-blue-theme

## Why

The widget still wears the violet palette from the original mock, but it is embedded inside the FinX app, whose design system is blue (primary `#2777F3` per the FinX-for-Harsha Figma). The mismatch makes Jini read as a third-party bolt-on instead of a native FinX surface. Palette confirmed with the product owner on 2026-07-20.

## What Changes

- Replace the violet accent token family in `frontend/src/index.css` with the FinX blue ramp (confirmed values):
  - `--color-accent`: `#7c3aed` → `#2777F3`
  - `--color-accent-strong`: `#6d28d9` → `#1D5FD0` (hover/pressed)
  - `--color-accent-soft`: `#a78bfa` → `#7AA8F8` (dark-theme accents)
  - `--color-accent-tint`: `#ede9fe` → `#E9F1FE` (chips/backgrounds)
- Launcher bubble gradient in `frontend/src/widget/widget.ts` becomes blue: `linear-gradient(135deg, #4A90F5 0%, #1D5FD0 100%)` (was `#8b5cf6 → #6d28d9`); "purple" wording in comments updated.
- Home-screen logo tile gradient (`from-violet-500 to-accent-strong` in `App.tsx`) moves to the blue ramp.
- Holdings donut segment palette leads with brand blue instead of violet (hue-collision handling is a design.md decision).
- Status colours are explicitly **unchanged**: online green `#16a34a`/`#4ade80`, alert red `#ef4444`.
- No behavioural changes; no backend changes.

## Capabilities

### New Capabilities

- `brand-theme`: the widget's colour system — accent token ramp pinned to the FinX blue design system, launcher/header gradients drawn from that ramp, status colours independent of the accent. Gives the palette one spec home so future re-brands are single-capability changes.

### Modified Capabilities

- `widget-launcher`: "purple launcher bubble" requirement becomes a blue-gradient bubble per `brand-theme`.
- `home-screen`: "purple send button" requirement becomes an accent-coloured send button per `brand-theme`.
- `whats-new`: "purple 'Got it' button" requirement becomes an accent-coloured button per `brand-theme`.

## Impact

- Frontend only: `frontend/src/index.css` (tokens), `frontend/src/widget/widget.ts` (launcher CSS + comment), `frontend/src/App.tsx` (logo gradient), `frontend/src/chat/datacards/HoldingsCard.tsx` (`SEG_COLORS`).
- Every other component already uses the semantic `accent` utilities, so both light and dark themes re-skin via the token swap — no per-component edits.
- No API, dependency, or test-assertion impact (no test references colours).
- Linear: CHO-221 · branch `cho-221-finx-blue-theme`.
