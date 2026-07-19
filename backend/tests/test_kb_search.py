"""KB retrieval (CHO-212): RRF fusion math, endpoint paths, live round-trip."""

import asyncio
import logging
import os

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

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


# --- live integration (skipped without a reachable KB) ----------------------

LIVE_DSN = os.environ.get("DATABASE_URL")


@pytest.mark.skipif(not LIVE_DSN, reason="DATABASE_URL not set")
def test_live_kb_round_trip():
    with TestClient(create_app()) as client:
        resp = client.post(
            "/api/kb/search", json={"query": "What are the DP charges?", "top_k": 5}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "ok"
    assert len(body["results"]) > 0
    top = body["results"][0]
    assert top["answer"]
    assert isinstance(top["score"], float)
