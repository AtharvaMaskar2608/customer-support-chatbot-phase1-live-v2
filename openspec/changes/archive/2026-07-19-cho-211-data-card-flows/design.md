# Design — CHO-211 Data-Card Flows

## The one distinction driving everything

File flows (CHO-207–210): the answer lives *outside* the chat; the hero is a download button.
Data flows (this change): **the answer is the thing on screen**; the chat is the destination. Download demotes to a quiet secondary action. Reusing the file-card pattern here would mean "download a PDF to see your holdings" — the exact friction this product exists to remove.

## Auth matrix (live-verified 2026-07-18)

| Endpoint | Host | `authorization` | Notes |
|---|---|---|---|
| Holdings `COTI/V1/Holdings` | `finxomne.choiceindia.com` | `Session <SessionId>` | Probed: web app also sends `ssotoken` + body `accessToken` (FINX-issued JWT: UserId+DeviceId+SessionId) + `fingerprint` — **none enforced** (A/B/C probe, all 200). |
| Pay-In `GetPayInTxnRpt` | `finx.choiceindia.com/api/middleware` | bare SessionId | Paginated: `StartPos`/`NoOfRecords`, `TotalCount.TotalRecords`. |
| Pay-Out `GetPayOutTxnRpt` | `finx.choiceindia.com/api/middleware` | bare SessionId | Same shape as Pay-In + `Reason`, `CANCELLED`. |
| Brokerage `middleware-go/v2/get-brokerage-slab` | `api.choiceindia.com` | **raw SSO JWT** | Per-client slabs (`ClientID` body). |

Empirical: the SessionId outlives the 8h SSO JWT (session still authorized 1.7h after SSO `exp`). Brokerage is the only data endpoint needing a *fresh* SSO token.

## Normalization layer (backend, at the boundary)

Upstream inconsistencies are normalized once, server-side — the frontend never sees them:

- **Units**: Holdings `LTP`/`CP` arrive in **paise** (÷100); `ABP` in rupees (confirmed against FinX's own CSV export). Money amounts are rupees.
- **Status casing**: `SUCCESS` (pay-in) vs `Success`/`Failure`/`CANCELLED` (pay-out) → canonical enum `SUCCESS | PENDING | FAILURE | CANCELLED`, matched case-insensitively.
- **Dates**: ISO-`T` (pay-in) vs space-separated (pay-out) → ISO 8601.
- **Empty sentinels**: `"1900-01-01T00:00:00"` (pay-in) vs `""` (pay-out) → `null`.
- **Excel artifact**: pay-out `ClientCode` arrives as `'X008593` (leading apostrophe) — not consumed, flagged to FinX.

## Derivation lives server-side

All displayed numbers are computed in one tested place (backend), never in the card: holdings per-row `current/invested/pnl/pnl%/day/day%/allocation` + portfolio totals; money landed-in/landed-out totals + status counts. The card renders; it does not calculate. (The prototype computes client-side only because it is a design artifact.)

## Time honesty (Holdings)

- Never "Today" — the session-move pill is **"1D"**: `Q×(LTP−CP)` is the last session's move, wrong to call "today" off-hours.
- Freshness line in the hero (gray dot — deliberately not the green online dot): "Prices as of `<max LUT across scrips>` — last fetch, not live". Derived from the response, never hardcoded.
- Footer teaches the conversational refresh model: "Ask again anytime — prices refetch on every request."
- No sparklines/history charts: we have no historical data — no data, no fake chart.

## Money: one passbook timeline, not tabs

FinX has two report screens; the user has one mental model (a passbook). Direction is an attribute (↓ green for in; ↑ neutral — only incoming money earns green), status carries the color, and **success is quiet** (✓ only) while exceptions get words (`● Pending` amber, `● Failed` red, `● Cancelled` gray) and failed/cancelled rows dim. Count-chips (`6 landed · 4 pending…`) double as filters (tap again to clear); only non-zero statuses render. Pay-out's `Reason` ("Request rejected due to low funds (Rs 70.61)…") displays **verbatim** in a full-width detail cell — displayed, never branched on (ground rule).

Backend merges both upstreams in one `/api/data/money` call (concurrent fetch, one normalized stream) — one round trip, one place to sort/merge/paginate.

## Brokerage: cluster by rate, computed at render time

The slab's information content is small (this client: 4 distinct rates across 10 rows). Cluster identical `(amount, unit)` pairs across segments → "All futures / All options / Equity ×2" with segment coverage as a subline. **Computed from the response** — slabs are per-client, so the grouping must degrade gracefully: unparseable `desc` strings or >6 clusters → plain per-segment list. Value-based rates display percentage-primary (`0.01%` — the number Indian brokers advertise) with the official ₹-per-₹10,000 phrasing beneath; flat rates display `₹20 · flat per order`.

## PII forwarding whitelist (the contract)

| Endpoint | Forward | Drop / mask |
|---|---|---|
| Holdings | Sym, Name, Q, ABP, LTP, CP (normalized) + derived | everything else (Token, TxnId, MTF fields…) |
| Pay-In | direction, amount, status, time, mode, masked dest (bank name + last-4), voucher ref | ClientName, full `ClientBankAccNo`, Jiffy/Atom IDs |
| Pay-Out | ditto + `Reason` verbatim | ditto + **`Search_All_Levels`** (internal branch/employee hierarchy) |
| Brokerage | title/desc groups as-is (no PII present) | — |

Logging stays status + timing only; response bodies never logged.

## CSV export without a new PII surface

The Holdings CSV (`{UserCode}_Holding_Overall_Report_{stamp}.csv`, FinX's own column set: Instrument, Exchange, QTY | LOT, Avg. Price, LTP, Invested Amt., Current Value, Returns, Returns %, Product) is generated **client-side from data the card already holds** — no extra endpoint, no second copy of the portfolio in flight. Feedback happens on the button (spinner → "Saved to downloads" → revert), never as a chat bubble with a machine filename.

## Compliance

Cards state facts only. A 51% single-stock concentration renders as a number, never as advice ("consider diversifying" must never appear). Footer disclaimer stays.
