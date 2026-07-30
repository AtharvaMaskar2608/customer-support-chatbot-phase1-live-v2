"""KB retrieval (CHO-212): RRF fusion math, endpoint paths, live round-trip."""

import asyncio
import json
import logging
import os

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import config
from app.kb.embed import to_pgvector
from app.kb.search import RRF_K, hybrid_search, rrf_fuse
from app.main import create_app

# --- helpers ----------------------------------------------------------------


def _row(rid, **over):
    row = {
        "id": rid,
        "topic": "Charges",
        "section": None,
        "question": f"q{rid}",
        "answer": f"a{rid}",
        "tat": "",
    }
    row.update(over)
    return row


class FakePool:
    """Answers the FTS and vector SQL with canned leg results, in call order."""

    def __init__(self, *legs):
        self._legs = list(legs)
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return self._legs.pop(0) if self._legs else []

    async def close(self):  # called by app shutdown
        pass


# --- RRF fusion math --------------------------------------------------------


def test_rrf_agreement_beats_single_leg():
    """A chunk ranked #2 in BOTH legs must outrank chunks that are #1 in only
    one leg — agreement is the whole point of the fusion."""
    fts = [_row(1), _row(3)]
    vec = [_row(2), _row(3)]
    fused = rrf_fuse([fts, vec])
    assert [r["id"] for r in fused] == [3, 1, 2]
    assert fused[0]["score"] == round(2 / (RRF_K + 2), 6)


def test_rrf_single_leg_survives():
    fused = rrf_fuse([[_row(7)], []])
    assert [r["id"] for r in fused] == [7]


def test_rrf_tie_breaks_on_id_for_determinism():
    fused = rrf_fuse([[_row(9)], [_row(4)]])  # identical 1/(k+1) scores
    assert [r["id"] for r in fused] == [4, 9]


def test_rrf_empty_tat_becomes_null():
    assert rrf_fuse([[_row(1, tat="")]])[0]["tat"] is None
    assert rrf_fuse([[_row(2, tat="T+1 day")]])[0]["tat"] == "T+1 day"


def test_hybrid_without_embedding_runs_fts_only():
    pool = FakePool([_row(1)])
    results = asyncio.run(hybrid_search(pool, "dp charges", None, 5))
    assert [r["id"] for r in results] == [1]
    assert len(pool.calls) == 1 and "websearch_to_tsquery" in pool.calls[0][0]


def test_hybrid_with_embedding_runs_both_legs():
    pool = FakePool([_row(1)], [_row(2)])
    results = asyncio.run(hybrid_search(pool, "dp charges", [0.1] * 4, 5))
    assert {r["id"] for r in results} == {1, 2}
    assert len(pool.calls) == 2
    vector_call = pool.calls[1]
    assert "::vector" in vector_call[0]
    assert vector_call[1][0] == to_pgvector([0.1] * 4)


# --- DSN normalization ------------------------------------------------------


def test_dsn_special_chars_in_password_are_encoded():
    """asyncpg parses DSNs with urlparse — a raw '[' in the password reads as
    IPv6 syntax and raises. database_url() must percent-encode userinfo."""
    from app.config import _normalize_dsn

    # NOT a credential — synthetic value exercising '[' and '!' handling.
    dsn = _normalize_dsn("postgresql://user:fake[dummy!@localhost:5433/db")
    assert dsn == "postgresql://user:fake%5Bdummy%21@localhost:5433/db"
    # already-encoded stays untouched; no-auth DSNs pass through
    assert _normalize_dsn("postgresql://user:p%5B@h/db").count("%") == 1
    assert _normalize_dsn("postgresql://localhost/db") == "postgresql://localhost/db"


# --- endpoint paths (no DB) -------------------------------------------------


