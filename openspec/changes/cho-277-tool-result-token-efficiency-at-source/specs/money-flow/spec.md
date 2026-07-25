# money-flow

## MODIFIED Requirements

### Requirement: Progressive disclosure
The rendered card SHALL show the 6 most recent rows with "Show all n" (n from the merged stream; upstream `TotalRecords` governs completeness). Filter changes reset to the first 6. The card's payload SHALL remain the **complete** merged passbook — the artifact the frontend receives is never truncated.

The **model-facing** payload of the money tool SHALL be bounded independently of the card. It SHALL carry the newest transactions up to a fixed cap, the flow's aggregates (`counts`, `landed`, `totalRecords`, `partial`) computed over **every** transaction in the merged stream and therefore exact regardless of the cap, and an explicit indication of how many rows are present out of how many exist. Because the flow declares no parameters, the omission indication SHALL state that the aggregates cover all transactions and that the complete list is on the card the user is already viewing, and SHALL NOT instruct the model to call the tool again for more rows. The bounded payload MUST NOT introduce any field carrying client data beyond the flow's existing PII whitelist — derived counts and the omission indication itself are permitted — and the truncation MUST NOT re-order the stream (it is a prefix of the newest-first list).

#### Scenario: Long history
- **WHEN** more than 6 transactions match the current filter
- **THEN** only 6 render with a Show-all affordance carrying the true count

#### Scenario: The card still receives every transaction
- **WHEN** the merged stream holds 72 transactions
- **THEN** the artifact payload carries all 72 and the card offers "Show all 72"

#### Scenario: The model receives a bounded payload
- **WHEN** the same 72-transaction result reaches the model
- **THEN** its tool_result carries only the newest capped set of rows, plus how many are shown out of 72 and the omission indication

#### Scenario: Aggregates stay exact under truncation
- **WHEN** a successful deposit falls outside the capped rows
- **THEN** the `landed` totals, status `counts` and `totalRecords` in the model-facing payload still account for it

#### Scenario: The page-size ceiling is bounded too
- **WHEN** both directions return their maximum record page and the merged stream is many hundreds of transactions
- **THEN** the model-facing payload stays at the cap while the card still receives the whole stream

#### Scenario: The omission indication does not invite a re-call
- **WHEN** the omission indication is rendered
- **THEN** it does not tell the model to call the money tool again for the missing rows, because a repeat call returns the same bounded view
