"""Langfuse trace mirror (CHO-286): identity mapping, the credential guard, the
shared mask, and that the mirror stays strictly subordinate to the Postgres
system of record.

Hermetic by construction: a fake stands in for the Langfuse SDK client, so the
real `langfuse_mirror` code paths run (start_root / start_child / set_identity /
end) with no network and no running Langfuse. What is under test is OUR logic —
the tree shape we hand Langfuse and the guarantees around it — not the SDK's.
"""

import asyncio

import pytest

from app.agent import langfuse_mirror, tracing


def _run(coro):
    return asyncio.run(coro)


# --- fakes -------------------------------------------------------------------


class FakePool:
    def __init__(self):
        self.calls = []

    async def execute(self, sql, *args):
        self.calls.append((sql, args))


class _FakeOtelSpan:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class _FakeSpan:
    """Stands in for LangfuseSpan / LangfuseGeneration."""

    def __init__(self, name, as_type, recorder, parent=None):
        self.name, self.as_type, self.parent = name, as_type, parent
        self.updates, self.ended = [], False
        self.children = []
        self._otel_span = _FakeOtelSpan()
        self._recorder = recorder

    def start_observation(self, *, name, as_type="span", **kw):
        child = _FakeSpan(name, as_type, self._recorder, parent=self)
        self.children.append(child)
        self._recorder.spans.append(child)
        return child

    def update(self, **fields):
        self.updates.append(fields)

    def end(self):
        self.ended = True


class _FakeClient:
    def __init__(self):
        self.spans = []
        self.shutdowns = 0

    def start_observation(self, *, name, as_type="span", **kw):
        span = _FakeSpan(name, as_type, self)
        self.spans.append(span)
        return span

    def shutdown(self):
        self.shutdowns += 1


class _ExplodingClient:
    """Every entry point raises — the never-degrade case."""

    def start_observation(self, **kw):
        raise RuntimeError("langfuse is down")

    def shutdown(self):
        raise RuntimeError("langfuse is down")


class _FinalMsg:
    model = "claude-sonnet-4-6"
    stop_reason = "end_turn"
    usage = {"input_tokens": 120, "output_tokens": 18}


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


class _Outcome:
    is_error = False
    error_code = None
    duration_ms = 12


@pytest.fixture
def mirror(monkeypatch):
    """Mirror armed with a fake client; Postgres tracing on. Restores both."""
    client = _FakeClient()
    monkeypatch.setattr(langfuse_mirror, "_client", client)
    monkeypatch.setattr(langfuse_mirror, "_ENABLED", True)
    monkeypatch.setattr(tracing, "_ENABLED", True)
    yield client


SSO_SESSION = "live-sso-session-token-value-do-not-store"
CLIENT_CODE = "X008593"
THREAD = "conv-uuid-286"


def _drive_turn(pool, *, thread_id=THREAD, session_id=SSO_SESSION):
    """A turn shaped like the real loop: llm → tool → (embed, search)."""

    async def run():
        tracing.bind_conversation_thread(thread_id)
        holder = {}
        async for d in tracing.observe_model_round(
            user_input="when does intraday square off happen",
            open_stream=lambda: _FakeStream(["Intra", "day"], _FinalMsg()),
            holder=holder,
        ):
            yield d

        async def kb_run():
            return [{"question": "Square off?", "answer": "3:10 pm"}]

        async def emb_run():
            return [0.1] * 8

        async def tool_run():
            await tracing.observe_embedding(query="square off", run=emb_run)
            await tracing.observe_retrieval(query="square off", run=kb_run)
            return _Outcome()

        await tracing.observe_tool(
            name="search_knowledge_base",
            tool_input={"query": "square off", "session_id": session_id},
            run=tool_run,
        )

    async def go():
        return [
            c
            async for c in tracing.observe_turn(
                message="when does intraday square off happen",
                session_id=session_id,
                client_code=CLIENT_CODE,
                pool=pool,
                run=run,
            )
        ]

    return _run(go())


def _by_name(client):
    return {s.name: s for s in client.spans}


# --- the mirrored tree -------------------------------------------------------


def test_mirror_reproduces_the_postgres_span_tree(mirror):
    _drive_turn(FakePool())
    names = [s.name for s in mirror.spans]
    assert names == [
        "chat_turn", "model_round", "search_knowledge_base", "kb_embed", "kb_search"
    ]
    spans = _by_name(mirror)
    # Same nesting the Postgres tree records: retriever spans under their tool.
    assert spans["chat_turn"].parent is None
    assert spans["model_round"].parent is spans["chat_turn"]
    assert spans["search_knowledge_base"].parent is spans["chat_turn"]
    assert spans["kb_embed"].parent is spans["search_knowledge_base"]
    assert spans["kb_search"].parent is spans["search_knowledge_base"]
    assert all(s.ended for s in mirror.spans)


