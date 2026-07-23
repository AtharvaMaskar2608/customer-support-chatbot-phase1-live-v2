# CHO-254: subtitle-text — tasks

## 1. Subtitle copy (`EmptyState.tsx`)

- [x] 1.1 Change line 1 to `Fetch your reports instantly, explain charges and processes.`
- [x] 1.2 Change line 2 to `Files land right here in chat —` with highlighted span `no email verification needed.`

## 2. Highlight colour (CHO-238 folded in)

- [x] 2.1 Replace `text-online dark:text-online-soft` on the highlight span with `text-accent dark:text-accent-soft` (keep `font-medium`)

## 3. Verification

- [x] 3.1 `cd frontend && npx tsc --noEmit` clean; `npm run build` passes
- [ ] 3.2 Visual check: home screen shows new copy; highlight is FinX blue in light and dark theme; no "ticket status" text
- [ ] 3.3 Screenshot updated subtitle for PR / deploy record

## 4. Ship & sync

- [ ] 4.1 `git-sync` with issue key CHO-254 (branch `cho-254-subtitle-text`) — land **before** CHO-260
- [ ] 4.2 `linear-connector` — summary comment + state on merge
