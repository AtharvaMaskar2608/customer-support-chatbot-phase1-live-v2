## MODIFIED Requirements

### Requirement: Query embedding at request time
The query SHALL be embedded with the same model family the corpus was embedded with (`text-embedding-3-large`, 3072 dimensions) via the OpenAI API at request time, using a timeout budget dedicated to the embedding call (independent of the general upstream-call timeout). An embedding failure SHALL degrade gracefully to FTS-only results flagged `"degraded": "fts_only"` rather than failing the request. The total time spent attempting embedding (across all retries) before degrading SHALL be bounded to a small ceiling (single-digit seconds), not the ~20s possible when the embedding call shares the general upstream timeout across two full-length retry attempts.

#### Scenario: Embeddings API down
- **WHEN** the embedding call fails after retry
- **THEN** the response carries FTS-only results with the degraded flag instead of an error

#### Scenario: Embeddings API slow on first attempt
- **WHEN** the first embedding attempt exceeds the embedding-specific timeout
- **THEN** the retry (and any subsequent degrade-to-FTS-only decision) completes within the bounded total ceiling, not the full general upstream timeout applied twice

#### Scenario: Embedding call duration is traced
- **WHEN** a KB search runs with tracing enabled
- **THEN** the embedding call's own duration appears as its own span, distinguishable from the retriever (hybrid search) span's duration
