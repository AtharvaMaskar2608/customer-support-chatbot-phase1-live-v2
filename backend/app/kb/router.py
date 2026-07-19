"""POST /api/kb/search — the KB retrieval tool endpoint.

Stateless and session-free by design: the contract is shaped to be registered
verbatim as an agent tool later. Privacy: user questions may carry personal
details (PANs, names), so logs record length/count/timing only — never the
query text.
"""

import logging
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.kb.embed import embed_query
from app.kb.search import hybrid_search

logger = logging.getLogger(__name__)

router = APIRouter()


class KbSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/api/kb/search")
async def kb_search(request: Request, body: KbSearchRequest):
    pool = getattr(request.app.state, "pg_pool", None)
    if pool is None:
        return JSONResponse(status_code=503, content={"error": "KB_UNAVAILABLE"})

    query = body.query.strip()
    if not query:
        return JSONResponse(status_code=422, content={"error": "EMPTY_QUERY"})

    started = time.monotonic()
    embedding = await embed_query(request.app.state.http_client, query)
    try:
        results = await hybrid_search(pool, query, embedding, body.top_k)
    except Exception:
        logger.exception("kb search failed (len=%s)", len(query))
        return JSONResponse(status_code=502, content={"error": "KB_ERROR"})

    elapsed_ms = round((time.monotonic() - started) * 1000)
    logger.info(
        "kb search: len=%s results=%s degraded=%s ms=%s",
        len(query),
        len(results),
        embedding is None,
        elapsed_ms,
    )
    payload: dict = {"kind": "ok", "results": results}
    if embedding is None:
        payload["degraded"] = "fts_only"
    return payload
