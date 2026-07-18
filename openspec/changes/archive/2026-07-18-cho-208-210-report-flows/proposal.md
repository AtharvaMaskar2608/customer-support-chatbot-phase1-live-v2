# CHO-208/209/210 · Wave 1 Report Flows

## Why

CHO-207 shipped the report-flow engine + chat shell + delivery layer, frozen and proven with P&L. Wave 1 lights up the remaining three FinX report APIs on that foundation: **Ledger** (CHO-208), **Capital Gains / Tax** (CHO-209), and **Contract Notes** (CHO-210). Each is an additive descriptor + a per-flow backend router — no change to the engine, chat shell, or P&L. Shipped as one combined branch/PR because they share the `main.py` router wiring and were built + verified together.

## What Changes

- **Ledger flow** — Normal/MTF (`Margin` 0/1) → date range → delivery; PDF only, PAN-protected. Upstream `GetLedgerDetailsPDF`.
- **Capital Gains flow** — financial year (dynamic: current + last 2) → **PDF/Excel format step** → delivery. The only flow exercising the descriptor's `format` slot. Upstream `GetTaxReportPDF` (`RequestFor=2` download fork, `FileFormat` 1/2).
- **Contract Notes flow** — the **selection step**: date range → month-grouped tap-to-get list → per-note download. Download-only (no FinX email), PDFs unprotected, `file_id` never surfaced (opaque per-session tokens, IDOR-defended). Two-step upstream (`/report/contract` list → `/contract/download`).
- Backend: three per-flow routers under `backend/app/reports/`, wired via `include_router`. Frontend: three descriptors flipped live + the selection-step UI (`chat/NotesList.tsx`, `chat/notes.ts`).

## Capabilities

### New Capabilities

- `ledger-report-flow`: the Ledger report flow (Normal/MTF, date range, PDF delivery).
- `capital-gains-report-flow`: the Capital Gains/Tax flow (dynamic FY, PDF/Excel format, delivery).
- `contract-notes-report-flow`: the Contract Notes selection-step flow (date → list → per-note download, download-only).

### Modified Capabilities

(none — additive on the CHO-207 engine; `report-flow-engine`, `report-chat-shell`, `finx-report-backend` are reused unchanged.)

## Impact

- New backend: `backend/app/reports/{ledger,tax,contract_notes}.py` + tests; `main.py` router wiring.
- New/changed frontend: three flow descriptors, `chat/NotesList.tsx`, `chat/notes.ts`, selection-step rendering in the chat shell.
- Docs: `docs/api_doc/api_documentation.md` §3–5 (the three endpoints); verification report `docs/reports/cho-208-210-wave1-report.html`.
- External: FinX `GetLedgerDetailsPDF`, `GetTaxReportPDF`, `/report/contract` + `/contract/download` — all verified live 2026-07-18.
