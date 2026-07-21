"""Endpoint tests for GET /api/greeting.

Upstream calls are intercepted with respx — no live network traffic. The
clock is pinned (CHO-226) so the greeting key is deterministic: without the
pin these assertions would flip with the wall clock.
"""

import datetime
import json
import logging

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import clock, config, greeting
from app.main import create_app

# 2026-07-20 is a Monday and an ordinary trading day; 09:30 UTC = 15:00 IST,
# inside the 09:15–15:30 MARKET window.
MARKET_HOURS_UTC = datetime.datetime(
    2026, 7, 20, 9, 30, tzinfo=datetime.timezone.utc
)

HEADERS = {
    "Authorization": "test-raw-jwt",
    "X-Session-Id": "test-session-token",
    "X-User-Id": "X008593",
}

SUCCESS_BODY = {
    "Status": "Success",
    "Response": {
        "InvCode": "X008593",
        "FirstHolderName": "PRITAM NITIN WAVHAL",
        "SomeOtherPiiField": "must never be forwarded",
    },
    "Reason": "",
}


@pytest.fixture(autouse=True)
def _pinned_clock(monkeypatch):
    """Freeze the market clock inside MARKET hours on a trading Monday."""
    monkeypatch.setattr(clock, "_utc_now", lambda: MARKET_HOURS_UTC)
    clock.reset_calendar_cache()
    yield
    clock.reset_calendar_cache()


@pytest.fixture()
def client():
    # Context manager runs the lifespan (creates the shared httpx client).
    with TestClient(create_app()) as test_client:
        yield test_client


def _mock_upstream(response: httpx.Response) -> respx.Route:
    return respx.post(config.upstream_profile_url()).mock(return_value=response)


@respx.mock
def test_success_returns_derived_first_name_only(client):
    route = _mock_upstream(httpx.Response(200, json=SUCCESS_BODY))

    resp = client.get("/api/greeting", headers=HEADERS)

    assert resp.status_code == 200
    assert resp.json() == {
        "firstName": "Pritam",
        "greetingKey": "MARKET",
        "template": "Hi {clientRef} — markets are live. Need a report or a quick answer?",
    }

    # Verify the upstream contract: raw JWT, session in `from`, InvCode body.
    upstream_request = route.calls.last.request
    assert upstream_request.headers["authorization"] == "test-raw-jwt"
    assert upstream_request.headers["from"] == "test-session-token"
    assert json.loads(upstream_request.content) == {"InvCode": "X008593"}


@respx.mock
def test_empty_first_holder_name_degrades_to_null(client):
    body = {"Status": "Success", "Response": {"FirstHolderName": ""}, "Reason": ""}
    _mock_upstream(httpx.Response(200, json=body))

    resp = client.get("/api/greeting", headers=HEADERS)

    assert resp.status_code == 200
    # No first name -> the placeholder-free fallback template.
    assert resp.json() == {
        "firstName": None,
        "greetingKey": "MARKET",
        "template": "Markets are live. Need a report or a quick answer?",
    }


@respx.mock
def test_missing_first_holder_name_degrades_to_null(client):
    body = {"Status": "Success", "Response": {}, "Reason": ""}
    _mock_upstream(httpx.Response(200, json=body))

    resp = client.get("/api/greeting", headers=HEADERS)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["firstName"] is None
    assert "{clientRef}" not in payload["template"]


@respx.mock
def test_missing_calendar_still_returns_200_with_default(client, monkeypatch, tmp_path):
    """Task 6.6: greeting selection must never 5xx the endpoint. A calendar
    that cannot be read degrades to DEFAULT, not to a 500."""
    monkeypatch.setattr(clock, "CALENDAR_PATH", tmp_path / "absent.json")
    clock.reset_calendar_cache()
    _mock_upstream(httpx.Response(200, json=SUCCESS_BODY))

    resp = client.get("/api/greeting", headers=HEADERS)

    assert resp.status_code == 200
    # 15:00 IST is inside the MARKET window, but with no calendar we cannot
    # know it is not a holiday — DEFAULT asserts nothing about the market.
    assert resp.json() == {
        "firstName": "Pritam",
        "greetingKey": "DEFAULT",
        "template": "Hey {clientRef} — what do you need?",
    }