@pytest.fixture()
def client_no_db(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("app.config.database_url", lambda: None)
    with TestClient(create_app()) as client:
        yield client


def test_endpoint_503_when_kb_unconfigured(client_no_db):
    resp = client_no_db.post("/api/kb/search", json={"query": "dp charges"})
    assert resp.status_code == 503
    assert resp.json()["error"] == "KB_UNAVAILABLE"


def test_endpoint_validates_input(client_no_db):
    assert client_no_db.post("/api/kb/search", json={}).status_code == 422
    assert (
        client_no_db.post(
            "/api/kb/search", json={"query": "x", "top_k": 99}
        ).status_code
        == 422
    )
    assert (
        client_no_db.post("/api/kb/search", json={"query": "x" * 1001}).status_code
        == 422
    )


@pytest.fixture()
def client_fake_db(monkeypatch):
    monkeypatch.setattr("app.config.database_url", lambda: None)
    app = create_app()
    with TestClient(app) as client:
        yield app, client


@respx.mock
def test_endpoint_degrades_to_fts_only_when_embedding_fails(
    client_fake_db, monkeypatch
):
    monkeypatch.setattr("app.config.openai_api_key", lambda: "test-key")
    respx.post("https://api.openai.com/v1/embeddings").mock(
        return_value=httpx.Response(500)
    )
    app, client = client_fake_db
    app.state.pg_pool = FakePool([_row(1)])

    resp = client.post("/api/kb/search", json={"query": "dp charges"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] == "fts_only"
    assert [r["id"] for r in body["results"]] == [1]


@respx.mock
def test_endpoint_fuses_when_embedding_succeeds(client_fake_db, monkeypatch):
    monkeypatch.setattr("app.config.openai_api_key", lambda: "test-key")
    respx.post("https://api.openai.com/v1/embeddings").mock(
        return_value=httpx.Response(
            200, json={"data": [{"embedding": [0.1, 0.2]}]}
        )
    )
    app, client = client_fake_db
    app.state.pg_pool = FakePool([_row(1), _row(3)], [_row(2), _row(3)])

    resp = client.post("/api/kb/search", json={"query": "dp charges", "top_k": 2})

    body = resp.json()
    assert "degraded" not in body
    assert [r["id"] for r in body["results"]] == [3, 1]


@respx.mock
def test_logs_never_contain_query_text(client_fake_db, monkeypatch, caplog):
    monkeypatch.setattr("app.config.openai_api_key", lambda: None)
    app, client = client_fake_db
    app.state.pg_pool = FakePool([_row(1)])
    secret_query = "why was PAN ABCDE1234F rejected"

    with caplog.at_level(logging.INFO):
        client.post("/api/kb/search", json={"query": secret_query})

    assert secret_query not in caplog.text
    assert "ABCDE1234F" not in caplog.text


# --- CHO-277: response_format ------------------------------------------------
#
# The format governs only how much of each result is SERIALIZED. Retrieval,
# fusion, ranking and the result count are identical in both — so every test
# here that asserts a shape also asserts the ids and their order did not move.

DETAILED_FIELDS = ["id", "topic", "section", "question", "answer", "tat", "score"]
CONCISE_FIELDS = ["id", "topic", "section", "question"]


def _long(n: int) -> str:
    return "x" * n


def _search(client, **body):
    resp = client.post("/api/kb/search", json={"query": "dp charges", **body})
    assert resp.status_code == 200, resp.text
    return resp.json()


@respx.mock
def test_detailed_reproduces_the_pre_change_field_set(client_fake_db, monkeypatch):
    """`detailed` is the exact envelope the endpoint returned before the format
    existed — same fields, same order, `score` included, `tat` "" → null."""
    monkeypatch.setattr("app.config.openai_api_key", lambda: None)
    app, client = client_fake_db
    app.state.pg_pool = FakePool([_row(1), _row(2)])

    body = _search(client, response_format="detailed")

    assert [list(r) for r in body["results"]] == [DETAILED_FIELDS] * 2
    assert body["results"][0] == {
        "id": 1,
        "topic": "Charges",
        "section": None,
        "question": "q1",
        "answer": "a1",
        "tat": None,
        "score": round(1 / (RRF_K + 1), 6),
    }


@respx.mock
def test_default_response_format_is_concise(client_fake_db, monkeypatch):
    monkeypatch.setattr("app.config.openai_api_key", lambda: None)
    app, client = client_fake_db
    app.state.pg_pool = FakePool([_row(i, tat="T+1 day") for i in range(1, 6)])

    body = _search(client)  # no response_format at all

    results = body["results"]
    assert len(results) == 5  # every ranked result survives — only fields shrink
    # top 3 keep the answer (+ tat); the rest are question + metadata only
    assert [list(r) for r in results[:3]] == [CONCISE_FIELDS + ["answer", "tat"]] * 3
    assert [list(r) for r in results[3:]] == [CONCISE_FIELDS] * 2
    assert all(r["tat"] == "T+1 day" for r in results[:3])
    assert all("score" not in r for r in results)
    assert all("truncated" not in r for r in results)


@respx.mock
def test_ids_and_order_are_identical_across_formats(client_fake_db, monkeypatch):
    monkeypatch.setattr("app.config.openai_api_key", lambda: "test-key")
    respx.post("https://api.openai.com/v1/embeddings").mock(
        return_value=httpx.Response(
            200, json={"data": [{"embedding": [0.1, 0.2]}]}
        )
    )
    app, client = client_fake_db
    legs = ([_row(1), _row(3), _row(5)], [_row(2), _row(3), _row(4)])

    app.state.pg_pool = FakePool(*legs)
    concise = _search(client, top_k=5)
    app.state.pg_pool = FakePool(*legs)
    detailed = _search(client, top_k=5, response_format="detailed")

    ids = [r["id"] for r in detailed["results"]]
    assert ids == [3, 1, 2, 4, 5]  # RRF: agreement first, then tie-break on id
    assert [r["id"] for r in concise["results"]] == ids


@respx.mock
def test_concise_bounds_a_long_answer_and_flags_it(client_fake_db, monkeypatch):
    monkeypatch.setattr("app.config.openai_api_key", lambda: None)
    app, client = client_fake_db
    app.state.pg_pool = FakePool(
        [_row(1, answer=_long(1201)), _row(2, answer=_long(1200)), _row(3)]
    )

    body = _search(client)

    over, at_bound, short = body["results"]
    assert len(over["answer"]) == 1200 and over["truncated"] is True
    # exactly at the bound is not truncated — no flag, no clip
    assert len(at_bound["answer"]) == 1200 and "truncated" not in at_bound
    assert short["answer"] == "a3" and "truncated" not in short


@respx.mock
def test_long_answers_below_the_top_three_are_dropped_not_truncated(
    client_fake_db, monkeypatch
):
    monkeypatch.setattr("app.config.openai_api_key", lambda: None)
    app, client = client_fake_db
    app.state.pg_pool = FakePool([_row(i, answer=_long(3000)) for i in range(1, 6)])

    body = _search(client)

    assert sum(len(r.get("answer") or "") for r in body["results"]) == 3 * 1200


@respx.mock
def test_empty_result_is_unchanged_in_both_formats(client_fake_db, monkeypatch):
    """An empty answer is an answer — and the format must not touch it."""
    monkeypatch.setattr("app.config.openai_api_key", lambda: None)
    app, client = client_fake_db
    for fmt in ("concise", "detailed"):
        app.state.pg_pool = FakePool([])
        resp = client.post(
            "/api/kb/search", json={"query": "dp charges", "response_format": fmt}
        )
        assert resp.json() == {"kind": "ok", "results": [], "degraded": "fts_only"}


@respx.mock
def test_degraded_fts_only_flag_survives_the_concise_projection(
    client_fake_db, monkeypatch
):
    monkeypatch.setattr("app.config.openai_api_key", lambda: "test-key")
    respx.post("https://api.openai.com/v1/embeddings").mock(
        return_value=httpx.Response(500)
    )
    app, client = client_fake_db
    app.state.pg_pool = FakePool([_row(1)])

    body = _search(client)  # concise by default

    assert body["degraded"] == "fts_only"
    assert [r["id"] for r in body["results"]] == [1]


@respx.mock
def test_default_top_k_is_still_ten(client_fake_db, monkeypatch):
    """CHO-267's recall default is untouched by the format work."""
    monkeypatch.setattr("app.config.openai_api_key", lambda: None)
    app, client = client_fake_db
    app.state.pg_pool = FakePool([_row(i) for i in range(1, 15)])

    assert len(_search(client)["results"]) == 10


def test_unrecognized_response_format_is_422(client_no_db):
    resp = client_no_db.post(
        "/api/kb/search", json={"query": "x", "response_format": "verbose"}
    )
    assert resp.status_code == 422
    assert "response_format" in resp.text


def _search_under_a_tool_span(pg_pool, query="dp charges"):
    """Run the tool core inside an active trace whose current parent is a `tool`
    span — the way the agent loop dispatches it. Returns (trace, tool span,
    payload)."""
    from app.agent import tracing
    from app.agent.ctx import ToolCtx
    from app.kb.router import run_kb_search

    trace = tracing._Trace(thread_id=None, user_id=None, input="q", start_ms=0.0)
    tool_span = trace.open("tool", "search_knowledge_base", parent_id=None)
    t_tok = tracing._current_trace.set(trace)
    p_tok = tracing._current_parent.set(tool_span.id)

    async def go():
        async with httpx.AsyncClient() as http:
            ctx = ToolCtx(
                session_id="",
                sso_jwt="",
                client_code="",
                http_client=http,
                pg_pool=pg_pool,
            )
            return await run_kb_search({"query": query}, ctx)

    try:
        payload = asyncio.run(go())
    finally:
        tracing._current_parent.reset(p_tok)
        tracing._current_trace.reset(t_tok)
    return trace, tool_span, payload


def _span_named(trace, name):
    return next(s for s in trace.spans if s.name == name)


def test_trace_retrieval_context_keeps_full_chunks_under_concise(monkeypatch):
    """The projection runs AFTER `tracing.observe_retrieval` returns, so the
    retriever span still carries the full question — answer text of every fused
    chunk (CHO-267's trace-viewer chunk view) even though the model gets the
    concise form."""
    monkeypatch.setattr("app.config.openai_api_key", lambda: None)
    rows = [_row(i, answer=f"full answer body {i}") for i in range(1, 6)]

    trace, _, payload = _search_under_a_tool_span(FakePool(rows))

    # what the model sees: answers only on the top 3
    assert sum("answer" in r for r in payload["results"]) == 3
    # what the trace kept: every chunk, whole
    context = _span_named(trace, "kb_search").metadata["retrieval_context"]
    assert context == [f"q{i} — full answer body {i}" for i in range(1, 6)]


# --- CHO-285: bounded embedding latency + its own span ----------------------
#
# embed_query used to inherit the shared client's FinX-tuned budget, so two
# attempts could stall a KB search ~20s before it degraded to FTS-only. It now
# carries its own, far shorter per-request timeout, and its duration is a span
# of its own rather than the gap between two other spans.


@respx.mock
def test_embed_call_overrides_the_shared_client_timeout(client_fake_db, monkeypatch):
    """The override must reach the transport — and be shorter than the client
    default it replaces, which is what the app would otherwise apply."""
    monkeypatch.setattr("app.config.openai_api_key", lambda: "test-key")
    route = respx.post("https://api.openai.com/v1/embeddings").mock(
        return_value=httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})
    )
    app, client = client_fake_db
    app.state.pg_pool = FakePool([_row(1)], [_row(2)])

    client.post("/api/kb/search", json={"query": "dp charges"})

    budget = config.kb_embed_timeout_seconds()
    # a float timeout binds every phase, not just read
    assert route.calls.last.request.extensions["timeout"] == {
        "connect": budget,
        "read": budget,
        "write": budget,
        "pool": budget,
    }
    assert budget < config.upstream_timeout_seconds()


