"""GET /api/greeting — proxy for the upstream Get Profile API.

PII rules (openspec profile-greeting spec, hard requirements):
- NEVER log the upstream response body (it contains PAN, DOB, address, email,
  mobile, and bank account details).
- NEVER log URLs or headers carrying credentials.
- NEVER store or forward any upstream field other than the derived first name.
- Logs contain at most the upstream status code and request timing.

CHO-226 adds the trading-day greeting: the response carries the selected
`greetingKey` and its `template` alongside `firstName`. The backend picks the
key from the market clock and owns the copy; the frontend interpolates, so the
accent-coloured name span in EmptyState survives (design D1). Templates keep
their `{clientRef}` placeholder — a fully rendered string would flatten that
span. Selection can never fail the request: any clock, calendar, or template
error degrades to DEFAULT. The log line carries the key and a timestamp only,
never the name.
"""

import datetime
import json
import logging
import re
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app import clock, config

logger = logging.getLogger("app.greeting")

router = APIRouter()

GREETINGS_PATH = (
    Path(__file__).resolve().parent.parent / "content" / "greetings.json"
)

PLACEHOLDER = "{clientRef}"

# Last-resort copy, used only when content/greetings.json is unreadable or
# malformed. DEFAULT must stay byte-identical to the pre-CHO-226 static
# headline ("Hey <name> — what do you need?") — that identity is a spec
# scenario and a test.
_FALLBACK_GREETINGS: dict[str, dict[str, str]] = {
    "templates": {clock.KEY_DEFAULT: "Hey {clientRef} — what do you need?"},
    "fallbackTemplates": {clock.KEY_DEFAULT: "Hey there — what do you need?"},
}


def load_greetings() -> dict:
    """Greeting copy from content/greetings.json; never raises."""
    try:
        with GREETINGS_PATH.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        logger.warning(
            "greetings content unreadable error=%s — using DEFAULT fallback copy",
            type(exc).__name__,
        )
        return _FALLBACK_GREETINGS
    if not isinstance(payload, dict) or not isinstance(
        payload.get("templates"), dict
    ):
        logger.warning("greetings content malformed — using DEFAULT fallback copy")
        return _FALLBACK_GREETINGS
    return payload


def _pick_template(content: dict, key: str, first_name: str | None) -> str | None:
    bucket = "templates" if first_name else "fallbackTemplates"
    templates = content.get(bucket)
    if isinstance(templates, dict):
        template = templates.get(key)
        if isinstance(template, str) and template:
            return template
    return None


def select_greeting(
    first_name: str | None, now: datetime.datetime | None = None
) -> tuple[str, str]:
    """(greetingKey, template) for this moment.

    Windows are walked by the market clock: MORNING on any day, MARKET and
    POST_MARKET on trading days only, a declared special session's key inside
    its window, DEFAULT when nothing matches. With no first name the template
    comes from `fallbackTemplates`, which carry no placeholder — so the
    rendered headline has no double space or dangling punctuation.

    Any failure at all degrades to DEFAULT; this function does not raise.
    """
    content = load_greetings()
    try:
        snapshot = clock.market_state(now)
        # Degraded mode is weekday-only guesswork. The agent's status line
        # hedges and carries on, but a greeting cannot hedge: "markets are
        # live" on an uncovered Republic Day would simply be a lie. DEFAULT
        # asserts nothing, so that is what an unavailable or expired calendar
        # gets (profile-greeting spec: "Calendar unavailable -> DEFAULT").
        key = clock.KEY_DEFAULT if snapshot.degraded else snapshot.greeting_key
    except Exception as exc:
        logger.warning(
            "greeting window selection failed error=%s — falling back to DEFAULT",
            type(exc).__name__,
        )
        key = clock.KEY_DEFAULT

    template = _pick_template(content, key, first_name)
    if template is None:
        # An unknown or uncovered key must still produce a usable headline.
        key = clock.KEY_DEFAULT
        template = _pick_template(content, key, first_name) or _pick_template(
            _FALLBACK_GREETINGS, key, first_name
        )
    return key, template or _FALLBACK_GREETINGS["fallbackTemplates"][clock.KEY_DEFAULT]


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


