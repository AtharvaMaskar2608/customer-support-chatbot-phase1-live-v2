# CHO-211 · Data-Card Flows (Holdings, Money in/out, Brokerage)

## Why

The four report flows shipped in CHO-207/208/209/210 are **file-delivery** flows — the answer is a PDF and the chat is the courier. The next FinX APIs (Holdings, Pay-In, Pay-Out, Brokerage slab) are different in kind: **the answer is data**, and forcing it through a file would be the exact friction a conversational UI exists to remove. This change adds the second flow family: **data cards** — the answer rendered live in the conversation as an interactive card, designed and approved in `docs/prototype/report-flow-prototype.html` (Holdings hero/allocation/rows, the merged Money passbook timeline, the rate-clustered Brokerage card).

All four upstream contracts were captured from live traffic and verified against real FinX on 2026-07-18 — including the probe that showed Holdings enforces only `Session <SessionId>` auth (the web app's extra `ssotoken`/`accessToken`/`fingerprint` are not required), which removed the last blocker.

## What Changes

- **Data-card system** (frontend): the shared card language proven in the prototype — hero fact → qualifying context → ranked/filtered list → depth-on-tap → quiet footer action; count-up reveal; paise-safe Indian-grouped INR formatting; expandable rows; count-chips that double as filters; the color discipline (success is quiet, exceptions carry the color).
- **FinX data backend**: routing for three new upstream families (Holdings on `finxomne` with `Session ` prefix; Pay-In/Pay-Out on `finx /api/middleware` with bare SessionId; Brokerage on `api.choiceindia.com /middleware-go` with the raw SSO JWT), a normalization layer for upstream inconsistencies (paise vs rupees, mixed-case statuses, two date formats, two empty-sentinels), server-side derivation of all displayed metrics, and strict PII forwarding (masked bank accounts; `Search_All_Levels`, names, and gateway IDs never leave the backend).
- **Holdings flow** (reference): zero-slot — sticker tap straight to the portfolio card. Time-honest by design: "1D" not "Today", freshness line derived from the API's own `LUT` timestamps, and a client-side CSV export matching FinX's own `{UserCode}_Holding_Overall_Report_{stamp}.csv`.
- **Money flow**: Pay-In + Pay-Out merged into **one passbook timeline** (direction is an attribute ↓/↑, not a tab), newest first, status-count chips as filters, failed/cancelled rows dimmed, and pay-out's human-readable `Reason` displayed verbatim in the row detail — the "why did my withdrawal fail?" ticket answered before it's raised.
- **Brokerage flow**: the plan's rate slab clustered **by rate, not by segment** (computed from the response at render time — slabs are per-client), percentage-primary for value-based rates, flat ₹ for per-order, with a plain per-segment fallback when descs don't parse.

Out of scope: live/streaming prices (cards state "last fetch, not live"); pay-in/pay-out initiation (display only); brokerage *charges billed* (the slab is the plan, not the bill); free-text/LLM entry (the flows remain seedable).

## Capabilities

### New Capabilities

- `data-card-system`: the shared in-chat data-card anatomy, formatting, interaction and color rules all three cards build on.
- `finx-data-backend`: backend client/routes for the four data endpoints with per-endpoint auth, normalization, derivation, and PII minimization.
- `holdings-flow`: the portfolio card (zero-slot, time-honest, CSV export).
- `money-flow`: the merged pay-in/pay-out timeline card.
- `brokerage-flow`: the rate-slab card.

### Modified Capabilities

- `report-chat-shell`: three new stickers (My holdings · Pay in / out · Brokerage) and their keyword routes join the existing four flows.

## Impact

- New frontend: card components + three flow descriptors under `frontend/src/`.
- New backend: `/api/data/holdings`, `/api/data/money`, `/api/data/brokerage` routes + normalizers under `backend/app/`.
- `docs/api_doc/api_documentation.md`: new sections for the four upstream APIs (fields we consume only).
- Security-sensitive: heaviest-PII responses so far (full names, bank account numbers, internal branch hierarchies) — the forwarding whitelist is the contract.
- Upstream quirks to flag to FinX (documented, worked around here): `'X008593` Excel-escape artifact in pay-out `ClientCode`; mixed status casing; Holdings' decorative auth extras.
