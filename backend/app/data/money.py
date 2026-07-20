"""Money data flow — `POST /api/data/money` (CHO-211): the merged passbook.

FinX has two report screens (Pay-In, Pay-Out); the user has one mental model
(a passbook). One backend call fetches BOTH upstreams concurrently and merges
them into a single normalized newest-first stream — direction is a per-row
attribute (`dir`: "in"/"out"), not a tab.

Zero-slot: no body parameter is declared (nothing client-controlled is read).
The period is financial-year-to-date, matching the FinX app: FromDate = FY
start (April 1), ToDate = today + 7 days. The upstream client code comes ONLY
from the authenticated session header (IDOR defense).

PII whitelist (the contract — enforced by construction, only these keys are
ever built): dir, amt, st, dt, mode, dest (masked bank + last-4), ref, rsn.
DROPPED, never read: ClientName, ClientCode, full ClientBankAccNo,
JiffyTransactionId, AtomReferenceNo, Search_All_Levels. Pay-out `Reason` is
forwarded VERBATIM for display and never branched on.

Degraded modes: a business no-data status on one direction is an empty
direction (an empty passbook side is an answer, not an error). A transport /
auth failure on ONE direction returns the other with `"partial": true`; both
failing returns the error envelope (AUTH_EXPIRED wins over UPSTREAM_ERROR).

Response envelope:
  ok    -> {"kind": "ok", "txns": [...], "counts": {...},
            "landed": {"in": ₹, "out": ₹}, "totalRecords": {"in": n, "out": n}}
           (+ "partial": true when one direction failed)
  empty -> {"kind": "empty"}
  errors -> 401 {"error": "AUTH_EXPIRED"} · 502 {"error": "UPSTREAM_ERROR"}
"""

import asyncio
import datetime
import logging

from fastapi import APIRouter, Header, Request

from app.agent.ctx import (
    ToolCtx,
    ToolError,
    error_json_response,
    tool_error_from_kind,
)
from app.clock import ist_today
from app.data.envelope import KIND_EMPTY, KIND_OK, missing_credentials
from app.data.normalize import (
    STATUS_SUCCESS,
    blank_to_none,
    mask_payin_destination,
    mask_payout_destination,
    normalize_status,
    parse_upstream_datetime,
)
from app.finx.client import FinxClient, ResultKind, UpstreamResult
from app.finx.routing import Endpoint

logger = logging.getLogger("app.data.money")

router = APIRouter()

_PAGE_SIZE = 500

# A direction with any of these kinds produced an answer (possibly "nothing"):
# business no-data on a txn report means zero transactions, not a failure.
_USABLE_KINDS = frozenset(
    {ResultKind.OK, ResultKind.EMPTY, ResultKind.NO_DATA}
)


def _fy_window(today: datetime.date) -> tuple[str, str]:
    """FY-to-date, matching the FinX app: April 1 → today + 7 days."""
    start_year = today.year if today.month >= 4 else today.year - 1
    from_date = datetime.date(start_year, 4, 1)
    to_date = today + datetime.timedelta(days=7)
    return from_date.isoformat(), to_date.isoformat()


def _txn_report_body(client_code: str) -> dict:
    """The captured GetPayIn/PayOutTxnRpt request body (UserID from session)."""
    # IST, not host-local: on 1 April between 00:00 and 05:30 IST a UTC-based
    # "today" still reads 31 March, anchoring the window to the previous FY.
    from_date, to_date = _fy_window(ist_today())
    return {
        "UserID": client_code,
        "FromDate": from_date,
        "ToDate": to_date,
        "Segment": "",
        "Status": "",
        "StartPos": 0,
        "NoOfRecords": _PAGE_SIZE,
    }


