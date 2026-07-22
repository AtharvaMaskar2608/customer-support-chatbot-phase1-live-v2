# CHO-231 — design decisions

## D1 — detection is reactive; there is no proactive probe

Session validity is only known when an authenticated upstream call returns HTTP 401.
The trigger surfaces are: the profile/greeting hit at boot, any agent tool call, and any
guided-flow / data-card REST call. This change does not add a "ping to check the session"
— it handles the 401 wherever it first appears.

## D2 — short-circuit auth expiry in the loop; the model never narrates it

On `AUTH_EXPIRED`, the loop ends the turn immediately with the terminal `AUTH_EXPIRED`
event and no continuation model call. Rationale: (a) auth expiry is a deterministic,
security-sensitive state — the model should not freelance wording on it; (b) it saves a
model round-trip; (c) the frontend already owns the fixed session-expired copy. Non-auth
errors (`NO_DATA`, `UPSTREAM_ERROR`) keep narrating — the model's plain-language
explanation there is genuinely useful. The auth-expired `tool_result` is still recorded in
the thread (byte-faithful replay is preserved); the model is simply not asked to respond.

## D3 — one frontend funnel for every auth-expiry sink

`AUTH_EXPIRED` currently lands in several independent places (greeting REST, agent SSE
`onError`, report/data REST mappers). All of them route through one
`handleAuthExpired(trigger)` that (1) shows the fixed session-expired copy and (2) fires the
`session.expired` bridge event. Centralizing means the host is signaled consistently no
matter where expiry is first observed.

## D4 — dedicated `session.expired` event (not `session.ended{reason:"token-expired"}`)

The native action for expiry is **re-authenticate**, which is different from a session
*close*. A dedicated `session.expired` event makes the app's handler unambiguous and carries
a `trigger` (`profile` | `agent` | `report` | `data`) for diagnostics. `session.ended` remains
a separate concept for deliberate close. Both reuse the CHO-230 envelope
(`type`/`v`/`id`/`ts`/`payload`) — same bridge format, different `type`.

## D5 — the app re-mints + reloads with fresh handoff params; web keeps the copy fallback

On the native side, `session.expired` prompts the app to re-mint the SSO JWT / session and
reload the WebView with fresh query-param handoff — which `session.ts` re-bootstraps at boot
(and scrubs from the URL). On plain web there is no app to re-auth, so the existing
"reopen Jini from FinX" copy stays as the terminal experience. The bridge is purely additive.

## D6 — fire once per expiry (debounce)

A single dead session can produce several 401s at once (parallel tool calls, a retry, or
greeting + first message racing). `handleAuthExpired` fires the `session.expired` event
**once** per detected expiry via a module-level guard that resets on reload / new session —
so the app is not spammed with duplicate re-auth signals.

## D7 — depends on CHO-230

Reuses the CHO-230 envelope, the `window.Android.postMessage` transport, capability
detection, and `bridge.ts`. CHO-231 adds the `session.expired` sender and the auth-expiry
funnel on top; it should land after CHO-230.
