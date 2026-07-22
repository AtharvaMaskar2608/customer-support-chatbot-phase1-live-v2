# agent-loop

## ADDED Requirements

### Requirement: Assistant identity name
The system prompt SHALL identify the assistant to the model as "AskFinX" — its self-identity, the name it uses when referring to itself, and the name it continues under when resisting identity-override or instruction-extraction attempts. The customer-facing product name shown in the widget (chat, launcher, What's new, browser title) SHALL likewise be "AskFinX". Programmatic identifiers — the embed API global and init function, persisted client-side keys, and Freshdesk routing constants (tags and custom-field values) — are NOT part of this name and SHALL remain unchanged for backward compatibility and support routing.

#### Scenario: The bot names itself AskFinX
- **WHEN** the user asks "who are you?" or attempts to change the assistant's identity
- **THEN** the assistant identifies and continues as AskFinX, not Choice Jini

#### Scenario: Programmatic identifiers are unchanged
- **WHEN** a host site initialises the widget or a bot ticket is routed in Freshdesk
- **THEN** the `ChoiceJini.init` embed API and the internal routing constants still work exactly as before — the rename is display-only