def _extract_txns(result: UpstreamResult, list_key: str) -> tuple[list, int]:
    """(raw txn rows, upstream TotalRecords) for one usable direction."""
    if result.kind is not ResultKind.OK:
        return [], 0
    response = (result.payload or {}).get("Response")
    if not isinstance(response, dict):
        return [], 0
    raw = response.get(list_key)
    rows = [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []
    return rows, _total_records(response, fallback=len(rows))


def _total_records(response: dict, *, fallback: int) -> int:
    """Response.TotalCount[0].TotalRecords (same shape on both directions)."""
    total_count = response.get("TotalCount")
    if isinstance(total_count, list) and total_count:
        first = total_count[0]
        if isinstance(first, dict):
            n = first.get("TotalRecords")
            if isinstance(n, int) and not isinstance(n, bool):
                return n
    return fallback


def _amount(raw: dict) -> float | None:
    value = raw.get("Amount")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _payin_txn(raw: dict) -> tuple[datetime.datetime | None, dict] | None:
    """One pay-in row → (sort key, whitelisted normalized txn)."""
    amount = _amount(raw)
    if amount is None:
        return None
    requested = parse_upstream_datetime(raw.get("RequestedDateTime"))
    return requested, {
        "dir": "in",
        "amt": amount,
        "st": normalize_status(raw.get("Status")),
        "dt": requested.isoformat(timespec="seconds") if requested else None,
        "mode": blank_to_none(raw.get("ModeOfPayment")),
        "dest": mask_payin_destination(raw.get("DepositBankName")),
        "ref": blank_to_none(raw.get("VoucherNo")),
        "rsn": None,
    }


def _payout_txn(raw: dict) -> tuple[datetime.datetime | None, dict] | None:
    """One pay-out row → (sort key, whitelisted normalized txn).

    No mode upstream; `Reason` is display-only and forwarded verbatim.
    """
    amount = _amount(raw)
    if amount is None:
        return None
    requested = parse_upstream_datetime(raw.get("RequestedDateTime"))
    return requested, {
        "dir": "out",
        "amt": amount,
        "st": normalize_status(raw.get("Status")),
        "dt": requested.isoformat(timespec="seconds") if requested else None,
        "mode": None,
        "dest": mask_payout_destination(
            raw.get("ClientBankName"), raw.get("ClientBankAccNo")
        ),
        "ref": blank_to_none(raw.get("VoucherNo")),
        "rsn": blank_to_none(raw.get("Reason")),
    }


def _merged_stream(raw_in: list, raw_out: list) -> list[dict]:
    """Both directions normalized and merged newest-first; undated rows
    (sentinel timestamps) sink to the end."""
    keyed: list[tuple[datetime.datetime | None, dict]] = []
    for raw, build in ((raw_in, _payin_txn), (raw_out, _payout_txn)):
        for row in raw:
            built = build(row)
            if built is not None:
                keyed.append(built)
    keyed.sort(key=lambda item: item[0] or datetime.datetime.min, reverse=True)
    return [txn for _, txn in keyed]


def _status_counts(txns: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for txn in txns:
        if txn["st"] is not None:
            counts[txn["st"]] = counts.get(txn["st"], 0) + 1
    return counts


def _landed_totals(txns: list[dict]) -> dict[str, float]:
    """SUCCESS only — pending and failed amounts never inflate the totals."""

    def _sum(direction: str) -> float:
        return round(
            sum(
                t["amt"]
                for t in txns
                if t["dir"] == direction and t["st"] == STATUS_SUCCESS
            ),
            2,
        )

    return {"in": _sum("in"), "out": _sum("out")}


def _both_failed_error(
    pay_in: UpstreamResult, pay_out: UpstreamResult
) -> ToolError:
    """AUTH_EXPIRED wins over UPSTREAM_ERROR when both directions failed."""
    if ResultKind.AUTH_EXPIRED in (pay_in.kind, pay_out.kind):
        return tool_error_from_kind(ResultKind.AUTH_EXPIRED)
    return tool_error_from_kind(ResultKind.UPSTREAM_ERROR)


async def run_money(params: dict | None, ctx: ToolCtx) -> dict | ToolError:
    """Money (pay-in/pay-out passbook) core — shared by route and agent tool.

    Zero-slot: `params` is ignored; the period is FY-to-date by design.
    Returns the route's exact 200 body on success (including the `partial`
    one-direction-degraded shape), a ToolError otherwise; never raises. The
    txn stream is field-whitelisted with masked bank destinations.
    """
    del params  # zero-slot: no user-intent fields exist for this flow

    upstream_body = _txn_report_body(ctx.client_code)
    finx = FinxClient(ctx.http_client)
    pay_in, pay_out = await asyncio.gather(
        finx.call(
            Endpoint.PAYIN,
            session_id=ctx.session_id,
            sso_jwt=ctx.sso_jwt,
            body=upstream_body,
        ),
        finx.call(
            Endpoint.PAYOUT,
            session_id=ctx.session_id,
            sso_jwt=ctx.sso_jwt,
            body=upstream_body,
        ),
    )

    in_usable = pay_in.kind in _USABLE_KINDS
    out_usable = pay_out.kind in _USABLE_KINDS
    if not in_usable and not out_usable:
        return _both_failed_error(pay_in, pay_out)
    partial = not (in_usable and out_usable)

    raw_in, total_in = _extract_txns(pay_in, "PayInTxn")
    raw_out, total_out = _extract_txns(pay_out, "PayOutTxn")
    txns = _merged_stream(raw_in, raw_out)

    if not txns:
        payload: dict = {"kind": KIND_EMPTY}
        if partial:
            payload["partial"] = True
    else:
        payload = {
            "kind": KIND_OK,
            "txns": txns,
            "counts": _status_counts(txns),
            "landed": _landed_totals(txns),
            "totalRecords": {"in": total_in, "out": total_out},
            # ALWAYS present — the pinned frontend contract requires a boolean;
            # omitting it on full success made the card reject every healthy
            # payload (CHO-220: the real pay-in/pay-out tester bug).
            "partial": partial,
        }
    return payload


@router.post("/api/data/money")
async def money(
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    if not authorization or not x_session_id or not x_user_id:
        return missing_credentials()

    ctx = ToolCtx(
        session_id=x_session_id,
        sso_jwt=authorization,
        client_code=x_user_id,
        http_client=request.app.state.http_client,
    )
    result = await run_money(None, ctx)
    if isinstance(result, ToolError):
        return error_json_response(result)
    return result
