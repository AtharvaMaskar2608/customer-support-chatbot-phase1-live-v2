# ledger-report-flow (delta)

## MODIFIED Requirements

### Requirement: Ledger result
A downloaded Ledger SHALL present as a PDF file card via the shared delivery layer (no password-protection claim — delivered PDFs are not password-protected); email SHALL return a masked confirmation.

#### Scenario: Download result
- **WHEN** the Ledger PDF is delivered
- **THEN** a file card shows the filename and "PDF" with no password note
