# CHO-248: regenerate-holdings — tasks

## 1. Refresh action

- [ ] 1.1 In `frontend/src/chat/ChatShell.tsx`, add a handler that re-runs the holdings data flow by calling the existing `generateData(getDataFlow('holdings'))` again (appends a fresh card below)
- [ ] 1.2 Surface a "Refresh prices" action as a continuation beneath the holdings card — on/next to the `dataFollowup`, or a dedicated action row — without removing the existing help ("something look off?" → Raise a ticket) path
- [ ] 1.3 Keep prior holdings cards as history (each refresh appends a new card, matching the "ask again anytime" footer)
- [ ] 1.4 Scope to holdings for this change (money/brokerage data flows unchanged)

## 2. Verification

- [ ] 2.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 2.2 Render holdings, tap "Refresh prices" → a fresh holdings card appears below after the narrated fetch; the prior card stays; the help / Raise-a-ticket path is still present
- [ ] 2.3 Screenshot before deploy (light + dark)

## 3. Ship & sync

- [ ] 3.1 `git-sync` with issue key CHO-248
- [ ] 3.2 `linear-connector` — summary comment + state on merge
