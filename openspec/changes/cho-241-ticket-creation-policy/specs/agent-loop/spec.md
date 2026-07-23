# agent-loop

## ADDED Requirements

### Requirement: Ticket creation is user-initiated only
The assistant SHALL offer to raise a support ticket but SHALL NEVER decide to raise one on its own judgement. The model SHALL call `raise_support_ticket` only when the user's latest message is an explicit escalation request (asks for a human, to raise a ticket/complaint, to escalate) or an affirmative acceptance of the assistant's own escalation offer — never preemptively. The prompt SHALL instruct: never announce ticket creation as a plan ("let me raise a ticket"); when a ticket would help, ask "Want me to raise a ticket so the team can take this up?" and stop; offer at most once per issue (if declined or ignored, do not offer again for that issue); never offer a ticket while refusing a request for security/policy/another client's data (refuse briefly and stop); never narrate retrieval or internal steps.

As a code-level guarantee independent of model behaviour, the orchestrator SHALL reject a model-emitted `raise_support_ticket` call whose triggering user turn is neither an explicit escalation request (allowlist match) nor an affirmative acceptance of the assistant's immediately-preceding escalation offer: the call SHALL return an error `tool_result` (steering the model to offer instead) and SHALL NOT create a ticket. The help-card entry point (`POST /api/ticket`) is inherently user-initiated and is NOT subject to this check.

#### Scenario: Preemptive ticket call is blocked
- **WHEN** the model emits `raise_support_ticket` on a turn where the user only asked a factual question (no escalation request, no accepted offer)
- **THEN** the orchestrator returns an error tool_result, no ticket is created, and the model offers a ticket instead of raising one

#### Scenario: Explicit request raises a ticket
- **WHEN** the user says "just connect me to a human" or "raise a ticket"
- **THEN** the model's `raise_support_ticket` call passes the check and a real ticket is created

#### Scenario: Not offered while refusing
- **WHEN** the user asks for something the assistant must refuse (another client's data, investment advice)
- **THEN** the assistant refuses briefly and does NOT offer a ticket

#### Scenario: Help-card chip is unaffected
- **WHEN** the user taps "Raise a ticket" on a help card
- **THEN** `POST /api/ticket` raises the ticket normally, not subject to the model-call guard
