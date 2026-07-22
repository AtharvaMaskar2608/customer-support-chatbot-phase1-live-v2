# CHO-231: session-expiry-bridge — tasks

## 1. Backend — short-circuit auth expiry in the agent loop

- [ ] 1.1 In `app/agent/loop.py`, after the tool round completes (where `auth_expired` is set from `outcome.error_code == CODE_AUTH_EXPIRED`), add a guard: if `auth_expired`, emit the terminal `AUTH_EXPIRED` error event and `return` — before the "every other case → call the model again" continuation.
- [ ] 1.2 Keep recording the auth-expired `tool_result` turn in the thread (byte-faithful replay preserved); only the continuation model call is skipped.
- [ ] 1.3 Leave non-auth errors (`NO_DATA`, `UPSTREAM_ERROR`) narrating exactly as before.
- [ ] 1.4 `uv run pytest` — assert: an `AUTH_EXPIRED` tool result yields exactly one terminal `AUTH_EXPIRED` event, no continuation model call, and no assistant narration text; a `NO_DATA` round still narrates.

## 2. Frontend — the auth-expiry funnel + session.expired sender

- [ ] 2.1 Add `sendSessionExpiredToHost(trigger)` to `frontend/src/bridge.ts` (from CHO-230): `session.expired` event with `payload: { trigger }`, via `window.Android.postMessage`; no-op (returns false) when no bridge.
- [ ] 2.2 Add `handleAuthExpired(trigger)` in the session/bridge layer: show the fixed session-expired copy path AND call `sendSessionExpiredToHost(trigger)` — guarded to fire the host event **once** per expiry (module-level flag, reset on reload / new session).
- [ ] 2.3 Route every `AUTH_EXPIRED` sink through it: `useGreeting.ts` (trigger `profile`), `ChatShell.tsx` `onError` AUTH_EXPIRED branch (trigger `agent`), the guided-flow error handler (trigger `report`), and the data-card error handler (trigger `data`).
- [ ] 2.4 Confirm the fixed copy still renders once (no double bubble): with the backend short-circuit the model no longer narrates, so only the shell's session-expired copy shows.

## 3. Docs — contract

- [ ] 3.1 In `docs/webview_bridge.md`, promote `session.expired` to a first-class event: envelope, `trigger` values, and the native handling (re-mint + reload the WebView with fresh handoff params; web fallback = "reopen from FinX" copy).

## 4. Verification

- [ ] 4.1 Backend: `uv run pytest` green (short-circuit assertions in §1.4).
- [ ] 4.2 Frontend: `npx tsc --noEmit` + `npm run lint` + `npm run build` clean.
- [ ] 4.3 Bridge present (stub `window.Android.postMessage` in the demo): an expired session at boot fires one `session.expired {trigger:"profile"}`; an expired session mid-chat fires one `{trigger:"agent"}`; a second 401 does not re-fire.
- [ ] 4.4 Web (no bridge): auth expiry shows the "reopen from FinX" copy, no errors from the absent bridge.

## 5. Ship & sync

- [ ] 5.1 `git-sync` with issue key CHO-231 (after CHO-230 lands — shared `bridge.ts`).
- [ ] 5.2 New frontend + backend image, deploy via the SCP/save-load path, verify on prod.
- [ ] 5.3 `linear-connector` — summary comment + state on merge.
