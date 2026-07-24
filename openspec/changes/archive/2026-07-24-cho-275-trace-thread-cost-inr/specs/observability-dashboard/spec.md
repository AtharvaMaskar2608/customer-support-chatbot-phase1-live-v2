# observability-dashboard (CHO-275 delta)

## ADDED Requirements

### Requirement: Estimated INR cost on traces and threads
The dashboard API SHALL compute an estimated cost in INR at read time (no
persisted cost columns) from billed token usage × Anthropic list USD rates ×
an FX rate (`TRACE_COST_USD_TO_INR`, default 96.46 INR per 1 USD). Each trace
payload SHALL include `cost_inr` (number or null when usage is missing/zero).
The threads list SHALL include `total_cost_inr` as the sum of that thread's
per-trace estimates for the page. Prefer span LLM metadata (input, output,
cache_read, cache_creation) when spans are available; otherwise use the row's
`input_tokens` / `output_tokens`. Unknown models SHALL fall back to Sonnet
rates. The UI SHALL label the figure as an estimate (e.g. “est.”) and SHALL
NOT present it as an invoice.

#### Scenario: Trace list carries estimated INR
- **WHEN** the trace list is requested with a valid admin token
- **THEN** each trace includes `cost_inr` derived from its token usage (spans
  when selected for cost calc; otherwise row totals) and does not include the
  `spans` array in the list response

#### Scenario: Thread list rolls up estimated INR
- **WHEN** the threads list is requested
- **THEN** each entry includes `total_cost_inr` as the sum of estimated costs
  for that thread's turns (null only when no turn had usable usage)

#### Scenario: UI shows estimated cost next to tokens
- **WHEN** an operator opens the traces or threads views
- **THEN** list rows and detail headers show an “est.” INR amount next to
  token chips when `cost_inr` / `total_cost_inr` is present
