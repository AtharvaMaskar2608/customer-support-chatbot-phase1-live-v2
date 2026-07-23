## MODIFIED Requirements

### Requirement: Narrated generation
While a report or data-flow fetch is in progress, the shell SHALL show a sequence of short progress captions specific to the flow (e.g. "Pulling your trades… → Tallying charges… → Packaging your report…") rather than a generic spinner. Captions SHALL NOT claim password protection. The shell SHALL advance through the flow's narration steps at a steady cadence (~720ms between steps). If the fetch is still pending after the last step, the shell SHALL cycle back to the first step and continue rotating through the sequence until the fetch settles — the progress pill MUST NOT freeze on the final caption. When the fetch resolves, the narrate pill SHALL be removed and the result (or error / empty state) SHALL appear as today.

#### Scenario: Narrated wait completes within one cycle
- **WHEN** a report or data flow fetch resolves during or shortly after the first pass through the narration steps
- **THEN** the progress caption advances through the flow's narration steps, the narrate pill is removed, and the result appears

#### Scenario: Long fetch cycles narration
- **WHEN** a report or data flow fetch takes longer than one full pass through the narration steps
- **THEN** the progress caption continues cycling through the same steps from the start until the fetch resolves, then the narrate pill is removed and the result appears

#### Scenario: Holdings long fetch (screenshot case)
- **WHEN** the holdings data fetch outlasts `Fetching your holdings…` → `Valuing at last prices…`
- **THEN** the pill cycles back to `Fetching your holdings…` (and continues) instead of freezing on `Valuing at last prices…`

#### Scenario: Contract-notes list fetch cycles
- **WHEN** a contract-notes selection step fetches the note list and the request outlasts one narration pass
- **THEN** the progress caption cycles through the flow's narration steps until the list returns, then the narrate pill is removed and the selection UI or result appears
