## REMOVED Requirements

### Requirement: Rate-clustered card computed from the response
**Reason**: The approved FinX mock (CHO-259) replaces cross-segment rate clustering ("All futures · Stock · Index · …") with a per-segment accordion. Clustering across segments contradicted the fixed Equity → Derivative → Commodity → Currency order and the default Equity-expanded layout.
**Migration**: Implement **Segment accordion card** (ADDED). Drop `brokerageClusters` / cluster labels from the card render path. Keep `parseRate` for ₹ phrasing; unparseable lines fall back per-line (see Graceful fallback).

## ADDED Requirements

### Requirement: Segment accordion card
The Brokerage flow SHALL fetch the client's slab once and render a **single answer card** whose body is a **segment accordion**. Each non-empty segment group is one panel. Panels SHALL appear in fixed order **Equity → Derivative → Commodity → Currency** regardless of API array order; any unrecognized segment title SHALL append after the known four (stable). On first render, the **Equity** panel SHALL be expanded when present; all other panels SHALL start collapsed. The user MAY expand or collapse any panel independently. Empty segments (no lines) MUST NOT render as panels.

#### Scenario: Default expand Equity
- **WHEN** the slab includes Equity, Derivative, Commodity, and Currency
- **THEN** the card shows four panels in that order, Equity expanded, the other three collapsed

#### Scenario: API order ignored
- **WHEN** upstream returns groups as Currency, Equity, Derivative
- **THEN** panels still render Equity → Derivative → Currency (Commodity omitted if empty/absent)

#### Scenario: Missing Equity
- **WHEN** the slab has no Equity group
- **THEN** the first ordered present segment starts expanded (others collapsed)

### Requirement: Segment visual identity
Each accordion panel header SHALL show a **22px rounded icon tile**, the segment title in uppercase, a muted count subline ("`N` rates" where `N` is the number of lines in that segment), and a chevron reflecting open/closed state. Tile colours SHALL use the FinX report four-colour family: Equity `#E8F0FE` / `#1D4FB8`, Derivative `#F0EBFE` / `#6941C6`, Commodity `#FEF4E6` / `#B76E00`, Currency `#E9F9F0` / `#17B26A`. Expanded panels SHALL list each line with the item title on the left and the rate display on the right.

#### Scenario: Equity header chrome
- **WHEN** Equity is present with two lines
- **THEN** its header shows the blue tile, "EQUITY", "2 rates", and an expanded-state chevron

### Requirement: Post-card follow-up chips
After a successful brokerage card, the shell SHALL show exactly two follow-up **pill chips** below the card (default full-plan view): **"Get my contract note"** (starts the Contract Notes flow) and **"🎫 Raise a ticket"** (escalation; ticket emoji required). These chips REPLACE the previous text·help follow-up for brokerage. Other data flows' text·help follow-ups remain unchanged.

#### Scenario: Contract note chip
- **WHEN** the user taps "Get my contract note" under the brokerage card
- **THEN** the Contract Notes flow starts (same entry behaviour as choosing that flow elsewhere)

#### Scenario: Ticket chip
- **WHEN** the user taps "🎫 Raise a ticket" under the brokerage card
- **THEN** the existing raise-ticket escalation path runs

## MODIFIED Requirements

### Requirement: Rate display
Value-based rates (`per10k`) SHALL display as a single primary line `₹{amount} per ₹10,000 traded`. Flat rates (`order`) SHALL display as `₹{amount} flat per order`. Trailing-zero noise (₹20.00) MUST NOT render. Percentage-primary display (e.g. `0.01%` as the bold value) MUST NOT appear on the brokerage card.

#### Scenario: Delivery rate
- **WHEN** the slab says "₹1.00 for trade value of 10 thousand"
- **THEN** the row shows "₹1 per ₹10,000 traded" (no percentage primary)

#### Scenario: Option flat rate
- **WHEN** the slab says "₹20.00 per order"
- **THEN** the row shows "₹20 flat per order"

### Requirement: Graceful fallback
If a line's `desc` fails to parse, that line SHALL show the upstream `desc` text verbatim on the right. The accordion shell and segment order MUST still render. The card MUST NEVER synthesize a cross-segment "All futures" (or similar) summary row.

#### Scenario: Unparseable desc
- **WHEN** one Derivative line uses a desc format the parser does not recognize
- **THEN** that line shows the original desc string, and other parseable lines in the same panel still show ₹ phrasing

### Requirement: Plan-vs-billed honesty
The card SHALL always show a footer stating that these are the plan's rates plus statutory charges (STT, exchange fees, GST, stamp duty), and that a specific trade's actual charges live on its contract note — the card MUST NOT present the slab as charges billed. The disclaimer remains visible regardless of which accordion panels are open or closed.

#### Scenario: Charges question
- **WHEN** the user asks what they were charged for a trade
- **THEN** the copy directs them to the trade's contract note rather than implying the slab is the bill

#### Scenario: Disclaimer always visible
- **WHEN** only Equity is expanded and the other panels are collapsed
- **THEN** the statutory disclaimer footer is still visible at the bottom of the card
