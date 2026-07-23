"""Trace viewer dashboard API (CHO-262): the admin-token gate (404 when unset,
401 on a bad token, 200 on a good one), the response shapes, and that filters
reach the SQL — all over a FAKE pool (no real DB, no external service).

The autouse `_tracing_off` fixture (conftest) keeps write-side tracing disabled;
this router is read-only and independent of it.
"""

import json
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

TOKEN = "s3cr3t-admin-token"


# --- a fake asyncpg pool -----------------------------------------------------


class FakePool:
    """Records every fetch/fetchrow/fetchval call and answers from canned
    queues, so a test can both assert the SQL/args and drive the handler."""

    def __init__(self, *, fetch=None, fetchrow=None, fetchval=None):
        self.calls: list[tuple[str, str, tuple]] = []
        self._fetch = list(fetch or [])
        self._fetchrow = list(fetchrow or [])
        self._fetchval = list(fetchval or [])

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        return self._fetch.pop(0) if self._fetch else []

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self._fetchrow.pop(0) if self._fetchrow else None

    async def fetchval(self, sql, *args):
        self.calls.append(("fetchval", sql, args))
        return self._fetchval.pop(0) if self._fetchval else 0

    async def close(self):  # called by app shutdown
        pass


def _trace_row(rid=1, **over):
    row = {
        "id": rid,
        "created_at": "2026-07-23T10:00:00+00:00",
        "thread_id": "abc123",
        "user_id": "u456",
        "model": "claude-haiku-4-5",
        "input_tokens": 120,
        "output_tokens": 18,
        "tools": ["search_knowledge_base"],
        "had_error": False,
        "latency_ms": 900,
        "input": "how do I transfer?",
        "output": "Use a DIS.",
    }
    row.update(over)
    return row


# --- app / client fixtures ---------------------------------------------------


@pytest.fixture()
def app_no_db(monkeypatch):
    """App with no DB pool; token config is per-test."""
    monkeypatch.setattr("app.config.database_url", lambda: None)
    return create_app()


@contextmanager
def _client_with(app, pool=None):
    """Enter the TestClient (runs lifespan startup, which sets pg_pool=None with
    no DATABASE_URL) THEN install the fake pool — so startup can't clobber it."""
    with TestClient(app) as client:
        app.state.pg_pool = pool
        yield client


# --- the token gate ----------------------------------------------------------


def test_404_when_token_unset(app_no_db, monkeypatch):
    monkeypatch.setattr("app.config.traces_admin_token", lambda: None)
    with _client_with(app_no_db) as client:
        for path in ("/api/traces", "/api/threads", "/api/traces/1"):
            resp = client.get(path, headers={"X-Traces-Token": "anything"})
            assert resp.status_code == 404, path


def test_401_on_bad_or_missing_token(app_no_db, monkeypatch):
    monkeypatch.setattr("app.config.traces_admin_token", lambda: TOKEN)
    with _client_with(app_no_db) as client:
        assert client.get("/api/traces").status_code == 401  # missing header
        assert (
            client.get(
                "/api/traces", headers={"X-Traces-Token": "wrong"}
            ).status_code
            == 401
        )


def test_503_when_pool_unavailable(app_no_db, monkeypatch):
    """Good token but no DB pool => 503 (not 500), like the KB route."""
    monkeypatch.setattr("app.config.traces_admin_token", lambda: TOKEN)
    with _client_with(app_no_db, pool=None) as client:
        resp = client.get("/api/traces", headers={"X-Traces-Token": TOKEN})
        assert resp.status_code == 503


# --- list traces: shape + filters --------------------------------------------


def test_list_traces_shape_and_total(app_no_db, monkeypatch):
    monkeypatch.setattr("app.config.traces_admin_token", lambda: TOKEN)
    pool = FakePool(fetch=[[_trace_row(1), _trace_row(2)]], fetchval=[2])
    with _client_with(app_no_db, pool=pool) as client:
        resp = client.get("/api/traces", headers={"X-Traces-Token": TOKEN})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["traces"]) == 2
    first = body["traces"][0]
    assert set(first) == {
        "id", "created_at", "thread_id", "user_id", "model",
        "input_tokens", "output_tokens", "tools", "had_error",
        "latency_ms", "input", "output",
    }
    # the list view is light — spans are NOT included
    assert "spans" not in first


