"""Tests for GET /api/whats-new (response shape, no credentials needed)."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

ITEM_FIELDS = ("emoji", "tint", "title", "description")


@pytest.fixture()
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def test_returns_200_without_any_credentials(client):
    # Broadcast content — no Authorization / X-Session-Id / X-User-Id needed.
    resp = client.get("/api/whats-new")

    assert resp.status_code == 200


def test_response_shape(client):
    body = client.get("/api/whats-new").json()

    assert set(body.keys()) == {"version", "items"}
    assert isinstance(body["version"], str)
    assert body["version"].strip() != ""
    assert isinstance(body["items"], list)
    assert len(body["items"]) >= 1


def test_every_item_has_all_four_fields_as_non_empty_strings(client):
    items = client.get("/api/whats-new").json()["items"]

    for item in items:
        assert set(item.keys()) == set(ITEM_FIELDS)
        for field in ITEM_FIELDS:
            assert isinstance(item[field], str), f"{field} must be a string"
            assert item[field].strip() != "", f"{field} must be non-empty"
