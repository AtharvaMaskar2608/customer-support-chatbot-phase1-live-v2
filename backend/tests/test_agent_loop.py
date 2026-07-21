"""Agent loop + /api/chat SSE endpoint (CHO-213 · task 4.6).

The Anthropic client is faked (scripted stream objects yielding text deltas
and final messages) — no live model calls. Tool execution runs either through
the real dispatcher against respx-mocked upstreams (credential isolation,
auth expiry) or through a monkeypatched dispatch_outcome (loop mechanics).
"""

import asyncio
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import config
from app.agent import tools as agent_tools
from app.agent.tools import DispatchOutcome
from app.main import create_app

SESSION_ID = "chat-session-token"
SSO_JWT = "test-sso-jwt"
CLIENT_CODE = "X008593"

HEADERS = {
    "Authorization": SSO_JWT,
    "X-Session-Id": SESSION_ID,
    "X-User-Id": CLIENT_CODE,
}


# --- fakes: scripted Anthropic streaming client ------------------------------


class FakeMessage:
    def __init__(self, content, stop_reason="end_turn", deltas=None):
        self.content = content  # plain dict blocks — the loop accepts both
        self.stop_reason = stop_reason
        self.model = "claude-haiku-4-5"
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


def _text_msg(text, stop_reason="end_turn"):
    return FakeMessage([{"type": "text", "text": text}], stop_reason=stop_reason)


def _tool_use(name, tool_input=None, block_id="tu_1"):
    return {
        "type": "tool_use",
        "id": block_id,
        "name": name,
        "input": tool_input or {},
    }


def _tool_msg(*blocks, text=None):
    content = ([{"type": "text", "text": text}] if text else []) + list(blocks)
    return FakeMessage(content, stop_reason="tool_use")


# --- helpers -----------------------------------------------------------------


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setattr("app.config.database_url", lambda: None)  # memory-only
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.delenv("AGENT_THINKING", raising=False)
    return create_app()


def _parse_events(resp):
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-accel-buffering"] == "no"
    events = []
    for chunk in resp.text.strip().split("\n\n"):
        event = data = None
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        events.append((event, data))
    return events


def _post_chat(client, message="hello"):
    return client.post("/api/chat", headers=HEADERS, json={"message": message})


def _get_thread(app):
    store = app.state.conversation_store
    return asyncio.run(store.get_thread(SESSION_ID, client_code=CLIENT_CODE))


def _append(app, thread, *, role, kind, text=None, content=None, meta=None):
    app.state.conversation_store.append_turn(
        thread,
        role=role,
        kind=kind,
        content=content or [{"type": "text", "text": text}],
        meta=meta or {},
    )


def _ok_outcome(envelope):
    async def fake(name, tool_input, ctx):
        return DispatchOutcome(
            content=json.dumps(envelope, sort_keys=True, separators=(",", ":")),
            is_error=False,
            duration_ms=3,
            envelope=envelope,
        )

    return fake


# --- loop termination + request assembly -------------------------------------


def test_end_turn_streams_text_and_terminates(app):
    fake = FakeAnthropic([_text_msg("Hello! How can I help you today?")])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        resp = _post_chat(client, "hi")
        events = _parse_events(resp)
        assert events == [
            ("text", {"delta": "Hello! How can I help you today?"}),
            # lastSeq: user_text(1) + assistant_text(2) — the feedback anchor
            ("done", {"thread": {"taskTurns": 1, "sessionTurns": 1, "lastSeq": 2}}),
        ]

        # one model call, correctly assembled
        assert len(fake.calls) == 1
        kwargs = fake.calls[0]
        assert kwargs["model"] == "claude-haiku-4-5"
        assert kwargs["max_tokens"] == 4096
        assert "thinking" not in kwargs  # AGENT_THINKING=off omits it
        assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert len(kwargs["tools"]) == 11  # 9 capability tools + form + ticket

        # primed first turn: two blocks — frozen instructions carrying the
        # cache breakpoint, then the live IST status line LAST (CHO-226 D8).
        messages = kwargs["messages"]
        primed = messages[0]["content"]
        assert messages[0]["role"] == "user"
        assert len(primed) == 2
        assert primed[0]["cache_control"] == {"type": "ephemeral"}
        assert "Right now it is" not in primed[0]["text"]
        assert "cache_control" not in primed[1]
        assert primed[1]["text"].startswith("Right now it is ")
        assert " IST on " in primed[1]["text"]
        assert messages[1] == {
            "role": "assistant",
            "content": [{"type": "text", "text": "Understood."}],
        }
        assert messages[2] == {
            "role": "user",
            "content": [{"type": "text", "text": "hi"}],
        }

        # store: wire-faithful turns with assistant meta
        thread = _get_thread(app)
        assert [t.kind for t in thread.turns] == ["user_text", "assistant_text"]
        meta = thread.turns[-1].meta
        assert meta["model"] == "claude-haiku-4-5"
        assert meta["stop_reason"] == "end_turn"
        assert meta["usage"] == {"input_tokens": 11, "output_tokens": 7}
        assert meta["latency_ms"] >= 0


