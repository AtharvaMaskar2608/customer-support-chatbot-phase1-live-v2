"""Unit tests for the CHO-211 data-endpoint routing entries: each endpoint
must send its live-verified credential scheme. Upstreams are mocked with respx
— no live network, no real tokens."""

import asyncio

import httpx
import respx

from app import config
from app.finx.client import FinxClient
from app.finx.routing import AuthSource, Endpoint, route

SESSION = "sess-abc"
JWT = "sso-jwt-xyz"

DATA_ENDPOINTS = (
    Endpoint.HOLDINGS,
    Endpoint.PAYIN,
    Endpoint.PAYOUT,
    Endpoint.BROKERAGE,
)


def _run_call(endpoint, body):
    """Invoke FinxClient.call synchronously (no async test plugin in use)."""

    async def _go():
        async with httpx.AsyncClient() as http:
            return await FinxClient(http).call(
                endpoint, session_id=SESSION, sso_jwt=JWT, body=body
            )

    return asyncio.run(_go())


# --- routing table ----------------------------------------------------------

def test_holdings_routes_to_session_id_with_session_prefix():
    spec = route(Endpoint.HOLDINGS)
    assert spec.auth_source is AuthSource.SESSION_ID
    assert spec.auth_prefix == "Session "


def test_payin_payout_route_to_bare_session_id():
    for endpoint in (Endpoint.PAYIN, Endpoint.PAYOUT):
        spec = route(endpoint)
        assert spec.auth_source is AuthSource.SESSION_ID
        assert spec.auth_prefix == ""


def test_brokerage_routes_to_sso_jwt():
    spec = route(Endpoint.BROKERAGE)
    assert spec.auth_source is AuthSource.SSO_JWT
    assert spec.auth_prefix == ""


def test_data_endpoints_carry_the_from_build_tag():
    for endpoint in DATA_ENDPOINTS:
        spec = route(endpoint)
        assert spec.extra_headers["from"] == config.finx_from_header()
        # `from` is a build tag, never a credential.
        assert spec.extra_headers["from"] not in (SESSION, JWT)


def test_default_urls_pin_the_verified_hosts(monkeypatch):
    for var in (
        "UPSTREAM_FINXOMNE_BASE",
        "UPSTREAM_MIS_BASE",
        "UPSTREAM_FINX_MIDDLEWARE_BASE",
        "UPSTREAM_HOLDINGS_URL",
        "UPSTREAM_PAYIN_URL",
        "UPSTREAM_PAYOUT_URL",
        "UPSTREAM_BROKERAGE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    assert (
        route(Endpoint.HOLDINGS).url
        == "https://finxomne.choiceindia.com/COTI/V1/Holdings"
    )
    assert (
        route(Endpoint.PAYIN).url
        == "https://finx.choiceindia.com/api/middleware/GetPayInTxnRpt"
    )
    assert (
        route(Endpoint.PAYOUT).url
        == "https://finx.choiceindia.com/api/middleware/GetPayOutTxnRpt"
    )
    assert (
        route(Endpoint.BROKERAGE).url
        == "https://api.choiceindia.com/middleware-go/v2/get-brokerage-slab"
    )


# --- credential actually sent on the wire -----------------------------------

@respx.mock
def test_holdings_call_sends_prefixed_session_id():
    route_mock = respx.post(config.upstream_holdings_url()).mock(
        return_value=httpx.Response(
            200,
            json={
                "Status": "Success",
                "Response": {"lDictHoldingData": {}, "BodStatus": 0},
                "Reason": "",
            },
        )
    )
    _run_call(Endpoint.HOLDINGS, {})
    sent = route_mock.calls.last.request
    assert sent.headers["authorization"] == f"Session {SESSION}"
    # The SSO JWT plays no part in the Holdings call.
    assert JWT not in sent.headers["authorization"]


@respx.mock
def test_payin_call_sends_bare_session_id():
    route_mock = respx.post(config.upstream_payin_url()).mock(
        return_value=httpx.Response(
            200, json={"Status": "Success", "Response": {"PayInTxn": []}}
        )
    )
    _run_call(Endpoint.PAYIN, {"UserID": "X008593"})
    assert route_mock.calls.last.request.headers["authorization"] == SESSION


@respx.mock
def test_payout_call_sends_bare_session_id():
    route_mock = respx.post(config.upstream_payout_url()).mock(
        return_value=httpx.Response(
            200, json={"Status": "Success", "Response": {"PayOutTxn": []}}
        )
    )
    _run_call(Endpoint.PAYOUT, {"UserID": "X008593"})
    assert route_mock.calls.last.request.headers["authorization"] == SESSION


@respx.mock
def test_brokerage_call_sends_raw_sso_jwt():
    route_mock = respx.post(config.upstream_brokerage_url()).mock(
        return_value=httpx.Response(
            200,
            json={"StatusCode": 200, "Status": "Success", "Response": []},
        )
    )
    _run_call(Endpoint.BROKERAGE, {"ClientID": "X008593"})
    sent = route_mock.calls.last.request
    # The slab authorizes with the raw SSO JWT, NOT the SessionId.
    assert sent.headers["authorization"] == JWT
    assert SESSION not in sent.headers["authorization"]
