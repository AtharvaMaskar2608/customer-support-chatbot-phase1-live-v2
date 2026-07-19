# CHO-212 · KB Retrieval Tool (RAG slice 1)

## Why

The widget can deliver reports and render account data, but free-text support questions ("what are the DP charges?", "why was my order rejected by RMS?") still dead-end at the sticker fallback. The team's support knowledge base — 1,102 curated Q&A chunks across Charges, Onboarding, DP, SLBM, Orders, Corporate action, RMS, Login, StrikeX and more — already lives in dev Postgres, fully embedded (text-embedding-3-large, 3072-d) with a generated FTS column and GIN index.

This change builds the **retrieval half of the RAG engine** exactly as the team's guide (`docs/rag_guide/1_building_rag_pt1.md`) prescribes, and serves it as a **tool-shaped endpoint** for the coming agentic loop. Per Atharva's scoping there is **no generator in this slice** — the agent's LLM will consume retrieval results directly, so the contract is designed as a tool from day one, not a chat feature retrofitted later.

## What Changes

- **Hybrid retrieval** (the guide's missing "pt2", designed here): Postgres FTS (`websearch_to_tsquery` over the GIN-indexed `fts` column) + pgvector cosine similarity (sequential scan — mandatory at 3072-d, and correct at 1,102 rows per the guide's own heuristic) fused with **Reciprocal Rank Fusion** (k=60). Query embedded at request time via OpenAI `text-embedding-3-large` (raw httpx, no SDK dependency).
- **Tool endpoint**: `POST /api/kb/search` — `{query, top_k?}` → ranked results `{id, topic, section, question, answer, tat, score}`. Stateless, no session coupling, JSON contract stable enough to register verbatim as an agent tool later.
- **Config**: `DATABASE_URL` + `OPENAI_API_KEY` from untracked `.env` (values never committed/logged). New backend deps: asyncpg.
- **Objective eval**: self-retrieval benchmark on the real KB — embed a sample of stored questions, assert their own chunk ranks; report hit-rate@1/3/5 and MRR for FTS-only vs vector-only vs hybrid, proving the fusion earns its keep.

Out of scope: generation/answer synthesis (the agentic loop's job), the agent loop itself, widget UI changes, DeepEval judge metrics + synthetic goldens (natural slice 2, keys already present), ingestion pipeline (data is already loaded/embedded by the team), reranker models.

## Capabilities

### New Capabilities

- `kb-retrieval`: hybrid FTS+vector retrieval over `qa_chunks` with RRF fusion, exposed as the `/api/kb/search` tool endpoint, with the self-retrieval benchmark.

### Modified Capabilities

(none — purely additive backend module.)

## Impact

- New backend: `app/kb/` module + `/api/kb/search` route; asyncpg pool wired into app lifespan.
- External dependencies: dev Postgres via SSH tunnel `localhost:5433` (up to the operator to keep open), OpenAI embeddings API.
- Security: KB content is generic support knowledge (no client PII); credentials only via env; queries logged length-only (user questions may contain personal details — never log query text).
