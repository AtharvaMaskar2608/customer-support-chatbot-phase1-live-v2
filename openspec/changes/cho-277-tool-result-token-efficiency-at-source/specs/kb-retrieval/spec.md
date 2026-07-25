# kb-retrieval

## MODIFIED Requirements

### Requirement: Tool-shaped endpoint
`POST /api/kb/search` SHALL accept `{"query": string (1–1000 chars), "top_k": int 1–20 (default 10), "response_format": "concise" | "detailed" (default "concise")}` and return `{"kind":"ok","results":[...]}` ranked by fused score. The contract SHALL be stateless (no session headers required) and stable for direct registration as an agent tool. Invalid input SHALL return a 422 with field errors, including an unrecognized `response_format`.

The response format SHALL govern **only how much of each result is serialized** — retrieval, fusion, ranking, and the number of results returned SHALL be identical in both formats. `detailed` SHALL return `{id, topic, section, question, answer, tat, score}` per result with `tat` null when absent (the field set the endpoint returned before this format existed). `concise` SHALL return the same results in the same order carrying `{id, topic, section, question}`, with `answer` and `tat` present only on the top-ranked few, `score` omitted, and any retained answer bounded to a fixed character limit and explicitly flagged when that bound truncates it. The projection SHALL be applied after the retrieval is recorded for tracing, so a trace's stored retrieval context keeps the full question-and-answer chunks in both formats.

#### Scenario: Basic search
- **WHEN** the agent posts `{"query":"what are the DP charges","top_k":10,"response_format":"detailed"}`
- **THEN** it receives up to 10 ranked results each carrying the full answer text and metadata

#### Scenario: Default top_k is ten
- **WHEN** the agent posts `{"query":"what are the DP charges"}` with no `top_k`
- **THEN** the search returns at most 10 results

#### Scenario: Default format is concise
- **WHEN** the agent posts a query with no `response_format`
- **THEN** the results are the concise form — every ranked result carries its question and metadata, full answers only for the top-ranked few, and no score field

#### Scenario: Detailed is always available
- **WHEN** the concise form does not carry the answer the agent needs
- **THEN** requesting `response_format: "detailed"` returns the same ranked results with every full answer, so no knowledge-base content is ever unreachable

#### Scenario: Ranking is format-independent
- **WHEN** the same query runs in both formats
- **THEN** the result ids and their order are identical

#### Scenario: A long answer is bounded and says so
- **WHEN** a retained concise answer exceeds the character bound
- **THEN** it is truncated at that bound and flagged as truncated rather than silently cut

#### Scenario: Empty result
- **WHEN** no chunk clears retrieval
- **THEN** `{"kind":"ok","results":[]}` is returned (an empty answer is an answer — never an error)

#### Scenario: Trace retrieval context is unaffected
- **WHEN** a concise search is traced
- **THEN** the retriever span's stored retrieval context still carries the full question-and-answer text of every fused chunk
