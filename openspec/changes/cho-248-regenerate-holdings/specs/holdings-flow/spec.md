# holdings-flow

## ADDED Requirements

### Requirement: Refresh for fresher prices
The Holdings result SHALL offer a one-tap action to re-run the flow for fresher prices (e.g. "Refresh prices"), presented as a continuation beneath the card alongside the existing help/escalation follow-up. Choosing it SHALL re-run the zero-slot holdings fetch — the same narrated fetch and card — and append a FRESH holdings card below the last message, leaving prior cards as history. This makes the footer's "Ask again anytime — prices refetch on every request" actionable, rather than requiring the user to retype the request or offering only "Raise a ticket".

#### Scenario: One-tap refresh
- **WHEN** the holdings card has rendered and the user taps "Refresh prices"
- **THEN** the holdings flow re-runs and a fresh holdings card appends below, with the prior card left as history

#### Scenario: Refresh sits beside escalation, not replacing it
- **WHEN** the holdings result renders its follow-up
- **THEN** both a "Refresh prices" action and the existing help / "Raise a ticket" path are available
