"""Brokerage data flow — `POST /api/data/brokerage` (CHO-211): the rate slab.

The slab is per-client, fetched from middleware-go with the raw SSO JWT (the
only data endpoint needing a fresh SSO token). The response carries no PII —
the backend gates on the body status field (never string-matching `Reason`)
and passes through ONLY each group's `title` and its items' `title`/`desc`;
any other upstream key is stripped. Rate clustering happens client-side at
render time (design: slabs are per-client, grouping must degrade gracefully).

Zero-slot: no body parameter is declared. The upstream `ClientID` comes ONLY
from the authenticated session header (IDOR defense).

Response envelope:
  ok    -> {"kind": "ok", "groups": [{"title", "list": [{"title", "desc"}]}]}
  empty -> {"kind": "empty"}
  errors -> 401 {"error": "AUTH_EXPIRED"} · 404 {"error": "NO_DATA"}
            · 502 {"error": "UPSTREAM_ERROR"}
"""

import logging

from fastapi import APIRouter, Header, Request

from app.data.envelope import (
    KIND_EMPTY,
    KIND_OK,
    error_response,
    missing_credentials,
)
from app.finx.client import FinxClient, ResultKind
from app.finx.routing import Endpoint

logger = logging.getLogger("app.data.brokerage")

router = APIRouter()


def _clean_item(raw: object) -> dict | None:
    """One slab line → {"title", "desc"} only; malformed items are skipped."""
    if not isinstance(raw, dict):
        return None
    title = raw.get("title")
    desc = raw.get("desc")
    if not isinstance(title, str) or not isinstance(desc, str):
        return None
    return {"title": title, "desc": desc}


def _clean_groups(response: object) -> list[dict] | None:
    """Whitelist passthrough of Response; None when the shape is malformed."""
    if not isinstance(response, list):
        return None
    groups: list[dict] = []
    for raw_group in response:
        if not isinstance(raw_group, dict):
            continue
        title = raw_group.get("title")
        raw_list = raw_group.get("list")
        if not isinstance(title, str) or not isinstance(raw_list, list):
            continue
        items = [i for i in (_clean_item(raw) for raw in raw_list) if i]
        if items:
            groups.append({"title": title, "list": items})
    return groups


@router.post("/api/data/brokerage")
async def brokerage(
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    if not authorization or not x_session_id or not x_user_id:
        return missing_credentials()

    # IDOR defense: ClientID comes ONLY from the session header — no request
    # body is even read.
    finx = FinxClient(request.app.state.http_client)
    result = await finx.call(
        Endpoint.BROKERAGE,
        session_id=x_session_id,
        sso_jwt=authorization,
        body={"ClientID": x_user_id},
    )
    if result.kind is ResultKind.EMPTY:
        return {"kind": KIND_EMPTY}
    if result.kind is not ResultKind.OK:
        return error_response(result.kind)

    groups = _clean_groups((result.payload or {}).get("Response"))
    if groups is None:
        return error_response(ResultKind.UPSTREAM_ERROR)
    if not groups:
        return {"kind": KIND_EMPTY}
    return {"kind": KIND_OK, "groups": groups}
