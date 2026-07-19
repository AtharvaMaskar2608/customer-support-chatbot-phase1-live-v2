# Design — CHO-207 Report Flows

## Context

The approved prototype (`docs/prototype/report-flow-prototype.html`) is the source of truth for the UX; `docs/finx_android_api_reference.html` is the source of truth for the upstream APIs. Four report APIs exist today (P&L, Ledger, Tax/Capital-Gains, Contract Notes); the prototype demonstrates all four off one engine. This change builds the shared machinery + the P&L reference flow; the other three are Wave 1.

The insight the prototype validates: **N report APIs are not N flows — they are one slot-filling engine plus N declarative descriptors.** Each flow differs only in which slots it collects and their rules, not in the machinery.

## Goals / Non-Goals

**Goals:**
- A frozen descriptor schema + engine that all four flows plug into.
- Backend routing that speaks each FinX backend's auth and error dialect correctly.
- A delivery layer that never leaks PII and matches the prototype's file/email cards.
- P&L working end-to-end against the live API as proof.
- Everything shaped so Ledger/Tax/Contract-Notes are pure additive descriptor changes.

**Non-Goals:**
- Free-text/LLM entry (engine is seed-ready for it; not built here).
- Contract Notes email (no FinX endpoint; our-own-mailer deferred).
- Ticket-status / brokerage-charges flows (no API).
- Real ticket backend — the help→ticket card is a UI stub returning a mock id.

## Decisions

1. **Descriptor-driven engine, schema frozen in Wave 0.** A flow is `{key, trigger, intro, slots[], delivery, narr, result}`. Slot types: `chips`, `date` (presets + calendar with per-flow constraints), `format`, `delivery`, and `selection` (the Contract Notes list→pick). The engine renders filled slots as editable chips and asks the first unfilled required slot — so "start at step N with 1..N-1 pre-filled" is just seeding, which the sticker path (empty seed) and the future LLM path (partial seed) share. **Validate the schema by hand against P&L (simple), Tax (adds `format`), and Contract Notes (adds `selection`) before freezing** — Contract Notes is the stress test, so its shape must be accommodated now even though it's implemented in Wave 1.

2. **Backend-for-frontend proxy; the browser never calls FinX.** Same PII-firewall rationale as the greeting proxy. `/api/report/<type>` accepts the collected slots + session credentials (headers), calls upstream, and returns a normalized `{delivery: "download"|"email", file?: {name, sizeLabel, format, passwordProtected}, streamUrl?, emailMasked?}` — never the raw upstream URL/`file_id`/email.

3. **Per-endpoint credential router.** The credential is a function of the backend, not the app: SessionId in `authorization` for the .NET/Go report endpoints (P&L, Ledger, Tax, Contract Notes list/download); SSO JWT for MIS/CML. The `from` header is a build tag, not auth. A small `route(endpoint) -> {url, authHeader, extraHeaders, bodyShape}` table encodes this; wrong routing fails, so it's centralized and tested.

4. **Two-layer error model.** Branch on transport first: real HTTP 401 → `AUTH_EXPIRED`; 204 (contract-notes empty) → typed empty. Then on body: `Status`/`StatusCode` != success → typed `NO_DATA` (never string-match `Reason` — wording differs across endpoints). Anything else → `UPSTREAM_ERROR`. The frontend degrades each gracefully.

5. **`RequestFor`/`FileFormat` are per-descriptor constants, never shared.** P&L/Ledger download=0, Tax download=2, email=1 everywhere. `FileFormat` 1=PDF/2=Excel only on Tax. These live in each descriptor's backend mapping so the "field that lies" can't leak into shared logic.

6. **Delivery/PII layer is shared and strict.** Download → backend fetches the file server-side and streams it to the client as a file card (raw upstream URL never reaches the browser or logs). Email → FinX sends it (RequestFor=1); we mask the echoed address before display. Logs carry status + timing only. Report PDFs are PAN-password-protected (surfaced as "password: PAN"); contract notes are not (help copy differs accordingly). Defend against the two live flags: contract-note chain is IDOR-exposed → bind every call to the authenticated session, never trust a client code from input; CML link is CloudFront-cached → treat as non-secret, fetch server-side.

7. **Chat shell = one continuous conversation.** The empty state (greeting + stickers) collapses on first engagement; messages append and auto-scroll; the composer is pinned and always available, with keyword routing that previews the LLM entry. Narrated generation (per-flow step captions) replaces the spinner. Icons are tinted inline SVGs (currentColor); download buttons give in-place ✓ feedback. Help ("Tell me") opens an actionable card → raise-a-ticket confirmation (seeds the future ticket-status flow).

8. **Wave 0 / Wave 1 split for parallelism.** This change (Wave 0) = engine + schema + chat shell + backend client/router/delivery + **P&L**. Wave 1 = Ledger, Tax, Contract Notes as three separate `cho-###` changes, each its own descriptor file + backend mapping + tests, fanned out in parallel worktrees/agents after this merges. The flow registry is a per-flow file (auto-discovered), never a shared array, so parallel flow changes don't collide.

## Risks / Trade-offs

- [Descriptor schema wrong → all flows rework] → mitigated by validating against P&L + Tax + Contract Notes shapes before freezing (Decision 1); Contract Notes' selection step is the specific risk and is designed for now.
- [Session/token expiry mid-flow] → 401 maps to `AUTH_EXPIRED`; flow shows a reopen prompt; no refresh path on our side.
- [Unconfirmed upstream branches: Ledger email, MTF `Margin:1`, Tax email shape] → documented as CONFIRM items; P&L (fully verified) is the reference, so Wave 0 doesn't depend on them.
- [Contract-note IDOR / CML cache are live infra flaws] → our layer defends (session-bound, server-side fetch) and we flag upstream; not blockers.
- [Excel URL shape differs (`_<epoch>.xlsx`)] → delivery layer names/labels by `FileFormat`, already in the descriptor.

## Migration Plan

Additive — no existing behavior changes. Ship behind the existing widget; P&L sticker becomes live while the other three stay prototype-only until their Wave 1 changes land. Rollback = disable the report routes and revert the sticker to inert.

## Open Questions

- Real ticketing backend for "raise a ticket" (stubbed here) — which system, and does it tie into the future ticket-status flow?
- Report caching: re-fetch on repeat requests, or briefly cache the generated file? (Affects delivery layer; default = no cache in Wave 0.)
