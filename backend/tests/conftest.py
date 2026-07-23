"""Shared test fixtures.

CHO-244: force DeepEval tracing OFF for every test. The dev `.env` carries a
real `CONFIDENT_API_KEY`, and `create_app()` initialises tracing at import — so
without this guard the suite would export test traces to the live Confident AI
account and make real network calls. Patching `config.tracing_enabled` beats
clearing the env var, since `config._secret` also falls back to the repo-root
`.env`.
"""

import pytest

from app.agent import tracing


@pytest.fixture(autouse=True)
def _tracing_off(monkeypatch):
    monkeypatch.setattr("app.config.tracing_enabled", lambda: False)
    tracing._ENABLED = False
    yield
    tracing._ENABLED = False
