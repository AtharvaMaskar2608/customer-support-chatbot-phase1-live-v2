# kb-retrieval Specification

## Purpose
TBD - created by archiving change cho-212-kb-retrieval-tool. Update Purpose after archive.
## Requirements
### Requirement: Hybrid retrieval with RRF fusion
KB search SHALL run both retrieval legs over `qa_chunks` — Postgres FTS (`websearch_to_tsquery('english', query)` against the stored `fts` column, ranked by `ts_rank_cd`) and pgvector cosine similarity (`embedding <=> query_vector`, sequential scan) — and fuse them with Reciprocal Rank Fusion (`score = Σ 1/(60 + rank)` across legs). A chunk found by both legs SHALL outrank chunks found by only one at similar positions. If the FTS leg yields nothing (no lexical overlap), vector results SHALL still be returned.

#### Scenario: Both legs contribute
- **WHEN** a query matches a chunk lexically and semantically
- **THEN** that chunk's RRF score combines both legs' ranks and it rises accordingly

#### Scenario: No lexical match
- **WHEN** a query shares no keywords with the KB but is semantically close to a chunk
- **THEN** vector results are returned (FTS contributes nothing, errors nothing)

### Requirement: Query embedding at request time
The query SHALL be embedded with the same model family the corpus was embedded with (`text-embedding-3-large`, 3072 dimensions) via the OpenAI API at request time. An embedding failure SHALL degrade gracefully to FTS-only results flagged `"degraded": "fts_only"` rather than failing the request.

#### Scenario: Embeddings API down
- **WHEN** the embedding call fails after retry
- **THEN** the response carries FTS-only results with the degraded flag instead of an error

### Requirement: Tool-shaped endpoint
`POST /api/kb/search` SHALL accept `{"query": string (1–1000 chars), "top_k": int 1–20 (default 10)}` and return `{"kind":"ok","results":[{id, topic, section, question, answer, tat, score}...]}` ranked by fused score, with `tat` null when absent. The contract SHALL be stateless (no session headers required) and stable for direct registration as an agent tool. Invalid input SHALL return a 422 with field errors.

#### Scenario: Basic search
- **WHEN** the agent posts `{"query":"what are the DP charges","top_k":10}`
- **THEN** it receives up to 10 ranked results each carrying the full answer text and metadata

#### Scenario: Empty result
- **WHEN** no chunk clears retrieval
- **THEN** `{"kind":"ok","results":[]}` is returned (an empty answer is an answer — never an error)

### Requirement: Privacy-safe logging
KB queries MAY contain user-personal details; the backend SHALL log only query length, result count, and timing — never the query text, and never `DATABASE_URL` or API keys.

#### Scenario: Query with personal detail
- **WHEN** a user asks "why was PAN ABCDE1234F rejected"
- **THEN** no log line contains the query text or the PAN

### Requirement: Self-retrieval benchmark
The change SHALL include a benchmark script that samples stored questions from the live KB, embeds them, runs FTS-only / vector-only / hybrid retrieval, and reports hit-rate@1/3/5 and MRR of each question's own chunk per configuration — proving hybrid ≥ each single leg before the tool is declared ready.

#### Scenario: Benchmark run
- **WHEN** the benchmark runs against the dev database
- **THEN** it prints hit-rate@1/3/5 + MRR for all three configurations over the sample

