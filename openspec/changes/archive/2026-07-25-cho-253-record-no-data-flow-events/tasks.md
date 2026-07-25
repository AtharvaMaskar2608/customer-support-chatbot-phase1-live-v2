# CHO-253: record-no-data-flow-events — tasks

## 1. Record no-data / failed outcomes

- [ ] 1.1 In `backend/app/agent/events.py`, add a no-data/failed memo variant to `render_memo` (e.g. "… The user asked for the <flow>: <labels> — no records for that period.") and let `record_flow_event` carry a non-success `outcome` (e.g. `"no_data"`) in both the memo and `meta`
- [ ] 1.2 In `backend/app/report.py` (P&L) and `backend/app/reports/{ledger,tax}.py`, record a no-data flow event in the `ToolError` guard when `result.code == CODE_NO_DATA` — before returning — so only the meaningful "attempt returned nothing" case is memoed (transient `UPSTREAM_ERROR` is not). Contract notes is deferred: its no-data is an empty *list* (a different shape from the single report-completion endpoints) and already has a frontend "Change dates" recovery
- [ ] 1.3 Preserve fire-and-forget semantics (never awaited, never delays/fails the report response) and PII hygiene (customer-facing labels + ISO dates only; never tokens or upstream fields)

## 2. Verification

- [ ] 2.1 `cd backend && uv run pytest` green; extend `events` / report tests to assert a no-data memo lands with `outcome: "no_data"` and that the success path is unchanged
- [ ] 2.2 Manual: request a P&L for a period with no trades, then send a follow-up — confirm the model's reply reflects that the prior attempt returned nothing (no crash, no PII in the memo)

## 3. Ship & sync

- [ ] 3.1 `git-sync` with issue key CHO-253
- [ ] 3.2 `linear-connector` — summary comment + state on merge