def test_list_traces_filters_reach_sql(app_no_db, monkeypatch):
    monkeypatch.setattr("app.config.traces_admin_token", lambda: TOKEN)
    pool = FakePool(fetch=[[]], fetchval=[0])
    with _client_with(app_no_db, pool=pool) as client:
        resp = client.get(
            "/api/traces",
            params={
                "thread_id": "abc123",
                "model": "claude-haiku-4-5",
                "had_error": "true",
                "tool": "search_knowledge_base",
                "since": "2026-07-01T00:00:00Z",
                "until": "2026-07-23T00:00:00Z",
                "limit": 10,
                "offset": 5,
            },
            headers={"X-Traces-Token": TOKEN},
        )
    assert resp.status_code == 200
    fetch_call = next(c for c in pool.calls if c[0] == "fetch")
    sql, args = fetch_call[1], fetch_call[2]
    # every filter contributed a clause + a parameter
    assert "thread_id = $1" in sql
    assert "model = $2" in sql
    assert "had_error = $3" in sql
    assert "$4 = ANY(tools)" in sql
    assert "created_at >= $5" in sql
    assert "created_at <= $6" in sql
    # the filter values, then LIMIT/OFFSET as the last two params
    assert args[0] == "abc123"
    assert args[1] == "claude-haiku-4-5"
    assert args[2] is True
    assert args[3] == "search_knowledge_base"
    assert args[-2] == 10 and args[-1] == 5


def test_list_traces_limit_capped_at_200(app_no_db, monkeypatch):
    monkeypatch.setattr("app.config.traces_admin_token", lambda: TOKEN)
    pool = FakePool(fetch=[[]], fetchval=[0])
    with _client_with(app_no_db, pool=pool) as client:
        resp = client.get(
            "/api/traces",
            params={"limit": 5000},
            headers={"X-Traces-Token": TOKEN},
        )
    assert resp.status_code == 200
    fetch_call = next(c for c in pool.calls if c[0] == "fetch")
    assert fetch_call[2][-2] == 200  # LIMIT clamped


def test_bad_datetime_is_400(app_no_db, monkeypatch):
    monkeypatch.setattr("app.config.traces_admin_token", lambda: TOKEN)
    pool = FakePool(fetch=[[]], fetchval=[0])
    with _client_with(app_no_db, pool=pool) as client:
        resp = client.get(
            "/api/traces",
            params={"since": "not-a-date"},
            headers={"X-Traces-Token": TOKEN},
        )
    assert resp.status_code == 400


# --- trace detail: includes parsed spans -------------------------------------


def test_get_trace_includes_parsed_spans(app_no_db, monkeypatch):
    monkeypatch.setattr("app.config.traces_admin_token", lambda: TOKEN)
    spans = [
        {"id": "s1", "parent_id": None, "type": "agent", "name": "chat_turn"},
        {"id": "s2", "parent_id": "s1", "type": "llm", "name": "model_round"},
    ]
    row = _trace_row(7, spans=json.dumps(spans))  # jsonb arrives as a string
    pool = FakePool(fetchrow=[row])
    with _client_with(app_no_db, pool=pool) as client:
        resp = client.get("/api/traces/7", headers={"X-Traces-Token": TOKEN})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 7
    assert body["spans"] == spans  # decoded from the jsonb string


def test_get_trace_404_when_missing(app_no_db, monkeypatch):
    monkeypatch.setattr("app.config.traces_admin_token", lambda: TOKEN)
    pool = FakePool(fetchrow=[None])
    with _client_with(app_no_db, pool=pool) as client:
        resp = client.get("/api/traces/999", headers={"X-Traces-Token": TOKEN})
    assert resp.status_code == 404


# --- threads: rollup + single thread -----------------------------------------


def test_list_threads_rollup_shape(app_no_db, monkeypatch):
    monkeypatch.setattr("app.config.traces_admin_token", lambda: TOKEN)
    grouped = [
        {
            "thread_id": "abc123",
            "turns": 3,
            "last_at": "2026-07-23T10:00:00+00:00",
            "total_input_tokens": 360,
            "had_error": False,
        }
    ]
    pool = FakePool(fetch=[grouped], fetchval=[1])
    with _client_with(app_no_db, pool=pool) as client:
        resp = client.get("/api/threads", headers={"X-Traces-Token": TOKEN})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    t = body["threads"][0]
    assert set(t) == {
        "thread_id", "turns", "last_at", "total_input_tokens", "had_error"
    }
    assert t["turns"] == 3 and t["total_input_tokens"] == 360


def test_get_thread_orders_and_includes_spans(app_no_db, monkeypatch):
    monkeypatch.setattr("app.config.traces_admin_token", lambda: TOKEN)
    rows = [
        _trace_row(1, spans=json.dumps([{"type": "agent"}])),
        _trace_row(2, spans=json.dumps([{"type": "agent"}])),
    ]
    pool = FakePool(fetch=[rows])
    with _client_with(app_no_db, pool=pool) as client:
        resp = client.get(
            "/api/threads/abc123", headers={"X-Traces-Token": TOKEN}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert [t["id"] for t in body["traces"]] == [1, 2]
    assert body["traces"][0]["spans"] == [{"type": "agent"}]
    # ordered chronologically for the token trend
    fetch_call = next(c for c in pool.calls if c[0] == "fetch")
    assert "ORDER BY created_at ASC" in fetch_call[1]
    assert fetch_call[2] == ("abc123",)
