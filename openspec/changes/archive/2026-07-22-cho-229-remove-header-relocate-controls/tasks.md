# CHO-229: remove-header-relocate-controls — tasks

## 1. Park the header (comment, do not delete)

- [ ] 1.1 In `frontend/src/App.tsx`, wrap the entire `Header` component in a labelled `CHO-229 — HEADER PARKED` comment block, verbatim, so logo/title/online/client-code/back markup stays recoverable
- [ ] 1.2 Comment the imports the header alone uses (`BackIcon`, `SparkleIcon` from `./icons`; `postCloseToHost` from `./embed`) with a note to restore them alongside the header
- [ ] 1.3 Remove the `<Header … />` usage from the `App` render and the `onBack` / `platform === 'web'` close wiring

## 2. Floating top-right controls

- [ ] 2.1 Add a `FloatingControls` component: idle → "✨ What's new" (with the unseen dot); engaged → "↻ Restart" (no dot). Reuse the existing pill styling; add a small shadow for legibility over content
- [ ] 2.2 Position it `absolute top-3 right-3 z-20` inside the `max-w-[480px]` `main` (make `main` `relative`) so it pins to the widget's top-right corner, not the viewport
- [ ] 2.3 Wire the existing handlers unchanged: `onWhatsNew` (graceful no-op when content is null), `onRestart` (reset + shell remount)

## 3. Content clearance

- [ ] 3.1 In `frontend/src/chat/ChatShell.tsx`, add top padding to the scroll container's content (`p-4` → `px-4 pb-4 pt-14`, or equivalent) so the greeting and first message clear the floating cluster
- [ ] 3.2 Verify both states: empty-state greeting and an active conversation both clear the overlay; the composer/footer are unaffected

## 4. Verification

- [ ] 4.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes (no unused-symbol errors from the parked header)
- [ ] 4.2 Screenshot the widget (idle + engaged, light + dark) — confirm no header, the floating What's New/Restart top-right, and no overlap with the greeting
- [ ] 4.3 Confirm What's New still opens the modal + shows the unseen dot; Restart still resets

## 5. Ship & sync

- [ ] 5.1 `git-sync` with issue key CHO-229
- [ ] 5.2 New frontend image (bump tag), deploy via the SCP/save-load path, verify on prod
- [ ] 5.3 `linear-connector` — summary comment + state on merge
