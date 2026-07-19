# CHO-216 · What's New on Home + Restart — Design

## D1 · Engagement state lives in App, fed by ChatShell

`ChatShell` already owns the `phase` state (`empty | collapsing | active`) internally. Rather than lifting the whole phase, App holds a boolean `engaged`, and ChatShell receives an `onEngaged` callback invoked from its existing `engage()` transition (idempotent — fires once per mount). The header renders "✨ What's new" when `!engaged`, "↻ Restart" when `engaged`.

## D2 · Restart = remount + server reset

Restart click:

1. `setEngaged(false)` and increment a `shellKey` counter — `<ChatShell key={shellKey} …/>` remounts, which resets every message, flow run, selection ref, and stream ref by construction (no bespoke clear-state code to keep in sync). ChatShell gains an unmount cleanup that aborts any in-flight agent stream (`agentAbort.current?.abort()`), so a streaming reply cannot write into the dead shell.
2. Fire `POST /api/chat/reset` with the session auth headers. Fire-and-forget from the UI's perspective (the home screen appears immediately); a failed reset degrades to today's behavior — the next message continues the old thread — which is safe, never blocking.

No confirm dialog: the action is instant and non-destructive server-side (the old thread is retained).

## D3 · Store reset: close-and-retain, latest-thread rehydration

`ThreadStore.reset_thread(session_id)`:

- The active thread (in-memory or rehydrated) gets `status = "resolved"` — persisted via the existing single-writer queue (a thread-status update write, same path as `set_status`).
- The session's cache entry is replaced by a fresh `Thread` (new uuid, same session id, current prompt hash) — empty turns, so caps, clarify counts, and flow-event memory all reset by derivation.
- DB keeps both rows: one session id → many thread rows over time. Rehydration on cache miss (backend restart) SHALL select the session's most recent thread by creation time; a closed (`resolved`) latest thread rehydrates as-is — its status prevents nothing, but the next `reset` or message simply continues it, matching today's semantics. (The reset endpoint always produces a fresh ACTIVE thread as the latest, so the normal post-restart path finds it.)

Flow events fired by report endpoints after a reset attach to the new thread via the same `get_thread` path — no special handling.

## D4 · `POST /api/chat/reset`

Same three auth headers as `/api/chat`, validated identically (`MISSING_CREDENTIALS` 400 pre-validation, no model call ever). On success: `{"ok": true}` 200. The endpoint is idempotent — resetting an already-fresh thread just starts another fresh thread; old empty threads are harmless rows.

## D5 · Header affordance

Same pill styling slot as What's New (dark pill, light in dark mode). Restart label: "↻ Restart". The unseen-dot logic stays bound to What's New only (no dot on Restart). After restart, the home screen shows What's New again — including the unseen dot if content was never opened.