def test_llm_round_is_a_generation_with_native_usage(mirror):
    _drive_turn(FakePool())
    gen = _by_name(mirror)["model_round"]
    assert gen.as_type == "generation"
    fields = gen.updates[-1]
    assert fields["model"] == "claude-sonnet-4-6"
    assert fields["usage_details"]["input"] == 120
    assert fields["usage_details"]["output"] == 18
    # Everything else is a plain span.
    assert _by_name(mirror)["kb_search"].as_type == "span"


# --- identity ----------------------------------------------------------------


def test_identity_matches_what_postgres_stores(mirror):
    """The join key: session = Thread.id, user = the same HMAC in the row."""
    pool = FakePool()
    _drive_turn(pool)

    attrs = _by_name(mirror)["chat_turn"]._otel_span.attributes
    assert attrs["session.id"] == THREAD
    assert attrs["user.id"] == tracing._stable_id(CLIENT_CODE)

    insert = [c for c in pool.calls if "INSERT INTO agent_traces" in c[0]][0]
    stored_thread, stored_user = insert[1][0], insert[1][1]
    assert attrs["session.id"] == stored_thread
    assert attrs["user.id"] == stored_user


def test_main_menu_reset_starts_a_new_session(mirror):
    """CHO-275, restated for the mirror: a new thread must not roll up."""
    _drive_turn(FakePool(), thread_id="conv-uuid-first")
    _drive_turn(FakePool(), thread_id="conv-uuid-second")
    roots = [s for s in mirror.spans if s.name == "chat_turn"]
    assert len(roots) == 2
    sessions = [r._otel_span.attributes["session.id"] for r in roots]
    assert sessions == ["conv-uuid-first", "conv-uuid-second"]
    # Same user across both — "everything this user did" is a user_id filter.
    users = {r._otel_span.attributes["user.id"] for r in roots}
    assert len(users) == 1


def test_sso_session_token_never_reaches_the_mirror(mirror):
    """The FinX SessionId authenticates the report endpoints. It must not appear
    anywhere in the exported payload — not as the session id, not in a field."""
    _drive_turn(FakePool())
    blob = repr(
        [
            (s.name, s.as_type, s.updates, s._otel_span.attributes)
            for s in mirror.spans
        ]
    )
    assert SSO_SESSION not in blob
    assert CLIENT_CODE not in blob
    # And the hashed user id is what is there instead.
    assert tracing._stable_id(CLIENT_CODE) in blob


# --- the mask ----------------------------------------------------------------


def test_mask_is_the_same_definition_as_the_postgres_path():
    """One mask governs both sinks, so the mirror cannot fall behind the
    denylist as it grows."""
    payload = {"authorization": "Bearer abc", "pan": "ABCDE1234F", "top_k": 5}
    masked = tracing._mirror_mask(data=payload)
    assert masked == tracing.redact(payload)
    assert masked["authorization"] == tracing._REDACT
    assert masked["pan"] == tracing._REDACT
    assert masked["top_k"] == 5


def test_mask_failure_redacts_rather_than_leaking(monkeypatch):
    """A raising mask would drop the span; falling back to a marker keeps the
    span without ever letting the unmasked value through."""
    monkeypatch.setattr(
        tracing, "redact", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("boom"))
    )
    assert tracing._mirror_mask(data={"pan": "ABCDE1234F"}) == "[redaction-failed]"


# --- subordinate to the system of record -------------------------------------


def test_langfuse_failure_does_not_degrade_the_turn(monkeypatch):
    """Every export call raises: the turn must still stream, and the
    agent_traces row must still be written complete."""
    monkeypatch.setattr(langfuse_mirror, "_client", _ExplodingClient())
    monkeypatch.setattr(langfuse_mirror, "_ENABLED", True)
    monkeypatch.setattr(tracing, "_ENABLED", True)

    pool = FakePool()
    chunks = _drive_turn(pool)

    assert chunks == ["Intra", "day"]
    insert = [c for c in pool.calls if "INSERT INTO agent_traces" in c[0]]
    assert len(insert) == 1
    assert insert[0][1][0] == THREAD  # thread_id still recorded


def test_mirror_handles_never_reach_postgres(mirror):
    """`lf` is runtime-only state; the persisted span shape must not carry it."""
    pool = FakePool()
    _drive_turn(pool)
    spans_json = [c for c in pool.calls if "INSERT INTO agent_traces" in c[0]][0][1][10]
    assert '"lf"' not in spans_json
    assert "_FakeSpan" not in spans_json


# --- inert unless fully configured -------------------------------------------


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LANGFUSE_TRACING", raising=False)
    from app import config

    assert config.langfuse_tracing_enabled() is False


def test_configure_builds_no_client_without_credentials(monkeypatch):
    monkeypatch.setattr("app.config.langfuse_tracing_enabled", lambda: True)
    monkeypatch.setattr("app.config.langfuse_public_key", lambda: "pk-lf-x")
    monkeypatch.setattr("app.config.langfuse_secret_key", lambda: None)
    monkeypatch.setattr("app.config.langfuse_base_url", lambda: "http://localhost:3000")
    langfuse_mirror.configure()
    assert langfuse_mirror.enabled() is False
    assert langfuse_mirror._client is None


