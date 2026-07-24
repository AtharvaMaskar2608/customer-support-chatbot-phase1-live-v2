"""Agent config getters (CHO-213 · task 4.3): model/thinking selection, the
per-model thinking mapping (design D10), caps, and the inner-round guard.
All values are read from the environment at call time.
"""

import pytest

from app import config

# --- model + thinking selection ----------------------------------------------


def test_agent_model_default(monkeypatch):
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    assert config.agent_model() == "claude-sonnet-4-6"


def test_agent_model_env_override(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL", "claude-haiku-4-5")
    assert config.agent_model() == "claude-haiku-4-5"


def test_agent_model_unknown_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL", "claude-opus-4-8")  # not in the allowlist
    assert config.agent_model() == "claude-sonnet-4-6"


def test_agent_thinking_default_and_override(monkeypatch):
    monkeypatch.delenv("AGENT_THINKING", raising=False)
    assert config.agent_thinking() == "off"
    monkeypatch.setenv("AGENT_THINKING", "minimal")
    assert config.agent_thinking() == "minimal"
    monkeypatch.setenv("AGENT_THINKING", "maximal")  # unknown -> off
    assert config.agent_thinking() == "off"


# --- the D10 mapping table: all four model × thinking combos ------------------


@pytest.mark.parametrize(
    "model,mode,expected",
    [
        ("claude-haiku-4-5", "off", {}),
        (
            "claude-haiku-4-5",
            "minimal",
            {"thinking": {"type": "enabled", "budget_tokens": 1024}},
        ),
        ("claude-sonnet-4-6", "off", {}),
        (
            "claude-sonnet-4-6",
            "minimal",
            {
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": "low"},
            },
        ),
    ],
)
def test_thinking_params_mapping(model, mode, expected):
    assert config.agent_thinking_params(model, mode) == expected


def test_sonnet_minimal_never_sends_budget_tokens():
    params = config.agent_thinking_params("claude-sonnet-4-6", "minimal")
    assert "budget_tokens" not in params["thinking"]


def test_haiku_minimal_budget_below_max_tokens(monkeypatch):
    """The API requires budget_tokens < max_tokens; the defaults respect it."""
    monkeypatch.delenv("AGENT_MAX_TOKENS", raising=False)
    params = config.agent_thinking_params("claude-haiku-4-5", "minimal")
    assert params["thinking"]["budget_tokens"] == 1024
    assert config.agent_max_tokens() == 4096
    assert params["thinking"]["budget_tokens"] < config.agent_max_tokens()


# --- caps + inner guard -------------------------------------------------------


def test_cap_defaults(monkeypatch):
    for key in (
        "CLARIFY_CAP",
        "TASK_TURN_CAP",
        "SESSION_TURN_CAP",
        "AGENT_MAX_TOOL_ROUNDS",
    ):
        monkeypatch.delenv(key, raising=False)
    assert config.clarify_cap() == 2
    assert config.task_turn_cap() == 100
    assert config.session_turn_cap() == 100
    assert config.agent_max_tool_rounds() == 5


def test_caps_env_overridable(monkeypatch):
    monkeypatch.setenv("CLARIFY_CAP", "3")
    monkeypatch.setenv("TASK_TURN_CAP", "7")
    monkeypatch.setenv("SESSION_TURN_CAP", "30")
    monkeypatch.setenv("AGENT_MAX_TOOL_ROUNDS", "2")
    assert config.clarify_cap() == 3
    assert config.task_turn_cap() == 7
    assert config.session_turn_cap() == 30
    assert config.agent_max_tool_rounds() == 2


# --- api key ------------------------------------------------------------------


def test_anthropic_api_key_reads_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert config.anthropic_api_key() == "sk-ant-test"