def test_embedding_retry_budget_lands_in_single_digit_seconds():
    """Two attempts stays the design; the per-attempt budget is what shrank.
    The spec's ceiling is single-digit seconds, against the ~20s both attempts
    cost while riding the general upstream budget."""
    worst_case = 2 * config.kb_embed_timeout_seconds()
    assert worst_case < 10
    assert worst_case < 2 * config.upstream_timeout_seconds()


def test_embedding_timeout_is_env_overridable(monkeypatch):
    """Read at call time, so the value is tunable from post-deploy traces with
    a container recreate rather than a rebuild."""
    monkeypatch.setenv("KB_EMBED_TIMEOUT_SECONDS", "1.5")
    assert config.kb_embed_timeout_seconds() == 1.5


@respx.mock
def test_timed_out_embedding_retries_once_then_degrades(client_fake_db, monkeypatch):
    """A timing-out first attempt still gets its retry — and when that also
    times out the request degrades to FTS-only, inside the bounded ceiling
    rather than after two full-length upstream timeouts."""
    monkeypatch.setattr("app.config.openai_api_key", lambda: "test-key")
    route = respx.post("https://api.openai.com/v1/embeddings").mock(
        side_effect=httpx.ReadTimeout("too slow")
    )
    app, client = client_fake_db
    app.state.pg_pool = FakePool([_row(1)])

    resp = client.post("/api/kb/search", json={"query": "dp charges"})

    assert route.call_count == 2  # the retry is kept — only its budget shrank
    body = resp.json()
    assert body["degraded"] == "fts_only"
    assert [r["id"] for r in body["results"]] == [1]
    assert len(app.state.pg_pool.calls) == 1  # FTS leg only, no vector leg


