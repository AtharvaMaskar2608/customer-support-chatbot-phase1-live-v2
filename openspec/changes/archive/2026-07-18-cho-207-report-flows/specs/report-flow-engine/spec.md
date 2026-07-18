# report-flow-engine

## ADDED Requirements

### Requirement: Descriptor-driven flow definition
A report flow SHALL be defined by a declarative descriptor (`key`, `trigger`, `intro`, ordered `slots`, `delivery` options, generation narration, and a result mapping). The engine SHALL be flow-agnostic — adding a flow means adding a descriptor, not engine code.

#### Scenario: New flow via descriptor
- **WHEN** a descriptor for a new report type is registered
- **THEN** the engine runs its flow with no changes to engine internals

### Requirement: One slot at a time with editable filled slots
The engine SHALL render every filled slot as an editable chip and actively prompt only the first unfilled required slot, in canonical order. Editing a filled slot SHALL re-open it and continue from the first still-unfilled slot.

#### Scenario: Sequential prompting
- **WHEN** a flow starts with no slots filled
- **THEN** the engine prompts slot 1 only; after it's answered, slot 2 appears; then delivery

#### Scenario: Editing an earlier slot
- **WHEN** the user taps the chip of an already-filled slot
- **THEN** that slot re-opens for editing and the flow resumes at the first unfilled slot afterward

### Requirement: Seedable slots (LLM-ready)
The engine SHALL accept a set of pre-filled slot values at flow start and prompt only the remaining gaps. Sticker entry seeds nothing; a future free-text entry may seed several. Non-contiguous seeds are allowed (fill 1 and 3, engine asks 2).

#### Scenario: Partial seed
- **WHEN** a flow is started with segment and delivery pre-seeded but date empty
- **THEN** the engine prompts only the date slot, then executes

### Requirement: Slot types
The engine SHALL support slot types: `chips` (single choice), `date` (presets + a calendar bounded by per-flow constraints), `format` (PDF/Excel), `delivery` (download vs email), and `selection` (choose one or more from a fetched list). Each flow uses only the slot types its endpoint requires.

#### Scenario: Date constraints per flow
- **WHEN** a date slot declares a future cap and range limit
- **THEN** the calendar disables dates beyond the cap and enforces the limit

#### Scenario: Selection step
- **WHEN** a flow includes a `selection` slot
- **THEN** after prior slots are filled the engine fetches a list and lets the user pick item(s) before delivering
