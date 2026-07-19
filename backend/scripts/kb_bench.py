"""Self-retrieval benchmark for KB retrieval (CHO-212, task 3.1).

For a random sample of stored questions, we embed the QUESTION text (the
corpus embeddings cover the full chunk = question + answer + TAT, so this is
a real retrieval task, not an identity lookup) and check where each
question's own chunk ranks under FTS-only, vector-only, and hybrid (RRF).

Run from backend/:  uv run python scripts/kb_bench.py [sample_size]
Needs DATABASE_URL + OPENAI_API_KEY (env or repo-root .env).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg  # noqa: E402
import httpx  # noqa: E402

from app import config  # noqa: E402
from app.kb.search import fts_leg, hybrid_search, rrf_fuse, vector_leg  # noqa: E402

DEPTH = 20  # rank horizon: misses beyond this count as rank=None


async def batch_embed(http: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    resp = await http.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {config.openai_api_key()}"},
        json={"model": config.kb_embed_model(), "input": texts},
        timeout=120,
    )
    resp.raise_for_status()
    data = sorted(resp.json()["data"], key=lambda d: d["index"])
    return [d["embedding"] for d in data]


def rank_of(rows, target_id) -> int | None:
    for i, row in enumerate(rows, start=1):
        if row["id"] == target_id:
            return i
    return None


class Tally:
    def __init__(self, name: str):
        self.name = name
        self.ranks: list[int | None] = []

    def add(self, rank: int | None):
        self.ranks.append(rank)

    def report(self) -> str:
        n = len(self.ranks)
        hit = lambda k: sum(1 for r in self.ranks if r is not None and r <= k) / n  # noqa: E731
        mrr = sum(1 / r for r in self.ranks if r is not None) / n
        return (
            f"{self.name:<12} hit@1 {hit(1):6.1%}   hit@3 {hit(3):6.1%}   "
            f"hit@5 {hit(5):6.1%}   MRR {mrr:.3f}"
        )


async def main(sample_size: int) -> None:
    dsn = config.database_url()
    if not dsn or not config.openai_api_key():
        raise SystemExit("DATABASE_URL and OPENAI_API_KEY are required")

    pool = await asyncpg.create_pool(dsn, min_size=0, max_size=5)
    async with httpx.AsyncClient() as http:
        sample = await pool.fetch(
            """SELECT id, question FROM qa_chunks
               WHERE question IS NOT NULL AND length(question) > 8
               ORDER BY random() LIMIT $1""",
            sample_size,
        )
        print(f"sample: {len(sample)} questions · depth {DEPTH}")
        embeddings = await batch_embed(http, [r["question"] for r in sample])

        fts_t, vec_t, hyb_t = Tally("fts-only"), Tally("vector-only"), Tally("hybrid")
        for row, emb in zip(sample, embeddings):
            fts_rows = await fts_leg(pool, row["question"], DEPTH)
            vec_rows = await vector_leg(pool, emb, DEPTH)
            hyb_rows = rrf_fuse([fts_rows, vec_rows])[:DEPTH]
            fts_t.add(rank_of(fts_rows, row["id"]))
            vec_t.add(rank_of(vec_rows, row["id"]))
            hyb_t.add(rank_of(hyb_rows, row["id"]))

        for tally in (fts_t, vec_t, hyb_t):
            print(tally.report())

        # spot-check the public path end-to-end for one sampled question
        sample_q = sample[0]["question"]
        top = await hybrid_search(pool, sample_q, embeddings[0], 3)
        print(f"\nspot-check top-3 ids for one sampled question: {[r['id'] for r in top]}")
    await pool.close()


if __name__ == "__main__":
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    asyncio.run(main(size))