async def fetch_first_name(
    client: httpx.AsyncClient,
    *,
    sso_jwt: str,
    session_id: str,
    client_code: str,
) -> str | None:
    """The client's first name for agent context (CHO-246), fetched from the
    Profile API. Best-effort and NEVER raises: any failure (network, non-2xx,
    malformed, or no name) returns None so the chat stream simply proceeds
    without a name. The name is never logged (same PII posture as the greeting
    route)."""
    try:
        started = time.perf_counter()
        upstream = await _fetch_profile(
            client, sso_jwt, session_id, client_code, started
        )
        if upstream is None or not 200 <= upstream.status_code < 300:
            return None
        payload = upstream.json()
        if not isinstance(payload, dict) or payload.get("Status") != "Success":
            return None
        profile = payload.get("Response")
        full_name = (
            profile.get("FirstHolderName") if isinstance(profile, dict) else None
        )
        return derive_first_name(full_name)
    except Exception as exc:  # best-effort: a name must never break the chat
        logger.warning("agent name fetch failed error=%s", type(exc).__name__)
        return None


# CHO-245: the client's email + phone for the support-ticket requester. The
# upstream response's exact field names are NOT in our docs (only
# FirstHolderName is documented), so candidate keys are tried and the value
# shape validated — CONFIRM against a live profile response before trusting in
# production; a missed key just leaves the ticket carrying the client code.
_EMAIL_KEYS = (
    "Email", "EmailId", "EmailID", "EmailAddress", "Email_Id", "MailId", "EMailId",
)
_PHONE_KEYS = (
    "Mobile", "MobileNo", "MobileNumber", "MobileNo1", "Phone", "PhoneNo",
    "PhoneNumber", "ContactNo", "ContactNumber",
)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?\d[\d\s-]{7,}$")


def _first_valid(profile: dict, keys: tuple[str, ...], pattern: re.Pattern) -> str | None:
    for key in keys:
        val = profile.get(key)
        if isinstance(val, str) and pattern.match(val.strip()):
            return val.strip()
    return None


async def fetch_contact_fields(
    client: httpx.AsyncClient,
    *,
    sso_jwt: str,
    session_id: str,
    client_code: str,
) -> dict[str, str]:
    """The client's email + phone for the support-ticket requester (CHO-245),
    from the Profile API. Best-effort and NEVER raises: returns {} on any
    failure. Only well-formed values are returned, and the values are never
    logged (same PII posture as the greeting route)."""
    try:
        started = time.perf_counter()
        upstream = await _fetch_profile(
            client, sso_jwt, session_id, client_code, started
        )
        if upstream is None or not 200 <= upstream.status_code < 300:
            return {}
        payload = upstream.json()
        if not isinstance(payload, dict) or payload.get("Status") != "Success":
            return {}
        profile = payload.get("Response")
        if not isinstance(profile, dict):
            return {}
        out: dict[str, str] = {}
        email = _first_valid(profile, _EMAIL_KEYS, _EMAIL_RE)
        if email:
            out["email"] = email
        phone = _first_valid(profile, _PHONE_KEYS, _PHONE_RE)
        if phone:
            out["phone"] = phone
        return out
    except Exception as exc:  # best-effort — a lookup must never fail a ticket
        logger.warning("ticket contact fetch failed error=%s", type(exc).__name__)
        return {}


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
    first_name = derive_first_name(full_name)

    greeting_key, template = select_greeting(first_name)
    # Key + timestamp only. The name must never reach the logs.
    logger.info(
        "greeting selected greeting_key=%s ts=%s",
        greeting_key,
        clock.ist_now().isoformat(timespec="seconds"),
    )
    return {
        "firstName": first_name,
        "greetingKey": greeting_key,
        "template": template,
    }