@respx.mock
def test_embedding_gets_its_own_span_beside_the_retriever_span(monkeypatch):
    """The whole point: embedding duration is readable directly off a span
    instead of inferred from the gap between the tool span and kb_search."""
    monkeypatch.setattr("app.config.openai_api_key", lambda: "test-key")
    respx.post("https://api.openai.com/v1/embeddings").mock(
        return_value=httpx.Response(
            200, json={"data": [{"embedding": [0.1] * 3072}]}
        )
    )

    trace, tool_span, _ = _search_under_a_tool_span(FakePool([_row(1)], [_row(2)]))

    embed = _span_named(trace, "kb_embed")
    search = _span_named(trace, "kb_search")
    # siblings under the same tool parent — not nested inside each other
    assert embed.parent_id == search.parent_id == tool_span.id
    assert embed.type == "retriever"
    assert embed.start_ms <= search.start_ms
    # a closed span, so duration_ms serializes for the dashboard
    assert embed.end_ms is not None and embed.end_ms >= embed.start_ms
    assert embed.output == {"dims": 3072}  # the count, never the 3072 floats
    assert embed.metadata["degraded"] is False
    assert embed.metadata["embedder"] == config.kb_embed_model()


def test_embedding_span_marks_the_degraded_fts_only_path(monkeypatch):
    """Degrading changes which legs run, not whether the trace records them."""
    monkeypatch.setattr("app.config.openai_api_key", lambda: None)

    trace, _, payload = _search_under_a_tool_span(FakePool([_row(1)]))

    embed = _span_named(trace, "kb_embed")
    assert embed.output == {"dims": None}
    assert embed.metadata["degraded"] is True
    assert payload["degraded"] == "fts_only"
    assert _span_named(trace, "kb_search")  # retriever span still recorded


