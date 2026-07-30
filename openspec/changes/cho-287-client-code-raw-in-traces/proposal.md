## Why

Tracing has pseudonymised the client code since CHO-261: `agent_traces.user_id` is a salted HMAC (`_stable_id(client_code)`), and `observability-tracing` states that "the raw client code SHALL never be stored". CHO-286 carried that same hash into the Langfuse mirror.

That treatment is wrong for what the value actually is. The FinX client code is an **internal account identifier**, not personal data — it is not a name, contact detail, financial identifier, or government id. Hashing it bought no compliance benefit and cost the thing traces exist for: given a customer, you cannot find their turns. An operator holding a client code has to resolve a salted hash before the trace viewer or Langfuse is any use, which in practice means the lookup does not happen.

This change stores the client code raw in both sinks.

It deliberately does **not** relax anything else. Two things stay exactly as they are, for reasons that were never about PII:

- The **SSO session id** remains excluded from traces entirely. Per `docs/finx_android_api_reference.html`, the P&L / Ledger / Tax endpoints authenticate with the SessionId as the `authorization` header — it is a live credential, so keeping it out of an observability store is a security constraint, not a privacy one. (Confirmed empirically during CHO-286: a SessionId alone was enough to return real holdings data.)
- The **redaction denylist** continues to mask client-code-shaped values that appear incidentally inside tool inputs or upstream payloads. Only the dedicated identity field changes; spans do not start carrying account identifiers in arbitrary positions.

## What Changes

- `agent_traces.user_id` and the Langfuse `user_id` become the client code verbatim instead of `_stable_id(client_code)`.
- `_stable_id` is retained, no longer applied to `user_id`. It stays for the SSO session id, which may only ever be correlated by hash if that is added later (a CHO-286 open question).
- Amend the two `observability-tracing` requirements that currently mandate the hash, and the `trace-mirror` identity requirement CHO-286 introduced.
- No change to the mask, the denylist, `thread_id`, span shape, the trace viewer, or the mirror's failure semantics.

## Capabilities

### Modified Capabilities
- `observability-tracing`: "No PII or secrets in stored traces" — the client code is no longer classed as personal data and is stored raw; the raw session token remains forbidden. "Trace thread_id matches conversation store" — its `user_id` SHALL-remain-hashed clause is replaced.
- `trace-mirror`: the identity requirement now sends the client code raw to Langfuse rather than the HMAC — still the identical value Postgres holds, so the two stores stay joinable.

## Impact

- `backend/app/agent/tracing.py` — one call site in `observe_turn`, plus the `_stable_id` docstring.
- `backend/app/agent/langfuse_mirror.py` — the identity-mapping docstring.
- `backend/tests/test_agent_tracing.py`, `backend/tests/test_agent_langfuse_mirror.py` — assertions that pinned the hash.
- **Existing rows are not migrated.** `agent_traces` will hold hashed `user_id` values before this change and raw ones after, and the same split exists in Langfuse. Any query spanning the boundary has to account for both forms; see `design.md`.
- `TRACING_SALT` remains in use only if the SSO-session-hash idea is taken up; otherwise it becomes vestigial. Left in place rather than removed as scope.
