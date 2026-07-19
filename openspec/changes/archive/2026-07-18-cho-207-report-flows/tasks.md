# Tasks — CHO-207 Report Flows

Groups 1–4 are the Wave-0 foundation and are sequential-ish (engine + backend + shell). Group 5 (P&L) proves the stack. Ledger / Tax / Contract Notes are **separate Wave-1 changes** that fan out in parallel once this merges — noted in Group 7.

## 1. FinX report backend — client, routing, errors

- [x] 1.1 `finx` upstream client (httpx async) with a `route(endpoint) → {url, authHeader, extraHeaders, bodyShape}` table encoding per-endpoint auth (SessionId vs SSO JWT) and the `from` build tag
- [x] 1.2 Two-layer error mapping: HTTP 401 → `AUTH_EXPIRED`, 204 → empty, body `Status`/`StatusCode` fail → `NO_DATA`, else `UPSTREAM_ERROR` (never string-match `Reason`)
- [x] 1.3 Session-bound client-code resolution (from authenticated session only; reject client codes from request input — IDOR defense)
- [x] 1.4 Unit-test routing (correct credential per endpoint) + error mapping, with mocked upstreams (no live calls)

## 2. Delivery / PII layer (backend)

- [x] 2.1 Server-side artifact fetch → stream to client as a file; never return upstream URL / signed link / `file_id`
- [x] 2.2 Email-confirmation masking (registered email → `xxx***@…`)
- [x] 2.3 PII-safe logging (status + timing only; no bodies, URLs, or credentials); normalized response envelope `{delivery, file?, streamUrl?, emailMasked?}`
- [x] 2.4 Tests: download hides the upstream URL; email is masked; logs carry no PII

## 3. Flow engine + descriptor schema (frontend)

- [x] 3.1 Descriptor schema + registry (per-flow file, auto-discovered — no shared array)
- [x] 3.2 Engine: render filled slots as editable chips, prompt first unfilled required slot, support seeded/non-contiguous slots
- [x] 3.3 Slot widgets: `chips`, `date` (presets + constrained calendar), `format`, `delivery`, `selection`
- [x] 3.4 Validate schema by hand-modelling P&L (simple), Tax (`format`), and Contract Notes (`selection`) descriptors before freezing; adjust schema if any doesn't fit
- [ ] 3.5 Engine unit tests (sequential prompt, edit-and-resume, partial seed, selection step)

## 4. Chat shell (frontend)

- [x] 4.1 Continuous conversation surface; empty state (greeting + stickers) collapses on engage
- [x] 4.2 Pinned composer with keyword routing (matched → flow; unmatched → available actions)
- [x] 4.3 Narrated generation (per-flow step captions) replacing the spinner
- [x] 4.4 Tinted inline-SVG icon system (currentColor)
- [x] 4.5 Download-button feedback (busy → ✓ → revert)
- [x] 4.6 Help → actionable card → raise-a-ticket confirmation card (stub id/status)
- [x] 4.7 Auto-scroll to newest message; light + dark

## 5. P&L flow (reference — proves the stack)

- [x] 5.1 P&L descriptor: segment (Equity/F&O/Commodity ↔ Cash/Derv/Comm), date range (Jan 2018 → +7d, max 2y), delivery (PDF/email); PDF-only, no format
- [x] 5.2 Backend `/api/report/pnl` → `GetGlobalPNLPDF` mapping (`Group`, dates, `RequestFor` 0/1, `With_Exp` true)
- [x] 5.3 Result cards: download file card ("PDF · password: PAN", incl. charges copy) + masked-email confirmation, both with the shell affordances
- [x] 5.4 Add the verified P&L contract to `docs/api_doc/api_documentation.md`

## 6. Verification

- [x] 6.1 End-to-end: P&L sticker → segment → date → download, against the live FinX API (fresh SSO/session)
- [x] 6.2 Degraded paths: expired session (401 → AUTH_EXPIRED), no-data (200 Status:Fail → NO_DATA)
- [x] 6.3 Visual/interaction check vs. the prototype (collapse, narration, download ✓, edit-a-slot) in light + dark
- [x] 6.4 Confirm no PII in logs and no upstream URL in client payloads

## 7. Wave-1 hand-off (parallel follow-on changes)

- [x] 7.1 Freeze the descriptor schema; open `cho-###` changes for **Ledger** (Normal/MTF + date + delivery), **Capital Gains/Tax** (FinYear + PDF/Excel + delivery), **Contract Notes** (date → list → select → download); each fans out to its own worktree/agent — shipped as CHO-208/209/210 (PR #3)
