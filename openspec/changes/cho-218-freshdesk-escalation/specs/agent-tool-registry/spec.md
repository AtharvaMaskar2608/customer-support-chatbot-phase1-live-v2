# agent-tool-registry (delta)

## ADDED Requirements

### Requirement: Escalation tool
The registry SHALL include a `raise_support_ticket` tool whose input schema carries only the user-intent field `reason` (short required string summarizing the issue in the user's terms). The system prompt SHALL direct the model to call it when the user asks for a human, accepts an escalation offer, or is unresolvable after clarification — never preemptively, and never twice for the same issue when a flow-event memo already records a raised ticket. Credentials and client identity are ctx-injected server-side per the registry's standing contract.

#### Scenario: Reason is the only model-controlled field
- **WHEN** the model calls `raise_support_ticket` with extra fields injected into the input
- **THEN** only `reason` is honored; identity and routing come from the request context and code constants

#### Scenario: No duplicate raise
- **WHEN** a flow-event memo already records ticket #N for the current issue and the user repeats the complaint
- **THEN** the model references the existing ticket instead of calling the tool again
