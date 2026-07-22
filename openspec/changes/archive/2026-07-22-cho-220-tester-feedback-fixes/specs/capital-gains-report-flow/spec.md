# capital-gains-report-flow (delta)

## MODIFIED Requirements

### Requirement: Capital Gains flow steps
The Capital Gains flow SHALL collect, one at a time: **financial year** (dynamically the current Indian FY plus the previous two, never hardcoded), **format** (PDF or Excel — the only flow with a format step), and **delivery** (download or email). No password-protection claim is made about the delivered report.

#### Scenario: Full Capital Gains flow
- **WHEN** the user starts Capital Gains from the sticker
- **THEN** the engine asks financial year, then format, then delivery, then produces the report

#### Scenario: Dynamic financial years
- **WHEN** the financial-year step renders
- **THEN** it offers the current FY and the prior two, computed from today (never a hardcoded list)
