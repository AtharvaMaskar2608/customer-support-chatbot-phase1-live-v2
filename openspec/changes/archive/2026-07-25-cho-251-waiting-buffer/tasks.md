## 1. Cycling narration helper

- [x] 1.1 In `frontend/src/chat/ChatShell.tsx`, extract or inline a shared loop that advances a `narrate` pill through a caption array at ~720ms cadence, wrapping to index 0 after the last step, until the overlapped fetch promise settles
- [x] 1.2 Ensure the loop exits promptly when the promise resolves (no extra caption tick after settlement)

## 2. Wire all narrated-wait call sites

- [x] 2.1 Refactor `generate` to use the cycling loop for report fetches (including email-mode step substitution); remove the post-sequence tail delay
- [x] 2.2 Refactor `generateData` to use the same loop for zero-slot data flows; remove the post-sequence tail delay
- [x] 2.3 Refactor `runSelection` (contract-notes list fetch) to use the same loop; remove its tail delay

## 3. Verification

- [x] 3.1 `cd frontend && npx tsc --noEmit` clean; `npm run lint` clean; `npm run build` passes
- [ ] 3.2 Trigger holdings (or P&L) with a slow/throttled backend — confirm captions cycle until the result appears, then the narrate pill is gone (no freeze on last caption)
- [ ] 3.3 Repeat for a report flow and contract-notes selection on a slow list fetch
- [ ] 3.4 Confirm fast responses still feel unchanged: pill walks the steps once (or partway) and clears when the result lands

## 4. Ship & sync

- [x] 4.1 `git-sync` with issue key CHO-251
- [ ] 4.2 `linear-connector` — In Progress at start, summary + In Review at PR, Done at merge
