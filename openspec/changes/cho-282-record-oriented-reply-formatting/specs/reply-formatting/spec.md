## ADDED Requirements

### Requirement: Record-oriented convention for multi-fact replies
When a streamed agent reply presents more than one related fact as a set (e.g. report column meanings, transaction-like breakdowns), the system prompt SHALL instruct the model to format it as one bold-headline line per record followed by that record's fields as plain text lines — never as a markdown pipe table (`| ... |` / `|---|---|` syntax). This convention SHALL generalize regardless of how many fields a given record has, since fields stack as lines under a headline rather than as grid columns.

#### Scenario: Report column glossary uses the record convention
- **WHEN** the model answers a question about what several report columns mean
- **THEN** each column is presented as a bold column name followed by its meaning as plain text, with no pipe characters or table separator syntax

#### Scenario: Convention holds regardless of field count
- **WHEN** a record-oriented reply describes records with a varying number of fields (e.g. one record with a single fact, another with several)
- **THEN** each record still renders as a bold headline followed by its own fields, without needing a fixed column count across records

### Requirement: Stray pipe tables render as a plain scrollable table, never as literal text
If a streamed agent reply still contains a markdown pipe table (a header line matching `| ... | ... |` immediately followed by a separator line matching `|---|---|`, with or without alignment colons) despite the record-oriented convention, the frontend SHALL detect that two-line signature and render the table as a real HTML table — styled with the app's existing rounded-corner/dark-mode tokens and horizontally scrollable when wider than the available message width — rather than as literal pipe/dash text. Text outside the detected table block SHALL continue to render through the existing bold-only inline renderer unaffected.

#### Scenario: A compliance miss still renders readably
- **WHEN** the model emits a markdown pipe table despite the prompt convention
- **THEN** the chat UI shows a real, styled, scrollable table instead of literal `|`/`-` characters as text

#### Scenario: Non-table text is unaffected
- **WHEN** a reply contains no pipe-table signature
- **THEN** it renders exactly as before (bold via `**`, plain text and line breaks otherwise) with no behavior change

#### Scenario: Incidental pipe characters are not mistaken for a table
- **WHEN** a reply contains a line with pipe characters that is NOT immediately followed by a valid table separator line
- **THEN** the text is rendered as plain text (via the existing bold-only renderer), not as a table
