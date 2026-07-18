"""GET /api/greeting — proxy for the upstream Get Profile API.

PII rules (openspec profile-greeting spec, hard requirements):
- NEVER log the upstream response body (it contains PAN, DOB, address, email,
  mobile, and bank account details).
- NEVER log URLs or headers carrying credentials.
- NEVER store or forward any upstream field other than the derived first name.
- Logs contain at most the upstream status code and request timing.
"""

import logging
import time

import httpx
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app import config

logger = logging.getLogger("app.greeting")

router = APIRouter()


def derive_first_name(full_name: object) -> str | None:
    """First whitespace-separated token of FirstHolderName, title-cased.

    "PRITAM NITIN WAVHAL" -> "Pritam". Returns None for empty, missing, or
    non-string values (degraded greeting).
    """
    if not isinstance(full_name, str):
        return None
    tokens = full_name.split()
    if not tokens:
        return None
    return tokens[0].title()


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _upstream_error() -> JSONResponse:
    return JSONResponse(status_code=502, content={"error": "UPSTREAM_ERROR"})


async def _fetch_profile(
    client: httpx.AsyncClient,
    authorization: str,
    x_session_id: str,
    x_user_id: str,
    started: float,
) -> httpx.Response | None:
    """POST to the upstream profile API; None on failure.

    Connect-phase failures are retried once: the upstream connects slowly at
    times, and a request that never reached the server is safe to resend.
    Exceptions are logged as class name only — httpx error messages can embed
    the request URL, which must never reach the logs alongside credentials.
    """
    for attempt in (1, 2):
        try:
            return await client.post(
                config.upstream_profile_url(),
                headers={
                    # Raw SSO JWT, no "Bearer" prefix — Choice convention.
                    "authorization": authorization,
                    "from": x_session_id,
                    "content-type": "application/json",
                },
                json={"InvCode": x_user_id},
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            logger.warning(
                "upstream profile connect failed error=%s attempt=%d elapsed_ms=%d",
                type(exc).__name__,
                attempt,
                _elapsed_ms(started),
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "upstream profile request failed error=%s elapsed_ms=%d",
                type(exc).__name__,
                _elapsed_ms(started),
            )
            return None
    return None


@router.get("/api/greeting")
async def greeting(
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    if not authorization or not x_session_id or not x_user_id:
        return JSONResponse(
            status_code=400, content={"error": "MISSING_CREDENTIALS"}
        )

    client: httpx.AsyncClient = request.app.state.http_client
    started = time.perf_counter()
    upstream = await _fetch_profile(
        client, authorization, x_session_id, x_user_id, started
    )
    if upstream is None:
        return _upstream_error()

    # The only permitted log line for a completed upstream call:
    # status code + timing, nothing else.
    logger.info(
        "upstream profile status=%d elapsed_ms=%d",
        upstream.status_code,
        _elapsed_ms(started),
    )

    if upstream.status_code == 401:
        return JSONResponse(status_code=401, content={"error": "AUTH_EXPIRED"})
    if not 200 <= upstream.status_code < 300:
        return _upstream_error()

    try:
        payload = upstream.json()
    except ValueError:
        return _upstream_error()

    if not isinstance(payload, dict) or payload.get("Status") != "Success":
        return _upstream_error()

    profile = payload.get("Response")
    full_name = (
        profile.get("FirstHolderName") if isinstance(profile, dict) else None
    )
    # Only the derived first name leaves this function — nothing else from
    # the upstream payload is stored or forwarded.
    return {"firstName": derive_first_name(full_name)}
