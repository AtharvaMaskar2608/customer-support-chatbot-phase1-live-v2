# CHO-216 · What's New on Home + Restart — Tasks

## 1. Backend — store reset + endpoint

- [ ] 1.1 `ThreadStore.reset_thread(session_id)`: close active thread (status `resolved` via the writer queue), replace the cache entry with a fresh thread; rehydration query selects the session's most recent thread; tests (reset clears counters/memory derivation, old rows retained, latest-thread rehydration, idempotency)
- [ ] 1.2 `POST /api/chat/reset` in the agent router: header validation → `MISSING_CREDENTIALS` 400 / reset → `{"ok": true}`; no model call; tests incl. blank-slate follow-up (reset then chat sees no history)

## 2. Frontend — pill swap + restart

- [ ] 2.1 ChatShell: `onEngaged` callback from the existing `engage()` transition + unmount cleanup aborting any in-flight agent stream
- [ ] 2.2 App/Header: `engaged` state renders "✨ What's new" (home) vs "↻ Restart" (conversation, no unseen dot); Restart click → `engaged=false`, shell remount via key, fire-and-forget `POST /api/chat/reset`
- [ ] 2.3 Frontend build green (`tsc -b` + both vite entries)

## 3. Verification

- [ ] 3.1 Backend suite green; live check: engage → Restart shows; Restart mid-stream → clean home screen, no stray text; message after restart → agent has no memory of the prior thread and Postgres shows the old thread `resolved` + a fresh active thread
