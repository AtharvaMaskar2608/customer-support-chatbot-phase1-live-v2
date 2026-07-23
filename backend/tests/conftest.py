"""Shared test fixtures.

CHO-261: force agent tracing OFF for every test. Tracing defaults ON
(AGENT_TRACING), and `create_app()` calls `tracing.configure()` at import — so
without this guard the suite could try to persist traces into a real DB pool.
Patching `config.tracing_enabled` also covers the persistence gate. The tracing
tests re-enable it explicitly with a fake pool.
"""

import pytest

from app.agent import tracing


@pytest.fixture(autouse=True)
def _tracing_off(monkeypatch):
    monkeypatch.setattr("app.config.tracing_enabled", lambda: False)
    tracing._ENABLED = False
    yield
    tracing._ENABLED = False
