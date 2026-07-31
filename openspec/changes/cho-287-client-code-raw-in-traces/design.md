## Context

`observe_turn` sets `user_id=_stable_id(client_code)` — a 16-char salted HMAC. Two `observability-tracing` requirements pin that ("The `user_id` SHALL be an HMAC hash of the client code… the raw client code SHALL never be stored", and "`user_id` SHALL remain an HMAC-hashed client code"), and CHO-286's `trace-mirror` capability carried it into Langfuse so both stores agreed. `_stable_id` is called in exactly one place; `client_code` also appears in the redaction denylist, which is a separate mechanism covering incidental occurrences inside payloads.

## Goals / Non-Goals

**Goals:**
- Make a trace findable by the identifier an operator actually holds.
- Keep the two sinks storing the identical value, so the CHO-286 join still works on `user_id`.
- Leave every genuinely credential-driven protection untouched.

**Non-Goals:**
- Not relaxing the SSO session id. Different category, different reason.
- Not touching the denylist. A client code appearing inside a tool input or upstream payload is incidental, not identity, and stays masked.
- Not backfilling historical rows.
- Not removing `_stable_id` or `TRACING_SALT`.

## Decisions

**1. Store the client code raw in the dedicated identity field only.**
The distinction that matters is *position*, not *value*: `user_id` is a field whose whole purpose is identifying whose turn this was, and an operator reaching for it already knows the client code. A client code appearing inside `span.input` is a different thing — unstructured, unpredictable, and adjacent to whatever else the payload carried — and the denylist continues to cover that.
*Alternative considered — drop `client_code` from `_DENY_KEYS` as well:* rejected. It would widen what spans carry with no lookup benefit, since the lookup is served entirely by `user_id`.

**2. Keep `_stable_id` and `TRACING_SALT`.**
`_stable_id` becomes unused by `user_id` but is the mechanism a future `finx_session_hash` would need — the SSO session id can only ever be correlated by hash, never stored. Deleting it now to re-add it later is churn; it stays with a docstring saying what it is and is not for.
*Trade-off acknowledged:* this leaves a helper with no production caller. That is deliberate and documented rather than accidental.

**3. Do not migrate existing rows.**
`agent_traces` has ~200 rows locally and more in prod, all with hashed `user_id`. Rewriting them would need the salt and the full client-code set to invert the hash — which is exactly what pseudonymisation prevents. It is not invertible, so a migration is impossible, not merely undesirable.
*Consequence:* both stores contain a hard split at deploy time — hashed before, raw after. A query for one customer's history across the boundary must match both `client_code` and `_stable_id(client_code)`. Worth knowing before anyone builds a dashboard on `user_id`.

## Risks / Trade-offs

- **[Risk]** The client code lands in an observability store that is admin-gated but broader-access than the FinX APIs themselves. → **Mitigation**: accepted deliberately — this is the change. The trace viewer is already admin-gated (CHO-262) and the Langfuse instance is self-hosted, so the value does not leave our infrastructure.
- **[Risk]** Someone reads this change as "identifiers in traces are fine now" and relaxes the session id too. → **Mitigation**: the proposal, the spec text and the code comment each state the distinction explicitly — the SessionId is excluded because it *authenticates*, not because it identifies.
- **[Trade-off]** The hashed/raw split is permanent and unfixable in the historical data. Cheap to live with (traces are operational, not analytical) but it should be stated rather than discovered.

## Migration Plan

Code and spec change only; no data migration, and none is possible (see decision 3). Rollback is reverting the commit — new rows return to hashed, and the split simply gains a third segment. Because the mirror derives its `user_id` from the same variable, both sinks change together with no risk of them disagreeing.

## Open Questions

- Should the trace viewer (CHO-262) offer a client-code search box now that the value is directly searchable? That is the payoff of this change and is not built here.
- Does the `finx_session_hash` metadata idea from CHO-286 get taken up, or does `_stable_id` stay unused indefinitely? If the latter, a later change should remove it and `TRACING_SALT` together.
