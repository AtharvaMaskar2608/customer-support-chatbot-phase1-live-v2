# report-chat-shell (delta)

## MODIFIED Requirements

### Requirement: Help resolves to an actionable ticket card
A result's help affordance ("Tell me") SHALL open an actionable card (context-appropriate options plus "Raise a ticket"). Raising a ticket SHALL call `POST /api/ticket` with the session's auth headers and render the ticket-confirmation card with the REAL Freshdesk ticket id and Open status; while the request is in flight the action SHALL show a busy state, and on failure the shell SHALL show a graceful line and keep the action available — a fabricated ticket id SHALL never render. Agent-raised tickets (the `ticket` artifact) SHALL render through the same confirmation card.

#### Scenario: Raise a ticket from help
- **WHEN** the user opens help on a delivered report and taps "Raise a ticket"
- **THEN** a ticket-confirmation card appears with the real Freshdesk id and Open status

#### Scenario: Agent-raised ticket renders the same card
- **WHEN** a `ticket` artifact arrives on the agent stream
- **THEN** the same confirmation card renders with the artifact's ticket id

#### Scenario: Ticket API failure
- **WHEN** `/api/ticket` fails
- **THEN** a graceful error line appears, no ticket card renders, and the user can retry
