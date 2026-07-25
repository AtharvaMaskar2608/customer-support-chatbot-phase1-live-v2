"""Prompt playground API (CHO-272): token gate + defaults isolation from
production /api/chat. No model calls — these tests stay offline.
"""

import json
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.agent.prompt import PRIMED_INSTRUCTIONS, SYSTEM_PROMPT
from app.main import create_app

TOKEN = "s3cr3t-playground-token"


@pytest.fixture()
def app_no_db(monkeypatch):
    monkeypatch.setattr("app.config.database_url", lambda: None)
    return create_app()


@contextmanager
def _client(app, monkeypatch, *, token: str | None):
    monkeypatch.setattr("app.config.playground_token", lambda: token)
    with TestClient(app) as client:
        yield client


def test_playground_disabled_when_token_unset(app_no_db, monkeypatch):
    with _client(app_no_db, monkeypatch, token=None) as client:
        assert client.get("/api/playground/defaults").status_code == 404
        assert (
            client.post(
                "/api/playground/chat",
                json={"message": "hi"},
                headers={
                    "Authorization": "jwt",
                    "X-Session-Id": "s",
                    "X-User-Id": "X1",
                },
            ).status_code
            == 404
        )


def test_playground_rejects_bad_token(app_no_db, monkeypatch):
    with _client(app_no_db, monkeypatch, token=TOKEN) as client:
        res = client.get(
            "/api/playground/defaults",
            headers={"X-Playground-Token": "nope"},
        )
        assert res.status_code == 401


def test_playground_defaults_match_production_constants(app_no_db, monkeypatch):
    with _client(app_no_db, monkeypatch, token=TOKEN) as client:
        res = client.get(
            "/api/playground/defaults",
            headers={"X-Playground-Token": TOKEN},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["systemPrompt"] == SYSTEM_PROMPT
        assert body["primedInstructions"] == PRIMED_INSTRUCTIONS


def test_production_chat_ignores_prompt_override_fields(app_no_db):
    """/api/chat must not accept playground prompt fields (extra=ignore)."""
    with TestClient(app_no_db) as client:
        res = client.post(
            "/api/chat",
            json={
                "message": "hi",
                "systemPrompt": "OVERRIDE SHOULD BE IGNORED",
                "primedInstructions": "ALSO IGNORED",
            },
        )
        assert res.status_code == 400
        assert res.json() == {"error": "MISSING_CREDENTIALS"}


def test_prompt_override_helpers_drop_cache_control():
    from app.agent import prompt as agent_prompt

    prod_sys = agent_prompt.system_blocks()
    assert "cache_control" in prod_sys[0]
    draft_sys = agent_prompt.system_blocks(override="experimental system")
    assert draft_sys[0]["text"] == "experimental system"
    assert "cache_control" not in draft_sys[0]

    # CHO-264: the primed turn is now a SINGLE block (the live tail moved to
    # the trailing message), so the override replaces the whole turn's content.
    prod_primed = agent_prompt.primed_messages()
    assert len(prod_primed[0]["content"]) == 1
    assert "cache_control" in prod_primed[0]["content"][0]
    draft = agent_prompt.primed_messages(instructions_override="draft primed")
    assert len(draft[0]["content"]) == 1
    assert draft[0]["content"][0]["text"] == "draft primed"
    assert "cache_control" not in draft[0]["content"][0]


def test_playground_overrides_drop_history_breakpoint(app_no_db, monkeypatch):
    """CHO-264: drafts stay uncached — an override request places no rolling
    history breakpoint either, so nothing of an operator's in-flight draft
    prefix is written to the cache."""
    calls: list[dict] = []

    class _FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        @property
        def text_stream(self):
            async def gen():
                yield "ok"

            return gen()

        async def get_final_message(self):
            class _Msg:
                content = [{"type": "text", "text": "ok"}]
                stop_reason = "end_turn"
                model = "claude-sonnet-4-6"
                usage = {"input_tokens": 1, "output_tokens": 1}

            return _Msg()

    class _FakeMessages:
        def stream(self, **kwargs):
            calls.append(kwargs)
            return _FakeStream()

    class _FakeAnthropic:
        messages = _FakeMessages()

    app_no_db.state.anthropic_client = _FakeAnthropic()

    with _client(app_no_db, monkeypatch, token=TOKEN) as client:
        res = client.post(
            "/api/playground/chat",
            json={"message": "hi", "systemPrompt": "draft system"},
            headers={
                "Authorization": "jwt-token",
                "X-Session-Id": "finx-live-session",
                "X-User-Id": "X008593",
                "X-Playground-Token": TOKEN,
            },
        )
        assert res.status_code == 200
        res.read()

    assert calls, "the playground stream never reached the model"
    messages = calls[0]["messages"]
    # messages[0:2] is the primed exchange (its own breakpoint is governed by
    # primedInstructions, untouched here); everything from the replayed history
    # onward must be unmarked.
    assert "cache_control" not in json.dumps(messages[2:])


def test_playground_chat_keeps_finx_session_id_on_tool_ctx(app_no_db, monkeypatch):
    """Thread isolation uses pg:…; ToolCtx.session_id must stay the live FinX id."""
    captured: dict = {}

    async def fake_stream(**kwargs):
        captured["ctx"] = kwargs["ctx"]
        captured["thread_session_id"] = kwargs.get("thread_session_id")
        if False:  # pragma: no cover — make this an async generator
            yield ""

    monkeypatch.setattr(
        "app.playground.router.run_chat_stream", fake_stream
    )

    with _client(app_no_db, monkeypatch, token=TOKEN) as client:
        res = client.post(
            "/api/playground/chat",
            json={"message": "show holdings"},
            headers={
                "Authorization": "jwt-token",
                "X-Session-Id": "finx-live-session",
                "X-User-Id": "X008593",
                "X-Playground-Token": TOKEN,
            },
        )
        # StreamingResponse consumes the generator; status is still 200.
        assert res.status_code == 200

    assert captured["ctx"].session_id == "finx-live-session"
    assert captured["thread_session_id"] == "pg:finx-live-session"


def test_playground_reset_uses_namespaced_store_key(app_no_db, monkeypatch):
    reset_keys: list[str] = []

    async def fake_reset(session_id, *, client_code=None):
        reset_keys.append(session_id)

    with _client(app_no_db, monkeypatch, token=TOKEN) as client:
        monkeypatch.setattr(
            client.app.state.conversation_store,
            "reset_thread",
            fake_reset,
        )
        res = client.post(
            "/api/playground/chat/reset",
            headers={
                "Authorization": "jwt-token",
                "X-Session-Id": "finx-live-session",
                "X-User-Id": "X008593",
                "X-Playground-Token": TOKEN,
            },
        )
        assert res.status_code == 200
        assert res.json() == {"ok": True}

    assert reset_keys == ["pg:finx-live-session"]