def test_embedding_span_is_a_no_op_without_an_active_trace(monkeypatch):
    """The REST route runs outside a turn — the span wrapper must pass through
    rather than fail, exactly as observe_retrieval does."""
    from app.agent import tracing

    monkeypatch.setattr("app.config.openai_api_key", lambda: None)

    async def go():
        async with httpx.AsyncClient() as http:
            from app.kb.embed import embed_query

            return await tracing.observe_embedding(
                query="dp charges", run=lambda: embed_query(http, "dp charges")
            )

    assert tracing._current_trace.get() is None
    assert asyncio.run(go()) is None


# --- live integration (skipped without a reachable KB) ----------------------

LIVE_DSN = os.environ.get("DATABASE_URL")


@pytest.mark.skipif(not LIVE_DSN, reason="DATABASE_URL not set")
def test_live_kb_round_trip():
    with TestClient(create_app()) as client:
        resp = client.post(
            "/api/kb/search",
            json={
                "query": "What are the DP charges?",
                "top_k": 5,
                "response_format": "detailed",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "ok"
    assert len(body["results"]) > 0
    top = body["results"][0]
    assert top["answer"]
    assert isinstance(top["score"], float)


@pytest.mark.skipif(not LIVE_DSN, reason="DATABASE_URL not set")
def test_live_concise_keeps_the_ranking_and_drops_the_bulk():
    with TestClient(create_app()) as client:
        query = {"query": "What are the DP charges?", "top_k": 10}
        concise = client.post("/api/kb/search", json=query).json()
        detailed = client.post(
            "/api/kb/search", json={**query, "response_format": "detailed"}
        ).json()

    assert [r["id"] for r in concise["results"]] == [
        r["id"] for r in detailed["results"]
    ]
    assert all("score" not in r for r in concise["results"])
    assert len(json.dumps(concise)) < len(json.dumps(detailed))
