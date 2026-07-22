# report-flow-engine Specification

## Purpose
TBD - created by archiving change cho-207-report-flows. Update Purpose after archive.
## Requirements
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
The engine SHALL support slot types: `chips` (single choice), `date` (presets + a calendar bounded by per-flow constraints, navigable by Year → Month → Date drill-down), `format` (PDF/Excel), `delivery` (download vs email), and `selection` (choose one or more from a fetched list). Each flow uses only the slot types its endpoint requires.

#### Scenario: Date constraints per flow
- **WHEN** a date slot declares a future cap and range limit
- **THEN** the calendar disables dates beyond the cap and enforces the limit

#### Scenario: Selection step
- **WHEN** a flow includes a `selection` slot
- **THEN** after prior slots are filled the engine fetches a list and lets the user pick item(s) before delivering

### Requirement: Calendar supports Year → Month → Date drill-down
The date slot's calendar SHALL let the customer jump directly to any selectable month without stepping month by month. Tapping the month/year header opens a year grid; choosing a year opens a month grid; choosing a month returns to the day grid. Month-by-month chevron navigation remains available for fine adjustment.

#### Scenario: Reaching the earliest permitted month in three taps
- **WHEN** a flow's `minDate` is 2018-01-01 and the customer opens the calendar in July 2026
- **THEN** they reach January 2018 by tapping the header, then 2018, then January — without repeated back-chevron taps

#### Scenario: Header returns to the coarser view
- **WHEN** the customer is in the month grid
- **THEN** tapping the header again opens the year grid

### Requirement: Drill-down levels honour the same effective bounds as the day grid
Year and month cells SHALL be disabled under exactly the constraints that disable days: before `minDate`, after the future cap, and — once a start date has been picked — beyond the flow's `maxRangeYears` window from that start. The customer MUST NOT be able to open a month in which every day is disabled.

#### Scenario: Range cap narrows the year grid after a start is chosen
- **WHEN** a flow declares a 2-year maximum range and the customer has picked a start date in 2019
- **THEN** the year grid offers only 2019 through 2021, and years outside that window are visibly disabled

#### Scenario: Future cap bounds the latest year
- **WHEN** a flow declares a future cap of 0 days
- **THEN** the year grid's newest selectable year is the current year, and months after the current month are disabled

#### Scenario: No dead months
- **WHEN** the customer selects any enabled year and then any enabled month
- **THEN** the day grid that opens contains at least one selectable day

