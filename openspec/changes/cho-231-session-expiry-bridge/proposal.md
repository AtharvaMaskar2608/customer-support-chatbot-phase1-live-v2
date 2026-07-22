# CHO-231: session-expiry-bridge

## Why

FinX session validity is only knowable **reactively** — there is no proactive probe. A
dead session surfaces as HTTP 401 (`AUTH_EXPIRED`) on the first authenticated upstream
call after expiry: the profile/greeting hit at boot ([greeting.py](../../../backend/app/greeting.py)),
any agent tool call, or any guided-flow / data-card REST call.

Today, on the agent path, that expiry is **fed to the LLM as a tool_result** — the model
narrates it in its own words ([ctx.py](../../../backend/app/agent/ctx.py) supplies the message; the
loop then emits a terminal `AUTH_EXPIRED` event *after* the narration, [loop.py:393](../../../backend/app/agent/loop.py)).
Three problems: the model **freelances on a security-sensitive state**, it costs a **wasted
model round-trip** on a fully deterministic outcome, and — most importantly — the **native
app is signaled nothing**, so it cannot re-authenticate on its own. The user is merely told
to reopen Jini from FinX manually.

## What Changes

- **Backend — short-circuit auth expiry:** when any call in a round surfaces `AUTH_EXPIRED`,
  the loop ends the turn immediately by emitting the terminal `AUTH_EXPIRED` error event with
  **no continuation model call** — the model never narrates auth expiry. (Non-auth failures
  — `NO_DATA`, `UPSTREAM_ERROR` — still narrate as before.)
- **Frontend — one funnel:** every `AUTH_EXPIRED` sink (profile/greeting hit, agent `onError`,
  guided-flow + data-card REST 401s) routes through a single `handleAuthExpired(trigger)` that
  shows the fixed session-expired copy **and** fires a `session.expired` bridge event — fired
  **once** per detected expiry (guarded against parallel/repeat 401s).
- **Bridge — `session.expired` event** (reusing the CHO-230 envelope), carrying a `trigger`
  (`profile` | `agent` | `report` | `data`). The native host re-mints the session and reloads
  the WebView with fresh handoff params (the query-param handoff [session.ts](../../../frontend/src/session.ts)
  reads at boot). On plain web (no bridge) the existing "reopen from FinX" copy stays as the fallback.

## Capabilities

### Modified Capabilities

- `agent-loop`: an `AUTH_EXPIRED` result short-circuits the turn (terminal event, no narration)
  instead of the model narrating the failure; other errored rounds are unchanged.
- `webview-host-bridge`: adds the `session.expired` host event and the requirement that every
  auth-expiry sink signals the host once.

## Impact

- **Backend**: a small guard in [loop.py](../../../backend/app/agent/loop.py) after the tool round — `if auth_expired:
  emit terminal AUTH_EXPIRED; return` before any continuation call. The auth-expired
  `tool_result` is still recorded in the thread for history; the model simply isn't asked to
  respond to it.
- **Frontend**: a shared `handleAuthExpired(trigger)` in the session/bridge layer, called from
  [useGreeting.ts](../../../frontend/src/useGreeting.ts), [ChatShell.tsx](../../../frontend/src/chat/ChatShell.tsx) `onError`,
  and the flow/data error handlers; a once-guard so the host is signaled a single time per expiry.
- **Docs**: `docs/webview_bridge.md` gains the `session.expired` event as a first-class contract
  entry (replacing the illustrative `session.ended` sibling).
- Depends on **CHO-230** (bridge envelope + `bridge.ts`). Frontend + backend change; ships as a
  new frontend + backend image. Backend tests cover the short-circuit (no continuation call, one
  terminal event).
- Linear: CHO-231 · branch `cho-231-session-expiry-bridge`.

## Open follow-up (not this change)

Whether the native app should silently auto-reload vs. prompt the user before re-auth is an
app-side UX call, specified as guidance in the contract doc, not enforced here. A proactive
session-refresh (before expiry) is out of scope — this change handles expiry reactively.
