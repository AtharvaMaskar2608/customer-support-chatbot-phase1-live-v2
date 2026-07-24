"""Prompt playground API (CHO-272): token gate + defaults isolation from
production /api/chat. No model calls — these tests stay offline.
"""

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

    prod_primed = agent_prompt.primed_messages()
    assert "cache_control" in prod_primed[0]["content"][0]
    draft = agent_prompt.primed_messages(instructions_override="draft primed")
    assert draft[0]["content"][0]["text"] == "draft primed"
    assert "cache_control" not in draft[0]["content"][0]
