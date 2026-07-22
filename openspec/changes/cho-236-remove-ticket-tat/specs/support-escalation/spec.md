# support-escalation

## ADDED Requirements

### Requirement: Ticket confirmation makes no turnaround-time commitment
The ticket-confirmation card SHALL NOT state a resolution turnaround time (e.g. "resolved within 24 hours") and SHALL NOT display a "Status: Open" label. It SHALL tell the user that updates arrive by email ("We'll email you updates" / "updates will reach your registered email"). Any reference to a self-service "my ticket status" check SHALL be framed as a future capability ("Coming soon"), never as an action the user can take today, until such a check actually ships.

#### Scenario: Confirmation copy after raising a ticket
- **WHEN** a ticket is raised and the confirmation card renders
- **THEN** the card shows "Ticket #<id> raised", tells the user updates come by email, states no turnaround time, and presents "my ticket status" as coming soon rather than an available action
