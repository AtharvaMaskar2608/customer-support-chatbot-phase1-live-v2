"""Self-hosted Postgres tracing (CHO-261): the mask, id hashing, config gating,
and that the observe wrappers build the correct nested span tree and persist it
via a FAKE pool (no real DB touched, no external service).
"""

import asyncio
import json

from app.agent import tracing


# --- redact (the mask) -------------------------------------------------------

_JWT = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJmYjFlNDk0YSJ9.AbC123deF456ghI789signature"


def test_redact_scrubs_jwt():
    assert _JWT not in tracing.redact(_JWT)
    embedded = tracing.redact(f"authorization {_JWT} end")
    assert _JWT not in embedded and tracing._REDACT in embedded


def test_redact_scrubs_pan_email_phone():
    assert "ABCDE1234F" not in tracing.redact("PAN ABCDE1234F on file")
    assert "@" not in tracing.redact("email john.doe@example.com please")
    assert "9876543210" not in tracing.redact("phone 9876543210 now")


def test_redact_denylisted_keys_and_keeps_safe_ones():
    data = {
        "authorization": "Bearer abc",
        "sso_jwt": "x",
        "segment": "Equity",
        "fromDate": "2026-07-01",
        "nested": {"client_code": "X008593", "top_k": 5},
    }
    out = tracing.redact(data)
    assert out["authorization"] == tracing._REDACT
    assert out["sso_jwt"] == tracing._REDACT
    assert out["segment"] == "Equity"
    assert out["fromDate"] == "2026-07-01"
    assert out["nested"]["client_code"] == tracing._REDACT
    assert out["nested"]["top_k"] == 5


def test_redact_recurses_lists_and_passes_scalars():
    assert tracing.redact([1, "ok", {"pan": "ABCDE1234F"}]) == [
        1, "ok", {"pan": tracing._REDACT}
    ]
    assert tracing.redact(42) == 42
    assert tracing.redact(None) is None


# --- stable id ---------------------------------------------------------------


def test_stable_id_is_stable_hashed_and_not_raw():
    sid = "01KY6Q3SKBGN502F6CDAZEGMER"
    first = tracing._stable_id(sid)
    assert first == tracing._stable_id(sid)
    assert first and sid not in first and len(first) == 16
    assert tracing._stable_id(None) is None
    assert tracing._stable_id("") is None


# --- config gating -----------------------------------------------------------


def test_configure_reflects_flag(monkeypatch):
    monkeypatch.setattr("app.config.tracing_enabled", lambda: False)
    tracing.configure()
    assert tracing.enabled() is False
    monkeypatch.setattr("app.config.tracing_enabled", lambda: True)
    tracing.configure()
    assert tracing.enabled() is True
    tracing._ENABLED = False


# --- fakes -------------------------------------------------------------------


class FakePool:
    def __init__(self):
        self.calls = []

    async def execute(self, sql, *args):
        self.calls.append((sql, args))


class _FakeStream:
    def __init__(self, deltas, final):
        self._deltas, self._final = deltas, final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    def text_stream(self):
        async def gen():
            for d in self._deltas:
                yield d

        return gen()

    async def get_final_message(self):
        return self._final


class _FinalMsg:
    model = "claude-haiku-4-5"
    stop_reason = "end_turn"
    usage = {
        "input_tokens": 120,
        "output_tokens": 18,
        "cache_read_input_tokens": 100,
        "cache_creation_input_tokens": 0,
    }


class _Outcome:
    is_error = False
    error_code = None
    duration_ms = 4


def _run(coro):
    return asyncio.run(coro)


# --- pass-through when disabled ---------------------------------------------


def test_turn_passthrough_when_disabled():
    tracing._ENABLED = False

    async def run():
        yield "a"
        yield "b"

    async def go():
        return [c async for c in tracing.observe_turn(
            message="hi", session_id="s", client_code="c", pool=FakePool(), run=run
        )]

    assert _run(go()) == ["a", "b"]


