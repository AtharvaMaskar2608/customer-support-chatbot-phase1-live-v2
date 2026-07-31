## 1. Store the client code raw

- [x] 1.1 `backend/app/agent/tracing.py`: `observe_turn` sets `user_id=client_code` instead of `_stable_id(client_code)`, with a comment recording why the SSO session id is NOT covered by the same reasoning.
- [x] 1.2 Retain `_stable_id`; update its docstring to say it is no longer applied to `user_id` and is kept for the SSO session id, which may only ever be correlated by hash.
- [x] 1.3 Leave `_DENY_KEYS` untouched — a client code appearing incidentally inside a tool input or upstream payload is still masked. Only the dedicated identity field changes.
- [x] 1.4 `backend/app/agent/langfuse_mirror.py`: update the identity-mapping docstring; no code change (the mirror reads `trace.user_id`, so it follows automatically — which is also why the two sinks cannot disagree).

## 2. Specs

- [x] 2.1 `observability-tracing` — amend both requirements that mandated the hash ("No PII or secrets in stored traces" and "Trace thread_id matches conversation store"), keeping the raw session token forbidden and adding a scenario that a client code inside a payload is still masked.
- [x] 2.2 `trace-mirror` — amend the identity requirement (CHO-286) to send the client code raw, and add a findable-by-client-code scenario.

## 3. Tests

- [x] 3.1 `test_agent_tracing.py`: the persisted `user_id` is the raw client code.
- [x] 3.2 `test_agent_langfuse_mirror.py`: Langfuse `user.id` is the raw client code and equals what Postgres stored; the client code IS expected in the exported payload while the SSO session id is still absent.
- [x] 3.3 `cd backend && uv run pytest` green.

## 4. Verify

- [x] 4.1 Live turn through `POST /api/chat`: `agent_traces.user_id` and the Langfuse `userId` both read the raw client code (previously a 16-char HMAC) and agree exactly; the SSO value is still absent from the exported trace.
- [x] 4.2 The payoff verified: `GET /api/public/traces?userId=<client code>` returns that customer's trace directly, with no hash to resolve. Confirmed over the API rather than the UI (no browser in this environment).

## 5. Ship

- [ ] 5.1 `git-sync` with issue key CHO-287, branched off `main`.
- [ ] 5.2 `linear-connector` — note Linear MCP was unauthenticated as of 2026-07-30.

## 6. Carried forward

- **No migration, and none is possible.** Existing rows hold a salted HMAC that cannot be inverted, so `agent_traces` and Langfuse will both contain a permanent hashed-before / raw-after split at deploy time. A query spanning that boundary must match both `client_code` and `_stable_id(client_code)`.
- `_stable_id` and `TRACING_SALT` now have no production caller. Kept for the `finx_session_hash` idea (a CHO-286 open question); if that is dropped, a later change should remove both together.
- The trace viewer (CHO-262) could now offer a client-code search box — the payoff of this change, deliberately not built here.