@respx.mock
def test_corrupt_greeting_content_still_returns_200_with_default(
    client, monkeypatch, tmp_path
):
    corrupt = tmp_path / "greetings.json"
    corrupt.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(greeting, "GREETINGS_PATH", corrupt)
    _mock_upstream(httpx.Response(200, json=SUCCESS_BODY))

    resp = client.get("/api/greeting", headers=HEADERS)

    assert resp.status_code == 200
    assert resp.json() == {
        "firstName": "Pritam",
        "greetingKey": "DEFAULT",
        "template": "Hey {clientRef} — what do you need?",
    }


@respx.mock
def test_greeting_log_carries_the_key_but_never_the_name(client, caplog):
    _mock_upstream(httpx.Response(200, json=SUCCESS_BODY))

    with caplog.at_level(logging.INFO, logger="app.greeting"):
        resp = client.get("/api/greeting", headers=HEADERS)

    assert resp.status_code == 200
    assert "greeting_key=MARKET" in caplog.text
    assert "ts=2026-07-20T15:00:00" in caplog.text
    for pii in ("Pritam", "PRITAM", "X008593", "test-raw-jwt"):
        assert pii not in caplog.text


@respx.mock
def test_upstream_401_maps_to_auth_expired(client):
    _mock_upstream(httpx.Response(401))

    resp = client.get("/api/greeting", headers=HEADERS)

    assert resp.status_code == 401
    assert resp.json() == {"error": "AUTH_EXPIRED"}


@respx.mock
def test_upstream_500_maps_to_upstream_error(client):
    _mock_upstream(httpx.Response(500))

    resp = client.get("/api/greeting", headers=HEADERS)

    assert resp.status_code == 502
    assert resp.json() == {"error": "UPSTREAM_ERROR"}


@respx.mock
def test_upstream_non_success_status_field_maps_to_upstream_error(client):
    body = {"Status": "Failure", "Response": None, "Reason": "boom"}
    _mock_upstream(httpx.Response(200, json=body))

    resp = client.get("/api/greeting", headers=HEADERS)

    assert resp.status_code == 502
    assert resp.json() == {"error": "UPSTREAM_ERROR"}


@respx.mock
def test_upstream_bad_json_maps_to_upstream_error(client):
    _mock_upstream(httpx.Response(200, content=b"<html>not json</html>"))

    resp = client.get("/api/greeting", headers=HEADERS)

    assert resp.status_code == 502
    assert resp.json() == {"error": "UPSTREAM_ERROR"}


@respx.mock
def test_upstream_timeout_maps_to_upstream_error(client):
    respx.post(config.upstream_profile_url()).mock(
        side_effect=httpx.ConnectTimeout("timed out")
    )

    resp = client.get("/api/greeting", headers=HEADERS)

    assert resp.status_code == 502
    assert resp.json() == {"error": "UPSTREAM_ERROR"}


@pytest.mark.parametrize(
    "missing_header", ["Authorization", "X-Session-Id", "X-User-Id"]
)
def test_missing_any_header_maps_to_missing_credentials(client, missing_header):
    headers = {k: v for k, v in HEADERS.items() if k != missing_header}

    resp = client.get("/api/greeting", headers=headers)

    assert resp.status_code == 400
    assert resp.json() == {"error": "MISSING_CREDENTIALS"}


def test_no_headers_at_all_maps_to_missing_credentials(client):
    resp = client.get("/api/greeting")

    assert resp.status_code == 400
    assert resp.json() == {"error": "MISSING_CREDENTIALS"}


def test_health(client):
    resp = client.get("/api/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
