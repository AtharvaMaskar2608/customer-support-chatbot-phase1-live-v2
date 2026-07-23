# agent-loop

## ADDED Requirements

### Requirement: User-facing voice conceals intermediary steps
User-visible assistant text SHALL NOT expose retrieval mechanics, internal process, retry loops, guessing after a miss, or self-narration. The system prompt SHALL include a **USER-FACING VOICE** section that forbids, in streamed replies, the following patterns (from CHO-265 / Jam):

- **Mechanism terms:** knowledge base, KB, search results, retrieval, documents, sources, index, process note, vector, embedding, context (when describing lookup), chunk.
- **Process narration (announce-then-act):** I'll search, let me search, searching for, let me look, let me check, let me find, I'm looking into, let me try, let me raise — the model SHALL call tools with no preceding narration and answer directly.
- **Retry disclosure:** let me search more specifically, let me try again, that didn't return, the first search, a different search, more relevant results.
- **Process-tied uncertainty / guessing after miss:** I'm not sure, I think, it seems, this is likely, may involve, might be, possibly, probably, I believe, it appears, as far as I can tell — when used to narrate lookup confidence, paper over an empty/failed lookup, or invent a likely process. Soft language in an otherwise clean factual answer that does not disclose process or mechanism is out of scope for this ban.
- **Self-narration:** based on what I found, according to the information I have, from what I can see, the results indicate, I don't have information on.

When a tool or knowledge-base lookup returns nothing usable, the assistant SHALL reply with a short, factual limitation using allowed phrasing (e.g. "That isn't covered in our support guides", "I can't pull that for your account") and MAY offer a support ticket per ticket policy — without mechanism terms, retry disclosure, process-tied uncertainty/guessing, or forbidden self-narration. The assistant SHALL NOT invent facts or likely causes to avoid sounding uncertain.

Enforcement SHALL be via the system/primed prompt and tool descriptions only; the backend SHALL NOT apply a post-generation regex filter on assistant text in this change.

Internal code, tool names (including `search_knowledge_base`), and specification text MAY continue to refer to the knowledge base; this requirement applies only to user-visible streamed text. Anthropic-facing tool descriptions SHALL NOT prime the model with "knowledge base", "search results", or "summarize the results".

#### Scenario: KB answer hides mechanism
- **WHEN** the user asks a general how-to and the model answers after a successful `search_knowledge_base` call
- **THEN** the streamed reply leads with the direct answer and contains none of the banned mechanism, process-narration, retry-disclosure, process-tied uncertainty, or self-narration phrases

#### Scenario: Tool call is silent
- **WHEN** the model needs to look up a general support answer
- **THEN** it calls `search_knowledge_base` with no preceding assistant text and the reply does not announce searching or looking

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

## MODIFIED Requirements

### Requirement: Concise, non-refusing knowledge answers
Knowledge-base narration SHALL lead with the direct answer in one to three short sentences, adding detail only when the user asks for it — no headers, lists, or preambles unless steps are requested. User-visible replies SHALL comply with the user-facing voice requirement: no mechanism terms, process narration, retry disclosure, process-tied uncertainty/guessing after a miss, or forbidden self-narration. The system prompt SHALL enumerate the knowledge base's actual topic catalog so the model knows what it covers, and SHALL direct that process/how-to questions — including account closure/deletion — are ALWAYS answered from the knowledge base: the assistant never refuses a how-to as an action it cannot perform. For account actions outside its capabilities it SHALL explain the process and offer to raise a support ticket.

#### Scenario: Account deletion is answered, not refused
- **WHEN** the user asks "how do I delete my account?"
- **THEN** the reply explains the closure process from the knowledge base (and may offer a ticket) — it does not respond that it cannot help with that, and it does not mention searching or the knowledge base

#### Scenario: KB answer is brief
- **WHEN** the user asks "what are AMC charges?"
- **THEN** the reply is a few short sentences leading with the amount/definition, not a multi-section explainer, and contains no banned mechanism or narration wording
