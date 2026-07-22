# agent-loop

## ADDED Requirements

### Requirement: Report columns are registry-grounded
The agent SHALL answer any question about what a report contains, what a column or field means, or how to read a report ONLY from the column registry via the `get_report_columns` tool — using each label verbatim and the registry's locked gloss for its meaning. It SHALL NOT enumerate, rename, or invent report columns from general knowledge or the knowledge base. The registry is server-side config (`backend/content/column_registry.json`, remote-updatable, no client data) covering the P&L, tax, ledger, contract-note, and holdings reports. When a field name is ambiguous across reports (returned by the tool as `ambiguousLabels`), the agent SHALL ask which report the user means. When a report is not in the registry, the agent SHALL NOT list columns — it offers to pull the report instead.

#### Scenario: P&L columns are grounded, not invented
- **WHEN** the user asks what their P&L report contains
- **THEN** the agent calls `get_report_columns` for `pnl` and describes only the registry's columns (Security, Open, Buy, Sell, Net Qty, CL. Price, Realized P&L, Unrealized P&L) with their locked glosses — never "Short-term / Long-term / Trading P&L / Charges", which are not in the P&L report

#### Scenario: field meaning comes from the locked gloss
- **WHEN** the user asks what a specific column means (e.g. "what is Derv Comm")
- **THEN** the agent answers from the registry's gloss ("derivative and commodity income") without guessing or renaming the label

#### Scenario: ambiguous field asks which report
- **WHEN** the user asks about a field that appears in more than one report (e.g. Net Qty)
- **THEN** the agent asks which report they mean before explaining it

#### Scenario: uncovered surface is not enumerated
- **WHEN** the user asks to explain the columns of something not in the registry
- **THEN** the agent does not list columns and offers to pull the relevant report instead
