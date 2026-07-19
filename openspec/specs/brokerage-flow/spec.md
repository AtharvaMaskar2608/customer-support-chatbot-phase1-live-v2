# brokerage-flow Specification

## Purpose
TBD - created by archiving change cho-211-data-card-flows. Update Purpose after archive.
## Requirements
### Requirement: Rate-clustered card computed from the response
The Brokerage flow SHALL fetch the client's slab and cluster line items with identical `(amount, unit)` parsed from each `desc` — across segments — into single statement rows. A single-item cluster labels as "`<Segment> <item>`" (e.g. "Equity intraday"); a multi-item cluster with a common kind labels "All `<kind>`s" with a coverage subline naming the segments. Clustering MUST be computed from the response at render time (slabs are per-client), never hardcoded.

#### Scenario: Uniform derivative rates
- **WHEN** all four futures items share ₹20 per ₹10,000
- **THEN** one row renders — "All futures · Stock · Index · Commodity · Currency" — instead of four

#### Scenario: Bespoke slab
- **WHEN** a client's rates differ across segments
- **THEN** the clusters reflect that client's actual groupings

### Requirement: Rate display
Value-based rates SHALL display percentage-primary (amount per ₹10,000 → `%`, e.g. ₹1 → 0.01%) with the official phrasing beneath ("₹1 per ₹10,000 traded"); flat rates SHALL display the ₹ amount with "flat per order". Trailing-zero noise (₹20.00) MUST NOT render.

#### Scenario: Delivery rate
- **WHEN** the slab says "₹1.00 for trade value of 10 thousand"
- **THEN** the row shows "0.01%" primary and "₹1 per ₹10,000 traded" beneath

### Requirement: Graceful fallback
If any `desc` fails to parse, or clustering would exceed 6 rows, the card SHALL fall back to the plain per-segment list showing upstream text verbatim — a wrong "All futures" claim MUST never render.

#### Scenario: Unparseable desc
- **WHEN** upstream introduces a desc format the parser doesn't recognize
- **THEN** the card renders the segment-grouped list with original desc strings

### Requirement: Plan-vs-billed honesty
The card SHALL state that these are the plan's rates plus statutory charges (STT, exchange fees, GST, stamp duty), and that a specific trade's actual charges live on its contract note — the card MUST NOT present the slab as charges billed.

#### Scenario: Charges question
- **WHEN** the user asks what they were charged for a trade
- **THEN** the copy directs them to the trade's contract note rather than implying the slab is the bill

