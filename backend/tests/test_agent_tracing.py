"""DeepEval tracing (CHO-244): the mask, config gating, id hashing, and that
the observe wrappers preserve behaviour (streamed + return values) whether
tracing is off (pass-through) or on. Export is never exercised — hermetic.
"""

import asyncio

from app.agent import tracing


def _drain(agen):
    async def go():
        return [chunk async for chunk in agen]

    return asyncio.run(go())


# --- redact (the global mask) ------------------------------------------------

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
    assert out["segment"] == "Equity"  # safe key untouched
    assert out["fromDate"] == "2026-07-01"
    assert out["nested"]["client_code"] == tracing._REDACT
    assert out["nested"]["top_k"] == 5


def test_redact_recurses_lists_and_passes_scalars():
    assert tracing.redact([1, "ok", {"pan": "ABCDE1234F"}]) == [
        1, "ok", {"pan": tracing._REDACT}
    ]
    assert tracing.redact(42) == 42
    assert tracing.redact(None) is None


# --- stable id (thread/user pseudonymisation) --------------------------------


def test_stable_id_is_stable_hashed_and_not_raw():
    sid = "chat-session-token"
    first = tracing._stable_id(sid)
    assert first == tracing._stable_id(sid)  # deterministic
    assert first and sid not in first and len(first) == 16
    assert tracing._stable_id(None) is None
    assert tracing._stable_id("") is None


# --- configure gating --------------------------------------------------------


def test_configure_noop_when_disabled(monkeypatch):
    monkeypatch.setattr("app.config.tracing_enabled", lambda: False)
    tracing._ENABLED = False
    tracing.configure()
    assert tracing.enabled() is False


def test_configure_enables_and_passes_mask(monkeypatch):
    calls = {}

    def fake_configure(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr("app.config.tracing_enabled", lambda: True)
    monkeypatch.setattr("app.config.confident_api_key", lambda: "test-key")
    monkeypatch.setattr("app.config.deepeval_env", lambda: "staging")
    monkeypatch.setattr("app.config.deepeval_sampling_rate", lambda: 0.5)
    monkeypatch.setattr(tracing.trace_manager, "configure", fake_configure)
    tracing._ENABLED = False
    tracing.configure()
    assert tracing.enabled() is True
    assert calls["mask"] is tracing.redact
    assert calls["tracing_enabled"] is True
    assert calls["environment"] == "staging"
    assert calls["sampling_rate"] == 0.5
    tracing._ENABLED = False  # reset for other tests


# --- fakes mirroring the loop's stream + dispatch ----------------------------


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
    usage = type("U", (), {"input_tokens": 11, "output_tokens": 7})()


class _Outcome:
    is_error = False
    error_code = None
    duration_ms = 3


# --- wrappers: behaviour identical whether tracing is off or on ---------------


def _run_turn_wrapper():
    async def run():
        yield "Hel"
        yield "lo"

    return _drain(
        tracing.observe_turn(
            message="hi", session_id="s1", client_code="c1", run=run
        )
    )


def test_observe_turn_passthrough_when_off():
    tracing._ENABLED = False
    assert _run_turn_wrapper() == ["Hel", "lo"]


def test_observe_turn_streams_when_on():
    tracing._ENABLED = True
    try:
        assert _run_turn_wrapper() == ["Hel", "lo"]
    finally:
        tracing._ENABLED = False


def _run_model_round():
    holder: dict = {}
    final = _FinalMsg()

    def open_stream():
        return _FakeStream(["a", "b", "c"], final)

    deltas = _drain(
        tracing.observe_model_round(
            user_input="hi", open_stream=open_stream, holder=holder
        )
    )
    return deltas, holder, final


def test_observe_model_round_passthrough_streams_and_sets_holder():
    tracing._ENABLED = False
    deltas, holder, final = _run_model_round()
    assert deltas == ["a", "b", "c"]
    assert holder["final"] is final


def test_observe_model_round_on_streams_and_sets_holder():
    tracing._ENABLED = True
    try:
        deltas, holder, final = _run_model_round()
        assert deltas == ["a", "b", "c"]
        assert holder["final"] is final
    finally:
        tracing._ENABLED = False


def test_observe_tool_returns_outcome_both_modes():
    outcome = _Outcome()

    async def run():
        return outcome

    for enabled in (False, True):
        tracing._ENABLED = enabled
        try:
            got = asyncio.run(
                tracing.observe_tool(
                    name="get_holdings", tool_input={"x": 1}, run=run
                )
            )
            assert got is outcome
        finally:
            tracing._ENABLED = False


def test_observe_retrieval_returns_results_both_modes():
    results = [{"question": "q", "answer": "a"}, {"question": "q2", "answer": "a2"}]

    async def run():
        return results

    for enabled in (False, True):
        tracing._ENABLED = enabled
        try:
            got = asyncio.run(tracing.observe_retrieval(query="hi", run=run))
            assert got == results
        finally:
            tracing._ENABLED = False
