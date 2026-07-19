# report-chat-shell (delta)

## MODIFIED Requirements

### Requirement: Pinned composer with keyword routing
A composer SHALL remain pinned and usable at every point, including after a flow completes. Submitting text SHALL send the message to the agent (`POST /api/chat` with the session's auth headers), consume the SSE response, and render the agent's reply incrementally as `text` deltas arrive; artifacts SHALL render as their `artifact` events arrive using the existing renderers — file artifacts as the standard download card (via `fileToken`), data artifacts as the standard data cards. Before the first delta and during tool rounds (`tool` events), the shell SHALL show a progress/typing state. Keyword routing is retained only as the degraded fallback: if the agent responds `AGENT_UNAVAILABLE`, the shell SHALL route by keyword to the matching flow — file flows (P&L, ledger, capital gains, contract notes) and data flows (holdings/portfolio, pay-in/pay-out/deposit/withdraw, brokerage/charges/slab) — or, if unmatched, reply with the available actions including the data flows.

#### Scenario: Free text answered by the agent
- **WHEN** the user types "what are the DP charges?"
- **THEN** the message posts to `/api/chat` and the agent's answer streams into a bot message as it generates

#### Scenario: Report produced through chat
- **WHEN** the agent's response includes a file artifact
- **THEN** the shell renders the existing download card wired to the artifact's fileToken

#### Scenario: Agent asks a clarifying question
- **WHEN** the agent's reply is a question about missing parameters
- **THEN** it renders as a normal bot message and the composer remains ready for the user's answer

#### Scenario: Agent unavailable falls back to keyword routing
- **WHEN** `/api/chat` returns `{"error": "AGENT_UNAVAILABLE"}`
- **THEN** the shell routes the same text by keyword to a matching flow, or replies with the available report and data actions if unmatched
