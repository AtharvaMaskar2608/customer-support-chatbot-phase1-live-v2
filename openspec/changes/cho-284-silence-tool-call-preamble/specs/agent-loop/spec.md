## MODIFIED Requirements

### Requirement: User-facing voice conceals intermediary steps
User-visible assistant text SHALL NOT expose retrieval mechanics, internal process, retry loops, guessing after a miss, or self-narration. The system prompt SHALL include a **USER-FACING VOICE** section that forbids, in streamed replies, the following patterns (from CHO-265 / Jam):

- **Mechanism terms:** knowledge base, KB, search results, retrieval, documents, sources, index, process note, vector, embedding, context (when describing lookup), chunk.
- **Process narration (announce-then-act):** I'll search, let me search, searching for, let me look, let me check, let me find, I'm looking into, let me try, let me raise — the model SHALL call tools with no preceding narration and answer directly.
- **Retry disclosure:** let me search more specifically, let me try again, that didn't return, the first search, a different search, more relevant results.
- **Process-tied uncertainty / guessing after miss:** I'm not sure, I think, it seems, this is likely, may involve, might be, possibly, probably, I believe, it appears, as far as I can tell — when used to narrate lookup confidence, paper over an empty/failed lookup, or invent a likely process. Soft language in an otherwise clean factual answer that does not disclose process or mechanism is out of scope for this ban.
- **Self-narration:** based on what I found, according to the information I have, from what I can see, the results indicate, I don't have information on.

Beyond the specific banned phrases above, `search_knowledge_base` SHALL be called with NO preceding assistant text of any kind — not only the enumerated narration phrases, but also any other assistant-generated sentence (including a plain factual statement that isn't itself a banned phrase). The tool call SHALL be the first thing the model does when it needs to look something up; the answer is composed only after the tool result returns, in a single grounded reply.

When a tool or knowledge-base lookup returns nothing usable, the assistant SHALL reply with a short, factual limitation using allowed phrasing (e.g. "That isn't covered in our support guides", "I can't pull that for your account") and MAY offer a support ticket per ticket policy — without mechanism terms, retry disclosure, process-tied uncertainty/guessing, or forbidden self-narration. The assistant SHALL NOT invent facts or likely causes to avoid sounding uncertain.

Enforcement SHALL be via the system/primed prompt and tool descriptions only; the backend SHALL NOT apply a post-generation regex filter on assistant text in this change.

Internal code, tool names (including `search_knowledge_base`), and specification text MAY continue to refer to the knowledge base; this requirement applies only to user-visible streamed text. Anthropic-facing tool descriptions SHALL NOT prime the model with "knowledge base", "search results", or "summarize the results".

#### Scenario: KB answer hides mechanism
- **WHEN** the user asks a general how-to and the model answers after a successful `search_knowledge_base` call
- **THEN** the streamed reply leads with the direct answer and contains none of the banned mechanism, process-narration, retry-disclosure, process-tied uncertainty, or self-narration phrases

#### Scenario: Tool call is silent
- **WHEN** the model needs to look up a general support answer
- **THEN** it calls `search_knowledge_base` with no preceding assistant text and the reply does not announce searching or looking

#### Scenario: A complete-sounding factual sentence before the tool call is still a violation
- **WHEN** the model's response, in the same turn it requests `search_knowledge_base`, would otherwise include a fluent factual statement that is not itself a banned narration phrase
- **THEN** the model instead emits no text at all before the tool call, and states that content (if still relevant) only in the reply composed after the tool result returns

#### Scenario: Empty lookup uses allowed miss phrasing
- **WHEN** `search_knowledge_base` returns no usable content for the user's question
- **THEN** the reply states the limitation in plain factual language (and may offer a ticket) without "I don't have information on", "based on what I found", inventing likely causes, or any banned mechanism term

#### Scenario: Retry is invisible
- **WHEN** the model performs a second `search_knowledge_base` call with a refined query in the same turn
- **THEN** the user-visible reply does not mention a first search, a retry, "search results", or "more relevant results"

#### Scenario: Jam-class miss does not guess
- **WHEN** the user asks how to update cost price for shares bought outside FinX and lookups return nothing relevant
- **THEN** the reply does not say "knowledge base", narrate search/retry, hedge with "this is likely" / "may involve", or announce "let me raise a support ticket" — it states the gap plainly and may ask whether to raise a ticket

#### Scenario: Grounded answer stays direct
- **WHEN** a tool returns account or knowledge-base data the model uses in its reply
- **THEN** the reply states the fact directly without process-tied hedges such as "I think" or "it seems" about the lookup

### Requirement: Report columns are registry-grounded
The agent SHALL answer any question about what a report contains, what a column or field means, or how to read a report ONLY from the column registry via the `get_report_columns` tool — using each label verbatim and the registry's locked gloss for its meaning. It SHALL NOT enumerate, rename, or invent report columns from general knowledge or the knowledge base. The registry is server-side config (`backend/content/column_registry.json`, remote-updatable, no client data) covering the P&L, tax, ledger, contract-note, and holdings reports. When a field name is ambiguous across reports (returned by the tool as `ambiguousLabels`), the agent SHALL ask which report the user means. When a report is not in the registry, the agent SHALL NOT list columns — it offers to pull the report instead. The `get_report_columns` call SHALL happen with no preceding assistant text, the same as the zero-parameter data tools (`get_holdings`, `get_money_transactions`, `get_brokerage_rates`) — the agent calls it directly and answers once, grounded in its result.

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

#### Scenario: get_report_columns call is silent
- **WHEN** the model needs to answer what a report or column means
- **THEN** it calls `get_report_columns` with no preceding assistant text, the same way it already calls `get_holdings`/`get_money_transactions`/`get_brokerage_rates` directly
