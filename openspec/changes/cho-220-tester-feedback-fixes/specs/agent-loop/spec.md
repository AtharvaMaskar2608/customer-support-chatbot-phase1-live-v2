# agent-loop (delta)

## ADDED Requirements

### Requirement: Concise, non-refusing knowledge answers
Knowledge-base narration SHALL lead with the direct answer in one to three short sentences, adding detail only when the user asks for it — no headers, lists, or preambles unless steps are requested. The system prompt SHALL enumerate the knowledge base's actual topic catalog so the model knows what it covers, and SHALL direct that process/how-to questions — including account closure/deletion — are ALWAYS answered from the knowledge base: the assistant never refuses a how-to as an action it cannot perform. For account actions outside its capabilities it SHALL explain the process and offer to raise a support ticket.

#### Scenario: Account deletion is answered, not refused
- **WHEN** the user asks "how do I delete my account?"
- **THEN** the reply explains the closure process from the knowledge base (and may offer a ticket) — it does not respond that it cannot help with that

#### Scenario: KB answer is brief
- **WHEN** the user asks "what are AMC charges?"
- **THEN** the reply is a few short sentences leading with the amount/definition, not a multi-section explainer
