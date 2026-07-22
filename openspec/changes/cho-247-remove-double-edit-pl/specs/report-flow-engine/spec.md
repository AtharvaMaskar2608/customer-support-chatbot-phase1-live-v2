# report-flow-engine

## MODIFIED Requirements

### Requirement: One slot at a time with editable filled slots
The engine SHALL render every filled slot as an editable chip and actively prompt only the first unfilled required slot, in canonical order. Editing a filled slot SHALL re-open it and continue from the first still-unfilled slot. A filled slot SHALL expose exactly ONE edit affordance — the chip itself (tap-to-edit, marked with a pencil glyph); the engine SHALL NOT render a second, redundant "Edit" control in the slot's row header.

#### Scenario: Sequential prompting
- **WHEN** a flow starts with no slots filled
- **THEN** the engine prompts slot 1 only; after it's answered, slot 2 appears; then delivery

#### Scenario: Editing an earlier slot
- **WHEN** the user taps the chip of an already-filled slot
- **THEN** that slot re-opens for editing and the flow resumes at the first unfilled slot afterward

#### Scenario: Single edit affordance per filled slot
- **WHEN** a filled slot renders on the flow card while the flow is still being set up
- **THEN** the only edit control is the chip itself (tap-to-edit) — no separate "Edit" button appears in the row header
