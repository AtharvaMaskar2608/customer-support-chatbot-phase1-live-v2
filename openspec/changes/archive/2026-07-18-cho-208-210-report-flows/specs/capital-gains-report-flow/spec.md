# capital-gains-report-flow

## ADDED Requirements

### Requirement: Capital Gains flow steps
The Capital Gains flow SHALL collect, one at a time: **financial year** (dynamically the current Indian FY plus the previous two, never hardcoded), **format** (PDF or Excel — the only flow with a format step), and **delivery** (download or email). The delivered report is PAN-password-protected.

#### Scenario: Full Capital Gains flow
- **WHEN** the user starts Capital Gains from the sticker
- **THEN** the engine asks financial year, then format, then delivery, then produces the report

#### Scenario: Dynamic financial years
- **WHEN** the financial-year step renders
- **THEN** it offers the current FY and the prior two, computed from today (never a hardcoded list)

### Requirement: Capital Gains upstream mapping
The backend SHALL call `GetTaxReportPDF` with the session client code, `FinYear` (`YYYY-YYYY`), `RequestFor` **2 for download** / 1 for email, and `FileFormat` 1 for PDF / 2 for Excel. The file is named/labelled by format (`.pdf` / `.xlsx`).

#### Scenario: Excel download
- **WHEN** the user selects Excel and download
- **THEN** the upstream carries `FileFormat: 2`, `RequestFor: 2`, and the file card shows an `.xlsx` Excel file

### Requirement: No-data wording independence
The flow SHALL branch on the upstream `Status` field, never on the `Reason` string (Tax uses "Data not available." vs P&L/Ledger's "Data not found.").

#### Scenario: No data
- **WHEN** upstream returns `Status: "Fail"`
- **THEN** the flow degrades to a no-data message regardless of the `Reason` wording
