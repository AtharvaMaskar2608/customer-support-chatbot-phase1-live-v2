"""Curation at the loop seam (CHO-271 · task 4.15) + the trace-span counts.

Task 4.15 was specced to live in `test_agent_loop.py`; it is here instead so
the shared loop suite stays untouched while three CHO-26x/27x changes land in
parallel. The fakes below are the same scripted-Anthropic pattern that file
uses.

What matters here and cannot be proven by unit tests: with the flag ON the
*assembled request* carries the earlier turn's artifact result as a stub while
block counts and `tool_use_id`s are unchanged, and with the flag OFF the array
is byte-identical to the lossless `thread.messages()`.
"""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.agent import curation, tracing
from app.agent.tools import DispatchOutcome
from app.main import create_app

SESSION_ID = "curation-session-token"
SSO_JWT = "test-sso-jwt"
CLIENT_CODE = "X008593"

HEADERS = {
    "Authorization": SSO_JWT,
    "X-Session-Id": SESSION_ID,
    "X-User-Id": CLIENT_CODE,
}

HOLDINGS = {
    "kind": "ok",
    "asOf": "2026-07-25T15:30:00",
    "rows": [
        {
            "Sym": "TCS", "Name": "Tata Consultancy", "Q": 10, "ABP": 3100.0,
            "LTP": 3250.5, "CP": 3240.0, "current": 32505.0,
            "invested": 31000.0, "pnl": 1505.0, "day": 105.0, "alloc": 27.1,
        }
    ] * 3,
    "totals": {
        "count": 3, "current": 97515.0, "invested": 93000.0, "pnl": 4515.0,
        "pnlPct": 4.85, "day": 315.0, "dayPct": 0.32,
    },
}


# --- fakes: scripted Anthropic streaming client ------------------------------


class FakeMessage:
    def __init__(self, content, stop_reason="end_turn", deltas=None):
        self.content = content
        self.stop_reason = stop_reason
        self.model = "claude-sonnet-4-6"
        self.usage = {"input_tokens": 11, "output_tokens": 7}
        if deltas is None:
            deltas = [b["text"] for b in content if b.get("type") == "text"]
        self.deltas = deltas


class FakeStream:
    def __init__(self, message):
        self._message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    def text_stream(self):
        async def gen():
            for delta in self._message.deltas:
                yield delta

        return gen()

    async def get_final_message(self):
        return self._message


class _FakeMessagesAPI:
    def __init__(self, outer):
        self._outer = outer

    def stream(self, **kwargs):
        self._outer.calls.append(kwargs)
        item = self._outer.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeStream(item)


class FakeAnthropic:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.messages = _FakeMessagesAPI(self)


def _tool_use_block(name, block_id="tu_1"):
    return {"type": "tool_use", "id": block_id, "name": name, "input": {}}


def _tool_msg(*blocks):
    return FakeMessage(list(blocks), stop_reason="tool_use")


def _text_msg(text):
    return FakeMessage([{"type": "text", "text": text}])


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setattr("app.config.database_url", lambda: None)  # memory-only
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.delenv("AGENT_THINKING", raising=False)
    return create_app()


def _get_thread(app):
    store = app.state.conversation_store
    return asyncio.run(store.get_thread(SESSION_ID, client_code=CLIENT_CODE))


def _post(client, message):
    return client.post("/api/chat", headers=HEADERS, json={"message": message})


def _holdings_dispatch(monkeypatch):
    async def fake(name, tool_input, ctx):
        return DispatchOutcome(
            content=json.dumps(HOLDINGS, sort_keys=True, separators=(",", ":")),
            is_error=False,
            duration_ms=3,
            envelope=HOLDINGS,
        )

    monkeypatch.setattr("app.agent.tools.dispatch_outcome", fake)


def _history_at_request(thread, *, curated):
    """The messages array the loop would have built for the LAST model call:
    every turn up to and including turn 2's user message (the assistant reply
    is appended only after the call returns)."""
    from app.agent.store import Thread

    mark = curation.watermark(thread)
    head = Thread(id=thread.id, session_id=thread.session_id)
    head.turns = [t for t in thread.turns if t.seq <= mark]
    transform = curation.curate(thread) if curated else None
    return head.messages(transform=transform)


def _tool_results(messages):
    return [
        block
        for message in messages
        for block in message["content"]
        if isinstance(block, dict) and block.get("type") == "tool_result"
    ]


