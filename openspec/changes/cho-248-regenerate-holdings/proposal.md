# CHO-248: regenerate-holdings

## Why

The Holdings card is time-honest — its footer says "Ask again anytime — prices refetch on every request," and its help follow-up explains "Prices here are from the last fetch — not a live feed — so they can lag the market. Ask again for fresher numbers." But the only actionable control there is **Raise a ticket** (via the help card). There is no one-tap way to actually re-run holdings for fresher prices — the user has to retype the request (CHO-248: add an option to run the flow again, as a continuation below the last message).

## What Changes

- Add a **"Refresh prices"** action (get fresher numbers) to the Holdings result, as a continuation beneath the card. Tapping it re-runs the holdings data flow — the same narrated fetch — and appends a **fresh** holdings card below, so the conversation reads as a running history of fetches (matching the footer's "ask again anytime").
- The existing help follow-up ("something look off?" → Raise a ticket) stays; this adds the refresh action alongside it, so the two paths — get fresher data vs escalate — are both one tap.
- Frontend-only. Re-uses the existing zero-slot holdings fetch; no backend/API change. Scoped to holdings (money/brokerage data flows unchanged).

## Capabilities

### Modified Capabilities

- `holdings-flow`: the Holdings result SHALL offer a one-tap "Refresh prices" action that re-runs the flow and appends a fresh card below (a continuation), not only a "Raise a ticket" escalation.

## Impact

- Frontend only: `frontend/src/chat/ChatShell.tsx` — a refresh handler that calls the existing `generateData(getDataFlow('holdings'))` again (appending a new card below); rendered as an action on/under the holdings `dataFollowup` (or a dedicated action row).
- `frontend/src/flow/dataflows/holdings.ts` / `frontend/src/chat/datacards/HoldingsCard.tsx` — surface the refresh affordance; the freshness copy is unchanged.
- No backend, API, or contract change. `tsc` + lint + build are the gates. Visible UI change → screenshot before deploy.
- Linear: CHO-248 · branch `cho-248-regenerate-holdings`.
