# CHO-221: finx-blue-theme — design

## Context

The frontend was built token-first: all components reference the semantic `accent` utilities generated from four Tailwind v4 `@theme` tokens in `frontend/src/index.css` (`--color-accent`, `-strong`, `-soft`, `-tint`). Only four places bypass the tokens with hard-coded violet: the launcher gradient (`widget.ts:62`), the home-screen logo tile gradient (`App.tsx:38`, `from-violet-500`), the holdings donut palette (`HoldingsCard.tsx:38`), and a "purple launcher bubble" code comment. Dark theme keys off the same tokens (`dark:` variants use `accent-soft` / `accent/20` etc.), so it re-skins automatically.

Palette confirmed with the product owner (2026-07-20) against the FinX-for-Harsha Figma: primary `#2777F3`, derived ramp accepted, launcher stays a gradient, status colours unchanged.

## Goals / Non-Goals

**Goals:**
- Swap the widget's accent identity from violet to FinX blue in both themes with zero behavioural change.
- Keep the palette in exactly one spec home (`brand-theme`) so future re-brands are single-capability changes.

**Non-Goals:**
- No changes to status colours (online green, alert red) or the zinc neutrals.
- No renaming of `TintKey` values (`'violet'` stays a key name in `flow/types.ts` / `Stickers.tsx` — the classes it maps to are token-based, so it recolours automatically; renaming would churn flow definitions for no visual gain).
- No backend, API, or copy changes.

## Decisions

1. **Token swap over component edits.** Change the four `@theme` values; touch only the four hard-coded spots. Alternative — per-component class rewrites (e.g. `text-blue-600`) — rejected: it would fork the palette from the token system the codebase was built around.

2. **Derived ramp, pinned as constants.** `accent #2777F3` (Figma-confirmed), `strong #1D5FD0` (≈15% darker for hover/pressed), `soft #7AA8F8` (lightened for legibility on zinc-900 dark surfaces), `tint #E9F1FE` (near-white wash for chips/backgrounds). Owner chose derivation over pasting Figma ramp tokens; the hexes are recorded in `brand-theme` so they are now canonical regardless of origin.

3. **Launcher keeps its gradient, in blue: `linear-gradient(135deg, #4A90F5 0%, #1D5FD0 100%)`.** Flat `#2777F3` (matching FinX's flat CTAs) was offered and declined — the bubble keeps its depth. The logo tile gradient in `App.tsx` reuses the same endpoints (`from-[#4A90F5] to-accent-strong`) so bubble and header read as one identity.

4. **Holdings donut palette: lead with brand blue, recycle violet as a categorical hue.** `SEG_COLORS` becomes `['#2777F3', '#7c3aed', '#0d9488', '#d97706', '#db2777']`. Rationale: the current second hue `#2563eb` (blue-600) is nearly indistinguishable from the new lead `#2777F3`, so it is replaced — and the outgoing violet is a perfectly good categorical colour once it no longer means "brand". Alternative (keep `#2563eb`) rejected for adjacent-segment ambiguity.

## Risks / Trade-offs

- [Contrast: `#2777F3` on white for small bold text is borderline WCAG AA (~4:1)] → It is only used at ≥13px semibold (same envelope as the violet before it); verify visually in the QA pass, and darken links to `accent-strong` if anything reads weak.
- [Dark theme: `#7AA8F8` legibility on zinc-900] → Chosen lighter than the primary specifically for this; verify the FeedbackChip/links in dark QA.
- [Gradient endpoints `#4A90F5`/`#1D5FD0` are derived, not Figma tokens] → Owner approved the derived preview; if design later supplies exact tokens, only `brand-theme` + two files change.

## Migration Plan

Pure CSS/class swap — no data, no config, no deploy sequencing. Rollback = revert the commit.

## Open Questions

None — all four colour decisions were confirmed by the owner on 2026-07-20.
