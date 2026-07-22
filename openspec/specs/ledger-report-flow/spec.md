# ledger-report-flow Specification

## Purpose
TBD - created by archiving change cho-208-210-report-flows. Update Purpose after archive.
## Requirements
### Requirement: Ledger flow steps
The Ledger flow SHALL collect, one at a time: **ledger type** (Normal / MTF), **date range** (same constraints as P&L — from Jan 2018, ≤7 days ahead, max 2-year range), and **delivery** (PDF download or email). PDF only; no format step.

#### Scenario: Full Ledger flow
- **WHEN** the user starts Ledger from the sticker
- **THEN** the engine asks ledger type, then date range, then delivery, then produces the report

### Requirement: Ledger upstream mapping
The backend SHALL call `GetLedgerDetailsPDF` with the session client code as `ClientId`/`LoginId`, `Group` fixed `"GROUP1"`, `Margin` 0 for Normal / 1 for MTF, the date range, and `RequestFor` 0 download / 1 email. The client code comes only from the authenticated session.

#### Scenario: Normal vs MTF
- **WHEN** the user selects MTF
- **THEN** the upstream body carries `Margin: 1` (Normal → `Margin: 0`)

### Requirement: Ledger result
A downloaded Ledger SHALL present as a PDF file card via the shared delivery layer (no password-protection claim — delivered PDFs are not password-protected); email SHALL return a masked confirmation.

#### Scenario: Download result
- **WHEN** the Ledger PDF is delivered
- **THEN** a file card shows the filename and "PDF" with no password note

