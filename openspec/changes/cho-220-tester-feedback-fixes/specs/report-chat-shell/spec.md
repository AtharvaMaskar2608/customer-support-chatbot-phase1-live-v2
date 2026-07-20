# report-chat-shell (delta)

## MODIFIED Requirements

### Requirement: Narrated generation
While a report is being produced, the shell SHALL show a sequence of short progress captions specific to the flow (e.g. "Pulling your trades… → Tallying charges… → Packaging your report…") rather than a generic spinner. Captions SHALL NOT claim password protection.

#### Scenario: Narrated wait
- **WHEN** a report is generating
- **THEN** the progress caption advances through the flow's narration steps, then the result appears

### Requirement: Deterministic captions for agent artifacts
The shell SHALL render the connective copy beside agent artifacts itself, from fixed code/flow-descriptor copy — never expecting narration text from the model. A `flow` artifact SHALL be preceded by a short handoff line (the flow's own intro when the seed is empty, a fixed "fill in the rest" line when seeded); a `file` artifact SHALL be accompanied by a fixed report-ready line; a `data` artifact SHALL render the card and its existing follow-up affordance with no extra line. Caption copy SHALL be byte-stable and MAY reference layout (it is rendered in place), which model text never may.

#### Scenario: Seeded form gets a deterministic handoff line
- **WHEN** a `flow` artifact with a non-empty seed renders
- **THEN** a fixed bot line appears above the FlowCard without any model-generated text in the exchange

#### Scenario: Data card closes the exchange silently
- **WHEN** a brokerage `data` artifact renders
- **THEN** the card and its follow-up affordance are the entire reply — no prose recap of the card's contents appears
