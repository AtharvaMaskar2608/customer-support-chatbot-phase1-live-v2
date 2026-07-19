"""Holdings data flow — `POST /api/data/holdings` (CHO-211).

Zero-slot: the endpoint takes no client input at all (no body parameter is
declared, so a smuggled client code cannot even be read — IDOR defense by
construction). The upstream call authorizes with `Session <SessionId>` only;
the web app's decorative extras (`ssotoken`, body `accessToken`,
`fingerprint`) are not enforced and not sent (probe-verified 2026-07-18).

All displayed numbers are derived HERE, in one tested place — the card
renders, it does not calculate (design: "Derivation lives server-side").
Prices normalize paise → rupees at this boundary; the freshness stamp is the
max `LUT` across scrips, never a hardcode.

PII whitelist: Sym, Name, Q, ABP, LTP, CP (normalized) + derived metrics.
Everything else in the upstream row (Seg, tokens, MTF fields, …) is dropped.

Response envelope:
  ok    -> {"kind": "ok", "asOf": "<ISO max LUT>", "rows": [...], "totals": {...}}
  empty -> {"kind": "empty"}          (empty portfolio — a renderable state)
  errors -> 401 {"error": "AUTH_EXPIRED"} · 404 {"error": "NO_DATA"}
            · 502 {"error": "UPSTREAM_ERROR"}
"""

import datetime
import logging

from fastapi import APIRouter, Header, Request

from app.data.envelope import (
    KIND_EMPTY,
    KIND_OK,
    error_response,
    missing_credentials,
)
from app.data.normalize import paise_to_rupees, parse_upstream_datetime
from app.finx.client import FinxClient, ResultKind
from app.finx.routing import Endpoint

logger = logging.getLogger("app.data.holdings")

router = APIRouter()

_EXCHANGE_SUFFIX = "-EQ"


def _number(value: object) -> int | float | None:
    """Pass a JSON number through untouched (501 stays an int, not 501.0)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _build_row(raw: object) -> tuple[dict, datetime.datetime | None] | None:
    """One upstream scrip → (whitelisted+derived row, parsed LUT), or None.

    Unusable rows (missing/malformed numbers) are skipped rather than
    surfaced broken — same posture as the contract-note list.
    """
    if not isinstance(raw, dict):
        return None
    sym = raw.get("Sym")
    if not isinstance(sym, str) or not sym.strip():
        return None
    qty = _number(raw.get("Q"))
    abp = _number(raw.get("ABP"))  # already rupees
    ltp = paise_to_rupees(raw.get("LTP"))  # paise -> rupees
    cp = paise_to_rupees(raw.get("CP"))  # paise -> rupees
    if qty is None or abp is None or ltp is None or cp is None:
        return None

    current = round(qty * ltp, 2)
    invested = round(qty * abp, 2)
    pnl = round(current - invested, 2)
    day = round(qty * (ltp - cp), 2)
    name = raw.get("Name")
    row = {
        "sym": sym.strip().removesuffix(_EXCHANGE_SUFFIX),
        "name": name if isinstance(name, str) else sym.strip(),
        "qty": qty,
        "abp": abp,
        "ltp": ltp,
        "current": current,
        "invested": invested,
        "pnl": pnl,
        "pnlPct": round(pnl / invested * 100, 2) if invested else 0.0,
        "day": day,
        "dayPct": round((ltp - cp) / cp * 100, 2) if cp else 0.0,
        # alloc needs the portfolio total — filled in after the full pass.
        "alloc": 0.0,
    }
    return row, parse_upstream_datetime(raw.get("LUT"))


def _extract_scrips(payload: dict | None) -> dict | None:
    """Response.lDictHoldingData, or None when the envelope is malformed."""
    response = (payload or {}).get("Response")
    if not isinstance(response, dict):
        return None
    scrip_dict = response.get("lDictHoldingData")
    return scrip_dict if isinstance(scrip_dict, dict) else None


def _totals(rows: list[dict]) -> dict:
    total_current = sum(r["current"] for r in rows)
    total_invested = sum(r["invested"] for r in rows)
    total_day = sum(r["day"] for r in rows)
    total_pnl = round(total_current - total_invested, 2)
    # 1D % is relative to the previous-close value (current minus the move).
    prev_close_value = total_current - total_day
    return {
        "current": round(total_current, 2),
        "invested": round(total_invested, 2),
        "pnl": total_pnl,
        "pnlPct": (
            round(total_pnl / total_invested * 100, 2) if total_invested else 0.0
        ),
        "day": round(total_day, 2),
        "dayPct": (
            round(total_day / prev_close_value * 100, 2) if prev_close_value else 0.0
        ),
        "count": len(rows),
    }


def _build_card(scrip_dict: dict) -> dict:
    """The full card payload: ranked rows + allocation + totals + freshness."""
    rows: list[dict] = []
    max_lut: datetime.datetime | None = None
    for raw in scrip_dict.values():
        built = _build_row(raw)
        if built is None:
            continue
        row, lut = built
        rows.append(row)
        if lut is not None and (max_lut is None or lut > max_lut):
            max_lut = lut
    if not rows:
        # Empty portfolio: the EMPTY kind, rendered as the card's empty state.
        return {"kind": KIND_EMPTY}

    rows.sort(key=lambda r: r["current"], reverse=True)
    total_current = sum(r["current"] for r in rows)
    for row in rows:
        row["alloc"] = (
            round(row["current"] / total_current * 100, 2) if total_current else 0.0
        )
    return {
        "kind": KIND_OK,
        "asOf": max_lut.isoformat(timespec="seconds") if max_lut else None,
        "rows": rows,
        "totals": _totals(rows),
    }


@router.post("/api/data/holdings")
async def holdings(
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    if not authorization or not x_session_id or not x_user_id:
        return missing_credentials()

    # Auth probe (A/B/C, all 200) showed only the Session header credential is
    # enforced — but the BODY fields are required (empty body → upstream 404).
    # All values come from the authenticated session headers, never user input.
    finx = FinxClient(request.app.state.http_client)
    result = await finx.call(
        Endpoint.HOLDINGS,
        session_id=x_session_id,
        sso_jwt=authorization,
        body={
            "UserId": x_user_id,
            "UserCode": x_user_id,
            "GroupId": "HO",
            "SessionId": x_session_id,
            "Status": "",
        },
    )
    if result.kind is ResultKind.EMPTY:
        return {"kind": KIND_EMPTY}
    if result.kind is not ResultKind.OK:
        return error_response(result.kind)

    scrip_dict = _extract_scrips(result.payload)
    if scrip_dict is None:
        return error_response(ResultKind.UPSTREAM_ERROR)
    return _build_card(scrip_dict)
