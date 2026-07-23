## MODIFIED Requirements

### Requirement: Tool-shaped endpoint
`POST /api/kb/search` SHALL accept `{"query": string (1–1000 chars), "top_k": int 1–20 (default 10)}` and return `{"kind":"ok","results":[{id, topic, section, question, answer, tat, score}...]}` ranked by fused score, with `tat` null when absent. The contract SHALL be stateless (no session headers required) and stable for direct registration as an agent tool. Invalid input SHALL return a 422 with field errors.

#### Scenario: Basic search
- **WHEN** the agent posts `{"query":"what are the DP charges","top_k":10}`
- **THEN** it receives up to 10 ranked results each carrying the full answer text and metadata

#### Scenario: Default top_k is ten
- **WHEN** the agent posts `{"query":"what are the DP charges"}` with no `top_k`
- **THEN** the search returns at most 10 results
