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

from app.agent.ctx import (
    CODE_KB_ERROR,
    CODE_KB_UNAVAILABLE,
    CODE_VALIDATION,
    ToolCtx,
    ToolError,
    parse_params,
)
from app.agent import tracing
from app.kb.embed import embed_query
from app.kb.search import hybrid_search

logger = logging.getLogger(__name__)

router = APIRouter()


class KbSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


async def run_kb_search(
    params: KbSearchRequest | dict, ctx: ToolCtx
) -> dict | ToolError:
    """KB hybrid-search core — shared by the REST route and the agent tool.

    Uses `ctx.pg_pool` (None is the degraded KB_UNAVAILABLE outcome) and
    `ctx.http_client` for query embedding; an embedding failure degrades to
    FTS-only retrieval and marks the envelope `degraded: "fts_only"` — exactly
    as the route always has. Returns the route's exact 200 body on success, a
    ToolError otherwise; never raises. Logs never contain the query text.
    """
    params = parse_params(KbSearchRequest, params)
    if isinstance(params, ToolError):
        return params

    if ctx.pg_pool is None:
        return ToolError(
            code=CODE_KB_UNAVAILABLE,
            message=(
                "The knowledge base is unavailable right now — answer without "
                "it or suggest trying again later."
            ),
        )

    query = params.query.strip()
    if not query:
        return ToolError(
            code=CODE_VALIDATION,
            message="query must be non-empty — ask the user.",
        )

    started = time.monotonic()
    embedding = await embed_query(ctx.http_client, query)
    try:
        # CHO-244: a `retriever` span carrying the fused chunks as
        # retrieval_context (RAG metrics). `pg_pool` rides in the closure; the
        # query is masked. No-op when tracing is off.
        results = await tracing.observe_retrieval(
            query=query,
            run=lambda: hybrid_search(ctx.pg_pool, query, embedding, params.top_k),
        )
    except Exception:
        logger.exception("kb search failed (len=%s)", len(query))
        return ToolError(
            code=CODE_KB_ERROR,
            message=(
                "Knowledge-base search failed — try again or answer without it."
            ),
        )

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


# Route-shell mapping of ToolError codes back to the pinned KB error shapes.
# VALIDATION here can only be the whitespace-only query (pydantic min_length
# rejects an empty string at the FastAPI layer first) — the route's 422.
_KB_ERROR_RESPONSES = {
    CODE_KB_UNAVAILABLE: (503, "KB_UNAVAILABLE"),
    CODE_VALIDATION: (422, "EMPTY_QUERY"),
    CODE_KB_ERROR: (502, "KB_ERROR"),
}


@router.post("/api/kb/search")
async def kb_search(request: Request, body: KbSearchRequest):
    ctx = ToolCtx(
        session_id="",  # session-free endpoint: no credentials involved
        sso_jwt="",
        client_code="",
        http_client=request.app.state.http_client,
        pg_pool=getattr(request.app.state, "pg_pool", None),
    )
    result = await run_kb_search(body, ctx)
    if isinstance(result, ToolError):
        status, error = _KB_ERROR_RESPONSES[result.code]
        return JSONResponse(status_code=status, content={"error": error})
    return result
