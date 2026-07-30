"""POST /api/kb/search — the KB retrieval tool endpoint.

Stateless and session-free by design: the contract is shaped to be registered
verbatim as an agent tool later. Privacy: user questions may carry personal
details (PANs, names), so logs record length/count/timing only — never the
query text.

CHO-277: `response_format` governs how much of each result is serialized, and
nothing else — retrieval, RRF fusion, ranking and the result count are
identical in both formats. `detailed` is the pre-CHO-277 field set exactly;
`concise` (the default) keeps every ranked result but carries full answers only
on the top few, because `top_k=10` full Q&A answers are both the second-largest
line in the context bill and — being mutually similar by construction — its
worst distractors.
"""

import logging
import time
from typing import Literal

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
    top_k: int = Field(default=10, ge=1, le=20)
    # Anything other than these two literals is a 422 with field errors.
    response_format: Literal["concise", "detailed"] = "concise"


# How many top-ranked results keep their full answer in the concise form. The
# answer bodies carry essentially all the mass (mean 174 chars, p99 1,548, max
# 3,010 — versus question 43, topic 8, section 23), so this is the whole lever.
_CONCISE_FULL_ANSWERS = 3
_CONCISE_ANSWER_LIMIT = 1200


def _concise_result(result: dict, *, with_answer: bool) -> dict:
    item = {
        "id": result.get("id"),
        "topic": result.get("topic"),
        "section": result.get("section"),
        "question": result.get("question"),
    }
    if not with_answer:
        return item
    answer = result.get("answer")
    clipped = isinstance(answer, str) and len(answer) > _CONCISE_ANSWER_LIMIT
    item["answer"] = answer[:_CONCISE_ANSWER_LIMIT] if clipped else answer
    item["tat"] = result.get("tat")
    if clipped:
        # Flagged, never silently cut: the model must be able to tell a short
        # answer from a clipped one before it quotes it as complete.
        item["truncated"] = True
    return item


def _concise_results(results: list) -> list:
    """Same results, same ids, same fused order — less of each.

    `score` is dropped (the model never ranks on it) and answers are kept only
    on the top `_CONCISE_FULL_ANSWERS`; the rest keep question + metadata, which
    is what the model needs to decide whether to ask for `detailed`.
    """
    return [
        _concise_result(r, with_answer=rank < _CONCISE_FULL_ANSWERS)
        if isinstance(r, dict)
        else r
        for rank, r in enumerate(results)
    ]


async def run_kb_search(
    params: KbSearchRequest | dict, ctx: ToolCtx
) -> dict | ToolError:
    """KB hybrid-search core — shared by the REST route and the agent tool.

    Uses `ctx.pg_pool` (None is the degraded KB_UNAVAILABLE outcome) and
    `ctx.http_client` for query embedding; an embedding failure degrades to
    FTS-only retrieval and marks the envelope `degraded: "fts_only"` — exactly
    as the route always has. Returns the route's exact 200 body on success, a
    ToolError otherwise; never raises. Logs never contain the query text.

    `response_format` shapes serialization only (CHO-277) and is applied last,
    after the retrieval has been recorded for tracing.
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
    # CHO-285: the embedding call gets its own span, sibling to the `retriever`
    # span below under the same `tool` parent. Its duration used to be readable
    # only as the gap between the tool span and kb_search — which is how a 20s
    # stall around a 4ms search went unnoticed until it was measured by hand.
    embedding = await tracing.observe_embedding(
        query=query, run=lambda: embed_query(ctx.http_client, query)
    )
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

    # CHO-277: projected AFTER observe_retrieval has returned, so the retriever
    # span's `metadata.retrieval_context` keeps the full question — answer text
    # of every fused chunk in both formats (CHO-267's trace-viewer chunk view).
    if params.response_format == "concise":
        results = _concise_results(results)

    elapsed_ms = round((time.monotonic() - started) * 1000)
    logger.info(
        "kb search: len=%s results=%s degraded=%s format=%s ms=%s",
        len(query),
        len(results),
        embedding is None,
        params.response_format,
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
