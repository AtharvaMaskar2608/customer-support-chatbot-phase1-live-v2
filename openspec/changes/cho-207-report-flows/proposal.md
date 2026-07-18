# CHO-207 · Report Flows (foundation + P&L reference)

## Why

The chat widget can greet a user but can't yet *do* anything — the composer is a no-op. The highest-value first action is pulling a report. The approved prototype (`docs/prototype/report-flow-prototype.html`) proves the whole experience: tap a sticker → answer a couple of questions → the file (or email) lands, in one continuous conversation. This change builds the reusable machinery behind that — a descriptor-driven flow engine, the backend routing to FinX's report APIs, the server-side delivery/PII layer, and the chat shell — and proves it end-to-end with the **P&L** flow. The other three flows (Ledger, Capital Gains, Contract Notes) then fan out in parallel against this frozen foundation.

## What Changes

- **Flow engine** (frontend): a descriptor-driven state machine that asks one slot at a time, renders filled slots as editable chips, and supports a *selection step* (for Contract Notes' list→pick). Slots are seedable so the future free-text/LLM entry drops in without touching flows.
- **Chat shell** (frontend): the continuous-conversation UX from the prototype — empty state collapses on engage, pinned composer with keyword routing, narrated generation, tinted SVG icons, download-button feedback, help → raise-a-ticket card.
- **FinX report backend**: per-endpoint auth routing (SessionId for the .NET/Go report endpoints, SSO JWT for MIS/CML), the two-layer error model (HTTP 200 `Status:Fail` vs. real 401), `RequestFor` hardcoded per endpoint, and `FileFormat` for Tax.
- **Delivery/PII layer**: fetch every artifact server-side; never surface report URLs, `file_id`, or raw emails; mask emails; report PDFs are PAN-protected, contract notes are not.
- **P&L flow** (reference): segment → date range → delivery, PDF only, "incl. charges", download or FinX-email — proving engine + backend + delivery + shell together.

Out of scope (this change): Ledger, Capital Gains, Contract Notes flows (Wave 1, parallel follow-ons); the free-text/LLM entry; Contract Notes email (FinX has no CN email endpoint); ticket-status and brokerage-charges (no API yet).

## Capabilities

### New Capabilities

- `report-flow-engine`: descriptor schema + slot-filling/selection state machine that drives any report flow one step at a time, with editable slots and seed-to-skip support.
- `report-chat-shell`: the conversation surface — collapse-on-engage empty state, pinned composer + keyword routing, narrated generation, tinted icon system, download feedback, help→ticket card.
- `finx-report-backend`: backend client for the FinX report APIs with per-endpoint credential routing, two-layer error handling, and the server-side delivery/PII layer.
- `pnl-report-flow`: the Profit & Loss report flow (reference implementation exercising the full stack).

### Modified Capabilities

(none — builds on the phase-1 scaffold; session-bootstrap already provides USER_ID/session/SSO token.)

## Impact

- New frontend: flow engine + descriptors + chat-shell components under `frontend/`.
- New backend: `finx` report client, auth router, delivery layer, and `/api/report/*` routes under `backend/`.
- External dependencies: FinX Android report APIs (`docs/finx_android_api_reference.html`; contracts to be added to `docs/api_doc/api_documentation.md` as each is consumed).
- Security-sensitive: PII minimization and the two live infra flags (contract-note IDOR, CML CloudFront cache) constrain the delivery layer.
- Unblocks Wave 1: Ledger, Capital Gains, Contract Notes as parallel changes once the descriptor schema freezes.
