# report-chat-shell Specification

## Purpose
TBD - created by archiving change cho-207-report-flows. Update Purpose after archive.
## Requirements
### Requirement: One continuous conversation
The widget SHALL present a single scrolling conversation. The greeting + quick-action stickers are the empty state; on first engagement (a sticker tap or a composer submit) that empty state SHALL collapse away and the conversation SHALL own the canvas.

#### Scenario: Collapse on engage
- **WHEN** the user taps a sticker or sends a message from the empty state
- **THEN** the greeting + stickers animate away and the flow continues inline as messages

### Requirement: Pinned composer with keyword routing
A composer SHALL remain pinned and usable at every point, including after a flow completes. Submitting text SHALL send the message to the agent (`POST /api/chat` with the session's auth headers), consume the SSE response, and render the agent's reply incrementally as `text` deltas arrive; artifacts SHALL render as their `artifact` events arrive using the existing renderers — file artifacts as the standard download card (via `fileToken`), data artifacts as the standard data cards, and flow artifacts (`kind: "flow"`) by booting the matching guided flow inline via the engine's seeded start (`startRun(descriptor, seed)`), pre-filling exactly the seed values that validate against the flow descriptor (chip values must match declared options; dates must satisfy the flow's constraints; invalid values are dropped so the widget asks for them) and prompting from the first unfilled slot — an empty seed boots the full flow identically to a sticker tap. A seeded delivery preference SHALL render as a highlighted delivery button only; generation fires exclusively on the user's delivery tap. From the moment a flow artifact renders, the interaction is the existing deterministic guided flow — editing, constraints, narration, and result cards behave exactly as sticker-started flows. Before the first delta and during tool rounds (`tool` events), the shell SHALL show a progress/typing state. Keyword routing is retained only as the degraded fallback: if the agent responds `AGENT_UNAVAILABLE`, the shell SHALL route by keyword to the matching flow — file flows (P&L, ledger, capital gains, contract notes) and data flows (holdings/portfolio, pay-in/pay-out/deposit/withdraw, brokerage/charges/slab) — or, if unmatched, reply with the available actions including the data flows.

#### Scenario: Free text answered by the agent
- **WHEN** the user types "what are the DP charges?"
- **THEN** the message posts to `/api/chat` and the agent's answer streams into a bot message as it generates

#### Scenario: Partial mention boots a seeded form
- **WHEN** the user types "P&L for equity" and the flow artifact arrives with segment "Equity"
- **THEN** the P&L FlowCard appears inline with the Equity chip already filled, prompting for the date range

#### Scenario: Nothing mentioned boots the full form
- **WHEN** the user types "get my P&L" and the flow artifact arrives with an empty seed
- **THEN** the full P&L FlowCard appears from its first slot, identical to tapping the sticker

#### Scenario: Seeded delivery highlights but never fires
- **WHEN** the flow artifact's seed includes delivery "email" and all slots are filled
- **THEN** the FlowCard lands on the delivery step with the email button highlighted, and nothing generates until the user taps it

#### Scenario: Invalid seed value degrades to asking
- **WHEN** a flow artifact's seed contains a chip value or date range the descriptor rejects
- **THEN** that value is dropped and the widget prompts for that slot normally

#### Scenario: Report produced through chat
- **WHEN** the agent's response includes a file artifact
- **THEN** the shell renders the existing download card wired to the artifact's fileToken

#### Scenario: Agent unavailable falls back to keyword routing
- **WHEN** `/api/chat` returns `{"error": "AGENT_UNAVAILABLE"}`
- **THEN** the shell routes the same text by keyword to a matching flow, or replies with the available report and data actions if unmatched

### Requirement: Narrated generation
While a report is being produced, the shell SHALL show a sequence of short progress captions specific to the flow (e.g. "Pulling your trades… → Tallying charges… → Packaging your report…") rather than a generic spinner. Captions SHALL NOT claim password protection.

#### Scenario: Narrated wait
- **WHEN** a report is generating
- **THEN** the progress caption advances through the flow's narration steps, then the result appears

### Requirement: Tinted icon system
All widget iconography SHALL use tinted inline SVG icons (colored via `currentColor`) — not native multi-color emoji — so icons match the tile/button color context.

#### Scenario: Delivery button icons
- **WHEN** the delivery step renders
- **THEN** the primary button shows a document/download glyph in its text color and the email option shows a mail glyph in the accent color

### Requirement: Download feedback
Tapping a download action SHALL give immediate in-place feedback: a brief busy state, then a success check, then revert — so the click is never silent.

#### Scenario: Download tapped
- **WHEN** the user taps a file card's download button
- **THEN** the button shows a spinner, then a green check, then returns to the download icon

### Requirement: Help resolves to an actionable ticket card
A result's help affordance ("Tell me") SHALL open an actionable card (context-appropriate options plus "Raise a ticket"). Raising a ticket SHALL call `POST /api/ticket` with the session's auth headers and render the ticket-confirmation card with the REAL Freshdesk ticket id and Open status; while the request is in flight the action SHALL show a busy state, and on failure the shell SHALL show a graceful line and keep the action available — a fabricated ticket id SHALL never render. Agent-raised tickets (the `ticket` artifact) SHALL render through the same confirmation card.

#### Scenario: Raise a ticket from help
- **WHEN** the user opens help on a delivered report and taps "Raise a ticket"
- **THEN** a ticket-confirmation card appears with the real Freshdesk id and Open status

#### Scenario: Agent-raised ticket renders the same card
- **WHEN** a `ticket` artifact arrives on the agent stream
- **THEN** the same confirmation card renders with the artifact's ticket id

#### Scenario: Ticket API failure
- **WHEN** `/api/ticket` fails
- **THEN** a graceful error line appears, no ticket card renders, and the user can retry

### Requirement: Data-flow stickers
The empty state SHALL include stickers for the three data flows — "My holdings", "Pay in / out", "Brokerage" — using the tinted icon system, alongside the four file-flow stickers.

#### Scenario: Sticker starts a data flow
- **WHEN** the user taps "My holdings" from the empty state
- **THEN** the empty state collapses and the holdings flow runs inline

### Requirement: Deterministic captions for agent artifacts
The shell SHALL render the connective copy beside agent artifacts itself, from fixed code/flow-descriptor copy — never expecting narration text from the model. A `flow` artifact SHALL be preceded by a short handoff line (the flow's own intro when the seed is empty, a fixed "fill in the rest" line when seeded); a `file` artifact SHALL be accompanied by a fixed report-ready line; a `data` artifact SHALL render the card and its existing follow-up affordance with no extra line. Caption copy SHALL be byte-stable and MAY reference layout (it is rendered in place), which model text never may.

#### Scenario: Seeded form gets a deterministic handoff line
- **WHEN** a `flow` artifact with a non-empty seed renders
- **THEN** a fixed bot line appears above the FlowCard without any model-generated text in the exchange

#### Scenario: Data card closes the exchange silently
- **WHEN** a brokerage `data` artifact renders
- **THEN** the card and its follow-up affordance are the entire reply — no prose recap of the card's contents appears

