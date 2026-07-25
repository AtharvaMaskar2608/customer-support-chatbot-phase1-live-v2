# conversation-store

## ADDED Requirements

### Requirement: Curated model-facing projection of spent tool results
The store SHALL expose a **curated projection** of a thread's turns for model consumption, alongside
the lossless wire array. The projection SHALL leave stored turns unmutated — it is a read-time pure
function of stored `content` bytes plus `meta`, so replay, ticket transcripts, derived counters,
feedback anchors and the training corpus are unaffected — and building it SHALL NOT mutate, alias, or
reorder any stored block. (The existing wire-faithful replay requirement continues to govern the
lossless array; this requirement governs the model-facing view only.)

In the projection, a **spent** `tool_result` block SHALL keep its `type`, `tool_use_id` and `is_error`
and SHALL have only its `content` string replaced by a deterministic stub. Every `tool_use` block
SHALL therefore retain exactly one matching `tool_result` block, and the API's requirement that
`tool_result` blocks come first in a merged user message SHALL continue to hold.

Curation SHALL be deterministic and byte-stable for a given watermark: no model call, no clock read,
no request state — the stub text is a function of the stored envelope fields alone. The **watermark**
SHALL be the `seq` of the newest `user_text` turn, and SHALL advance monotonically: a result becomes
spent once a newer user message exists and stays spent for the rest of the thread. Because mid-turn
appends are `tool_result` and `flow_event` turns rather than `user_text`, the watermark SHALL NOT move
between rounds of one turn.

Stubs SHALL contain only counts, customer-facing labels, ISO dates and opaque ids — never currency
amounts, prices, scrip names, credentials, file tokens, masked contact values, or raw upstream
fields — and SHALL always end with an actionable recovery clause naming the tool to call again, so a
stub never reads as a claim that information was absent. A stub that preserves opaque ids SHALL state
their expiry alongside the recovery, so a stale id is never presented as usable. Results whose
`meta["is_error"]` is true, and results of the routing/state tools (`open_report_form`,
`raise_support_ticket`), SHALL never be curated; a tool with no registered renderer SHALL be left
verbatim.

#### Scenario: Artifact result is stubbed once a newer user message exists
- **WHEN** a `get_holdings` result is stored in one turn and the user sends another message
- **THEN** the curated projection for the next model call carries a deterministic stub in that block's `content` — naming the holdings count and instructing that `get_holdings` be called again — while the same block was verbatim for every model call of its own turn

#### Scenario: Error results are kept verbatim
- **WHEN** a thread contains a `tool_result` whose `meta["is_error"]` is true
- **THEN** the curated projection reproduces that block's stored `content` byte-for-byte, no matter how many user turns have passed

#### Scenario: Note ids are preserved with their expiry stated
- **WHEN** a spent `list_contract_notes` result held 20 notes
- **THEN** the stub lists every note id with its date and segment, states that the ids expire about ten minutes after they were issued, and tells the model to call `list_contract_notes` again if a download bounces

#### Scenario: The projection is byte-identical at one watermark
- **WHEN** two model calls are built from the same thread with no new `user_text` turn between them
- **THEN** the serialized curated arrays are byte-identical, including every stub string

#### Scenario: Stored turns are unchanged by curation
- **WHEN** the curated projection has been built
- **THEN** every stored turn's `content` is byte-identical to what was appended, and the lossless array built without curation is byte-identical to what it was before

#### Scenario: tool_use / tool_result pairing survives curation
- **WHEN** a turn dispatched three parallel tools and all three results are later spent
- **THEN** the curated array still answers each `tool_use` id with exactly one `tool_result` block carrying that id, in one user message with the `tool_result` blocks first
