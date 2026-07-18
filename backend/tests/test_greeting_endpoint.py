"""Endpoint tests for GET /api/greeting.

Upstream calls are intercepted with respx — no live network traffic.
"""

import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import config
from app.main import create_app

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
    assert resp.json() == {"firstName": "Pritam"}

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
    assert resp.json() == {"firstName": None}


@respx.mock
def test_missing_first_holder_name_degrades_to_null(client):
    body = {"Status": "Success", "Response": {}, "Reason": ""}
    _mock_upstream(httpx.Response(200, json=body))

    resp = client.get("/api/greeting", headers=HEADERS)

    assert resp.status_code == 200
    assert resp.json() == {"firstName": None}


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
