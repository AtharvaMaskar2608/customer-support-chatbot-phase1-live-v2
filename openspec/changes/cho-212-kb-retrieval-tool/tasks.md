# Tasks — CHO-212 KB Retrieval Tool

## 1. Backend module

- [x] 1.1 Config: `DATABASE_URL` + `OPENAI_API_KEY` read from env (root `.env` in dev); asyncpg pool in app lifespan (lazy — app must still boot without a DB for non-KB routes/tests)
- [x] 1.2 Query embedder: `text-embedding-3-large` via httpx (3072-d), 1 retry, graceful `fts_only` degrade
- [x] 1.3 Hybrid search: FTS leg (`websearch_to_tsquery` + `ts_rank_cd`) + vector leg (cosine seq scan) + RRF k=60 fusion, single SQL round-trip per leg
- [x] 1.4 `POST /api/kb/search` route with validation (query 1–1000 chars, top_k 1–20 default 5) + privacy-safe logging (length/count/timing only)

## 2. Tests

- [x] 2.1 Unit: RRF fusion math (both-legs boost, single-leg survival, ordering), input validation, degraded path (mocked embedder/pool)
- [x] 2.2 Integration (skipped when no `DATABASE_URL`): live qa_chunks round-trip returns ranked results with answers

## 3. Benchmark + verify

- [x] 3.1 Self-retrieval benchmark script: sample ≥100 stored questions → hit-rate@1/3/5 + MRR for fts / vector / hybrid; hybrid must beat or match each leg
- [x] 3.2 Live verify the endpoint with real support questions across topics (Charges, RMS, Onboarding, SLBM) and record results

## 4. Docs + ship

- [x] 4.1 `docs/api_doc/api_documentation.md` §9: KB search tool contract (+ note: KB content, no PII, no upstream FinX call)
- [ ] 4.2 git-sync ship (`CHO-212:` commit, PR with `Fixes CHO-212`) + linear-connector lifecycle