def test_tool_and_retrieval_passthrough_without_active_trace():
    tracing._ENABLED = True  # enabled, but no observe_turn wrapping ⇒ no trace
    try:
        async def tool_run():
            return _Outcome()

        async def kb_run():
            return [{"question": "q", "answer": "a"}]

        async def go():
            o = await tracing.observe_tool(name="t", tool_input={}, run=tool_run)
            r = await tracing.observe_retrieval(query="q", run=kb_run)
            return o, r

        outcome, results = _run(go())
        assert isinstance(outcome, _Outcome)
        assert results == [{"question": "q", "answer": "a"}]
    finally:
        tracing._ENABLED = False


# --- the full tree: builds nested spans + persists --------------------------


def _drive_full_turn(pool):
    """A turn exercising llm → tool → retriever, like the real loop."""
    async def run():
        holder = {}
        async for d in tracing.observe_model_round(
            user_input="hi",
            open_stream=lambda: _FakeStream(["Hel", "lo"], _FinalMsg()),
            holder=holder,
        ):
            yield d

        async def kb_run():
            return [{"question": "Off-market?", "answer": "DIS transfer"}]

        async def dispatch():
            await tracing.observe_retrieval(query="transfer to demat", run=kb_run)
            return _Outcome()

        await tracing.observe_tool(
            name="search_knowledge_base",
            tool_input={"query": "transfer to demat"},
            run=dispatch,
        )
        yield "done"

    async def go():
        out = [c async for c in tracing.observe_turn(
            message="how do I transfer to another demat?",
            session_id="sess-123", client_code="X008593", pool=pool, run=run,
        )]
        pending = list(tracing._pending)
        if pending:
            await asyncio.gather(*pending)  # flush the fire-and-forget persist
        return out

    return _run(go())


def test_full_turn_builds_tree_and_persists():
    tracing._ENABLED = True
    pool = FakePool()
    try:
        out = _drive_full_turn(pool)
        assert out == ["Hel", "lo", "done"]  # streaming preserved

        inserts = [c for c in pool.calls if "INSERT INTO agent_traces" in c[0]]
        assert len(inserts) == 1
        args = inserts[0][1]
        (thread_id, user_id, latency_ms, model, in_tok, out_tok, tools,
         had_error, tin, tout, spans_json) = args

        assert thread_id == tracing._stable_id("sess-123")  # hashed, not raw
        assert "sess-123" != thread_id
        assert model == "claude-haiku-4-5"
        assert in_tok == 120 and out_tok == 18
        assert tools == ["search_knowledge_base"]
        assert had_error is False
        assert tout == "Hello"  # trace output = joined llm text

        spans = json.loads(spans_json)
        by_type = {s["type"]: s for s in spans}
        assert set(by_type) == {"agent", "llm", "tool", "retriever"}
        agent, llm, tool, retr = (
            by_type["agent"], by_type["llm"], by_type["tool"], by_type["retriever"]
        )
        # nesting: agent root, llm+tool under agent, retriever under the tool
        assert agent["parent_id"] is None
        assert llm["parent_id"] == agent["id"]
        assert tool["parent_id"] == agent["id"]
        assert retr["parent_id"] == tool["id"]
        # llm carries model + token split (incl. cache tokens)
        assert llm["metadata"]["cache_read_input_tokens"] == 100
        # retriever carries the fused chunks + embedder
        assert retr["metadata"]["retrieval_context"] == ["Off-market? — DIS transfer"]
        assert retr["metadata"]["embedder"]
        # tool input is present and its span records no error
        assert tool["metadata"]["is_error"] is False
    finally:
        tracing._ENABLED = False


# --- schema ------------------------------------------------------------------


def test_ensure_schema_creates_table_when_enabled():
    tracing._ENABLED = True
    pool = FakePool()
    try:
        _run(tracing.ensure_schema(pool))
        assert any("CREATE TABLE" in c[0] for c in pool.calls)
    finally:
        tracing._ENABLED = False


def test_ensure_schema_noop_without_pool_or_disabled():
    tracing._ENABLED = True
    _run(tracing.ensure_schema(None))  # no pool → no crash
    tracing._ENABLED = False
    _run(tracing.ensure_schema(FakePool()))  # disabled → no-op
