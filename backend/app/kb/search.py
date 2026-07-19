"""Hybrid KB retrieval: Postgres FTS + pgvector cosine, fused with RRF.

The corpus is 1,102 short chunks with 3072-d embeddings, which rules out
HNSW/IVFFlat (pgvector caps indexed vectors at 2000 dims) — and at this scale
a sequential scan is exact and effectively free, per the team's RAG guide.
Each leg runs as its own single SQL round-trip; fusion happens in Python so
the math is unit-testable.
"""

import asyncio
from typing import Any, Protocol

from app.kb.embed import to_pgvector

RRF_K = 60
_COLUMNS = "id, topic, section, question, answer, tat"

_FTS_SQL = f"""
SELECT {_COLUMNS}
FROM qa_chunks, websearch_to_tsquery('english', $1) AS q
WHERE fts @@ q
ORDER BY ts_rank_cd(fts, q) DESC, id
LIMIT $2
"""

_VECTOR_SQL = f"""
SELECT {_COLUMNS}
FROM qa_chunks
WHERE embedding IS NOT NULL
ORDER BY embedding <=> $1::vector, id
LIMIT $2
"""


class FetchPool(Protocol):
    """The slice of asyncpg.Pool we use (lets tests substitute a fake)."""

    async def fetch(self, sql: str, *args: Any) -> list[Any]: ...


def rrf_fuse(legs: list[list[Any]], k: int = RRF_K) -> list[dict]:
    """Reciprocal Rank Fusion: score(chunk) = Σ_legs 1/(k + rank_in_leg).

    A chunk present in several legs accumulates score from each, so agreement
    between lexical and semantic retrieval outranks a single strong leg hit.
    Ties break on id for determinism.
    """
    scores: dict[int, float] = {}
    rows: dict[int, Any] = {}
    for leg in legs:
        for rank, row in enumerate(leg, start=1):
            rid = row["id"]
            scores[rid] = scores.get(rid, 0.0) + 1.0 / (k + rank)
            rows.setdefault(rid, row)
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        {
            "id": rid,
            "topic": rows[rid]["topic"],
            "section": rows[rid]["section"],
            "question": rows[rid]["question"],
            "answer": rows[rid]["answer"],
            "tat": rows[rid]["tat"] or None,
            "score": round(score, 6),
        }
        for rid, score in ordered
    ]


async def fts_leg(pool: FetchPool, query: str, depth: int) -> list[Any]:
    return await pool.fetch(_FTS_SQL, query, depth)


async def vector_leg(pool: FetchPool, embedding: list[float], depth: int) -> list[Any]:
    return await pool.fetch(_VECTOR_SQL, to_pgvector(embedding), depth)


async def hybrid_search(
    pool: FetchPool,
    query: str,
    embedding: list[float] | None,
    top_k: int,
) -> list[dict]:
    """Run available legs (both, concurrently, when the embedding exists) and
    fuse. With embedding=None this IS the degraded FTS-only path."""
    depth = max(20, top_k * 2)
    if embedding is None:
        legs = [await fts_leg(pool, query, depth)]
    else:
        legs = list(
            await asyncio.gather(
                fts_leg(pool, query, depth), vector_leg(pool, embedding, depth)
            )
        )
    return rrf_fuse(legs)[:top_k]
