# Tasks — CHO-208/209/210 Wave 1 Report Flows

Retroactive change capturing the Wave-1 flows (built + verified before this record; all tasks complete). Grouped per issue.

## 1. Ledger (CHO-208)

- [x] 1.1 `backend/app/reports/ledger.py` — `/api/report/ledger` → `GetLedgerDetailsPDF` (Margin 0/1, GROUP1, RequestFor 0/1)
- [x] 1.2 `frontend/src/flow/flows/ledger.ts` — live descriptor (Normal/MTF, date, delivery), PAN password note
- [x] 1.3 `backend/tests/test_report_ledger.py` (19 tests) + live-verified

## 2. Capital Gains / Tax (CHO-209)

- [x] 2.1 `backend/app/reports/tax.py` — `/api/report/tax` → `GetTaxReportPDF` (RequestFor 2/1, FileFormat 1/2, .xlsx naming)
- [x] 2.2 `frontend/src/flow/flows/tax.ts` — live descriptor with dynamic FY + PDF/Excel format step
- [x] 2.3 `backend/tests/test_report_tax.py` (20 tests, PDF+Excel) + live-verified

## 3. Contract Notes (CHO-210)

- [x] 3.1 `backend/app/reports/contract_notes.py` — list + download routes; opaque id↔file_id map; `Session ` prefix; IDOR defense
- [x] 3.2 `frontend/src/chat/NotesList.tsx` + `notes.ts` + selection-step rendering in the chat shell
- [x] 3.3 `frontend/src/flow/flows/contractNotes.ts` — live descriptor (date presets, cap=today, single-note shortcut)
- [x] 3.4 `backend/tests/test_report_contract_notes.py` (23 tests) + live-verified

## 4. Integration & verification

- [x] 4.1 Wire the three routers into `backend/app/main.py` (`include_router`)
- [x] 4.2 Full backend suite green (120 tests)
- [x] 4.3 Playwright across all four flows, live FinX (16/16) — `docs/reports/cho-208-210-wave1-report.html`
- [x] 4.4 `docs/api_doc/api_documentation.md` §3–5 for the three endpoints
