# CHO-216 · What's New on Home + Restart

## Why

The "✨ What's new" pill occupies the header at all times, but announcements only matter before a conversation starts — and once one IS running, the header offers no way to start over. A user deep in a thread (or one whose conversation went sideways) has no reset: the UI scrolls forever and the agent's memory and cap counters keep accumulating on the session thread. Requested behavior: What's New lives only on the home screen; the moment anything kicks off, that slot becomes a **Restart** control that resets the entire thing — UI *and* agent memory.

## What Changes

- **Header pill swaps by conversation state**: on the home screen (greeting + stickers) the header shows "✨ What's new" exactly as today (unseen dot, modal, remote content). The moment the user engages — sticker tap or first composer submit — the pill becomes "↻ Restart". It stays Restart for the life of the conversation and reverts to What's New after a restart returns the widget to the home screen.
- **Restart resets the frontend completely**: any in-flight agent stream is aborted, the conversation clears, and the widget returns to the greeting/sticker home screen (implementation: remount the chat shell — every message, flow run, and stream ref resets by construction).
- **Restart resets the agent too**: a new `POST /api/chat/reset` (same auth headers as `/api/chat`, no model call) closes the session's current thread in the store — status `resolved`, all rows retained for the training corpus — and starts a fresh thread for the session: empty history, fresh cap counters, no flow-event memory. The next message starts from a blank slate.
- **Store: one session, many threads**: the conversation store gains restart support — a session id maps to its *latest* thread; rehydration after a backend restart picks the most recent thread for the session, never a closed one.

Out of scope: a confirm dialog (restart is instant; the old thread is retained server-side), restart analytics, and any change to What's New content or modal behavior.

## Capabilities

### Modified Capabilities

- `whats-new`: the pill's visibility becomes home-screen-only, with the Restart control taking its header slot during a conversation.
- `agent-loop`: new `/api/chat/reset` endpoint (credential-validated, no model call).
- `conversation-store`: per-session thread reset — close-and-retain the active thread, start a fresh one, latest-thread rehydration.

## Impact

- Backend: `app/agent/router.py` (+reset route), `app/agent/store.py` (`reset_thread`, latest-thread rehydration query), `app/agent/schema.sql` (drop the CHO-213 `UNIQUE(session_id)` constraint — discovered live: it enforced one-thread-per-session and silently rejected the fresh thread's insert — plus a `(session_id, created_at DESC)` index for latest-thread rehydration; idempotent migration statements applied to the dev DB). No model calls, no new tables.
- Frontend: `App.tsx` (pill swap + restart wiring + shell remount key), `ChatShell.tsx` (engagement callback, stream-abort on unmount). What's New modal/hook untouched.
- PII/compliance: unchanged — reset stores nothing new; old threads retain their existing content under the existing retention rule.
