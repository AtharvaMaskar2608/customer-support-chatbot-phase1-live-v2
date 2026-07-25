# observability-dashboard

## MODIFIED Requirements

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

Cache **writes** SHALL be priced per TTL, not at one hardcoded rate: the rate
table SHALL carry a distinct 5-minute and 1-hour cache-write rate for each
model (a 1-hour write costs 2× base input where a 5-minute write costs 1.25×),
and each bucket SHALL be priced at its own rate. The per-TTL token split SHALL
be captured from the SDK's usage object (`cache_creation.ephemeral_5m_input_tokens`
and `ephemeral_1h_input_tokens`) into the stored turn usage and the `llm` span
metadata, so the estimate never has to infer a TTL. When only the aggregate
cache-write count is available — every trace recorded before the split was
captured — it SHALL be priced at the 5-minute rate, so historical estimates do
not move.

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

#### Scenario: A one-hour cache write is priced at its own rate
- **WHEN** a round writes cache entries under a 1-hour TTL and the usage split
  reports them as `ephemeral_1h_input_tokens`
- **THEN** those tokens are priced at the model's 1-hour write rate (2× base
  input), not at the 5-minute rate

#### Scenario: The per-TTL split is captured, not inferred
- **WHEN** a streamed model round completes and the SDK usage exposes
  `cache_creation`
- **THEN** both `ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens` are
  recorded on the `llm` span metadata and in the stored turn usage

#### Scenario: Historical traces keep their figures
- **WHEN** a trace recorded before the split was captured carries only an
  aggregate cache-write count
- **THEN** it is priced at the 5-minute write rate and its `cost_inr` is
  unchanged from before this change
