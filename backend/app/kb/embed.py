"""Query embedding for KB retrieval.

The corpus (qa_chunks.embedding) was embedded with text-embedding-3-large at
its full 3072 dimensions, so queries MUST use the same model and dimensions —
a mismatch silently ruins cosine distances. Raw httpx (no SDK dependency);
failures degrade to FTS-only retrieval rather than failing the request.
"""

import logging

import httpx

from app import config

logger = logging.getLogger(__name__)

_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


async def embed_query(http: httpx.AsyncClient, text: str) -> list[float] | None:
    """Embed one query string; None on failure (caller degrades to FTS-only)."""
    api_key = config.openai_api_key()
    if not api_key:
        return None
    for attempt in (1, 2):
        try:
            resp = await http.post(
                _EMBEDDINGS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": config.kb_embed_model(), "input": text},
            )
            if resp.status_code == 200:
                return resp.json()["data"][0]["embedding"]
            # 4xx won't improve on retry; log status only (never the query).
            logger.warning(
                "kb embed: upstream %s (attempt %s)", resp.status_code, attempt
            )
            if resp.status_code < 500:
                return None
        except httpx.HTTPError as exc:
            logger.warning("kb embed: %s (attempt %s)", type(exc).__name__, attempt)
    return None


def to_pgvector(embedding: list[float]) -> str:
    """Render a float list as a pgvector literal for a $n::vector parameter."""
    return "[" + ",".join(repr(v) for v in embedding) + "]"