def test_sonnet_minimal_thinking_kwargs(app, monkeypatch):
    monkeypatch.setenv("AGENT_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("AGENT_THINKING", "minimal")
    fake = FakeAnthropic([_text_msg("hello")])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        _post_chat(client)
    kwargs = fake.calls[0]
    assert kwargs["model"] == "claude-sonnet-4-6"
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {"effort": "low"}
    assert "budget_tokens" not in json.dumps(kwargs["thinking"])


# --- parallel tools, error bounce --------------------------------------------


def test_parallel_tool_use_answered_in_one_user_message(app, monkeypatch):
    executed = []

    async def fake_dispatch(name, tool_input, ctx):
        executed.append(name)
        return DispatchOutcome(
            content='{"kind":"ok"}', is_error=False, duration_ms=2,
            envelope={"kind": "ok"},
        )

    monkeypatch.setattr("app.agent.tools.dispatch_outcome", fake_dispatch)
    # Narration tools (KB + note list) — artifact tools would short-circuit
    # (CHO-215) and this test's wire-shape assertion needs the second call.
    fake = FakeAnthropic([
        _tool_msg(
            _tool_use("search_knowledge_base", block_id="tu_1"),
            _tool_use("list_contract_notes", block_id="tu_2"),
        ),
        _text_msg("Here's both."),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        resp = _post_chat(client, "charges info and my notes please")
        events = _parse_events(resp)

        assert sorted(executed) == ["list_contract_notes", "search_knowledge_base"]
        started = [d for e, d in events if e == "tool" and d["status"] == "started"]
        finished = [d for e, d in events if e == "tool" and d["status"] == "finished"]
        assert [d["name"] for d in started] == [
            "search_knowledge_base", "list_contract_notes",
        ]
        assert all(d["is_error"] is False for d in started + finished)

        # both tool_results ride in ONE user message on the wire
        followup = fake.calls[1]["messages"][-1]
        assert followup["role"] == "user"
        assert [b["type"] for b in followup["content"]] == ["tool_result"] * 2
        assert [b["tool_use_id"] for b in followup["content"]] == ["tu_1", "tu_2"]

        # store: assistant_tool_use turn + two tool_result turns with meta
        thread = _get_thread(app)
        kinds = [t.kind for t in thread.turns]
        assert kinds == [
            "user_text", "assistant_tool_use",
            "tool_result", "tool_result", "assistant_text",
        ]
        assert thread.turns[2].meta == {
            "duration_ms": 2, "is_error": False,
            "tool_name": "search_knowledge_base",
        }


def test_is_error_bounce_feeds_validation_back_to_model(app):
    """Missing params → is_error tool_result → the model asks the user."""
    fake = FakeAnthropic([
        _tool_msg(_tool_use("get_pnl_report", {"segment": "Equity"})),
        _text_msg("Which date range and delivery would you like?"),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        resp = _post_chat(client, "pnl for equity")
        events = _parse_events(resp)

        finished = [d for e, d in events if e == "tool" and d["status"] == "finished"]
        assert finished == [
            {"name": "get_pnl_report", "status": "finished", "is_error": True}
        ]
        assert not [e for e, _ in events if e == "artifact"]
        assert events[-1][0] == "done"

        # the bounced tool_result reached the second model call
        bounce = fake.calls[1]["messages"][-1]["content"][0]
        assert bounce["type"] == "tool_result"
        assert bounce["is_error"] is True
        assert "fromDate" in bounce["content"] and "ask the user" in bounce["content"]

        thread = _get_thread(app)
        error_turn = [t for t in thread.turns if t.kind == "tool_result"][0]
        assert error_turn.meta["is_error"] is True


# --- caps ---------------------------------------------------------------------


def _reminder_texts(call_kwargs):
    return [
        block["text"]
        for message in call_kwargs["messages"]
        for block in message["content"]
        if isinstance(block, dict) and "<system-reminder>" in block.get("text", "")
    ]


def test_clarify_cap_counts_statement_tailed_questions(app):
    """Live models end clarifying replies with reassurance statements
    ("...Once you let me know, I'll generate it right away.") — the clarify
    detector must count a "?" anywhere in the text, not only at the end.
    Regression for the live cap-trip miss found in CHO-213 smoke."""
    fake = FakeAnthropic([_text_msg("Let me connect you with a human agent.")])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        thread = _get_thread(app)
        _append(app, thread, role="user", kind="user_text", text="a report")
        _append(app, thread, role="assistant", kind="assistant_text",
                text="Which report do you need — P&L, ledger, or capital "
                     "gains? Once you let me know, I'll ask for the details.")
        _append(app, thread, role="user", kind="user_text", text="trading one")
        _append(app, thread, role="assistant", kind="assistant_text",
                text="Got it. Which segment: Equity, F&O, or Commodity?\n\n"
                     "Once you give me those details, I'll generate it right away.")
        resp = _post_chat(client, "you know, the usual")
        _parse_events(resp)

        reminders = _reminder_texts(fake.calls[0])
        assert len(reminders) == 1
        assert "raise_support_ticket" in reminders[0]  # CHO-218 wording


def test_clarify_cap_trips_and_injects_escalation(app):
    fake = FakeAnthropic([_text_msg("Let me connect you with a human agent.")])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        thread = _get_thread(app)
        _append(app, thread, role="user", kind="user_text", text="pnl please")
        _append(app, thread, role="assistant", kind="assistant_text",
                text="Which segment do you want?")
        _append(app, thread, role="user", kind="user_text", text="the usual")
        _append(app, thread, role="assistant", kind="assistant_text",
                text="Sorry — Equity, F&O, or Commodity?")
        resp = _post_chat(client, "just give it to me")
        events = _parse_events(resp)

        reminders = _reminder_texts(fake.calls[0])
        assert len(reminders) == 1
        assert "raise_support_ticket" in reminders[0]  # CHO-218 wording
        assert "clarifying question" in reminders[0]
        # reminder is appended at the END of messages, never stored
        assert fake.calls[0]["messages"][-1]["content"][0]["text"] == reminders[0]
        assert "<system-reminder>" not in json.dumps(thread.messages())
        assert events[-1] == (
            "done", {"thread": {"taskTurns": 3, "sessionTurns": 3, "lastSeq": 6}},
        )


def test_resolution_event_resets_task_counters(app):
    fake = FakeAnthropic([_text_msg("Sure — which segment, dates, delivery?")])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        thread = _get_thread(app)
        # two clarifying questions ... then a SUCCESSFUL tool call (resolution)
        _append(app, thread, role="user", kind="user_text", text="pnl please")
        _append(app, thread, role="assistant", kind="assistant_text",
                text="Which segment?")
        _append(app, thread, role="user", kind="user_text", text="equity")
        _append(app, thread, role="assistant", kind="assistant_text",
                text="Which dates?")
        _append(app, thread, role="user", kind="user_text", text="april, download")
        _append(app, thread, role="assistant", kind="assistant_tool_use",
                content=[_tool_use("get_pnl_report")])
        _append(app, thread, role="user", kind="tool_result",
                content=[{"type": "tool_result", "tool_use_id": "tu_1",
                          "content": "{}", "is_error": False}],
                meta={"tool_name": "get_pnl_report", "is_error": False,
                      "duration_ms": 5})
        _append(app, thread, role="assistant", kind="assistant_text",
                text="Your report is ready.")
        resp = _post_chat(client, "now the ledger")
        events = _parse_events(resp)

        assert _reminder_texts(fake.calls[0]) == []  # counters were reset
        # fresh task window: 1 user turn since resolution; session total 4
        assert events[-1] == (
            "done", {"thread": {"taskTurns": 1, "sessionTurns": 4, "lastSeq": 10}},
        )


def test_session_backstop_trips_at_twenty_user_messages(app, monkeypatch):
    monkeypatch.setenv("SESSION_TURN_CAP", "20")  # default is 100 (CHO-215)
    fake = FakeAnthropic([_text_msg("Here's an answer — or I can get a human.")])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        thread = _get_thread(app)
        for index in range(19):
            _append(app, thread, role="user", kind="user_text",
                    text=f"question {index}")
            # every answer "succeeds" — per-task counters keep resetting
            _append(app, thread, role="user", kind="tool_result",
                    content=[{"type": "tool_result", "tool_use_id": f"t{index}",
                              "content": "{}", "is_error": False}],
                    meta={"tool_name": "search_knowledge_base",
                          "is_error": False, "duration_ms": 1})
            _append(app, thread, role="assistant", kind="assistant_text",
                    text=f"answer {index}")
        resp = _post_chat(client, "message twenty")
        events = _parse_events(resp)

        assert len(_reminder_texts(fake.calls[0])) == 1  # backstop tripped
        assert events[-1] == (
            "done", {"thread": {"taskTurns": 1, "sessionTurns": 20, "lastSeq": 59}},
        )


# --- inner-round guard --------------------------------------------------------


def test_tool_round_guard_forces_wrapup_call(app, monkeypatch):
    monkeypatch.setattr(
        "app.agent.tools.dispatch_outcome", _ok_outcome({"kind": "ok"})
    )
    # A narration tool (KB) — artifact tools would short-circuit (CHO-215)
    # and never reach the guard.
    fake = FakeAnthropic(
        [_tool_msg(_tool_use("search_knowledge_base", block_id=f"tu_{i}"))
         for i in range(5)]
        + [_text_msg("Here's what I found so far.")]
    )
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        resp = _post_chat(client, "keep digging")
        events = _parse_events(resp)

    assert len(fake.calls) == 6  # 5 tool rounds + 1 forced wrap-up
    assert all("tool_choice" not in call for call in fake.calls[:5])
    assert fake.calls[5]["tool_choice"] == {"type": "none"}
    wrapup = _reminder_texts(fake.calls[5])
    assert len(wrapup) == 1 and "Tool-call limit" in wrapup[0]
    started = [d for e, d in events if e == "tool" and d["status"] == "started"]
    assert len(started) == 5
    assert events[-1][0] == "done"  # guard exhaustion still ends cleanly


# --- SSE sequence + artifacts -------------------------------------------------


def test_sse_ordering_text_tool_artifact_done(app, monkeypatch):
    """CHO-215: an artifact-only round ends the turn — the card is the
    answer, so no continuation model call and no trailing narration."""
    envelope = {"kind": "ok", "rows": [{"sym": "TCS"}], "totals": {"count": 1}}
    monkeypatch.setattr("app.agent.tools.dispatch_outcome", _ok_outcome(envelope))
    fake = FakeAnthropic([
        _tool_msg(_tool_use("get_holdings"), text="Let me pull that up."),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        resp = _post_chat(client, "my holdings")
        events = _parse_events(resp)

    assert len(fake.calls) == 1  # no continuation call after the artifact
    assert [e for e, _ in events] == [
        "text", "tool", "tool", "artifact", "done",
    ]
    artifact = dict(events)["artifact"]
    # data artifact: envelope fields spread at top level, its "kind" dropped
    assert artifact == {
        "kind": "data",
        "tool": "get_holdings",
        "rows": [{"sym": "TCS"}],
        "totals": {"count": 1},
    }


def test_file_artifact_carries_file_token_and_flow_key(app, monkeypatch):
    envelope = {
        "delivery": "download",
        "file": {"name": "PnL_Equity.pdf", "sizeLabel": "5 KB",
                 "format": "PDF", "passwordProtected": True},
        "fileToken": "tok-123",
    }
    monkeypatch.setattr("app.agent.tools.dispatch_outcome", _ok_outcome(envelope))
    fake = FakeAnthropic([
        _tool_msg(_tool_use("get_pnl_report")),
        _text_msg("Your P&L is ready — it opens with your PAN."),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        resp = _post_chat(client, "pnl equity april download")
        events = _parse_events(resp)

    artifact = dict(events)["artifact"]
    assert artifact == {
        "kind": "file",
        "file": envelope["file"],
        "fileToken": "tok-123",
        "flowKey": "pnl",
    }


def test_empty_data_envelope_is_narrated_not_artifacted(app, monkeypatch):
    monkeypatch.setattr(
        "app.agent.tools.dispatch_outcome", _ok_outcome({"kind": "empty"})
    )
    fake = FakeAnthropic([
        _tool_msg(_tool_use("get_holdings")),
        _text_msg("Your portfolio is currently empty."),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        events = _parse_events(_post_chat(client, "holdings"))
    assert not [e for e, _ in events if e == "artifact"]
    assert events[-1][0] == "done"


# --- error paths --------------------------------------------------------------


def test_missing_credentials_is_pre_stream_400(app):
    fake = FakeAnthropic([_text_msg("never called")])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        resp = client.post("/api/chat", json={"message": "hi"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "MISSING_CREDENTIALS"}
    assert fake.calls == []  # no model call is made


def test_anthropic_failure_emits_agent_unavailable(app):
    fake = FakeAnthropic([RuntimeError("api down")])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        resp = _post_chat(client, "hi")
        events = _parse_events(resp)
    assert events == [("error", {"error": "AGENT_UNAVAILABLE"})]


def test_anthropic_failure_midway_still_terminates_with_error(app, monkeypatch):
    """First round succeeds, second model call blows up: the stream still ends
    with exactly one terminal event (error), never a hung stream or a 500."""
    monkeypatch.setattr(
        "app.agent.tools.dispatch_outcome", _ok_outcome({"kind": "ok"})
    )
    # KB (narration) tool: an artifact round would short-circuit (CHO-215)
    # and never make the failing second call this test is about.
    fake = FakeAnthropic([
        _tool_msg(_tool_use("search_knowledge_base")),
        RuntimeError("api down mid-loop"),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        events = _parse_events(_post_chat(client, "what are DP charges?"))
    terminals = [e for e, _ in events if e in ("done", "error")]
    assert terminals == ["error"]
    assert events[-1] == ("error", {"error": "AGENT_UNAVAILABLE"})


@respx.mock
def test_auth_expired_narrated_then_terminal_error(app):
    respx.post(config.upstream_holdings_url()).mock(
        return_value=httpx.Response(401)
    )
    fake = FakeAnthropic([
        _tool_msg(_tool_use("get_holdings")),
        _text_msg("Your FinX session has expired — please sign in again."),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        resp = _post_chat(client, "my holdings")
        events = _parse_events(resp)

    # tool errored, model narrated (second call happened), then the pinned
    # AUTH_EXPIRED error is the single terminal event — no done after it
    assert len(fake.calls) == 2
    finished = [d for e, d in events if e == "tool" and d["status"] == "finished"]
    assert finished[0]["is_error"] is True
    assert ("text", {"delta": "Your FinX session has expired — please sign in again."}) in events
    assert events[-1] == ("error", {"error": "AUTH_EXPIRED"})
    assert "done" not in [e for e, _ in events]


# --- credential isolation end-to-end ------------------------------------------


@respx.mock
def test_model_supplied_credentials_are_ignored_end_to_end(app):
    """A tool_use input smuggling ClientId/SessionId is dropped by the request
    model; the upstream call carries only header-derived credentials."""
    route = respx.post(config.upstream_pnl_url()).mock(
        return_value=httpx.Response(
            200,
            json={"Status": "Success", "Response": "user@example.com",
                  "Reason": ""},
        )
    )
    fake = FakeAnthropic([
        _tool_msg(_tool_use("get_pnl_report", {
            "segment": "Equity",
            "fromDate": "2026-04-01",
            "toDate": "2026-07-01",
            "delivery": "email",
            "ClientId": "EVIL01",
            "SessionId": "stolen-session",
        })),
        _text_msg("Sent to your registered email."),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        resp = _post_chat(client, "email me my equity pnl for April-June")
        events = _parse_events(resp)

    sent = json.loads(route.calls.last.request.content)
    assert sent["ClientId"] == CLIENT_CODE
    assert sent["UserId"] == CLIENT_CODE
    assert sent["SessionId"] == SESSION_ID
    assert "EVIL01" not in json.dumps(sent)
    assert "stolen-session" not in json.dumps(sent)
    assert events[-1][0] == "done"


# --- form handover (CHO-214) --------------------------------------------------


def test_open_report_form_emits_flow_artifact_and_resolves(app):
    """A partial P&L request opens the form: the flow artifact carries the
    validated seed, and the successful tool call is a resolution event (the
    task window resets the moment the form appears)."""
    fake = FakeAnthropic([
        _tool_msg(_tool_use(
            "open_report_form", {"flow": "pnl", "segment": "Equity"}
        )),
        _text_msg("Opening your P&L setup — Equity's filled in."),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        resp = _post_chat(client, "P&L for equity")
        events = _parse_events(resp)

    artifacts = [d for e, d in events if e == "artifact"]
    assert artifacts == [
        {"kind": "flow", "flowKey": "pnl", "seed": {"segment": "Equity"}}
    ]
    # Resolution: the successful form-open resets the task window. lastSeq on
    # the CHO-215 short-circuit path too: user(1) + tool_use(2) + result(3).
    assert events[-1] == (
        "done", {"thread": {"taskTurns": 0, "sessionTurns": 1, "lastSeq": 3}},
    )


def test_open_report_form_drops_invalid_seed_values(app):
    """A hallucinated segment degrades to an unseeded field in the artifact —
    never an error, never a mis-filled form."""
    fake = FakeAnthropic([
        _tool_msg(_tool_use(
            "open_report_form", {"flow": "pnl", "segment": "Crypto"}
        )),
        _text_msg("Here you go — pick the details."),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        resp = _post_chat(client, "crypto P&L")
        events = _parse_events(resp)

    artifacts = [d for e, d in events if e == "artifact"]
    assert artifacts == [{"kind": "flow", "flowKey": "pnl", "seed": {}}]


def test_session_backstop_alone_injects_soft_reminder(app, monkeypatch):
    """CHO-214 · D6: a long session with no current-task struggle gets the
    conditional instruction — a fresh, clean query must not be told the
    conversation has been 'going back and forth'."""
    monkeypatch.setenv("SESSION_TURN_CAP", "20")  # default is 100 (CHO-215)
    fake = FakeAnthropic([_text_msg("Here's your answer.")])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        thread = _get_thread(app)
        for index in range(19):
            _append(app, thread, role="user", kind="user_text",
                    text=f"question {index}")
            _append(app, thread, role="user", kind="tool_result",
                    content=[{"type": "tool_result", "tool_use_id": f"t{index}",
                              "content": "{}", "is_error": False}],
                    meta={"tool_name": "search_knowledge_base",
                          "is_error": False, "duration_ms": 1})
            _append(app, thread, role="assistant", kind="assistant_text",
                    text=f"answer {index}")
        resp = _post_chat(client, "what are the DP charges?")
        _parse_events(resp)

        reminders = _reminder_texts(fake.calls[0])
        assert len(reminders) == 1
        assert "seems stuck" in reminders[0]          # conditional offer
        assert "Conversation limit" not in reminders[0]  # not the mandatory one


def test_clarify_trip_still_injects_mandatory_reminder(app):
    """Clarify-cap trips keep the unconditional escalation instruction even
    when the session backstop has also tripped."""
    fake = FakeAnthropic([_text_msg("Let me get you a human.")])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        thread = _get_thread(app)
        _append(app, thread, role="user", kind="user_text", text="a report")
        _append(app, thread, role="assistant", kind="assistant_text",
                text="Which report do you want?")
        _append(app, thread, role="user", kind="user_text", text="the usual")
        _append(app, thread, role="assistant", kind="assistant_text",
                text="Could you name the report — P&L, ledger, or gains?")
        resp = _post_chat(client, "come on")
        _parse_events(resp)

        reminders = _reminder_texts(fake.calls[0])
        assert len(reminders) == 1
        assert "Conversation limit reached" in reminders[0]
        assert "clarifying question" in reminders[0]


# --- artifact-only rounds end the turn (CHO-215) ------------------------------


def test_data_artifact_round_short_circuits(app, monkeypatch):
    """The card is the answer: one model call, no narration after the card."""
    envelope = {"kind": "ok", "clusters": [{"rate": "0.01%"}]}
    monkeypatch.setattr("app.agent.tools.dispatch_outcome", _ok_outcome(envelope))
    fake = FakeAnthropic([_tool_msg(_tool_use("get_brokerage_rates"))])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        events = _parse_events(_post_chat(client, "what is my brokerage?"))

    assert len(fake.calls) == 1
    assert [e for e, _ in events] == ["tool", "tool", "artifact", "done"]
    assert not [e for e, _ in events if e == "text"]


def test_parallel_two_artifact_round_short_circuits(app, monkeypatch):
    envelope = {"kind": "ok", "rows": []}
    monkeypatch.setattr("app.agent.tools.dispatch_outcome", _ok_outcome(envelope))
    fake = FakeAnthropic([
        _tool_msg(
            _tool_use("get_holdings", block_id="tu_a"),
            _tool_use("get_brokerage_rates", block_id="tu_b"),
        ),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        events = _parse_events(_post_chat(client, "holdings and brokerage"))

    assert len(fake.calls) == 1
    artifacts = [d for e, d in events if e == "artifact"]
    assert len(artifacts) == 2
    assert events[-1][0] == "done"


def test_mixed_artifact_and_kb_round_still_narrates(app, monkeypatch):
    """A round with a narration-needing success (KB) continues to the model."""
    envelope = {"kind": "ok", "results": [{"answer": "AMC is yearly."}]}
    monkeypatch.setattr("app.agent.tools.dispatch_outcome", _ok_outcome(envelope))
    fake = FakeAnthropic([
        _tool_msg(
            _tool_use("get_holdings", block_id="tu_a"),
            _tool_use("search_knowledge_base", block_id="tu_b"),
        ),
        _text_msg("Here's what AMC means for your account."),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        events = _parse_events(_post_chat(client, "holdings and what is AMC?"))

    assert len(fake.calls) == 2  # continuation still happens
    assert [d for e, d in events if e == "artifact"]  # holdings card emitted
    assert "".join(d["delta"] for e, d in events if e == "text")
    assert events[-1][0] == "done"


def test_short_circuited_turn_continues_cleanly(app):
    """After a silent form-open, the next message replays a valid array:
    the trailing tool_result merges ahead of the new user text."""
    fake = FakeAnthropic([
        _tool_msg(_tool_use("open_report_form", {"flow": "pnl"})),
        _text_msg("Answering the follow-up."),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        _parse_events(_post_chat(client, "get my P&L"))
        events = _parse_events(_post_chat(client, "thanks, what are DP charges?"))

    assert events[-1][0] == "done"
    # The second call's last user message: tool_result first, then the text.
    last_user = fake.calls[1]["messages"][-1]
    assert last_user["role"] == "user"
    types = [block["type"] for block in last_user["content"]]
    assert types == ["tool_result", "text"]


# --- freshdesk escalation rounds (CHO-218) ------------------------------------

# Fake Freshdesk endpoint + key — respx intercepts; NOT a real credential.
FD_ROOT = "https://fd-test.invalid/api/v2"


def _fd_env(monkeypatch):
    monkeypatch.setenv("FRESHDESK_API_ROOT", FD_ROOT)
    monkeypatch.setenv("FRESHDESK_API_KEY", "fd-test-key")


@respx.mock
def test_raise_ticket_round_emits_artifact_and_memo(app, monkeypatch):
    """Successful escalation: ticket artifact, artifact-only short-circuit
    (single model call), flow-event memo after the tool_result, and the
    successful raise is a resolution event (task window resets)."""
    _fd_env(monkeypatch)
    route = respx.post(f"{FD_ROOT}/tickets").mock(
        return_value=httpx.Response(201, json={"id": 7551234})
    )
    fake = FakeAnthropic([
        _tool_msg(_tool_use("raise_support_ticket", {"reason": "need a human"})),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        events = _parse_events(_post_chat(client, "connect me to a person"))

        assert len(fake.calls) == 1  # the card is the answer — no narration
        assert [e for e, _ in events] == ["tool", "tool", "artifact", "done"]
        assert dict(events)["artifact"] == {
            "kind": "ticket", "ticketId": 7551234, "status": "Open",
        }

        # the transcript carried the conversation (this message included)
        sent = json.loads(route.calls.last.request.content)
        assert "connect me to a person" in sent["description"]

        # memo lands AFTER the tool_result; resolution resets the task window
        thread = _get_thread(app)
        assert [t.kind for t in thread.turns] == [
            "user_text", "assistant_tool_use", "tool_result", "flow_event",
        ]
        memo = thread.turns[-1]
        assert memo.content[0]["text"].endswith(
            "Support ticket #7551234 raised — need a human."
        )
        assert memo.meta == {
            "flow": "ticket", "reason": "need a human", "ticketId": 7551234,
        }
        assert dict(events)["done"] == {
            "thread": {"taskTurns": 0, "sessionTurns": 1, "lastSeq": 4},
        }


@respx.mock
def test_raise_ticket_failure_bounces_and_model_narrates(app, monkeypatch):
    """Freshdesk down: is_error tool_result, the model narrates alternatives
    (continuation call happens), no artifact, no memo, never a stub id."""
    _fd_env(monkeypatch)
    respx.post(f"{FD_ROOT}/tickets").mock(return_value=httpx.Response(500))
    fake = FakeAnthropic([
        _tool_msg(_tool_use("raise_support_ticket", {"reason": "app crash"})),
        _text_msg("I couldn't reach support just now — please try the Help "
                  "section in the FinX app."),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        events = _parse_events(_post_chat(client, "raise a ticket"))

        assert len(fake.calls) == 2  # errored round continues to the model
        finished = [
            d for e, d in events if e == "tool" and d["status"] == "finished"
        ]
        assert finished == [{
            "name": "raise_support_ticket", "status": "finished",
            "is_error": True,
        }]
        assert not [e for e, _ in events if e == "artifact"]
        assert events[-1][0] == "done"

        # the bounced tool_result is actionable; no flow_event memo appended
        bounce = fake.calls[1]["messages"][-1]["content"][0]
        assert bounce["is_error"] is True
        assert "support system" in bounce["content"]
        thread = _get_thread(app)
        assert "flow_event" not in [t.kind for t in thread.turns]


# --- conversation reset (CHO-216) ---------------------------------------------


def test_chat_reset_requires_credentials(app):
    with TestClient(app) as client:
        resp = client.post("/api/chat/reset")
        assert resp.status_code == 400
        assert resp.json() == {"error": "MISSING_CREDENTIALS"}


def test_chat_reset_gives_blank_slate(app):
    """Reset → the next message starts a brand-new thread: the model sees no
    prior conversation and counters restart from zero."""
    fake = FakeAnthropic([
        _text_msg("Noted — F&O it is."),
        _text_msg("Hello! How can I help?"),
    ])
    with TestClient(app) as client:
        app.state.anthropic_client = fake
        _parse_events(_post_chat(client, "remember: I only care about F&O"))

        resp = client.post("/api/chat/reset", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        events = _parse_events(_post_chat(client, "hello"))

    # Second model call sees ONLY the primed exchange + the new message.
    messages = fake.calls[1]["messages"]
    assert len(messages) == 3
    assert messages[2] == {
        "role": "user", "content": [{"type": "text", "text": "hello"}],
    }
    assert "only care about" not in json.dumps(messages)  # old turn is gone
    # Counters (and the feedback anchor) restarted with the fresh thread.
    assert events[-1] == (
        "done", {"thread": {"taskTurns": 1, "sessionTurns": 1, "lastSeq": 2}},
    )


# --- answer feedback endpoint (CHO-217) ----------------------------------------


def _feedback_jobs(app):
    """Drain the store queue (writer never runs in the memory-only fixture)
    and return the feedback jobs it held."""
    store = app.state.conversation_store
    jobs = []
    while True:
        try:
            jobs.append(store._queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    return [job for job in jobs if job[0] == "feedback"]


def test_feedback_requires_credentials(app):
    with TestClient(app) as client:
        resp = client.post("/api/feedback", json={"rating": "up"})
    assert resp.status_code == 400
    assert resp.json() == {"error": "MISSING_CREDENTIALS"}


def test_feedback_invalid_body_is_400(app):
    with TestClient(app) as client:
        for body in (
            {"rating": "sideways"},                 # not up|down
            {"rating": "up", "anchorSeq": 0},       # anchor below 1
            {"rating": "up", "anchorSeq": "three"}, # non-int anchor
            {},                                     # rating missing
        ):
            resp = client.post("/api/feedback", headers=HEADERS, json=body)
            assert resp.status_code == 400
            assert resp.json() == {"error": "INVALID_FEEDBACK"}
        assert _feedback_jobs(app) == []  # nothing stored


def test_feedback_happy_path_stores_given_anchor(app):
    """Agent path: the shell's anchorSeq (from done.lastSeq) is stored as-is;
    the write is a ("feedback", row) job on the store's writer queue."""
    with TestClient(app) as client:
        thread = _get_thread(app)
        _append(app, thread, role="user", kind="user_text", text="hi")
        _append(app, thread, role="assistant", kind="assistant_text", text="hello")
        store = app.state.conversation_store
        store._pool = object()  # writer not running → jobs stay inspectable
        resp = client.post(
            "/api/feedback",
            headers=HEADERS,
            json={"rating": "up", "anchorSeq": 2, "source": "agent"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert _feedback_jobs(app) == [
            ("feedback", {"thread_id": thread.id, "anchor_seq": 2,
                          "rating": "up", "source": "agent"})
        ]


def test_feedback_anchors_to_latest_turn_when_seq_omitted(app):
    """Sticker path: no anchorSeq → the thread's latest turn (post-CHO-214,
    the flow-event memo of exactly the rated completion) anchors the row."""
    with TestClient(app) as client:
        thread = _get_thread(app)
        _append(app, thread, role="user", kind="user_text", text="my pnl")
        _append(app, thread, role="assistant", kind="assistant_text",
                text="Here's the form.")
        _append(app, thread, role="user", kind="flow_event",
                content=[{"type": "text", "text": "[App event] P&L done"}],
                meta={"flow": "pnl"})
        store = app.state.conversation_store
        store._pool = object()
        resp = client.post(
            "/api/feedback", headers=HEADERS,
            json={"rating": "down", "source": "flow"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert _feedback_jobs(app) == [
            ("feedback", {"thread_id": thread.id, "anchor_seq": 3,
                          "rating": "down", "source": "flow"})
        ]


def test_feedback_on_empty_thread_is_ok_and_stores_nothing(app):
    with TestClient(app) as client:
        _get_thread(app)  # fresh thread, zero turns — nothing to anchor
        app.state.conversation_store._pool = object()
        resp = client.post("/api/feedback", headers=HEADERS, json={"rating": "up"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert _feedback_jobs(app) == []
