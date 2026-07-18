"""Async httpx client for the FinX report backends.

Responsibilities:
  - pick the right credential per endpoint (via routing.route)
  - make the upstream call
  - map the response through the two-layer error model

PII rules (same posture as greeting.py): the only thing this module logs about
an upstream call is the endpoint key, the HTTP status, and the elapsed time.
Never the request/response body, the URL, or any credential. httpx error
messages can embed the request URL, so exceptions are logged as class name only.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum

import httpx

from app.finx.routing import AuthSource, Endpoint, RouteSpec, route

logger = logging.getLogger("app.finx.client")


class ResultKind(str, Enum):
    OK = "ok"
    AUTH_EXPIRED = "auth_expired"  # real HTTP 401
    EMPTY = "empty"  # HTTP 204 (contract-notes empty case)
    NO_DATA = "no_data"  # HTTP 200 with a failure status in the body
    UPSTREAM_ERROR = "upstream_error"  # everything else


@dataclass
class UpstreamResult:
    kind: ResultKind
    # Parsed response envelope, present only when kind is OK.
    payload: dict | None = None


def map_response(resp: httpx.Response, spec: RouteSpec) -> UpstreamResult:
    """The two-layer error model (design decision 4).

    Layer 1 — transport: real 401 -> AUTH_EXPIRED, 204 -> EMPTY, non-2xx ->
    UPSTREAM_ERROR. Layer 2 — body: the envelope's status field must be a
    success value, else NO_DATA. `Reason` is never inspected — its wording
    differs across endpoints.
    """
    if resp.status_code == 401:
        return UpstreamResult(ResultKind.AUTH_EXPIRED)
    if resp.status_code == 204:
        return UpstreamResult(ResultKind.EMPTY)
    if not 200 <= resp.status_code < 300:
        return UpstreamResult(ResultKind.UPSTREAM_ERROR)

    try:
        body = resp.json()
    except ValueError:
        return UpstreamResult(ResultKind.UPSTREAM_ERROR)
    if not isinstance(body, dict):
        return UpstreamResult(ResultKind.UPSTREAM_ERROR)

    status = body.get(spec.body_shape.status_field)
    if status not in spec.body_shape.success_values:
        return UpstreamResult(ResultKind.NO_DATA)
    return UpstreamResult(ResultKind.OK, payload=body)


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


class FinxClient:
    """Thin wrapper around the shared httpx.AsyncClient."""

    def __init__(self, http_client: httpx.AsyncClient):
        self._http = http_client

    async def call(
        self,
        endpoint: Endpoint,
        *,
        session_id: str,
        sso_jwt: str,
        body: dict,
    ) -> UpstreamResult:
        """Call an upstream endpoint with the endpoint-correct credential.

        `session_id` and `sso_jwt` are both accepted; `route()` decides which
        one lands in `authorization`. The caller is responsible for having built
        `body` with a session-derived client code (never a client-supplied one).
        """
        spec = route(endpoint)
        if spec.auth_source is AuthSource.SESSION_ID:
            auth_value = session_id
        else:
            auth_value = sso_jwt
        headers = {
            **spec.extra_headers,
            "authorization": f"{spec.auth_prefix}{auth_value}",
        }

        started = time.perf_counter()
        # Connect-phase failures are retried once: the FinX upstream connects
        # slowly at times (observed live), and a request that never reached the
        # server is safe to resend. Same posture as the greeting proxy.
        resp = None
        for attempt in (1, 2, 3):
            try:
                resp = await self._http.post(spec.url, headers=headers, json=body)
                break
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                logger.warning(
                    "finx connect failed endpoint=%s error=%s attempt=%d elapsed_ms=%d",
                    endpoint.value,
                    type(exc).__name__,
                    attempt,
                    _elapsed_ms(started),
                )
                if attempt == 3:
                    return UpstreamResult(ResultKind.UPSTREAM_ERROR)
            except httpx.HTTPError as exc:
                logger.warning(
                    "finx call failed endpoint=%s error=%s elapsed_ms=%d",
                    endpoint.value,
                    type(exc).__name__,
                    _elapsed_ms(started),
                )
                return UpstreamResult(ResultKind.UPSTREAM_ERROR)

        # The only permitted log line for a completed call: endpoint key,
        # status code, timing. No body, no URL, no credential.
        logger.info(
            "finx upstream endpoint=%s status=%d elapsed_ms=%d",
            endpoint.value,
            resp.status_code,
            _elapsed_ms(started),
        )
        return map_response(resp, spec)
