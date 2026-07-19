# Tasks — CHO-211 Data-Card Flows

Groups 1–3 are the foundation (backend routes/normalizers + shared card system). Group 4 (Holdings) proves the stack end-to-end. Groups 5–6 (Money, Brokerage) can fan out in parallel once 1–3 freeze. Group 7 wires the shell; 8–9 verify and ship.

## 1. FinX data backend — routing + normalization

- [x] 1.1 Routing entries: `holdings` (finxomne, `Session ` prefix), `payin`/`payout` (finx `/api/middleware`, bare SessionId), `brokerage` (api.choiceindia.com `/middleware-go`, raw SSO JWT) — reusing the existing `route()` table + two-layer error model
- [x] 1.2 Normalizers: paise→rupees (Holdings LTP/CP), case-insensitive status → `SUCCESS|PENDING|FAILURE|CANCELLED`, both date formats → ISO, both empty-sentinels → null
- [x] 1.3 PII whitelist filters per endpoint (masked bank dest = name + last-4; drop ClientName, full acct, Jiffy/Atom IDs, `Search_All_Levels`)
- [x] 1.4 Unit tests: routing credentials per endpoint, every normalizer, whitelist (assert dropped fields absent from output)

## 2. Backend endpoints

- [x] 2.1 `POST /api/data/holdings` — call upstream, normalize, derive per-row + portfolio metrics server-side, freshness = max(LUT); empty dict → EMPTY
- [x] 2.2 `POST /api/data/money` — fetch Pay-In + Pay-Out concurrently, merge into one normalized newest-first stream + status counts + landed-in/out totals; surface `TotalRecords`; Reason forwarded verbatim
- [x] 2.3 `POST /api/data/brokerage` — slab passthrough (no PII), Status gate
- [x] 2.4 Tests per endpoint with mocked upstreams (incl. paise fidelity vs the captured CSV values, merge ordering, Reason passthrough, pay-out casing)

## 3. Data-card system (frontend)

- [x] 3.1 Card primitives: hero (count-up value + label + context line), stat pills (up/down), expandable row (`item` + detail grid incl. full-width cell), count-chips-as-filters, show-more, quiet footer
- [x] 3.2 INR formatter: Indian digit grouping, paise-safe (₹0.10 renders, integers stay clean)
- [x] 3.3 Color discipline tokens: success-quiet ✓, pending amber, failed red, cancelled gray, dimmed rows; direction glyphs (↓ green / ↑ neutral)
- [x] 3.4 Light + dark theme verified for all primitives

## 4. Holdings flow (reference — proves the stack)

- [x] 4.1 Descriptor + zero-slot start (sticker → narrate → card, no questions)
- [x] 4.2 Card per prototype: hero + Invested + 1D/Overall pills + freshness line (gray dot, API-derived stamp) + allocation bar (top-5 + gray Other, animated) + legend + top-4 rows + Show all + expandable detail
- [x] 4.3 CSV export client-side: FinX column set + `{UserCode}_Holding_Overall_Report_{stamp}.csv`, on-button feedback only
- [x] 4.4 Footer refresh copy + "Something look off?" help (last-fetch explanation) + empty-portfolio state

## 5. Money flow

- [x] 5.1 Descriptor + card: merged timeline newest-first, direction glyphs, quiet-success statuses, dimmed failed/cancelled
- [x] 5.2 Count-chips as filters (non-zero only, tap-again clears), first 6 + Show all, 12-hour times
- [x] 5.3 Detail grid: direction-labeled request time, mode, masked destination, reference, full-width "Why" when Reason present
- [x] 5.4 Footer landed-in/out totals + "Something not adding up?" help copy

## 6. Brokerage flow

- [x] 6.1 Descriptor + card: rate clustering computed from response (singleton/`All <kind>s` labels + coverage line), percentage-primary display, flat-per-order display
- [x] 6.2 Fallback rendering (unparseable desc or >6 clusters → per-segment list), statutory-charges note, plan-vs-billed distinction in copy

## 7. Shell integration

- [x] 7.1 Three stickers (My holdings · Pay in / out · Brokerage) with tinted icons; keyword routes (holding/portfolio…, payin/payout/deposit/withdraw…, brokerage/charges/slab…); unmatched-text reply mentions data flows
- [x] 7.2 `docs/api_doc/api_documentation.md`: sections for the four upstream APIs (fields we consume only)

## 8. Verification

- [x] 8.1 Backend tests green (198); live-verified holdings + money; brokerage OK-path deferred — needs fresh SSO (its AUTH_EXPIRED path verified live)
- [x] 8.2 Playwright: all three cards end-to-end (mock upstream), incl. filter chips, expand, CSV download, dark theme
- [x] 8.3 HTML verification report with screenshots (per project convention)

## 9. Ship

- [x] 9.1 git-sync: commit(s) `CHO-211: …`, push, PR `CHO-211: data-card flows` with `Fixes CHO-211`
- [x] 9.2 linear-connector: In Progress at implementation start; summary comment + Done at merge