def _drive_two_turns(app, monkeypatch):
    """Turn 1 renders the holdings card (artifact-only round short-circuits);
    turn 2 is a plain answer, so its FIRST model call is the one that must
    already carry the stub."""
    _holdings_dispatch(monkeypatch)
    fake = FakeAnthropic([
        _tool_msg(_tool_use_block("get_holdings", "tu_hold")),
        _text_msg("You asked earlier about your portfolio."),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        _post(client, "what do I hold?")
        _post(client, "and what did I hold again?")
    return fake


# --- 4.15 flag ON: the earlier artifact result arrives as a stub -------------


def test_flag_on_sends_the_earlier_artifact_result_as_a_stub(app, monkeypatch):
    monkeypatch.setenv("AGENT_CONTEXT_CURATION", "1")
    fake = _drive_two_turns(app, monkeypatch)
    assert len(fake.calls) == 2

    messages = fake.calls[-1]["messages"]
    results = _tool_results(messages)
    assert len(results) == 1
    block = results[0]
    assert block["type"] == "tool_result"
    assert block["tool_use_id"] == "tu_hold"  # pairing preserved
    assert block["is_error"] is False
    assert block["content"].startswith(curation._FRAME)
    assert "get_holdings result cleared" in block["content"]
    assert "call get_holdings again" in block["content"]
    # no figure, no scrip name survives into the request
    assert "TCS" not in block["content"]
    assert "3250.5" not in block["content"]
    assert "97515.0" not in block["content"]

    # block counts and roles match the lossless array exactly
    thread = _get_thread(app)
    lossless = _history_at_request(thread, curated=False)
    history = messages[len(messages) - len(lossless):]
    assert [m["role"] for m in history] == [m["role"] for m in lossless]
    assert [len(m["content"]) for m in history] == [
        len(m["content"]) for m in lossless
    ]
    assert json.dumps(history) == json.dumps(
        _history_at_request(thread, curated=True)
    )
    # the tool_use block that this result answers is still verbatim
    uses = [
        b
        for m in history
        for b in m["content"]
        if isinstance(b, dict) and b.get("type") == "tool_use"
    ]
    assert [b["id"] for b in uses] == ["tu_hold"]

    # the STORE still holds the full envelope, byte for byte
    stored = [t for t in thread.turns if t.kind == "tool_result"]
    assert len(stored) == 1
    assert stored[0].content[0]["content"] == json.dumps(
        HOLDINGS, sort_keys=True, separators=(",", ":")
    )
    assert "TCS" in stored[0].content[0]["content"]


def test_flag_on_shrinks_the_history(app, monkeypatch):
    monkeypatch.setenv("AGENT_CONTEXT_CURATION", "1")
    fake = _drive_two_turns(app, monkeypatch)
    thread = _get_thread(app)
    lossless = curation.history_tokens_est(thread.messages())
    curated = curation.history_tokens_est(
        curation.messages_for_model(thread)
    )
    assert curated < lossless
    sent = json.dumps(fake.calls[-1]["messages"])
    assert "result cleared" in sent


# --- flag OFF: byte-identical to today --------------------------------------


def test_flag_off_history_is_byte_identical_to_the_lossless_array(
    app, monkeypatch
):
    monkeypatch.delenv("AGENT_CONTEXT_CURATION", raising=False)
    fake = _drive_two_turns(app, monkeypatch)

    messages = fake.calls[-1]["messages"]
    assert "result cleared" not in json.dumps(messages)

    thread = _get_thread(app)
    lossless = _history_at_request(thread, curated=False)
    history = messages[len(messages) - len(lossless):]
    assert json.dumps(history) == json.dumps(lossless)
    assert thread.curated == {}  # the memo cache was never touched


def test_flag_off_leaves_the_envelope_verbatim_in_the_request(app, monkeypatch):
    monkeypatch.delenv("AGENT_CONTEXT_CURATION", raising=False)
    fake = _drive_two_turns(app, monkeypatch)
    results = _tool_results(fake.calls[-1]["messages"])
    assert len(results) == 1
    assert results[0]["content"] == json.dumps(
        HOLDINGS, sort_keys=True, separators=(",", ":")
    )


# --- the llm span records counts only ---------------------------------------


class _FinalMsg:
    model = "claude-sonnet-4-6"
    stop_reason = "end_turn"
    usage = {"input_tokens": 120, "output_tokens": 18}
    content = [{"type": "text", "text": "Hello"}]


class _SpanStream:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    def text_stream(self):
        async def gen():
            yield "Hello"

        return gen()

    async def get_final_message(self):
        return _FinalMsg()


def test_observe_model_round_merges_extra_counts_into_the_llm_span():
    tracing._ENABLED = True
    pool_calls: list = []

    class FakePool:
        async def execute(self, sql, *args):
            pool_calls.append((sql, args))

    async def run():
        holder: dict = {}
        async for delta in tracing.observe_model_round(
            user_input="hi",
            open_stream=lambda: _SpanStream(),
            holder=holder,
            extra={"curated_turns": 4, "history_tokens_est": 2323},
        ):
            yield delta

    async def go():
        out = [
            chunk
            async for chunk in tracing.observe_turn(
                message="hi",
                session_id="s",
                client_code=CLIENT_CODE,
                pool=FakePool(),
                run=run,
            )
        ]
        pending = list(tracing._pending)
        if pending:
            await asyncio.gather(*pending)
        return out

    try:
        assert asyncio.run(go()) == ["Hello"]
    finally:
        tracing._ENABLED = False

    inserts = [c for c in pool_calls if "INSERT INTO agent_traces" in c[0]]
    assert len(inserts) == 1
    spans = json.loads(inserts[0][1][-1])
    llm = next(s for s in spans if s["type"] == "llm")
    assert llm["metadata"]["curated_turns"] == 4
    assert llm["metadata"]["history_tokens_est"] == 2323
    # the pre-existing usage fields are untouched
    assert llm["metadata"]["input_tokens"] == 120
    assert llm["metadata"]["model"] == "claude-sonnet-4-6"


def test_observe_model_round_without_extra_is_unchanged():
    tracing._ENABLED = False

    async def go():
        holder: dict = {}
        out = [
            d
            async for d in tracing.observe_model_round(
                user_input="hi",
                open_stream=lambda: _SpanStream(),
                holder=holder,
            )
        ]
        return out, holder

    deltas, holder = asyncio.run(go())
    assert deltas == ["Hello"]
    assert holder["final"] is not None
