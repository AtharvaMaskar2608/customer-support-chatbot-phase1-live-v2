# CHO-273: reset-thread-on-main-menu-including-cold-load

## Why

FinX SSO sessions last ~8 hours. The conversation store rehydrates the
**latest** thread for that `sessionId`, so returning to the widget (or
landing on home without tapping Main Menu) can feed the agent hours of
rotted short-term memory from an earlier visit.

CHO-216 already blanks the thread when the user taps **Main Menu**. Cold
open onto the home screen did not — that gap is the bug.

## What

- On every path that lands the user on the main menu / home empty state,
  fire `POST /api/chat/reset` (same fire-and-forget posture as CHO-216):
  - **Cold load** (widget open → home)
  - **Main Menu** pill (already did; keep via shared helper)
- No backend contract change — reuse `/api/chat/reset`.
- Production chat after reset still starts from primed instructions only
  (empty thread turns).

## Out of scope

- Changing ThreadStore rehydration / retention semantics.
- Idle-timeout or server-side session TTL for threads.
- Playground session namespacing (already isolated under `pg:`).