def test_configure_off_makes_every_entry_point_a_noop(monkeypatch):
    monkeypatch.setattr("app.config.langfuse_tracing_enabled", lambda: False)
    langfuse_mirror.configure()
    assert langfuse_mirror.enabled() is False
    # None-returning, non-raising, no client touched.
    assert langfuse_mirror.start_root(name="x", input={}) is None
    assert langfuse_mirror.start_child(None, name="y") is None
    langfuse_mirror.set_identity(None, user_id="u", session_id="s")
    langfuse_mirror.end(None)
    langfuse_mirror.shutdown()


def test_turn_is_unaffected_when_mirror_is_off(monkeypatch):
    """With the mirror off, tracing behaves exactly as it did before CHO-286."""
    monkeypatch.setattr(langfuse_mirror, "_ENABLED", False)
    monkeypatch.setattr(langfuse_mirror, "_client", None)
    monkeypatch.setattr(tracing, "_ENABLED", True)

    pool = FakePool()
    assert _drive_turn(pool) == ["Intra", "day"]
    assert len([c for c in pool.calls if "INSERT INTO agent_traces" in c[0]]) == 1


def test_shutdown_flushes_when_enabled(mirror):
    langfuse_mirror.shutdown()
    assert mirror.shutdowns == 1


# --- error paths: a span left open never reaches Langfuse at all -------------
# OTel exports a span when it ENDS. One left open is silently ABSENT from the
# mirror while Postgres still records it (with a null duration) — the exact
# shape divergence the mirror must never produce. Tool and model failures are
# an ordinary path, so each helper needs its own guard.


@pytest.mark.parametrize(
    "failing",
    ["tool", "model_round", "kb_embed", "kb_search"],
)
def test_every_helper_ends_its_mirror_span_when_the_body_raises(mirror, failing):
    async def boom():
        raise RuntimeError("upstream exploded")

    async def ok_embed():
        return [0.1] * 4

    async def ok_kb():
        return [{"question": "q", "answer": "a"}]

    async def run():
        tracing.bind_conversation_thread(THREAD)
        if failing == "model_round":
            async for d in tracing.observe_model_round(
                user_input="hi",
                open_stream=lambda: _ExplodingStream(),
                holder={},
            ):
                yield d
            return

        async def tool_body():
            if failing == "kb_embed":
                await tracing.observe_embedding(query="q", run=boom)
            else:
                await tracing.observe_embedding(query="q", run=ok_embed)
            if failing == "kb_search":
                await tracing.observe_retrieval(query="q", run=boom)
            else:
                await tracing.observe_retrieval(query="q", run=ok_kb)
            return _Outcome()

        await tracing.observe_tool(
            name="search_knowledge_base",
            tool_input={"query": "q"},
            run=boom if failing == "tool" else tool_body,
        )
        yield "x"

    async def go():
        return [
            c
            async for c in tracing.observe_turn(
                message="m", session_id=SSO_SESSION, client_code=CLIENT_CODE,
                pool=FakePool(), run=run,
            )
        ]

    with pytest.raises(RuntimeError):
        _run(go())

    unended = [s.name for s in mirror.spans if not s.ended]
    assert not unended, f"open mirror spans would never export: {unended}"
    # The failing span is marked, not silently closed as if it succeeded.
    failed = [
        s for s in mirror.spans
        if any(u.get("level") == "ERROR" for u in s.updates)
    ]
    assert failed, "the failing span carries no ERROR level"
    assert all(
        u.get("status_message") == "RuntimeError"
        for s in failed for u in s.updates if u.get("level") == "ERROR"
    )


class _ExplodingStream:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    def text_stream(self):
        async def gen():
            raise RuntimeError("upstream exploded")
            yield  # pragma: no cover

        return gen()

    async def get_final_message(self):  # pragma: no cover
        raise RuntimeError("upstream exploded")


def test_concurrent_turns_do_not_cross_wire_identity(mirror):
    """Two turns in flight at once must not share a session. Parenting is
    explicit (off the parent handle) rather than via ambient OTel context
    precisely so interleaved coroutines cannot braid each other's trees."""

    def one(thread_id):
        async def run():
            tracing.bind_conversation_thread(thread_id)
            await asyncio.sleep(0)  # force interleaving
            holder = {}
            async for _ in tracing.observe_model_round(
                user_input="hi",
                open_stream=lambda: _FakeStream(["a"], _FinalMsg()),
                holder=holder,
            ):
                await asyncio.sleep(0)
            yield "x"

        return tracing.observe_turn(
            message="m", session_id=SSO_SESSION, client_code=CLIENT_CODE,
            pool=FakePool(), run=run,
        )

    async def drain(gen):
        return [c async for c in gen]

    async def go():
        await asyncio.gather(drain(one("thread-A")), drain(one("thread-B")))

    _run(go())

    roots = [s for s in mirror.spans if s.name == "chat_turn"]
    assert len(roots) == 2
    assert {r._otel_span.attributes["session.id"] for r in roots} == {
        "thread-A", "thread-B"
    }
    # Each root owns exactly its own model_round — no braiding.
    for r in roots:
        assert [c.name for c in r.children] == ["model_round"]
