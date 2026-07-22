# agent-loop

## ADDED Requirements

### Requirement: Tax and capital-gains figures are report-only
The system prompt SHALL forbid the model from computing tax or capital-gains figures, classifying a specific lot's holding period into short- vs long-term for a figure, or stating any tax rate or exemption threshold from general knowledge. Any question involving such figures or rates SHALL route to the capital gains report (via `open_report_form` for tax, or `get_capital_gains_report` when every parameter is known), which is the authoritative statement. This mirrors the brokerage grounding rule: the authoritative source answers, never the model's memory. The model MAY explain the concept in plain terms without producing a figure or a rate.

#### Scenario: User asks for a computed tax figure
- **WHEN** the user provides lot data or asks how much tax they will owe on a sale
- **THEN** the model does not compute a gain, does not apply FIFO/LIFO, does not classify the holding period into a figure, and does not state a tax rate; it explains that the figure comes from the official capital gains statement and offers to open the capital gains report

#### Scenario: No tax rate is ever quoted
- **WHEN** any reply touches capital-gains tax
- **THEN** it contains no tax rate or exemption threshold (e.g. no "10%", no "12.5%", no "₹1 lakh" / "₹1.25 lakh" exemption) — these change with tax law and are not in the system's ground truth

#### Scenario: Concept explanation without figures is allowed
- **WHEN** the user asks what capital gains are or how holding period affects them
- **THEN** the model may explain the concept in plain terms (that gains are computed on sale, that holding period determines short- vs long-term treatment) without producing any specific figure or rate, and offers the report for actual numbers
