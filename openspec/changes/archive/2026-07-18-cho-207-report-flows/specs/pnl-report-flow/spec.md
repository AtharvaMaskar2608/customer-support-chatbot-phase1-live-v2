# pnl-report-flow

## ADDED Requirements

### Requirement: P&L flow steps
The P&L flow SHALL collect, one at a time: **segment** (Equity / F&O / Commodity — shown with those customer labels, never the raw `Cash`/`Derv`/`Comm` codes), **date range** (presets + custom calendar; from Jan 2018, up to 7 days ahead, max 2-year range), and **delivery** (PDF download or email). P&L is PDF-only — there is no format step.

#### Scenario: Full P&L flow
- **WHEN** the user starts P&L from the sticker
- **THEN** the engine asks segment, then date range, then delivery, then produces the report

#### Scenario: Customer-facing segment labels
- **WHEN** the segment step renders
- **THEN** it shows Equity / F&O / Commodity (not Cash / Derv / Comm)

### Requirement: P&L upstream mapping
The backend SHALL call `GetGlobalPNLPDF` with the session-derived client code, the chosen `Group`, `FromDate`/`ToDate` (`YYYY-MM-DD`), and `RequestFor` = 0 for download / 1 for email. Charges are included (`With_Exp` true) and surfaced in the result copy.

#### Scenario: Download request
- **WHEN** the user chooses PDF download
- **THEN** the backend sends `RequestFor` 0 and streams the resulting PDF back as a file card

#### Scenario: Email request
- **WHEN** the user chooses email
- **THEN** the backend sends `RequestFor` 1 and returns a masked-email confirmation

### Requirement: P&L result presentation
A downloaded P&L SHALL present as a file card (filename, size, "PDF · password: PAN") with working download feedback and an email-it action; the summary line SHALL state the segment, range, as-of date, and "incl. charges". The delivered PDF is PAN-password-protected.

#### Scenario: Download result
- **WHEN** the P&L PDF is delivered
- **THEN** a file card shows the filename, "PDF · password: PAN", and the summary notes the segment, range, and "incl. charges"
