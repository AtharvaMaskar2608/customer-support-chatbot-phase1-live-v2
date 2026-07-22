# report-chat-shell

## ADDED Requirements

### Requirement: Adjust and run a delivered report again
After a guided report is delivered (a file downloaded or emailed), the shell SHALL offer an affordance to adjust the inputs and run the report again. Choosing it SHALL append a FRESH guided flow card below the last message, seeded (via the engine's seeded start) with the completed run's collected slot values so every slot is pre-filled and editable and the card lands on the delivery step; the delivered card SHALL remain unchanged as conversation history — the shell MUST NOT mutate or re-open the original card in place. The affordance SHALL appear only for reports produced by a guided flow run (which carries slot values); agent-produced file artifacts, which carry no slot values, SHALL NOT show it, and parameter or delivery changes for those go back through chat.

#### Scenario: Regenerate with a tweak
- **WHEN** a P&L report has been downloaded for F&O · June 2026 and the user chooses "Adjust & run again"
- **THEN** a fresh P&L card appears below, pre-filled with F&O and June 2026, every slot editable, and the delivered card stays above unchanged

#### Scenario: Fresh card, never in place
- **WHEN** the user changes the fresh card's segment to Equity and taps download
- **THEN** a new report generates below and the earlier F&O result card is left intact as history

#### Scenario: Agent file artifact has nothing to seed
- **WHEN** a report was produced by an agent `file` artifact (no slot values)
- **THEN** no "Adjust & run again" affordance is shown, and the user changes parameters by asking in chat
