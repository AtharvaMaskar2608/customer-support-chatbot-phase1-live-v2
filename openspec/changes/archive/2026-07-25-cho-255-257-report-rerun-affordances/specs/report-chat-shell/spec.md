# report-chat-shell

## ADDED Requirements

### Requirement: Report re-run affordance appears only on a no-data result
A re-run affordance for a guided report (P&L, ledger, capital gains) SHALL appear only when the report returns **no data**, never on a delivered report. On a successful delivery (a file downloaded or emailed) the shell SHALL show the result card and its help affordance only — no adjust / re-run pill. On a **no-data** result the shell SHALL render a "Try a different range" affordance beneath the empty-result message; choosing it SHALL append a FRESH guided flow card below, seeded (via the engine's seeded start) with the attempted run's collected slot values so every slot is pre-filled and editable and the card lands on the delivery step — the earlier messages SHALL remain unchanged as history and the shell MUST NOT mutate or re-open a card in place. Session-expiry (`AUTH_EXPIRED`) and generic errors SHALL keep their text-only remediation and SHALL NOT show a range affordance (a different range does not resolve them). The affordance SHALL appear only for reports produced by a guided flow run (which carries slot values); agent-produced file artifacts, which carry no slot values, SHALL NOT show it.

#### Scenario: Delivered report shows no re-run pill
- **WHEN** a P&L report is downloaded or emailed for a segment and range
- **THEN** the result card and its "Tell me" help affordance are the entire reply — no "Adjust & run again" pill appears

#### Scenario: No-data result offers a different range
- **WHEN** a guided P&L report returns no data for F&O · July 2026
- **THEN** the empty-result line is followed by a "Try a different range" affordance

#### Scenario: Choosing it starts a new message
- **WHEN** the user taps "Try a different range"
- **THEN** a fresh P&L flow card appears below, pre-filled with F&O and July 2026 and every slot editable, and the earlier no-data message stays above unchanged

#### Scenario: Session expiry keeps text-only remediation
- **WHEN** a report fails with `AUTH_EXPIRED`
- **THEN** the shell shows the reopen-AskFinX line only, with no range affordance
