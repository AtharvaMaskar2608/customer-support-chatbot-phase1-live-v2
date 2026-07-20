# pnl-report-flow (delta)

## MODIFIED Requirements

### Requirement: P&L result presentation
A downloaded P&L SHALL present as a file card (filename, size, "PDF") with working download feedback and an email-it action; the summary line SHALL state the segment, range, as-of date, and "incl. charges". No password-protection claim is made — delivered PDFs are not password-protected.

#### Scenario: Download result
- **WHEN** the P&L PDF is delivered
- **THEN** a file card shows the filename and "PDF" (no password note), and the summary notes the segment, range, and "incl. charges"
