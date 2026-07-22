# CHO-229: remove-header-relocate-controls

## Why

The widget's top header bar carries chrome the product no longer wants on screen: the sparkle logo, the "Choice Jini" title, the green online dot, and the client code (e.g. `X008593`). Confirmed with product — remove the whole bar. Its two *functional* controls (What's New and the Restart takeover) still matter, so they move rather than disappear. The back/close chevron is dropped entirely: in the native Android WebView the app owns closing, and the corner-web embed can close via the launcher bubble.

## What Changes

- **Remove the header bar** from the live layout: sparkle logo, "Choice Jini" title, online status dot, client code, and the back chevron.
- **Drop the back/close wiring** — the `onBack` / `postCloseToHost` path (`platform === 'web'` close-to-host) goes away with the chevron. Native chrome owns closing.
- **Relocate What's New + Restart** to a small **floating cluster pinned to the top-right** of the widget, rendered by React inside the webview, overlaying the chat content. Same dual-purpose slot as today (CHO-216): idle → "✨ What's new" (with unseen dot); engaged → "↻ Restart". The unseen dot never renders on Restart.
- **Top spacing** on the chat content (ChatShell's scroll container) so the greeting / first message clears the floating cluster — replacing the vertical space the header used to occupy.
- Frontend-only. No backend, API, or contract change.

### Implementation note — park, don't delete (product request)

The header markup is **commented out in place, not deleted** — kept as a labelled `CHO-229 — HEADER PARKED` block in `App.tsx` (with its logo tile gradient, title, online/client-code treatment, and back-button markup intact) so the design is recoverable if a header is ever reinstated. The imports it alone used (`BackIcon`, `SparkleIcon`, `postCloseToHost`) are commented alongside it so nothing reads as unused. Only the two live controls are re-implemented (as the floating cluster).

## Capabilities

### Modified Capabilities

- `home-screen`: the layout no longer includes a header bar; the logo, title, online status, and client code are not displayed anywhere; the What's New / Restart control renders as a floating top-right overlay instead of in a header.
- `whats-new`: the "What's new" control (and its Restart takeover) is a floating top-right control, not a header pill.

## Impact

- Frontend only: `frontend/src/App.tsx` (park the header, add the floating cluster, drop the back wiring) and `frontend/src/chat/ChatShell.tsx` (top padding on the scroll container so content clears the overlay).
- `frontend/src/embed.ts`'s `postCloseToHost` becomes unused by the app (still exported; harmless) — the corner-web close now relies on the launcher bubble toggle.
- No test impact expected (no test asserts header contents); `tsc` + build are the gates. The frontend has no unit-test runner.
- Ships to production as a new frontend image (v1.0.7) — visible UI change, so a screenshot review before deploy is warranted.
- Linear: CHO-229 · branch `cho-229-remove-header-relocate-controls`.

## Open follow-up (not this change)

Where the floating cluster sits and its exact styling (over-content legibility, safe-area on small webviews) is a visual-polish pass — capture any tweaks during implementation review, not here.
