"""Unit tests for the FinX routing table, credential selection, and the
two-layer error model. Upstreams are mocked — no live network."""

import asyncio

import httpx
import respx

from app import config
from app.finx.client import FinxClient, ResultKind, map_response
from app.finx.routing import AuthSource, Endpoint, route


def _run_call(endpoint, body):
    """Invoke FinxClient.call synchronously (no async test plugin in use)."""

    async def _go():
        async with httpx.AsyncClient() as http:
            return await FinxClient(http).call(
                endpoint, session_id=SESSION, sso_jwt=JWT, body=body
            )

    return asyncio.run(_go())

SESSION = "sess-abc"
JWT = "sso-jwt-xyz"
PNL_BODY = {
    "ClientId": "X008593",
    "UserId": "X008593",
    "Group": "Cash",
    "FromDate": "2026-04-01",
    "ToDate": "2026-07-21",
    "RequestFor": 0,
    "With_Exp": True,
    "SessionId": SESSION,
}


# --- routing table ----------------------------------------------------------

def test_report_endpoints_route_to_session_id():
    for endpoint in (Endpoint.PNL, Endpoint.LEDGER, Endpoint.TAX):
        assert route(endpoint).auth_source is AuthSource.SESSION_ID


def test_mis_endpoint_routes_to_sso_jwt():
    assert route(Endpoint.CML).auth_source is AuthSource.SSO_JWT


def test_from_header_is_present_and_not_a_credential():
    spec = route(Endpoint.PNL)
    assert spec.extra_headers["from"] == config.finx_from_header()
    # `from` must not carry the session or the jwt.
    assert spec.extra_headers["from"] not in (SESSION, JWT)


def test_mis_carries_jwt_marker_headers():
    spec = route(Endpoint.CML)
    assert spec.extra_headers["authType"] == "jwt"
    assert spec.extra_headers["source"] == "FINX_ANDROID"


# --- credential selection actually sent on the wire -------------------------

@respx.mock
def test_pnl_call_sends_session_id_as_authorization():
    route_mock = respx.post(config.upstream_pnl_url()).mock(
        return_value=httpx.Response(
            200, json={"Status": "Success", "Response": "http://x/y.pdf"}
        )
    )
    _run_call(Endpoint.PNL, PNL_BODY)
    sent = route_mock.calls.last.request
    # SessionId is the credential for .NET report endpoints, NOT the SSO JWT.
    assert sent.headers["authorization"] == SESSION
    assert sent.headers["from"] == config.finx_from_header()


@respx.mock
def test_cml_call_sends_sso_jwt_as_authorization():
    route_mock = respx.post(config.upstream_cml_url()).mock(
        return_value=httpx.Response(200, json={"statusCode": 200, "body": {}})
    )
    _run_call(Endpoint.CML, {"reportType": "cml"})
    sent = route_mock.calls.last.request
    # MIS/CML authenticates with the SSO JWT, NOT the SessionId.
    assert sent.headers["authorization"] == JWT
    assert sent.headers["authtype"] == "jwt"


# --- two-layer error model --------------------------------------------------

def _pnl_spec():
    return route(Endpoint.PNL)


def test_http_401_maps_to_auth_expired():
    resp = httpx.Response(
        401, json={"Status": "Fail", "Response": "", "Reason": "Invalid SessionId"}
    )
    assert map_response(resp, _pnl_spec()).kind is ResultKind.AUTH_EXPIRED


def test_http_204_maps_to_empty():
    resp = httpx.Response(204)
    assert map_response(resp, _pnl_spec()).kind is ResultKind.EMPTY


def test_body_failure_status_maps_to_no_data():
    # HTTP 200 but a business failure in the body — distinct from AUTH_EXPIRED.
    resp = httpx.Response(
        200, json={"Status": "Fail", "Response": None, "Reason": "Data not found."}
    )
    assert map_response(resp, _pnl_spec()).kind is ResultKind.NO_DATA


def test_success_status_maps_to_ok_with_payload():
    resp = httpx.Response(
        200, json={"Status": "Success", "Response": "http://x/y.pdf", "Reason": ""}
    )
    result = map_response(resp, _pnl_spec())
    assert result.kind is ResultKind.OK
    assert result.payload["Response"] == "http://x/y.pdf"


def test_non_2xx_maps_to_upstream_error():
    assert map_response(httpx.Response(500), _pnl_spec()).kind is ResultKind.UPSTREAM_ERROR


def test_bad_json_maps_to_upstream_error():
    resp = httpx.Response(200, content=b"<html>nope</html>")
    assert map_response(resp, _pnl_spec()).kind is ResultKind.UPSTREAM_ERROR


def test_error_mapping_never_inspects_reason():
    # A "success-looking" Reason with a failure Status must still be NO_DATA:
    # proves the branch is on Status, never on Reason wording.
    resp = httpx.Response(
        200, json={"Status": "Fail", "Response": None, "Reason": "Success!"}
    )
    assert map_response(resp, _pnl_spec()).kind is ResultKind.NO_DATA


@respx.mock
def test_transport_error_maps_to_upstream_error():
    respx.post(config.upstream_pnl_url()).mock(
        side_effect=httpx.ConnectTimeout("boom")
    )
    result = _run_call(Endpoint.PNL, PNL_BODY)
    assert result.kind is ResultKind.UPSTREAM_ERROR
