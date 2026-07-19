"""Endpoint tests for POST /api/data/brokerage. Upstream (middleware-go slab)
is mocked with respx — no live network. Covers: the raw-SSO-JWT credential,
title/desc whitelist passthrough, the field-based Status gate (Reason never
inspected), IDOR defense, and the error map."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import config
from app.main import create_app

HEADERS = {
    "Authorization": "test-sso-jwt",
    "X-Session-Id": "test-session-token",
    "X-User-Id": "X008593",
}

# Live-captured slab shape (per-client). Stray upstream keys added to prove
# the whitelist strips them.
SLAB_RESPONSE = {
    "StatusCode": 200,
    "Status": "Success",
    "Response": [
        {
            "title": "Equity",
            "internal_code": "EQ-77",  # must be stripped
            "list": [
                {"title": "Intraday", "desc": "₹0.10 for trade value of 10 thousand"},
                {"title": "Delivery", "desc": "₹1.00 for trade value of 10 thousand", "slab_id": 42},
            ],
        },
        {
            "title": "Derivative",
            "list": [
                {"title": "Stock Future", "desc": "₹20.00 for trade value of 10 thousand"},
                {"title": "Stock Option", "desc": "₹20.00 per order"},
            ],
        },
    ],
    "Reason": "",
}


@pytest.fixture()
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def _mock_slab(response: httpx.Response) -> respx.Route:
    return respx.post(config.upstream_brokerage_url()).mock(return_value=response)


# --- credential + upstream call --------------------------------------------

@respx.mock
def test_sends_raw_sso_jwt_as_authorization(client):
    route = _mock_slab(httpx.Response(200, json=SLAB_RESPONSE))

    client.post("/api/data/brokerage", headers=HEADERS)

    sent = route.calls.last.request
    # The slab is the one data endpoint on the SSO JWT — never the SessionId.
    assert sent.headers["authorization"] == "test-sso-jwt"
    assert "test-session-token" not in sent.headers["authorization"]
    assert sent.headers["from"] == config.finx_from_header()


@respx.mock
def test_client_id_comes_from_session_header_only(client):
    route = _mock_slab(httpx.Response(200, json=SLAB_RESPONSE))

    client.post(
        "/api/data/brokerage", headers=HEADERS, json={"ClientID": "X999999"}
    )

    body = httpx.Response(200, content=route.calls.last.request.content).json()
    assert body == {"ClientID": "X008593"}  # from X-User-Id, not the body


# --- passthrough ------------------------------------------------------------

@respx.mock
def test_groups_pass_through_title_and_desc_only(client):
    _mock_slab(httpx.Response(200, json=SLAB_RESPONSE))

    resp = client.post("/api/data/brokerage", headers=HEADERS)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["kind"] == "ok"
    assert payload["groups"] == [
        {
            "title": "Equity",
            "list": [
                {"title": "Intraday", "desc": "₹0.10 for trade value of 10 thousand"},
                {"title": "Delivery", "desc": "₹1.00 for trade value of 10 thousand"},
            ],
        },
        {
            "title": "Derivative",
            "list": [
                {"title": "Stock Future", "desc": "₹20.00 for trade value of 10 thousand"},
                {"title": "Stock Option", "desc": "₹20.00 per order"},
            ],
        },
    ]
    # Stray upstream keys are stripped by the whitelist.
    assert "internal_code" not in resp.text
    assert "slab_id" not in resp.text


@respx.mock
def test_empty_slab_is_empty_kind(client):
    _mock_slab(
        httpx.Response(
            200, json={"StatusCode": 200, "Status": "Success", "Response": [], "Reason": ""}
        )
    )

    resp = client.post("/api/data/brokerage", headers=HEADERS)

    assert resp.status_code == 200
    assert resp.json() == {"kind": "empty"}


# --- Status gate + error map ------------------------------------------------

@respx.mock
def test_status_gate_is_field_based_never_reason(client):
    # A "success-looking" Reason with a failure Status must still be NO_DATA:
    # proves the branch is on the status field, never on Reason wording.
    _mock_slab(
        httpx.Response(
            200,
            json={"StatusCode": 500, "Status": "Fail", "Response": None, "Reason": "Success!"},
        )
    )

    resp = client.post("/api/data/brokerage", headers=HEADERS)

    assert resp.status_code == 404
    assert resp.json() == {"error": "NO_DATA"}


@respx.mock
def test_upstream_401_maps_to_auth_expired(client):
    _mock_slab(httpx.Response(401, json={"Status": "Fail", "Reason": "expired"}))

    resp = client.post("/api/data/brokerage", headers=HEADERS)

    assert resp.status_code == 401
    assert resp.json() == {"error": "AUTH_EXPIRED"}


@respx.mock
def test_upstream_500_maps_to_upstream_error(client):
    _mock_slab(httpx.Response(500))

    resp = client.post("/api/data/brokerage", headers=HEADERS)

    assert resp.status_code == 502
    assert resp.json() == {"error": "UPSTREAM_ERROR"}


@pytest.mark.parametrize("missing", ["Authorization", "X-Session-Id", "X-User-Id"])
def test_missing_header_is_missing_credentials(client, missing):
    headers = {k: v for k, v in HEADERS.items() if k != missing}
    resp = client.post("/api/data/brokerage", headers=headers)
    assert resp.status_code == 400
    assert resp.json() == {"error": "MISSING_CREDENTIALS"}
