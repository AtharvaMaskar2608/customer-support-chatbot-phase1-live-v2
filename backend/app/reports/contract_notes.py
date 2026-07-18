"""Contract Notes report flow (CHO-210, Wave 1) — the two-step selection flow.

Unlike the P&L/Ledger/Tax file endpoints (one call → one PDF), contract notes
are a two-call chain on two upstream paths:

  1. POST /api/report/contract-notes/list      → upstream /middleware-go/report/contract
     Lists the notes over a date range. `authorization` = SessionId (no prefix).
  2. POST /api/report/contract-notes/download   → upstream /middleware-go/contract/download
     Pulls one note's raw PDF bytes. `authorization` = "Session <SessionId>".

Two hard rules carried over from the P&L route (design decisions 5/6):

  * IDOR (Flag A): the contract-note chain authorizes purely on the body
    `client_id`/`client_code`. We ALWAYS derive it from the authenticated
    session header (X-User-Id) and never from the request body.
  * file_id is a ~88-char opaque download handle and is SENSITIVE. It never
    reaches the client: the list maps each file_id to an opaque, session-bound,
    short-TTL token; the download resolves that token back to the file_id
    server-side. The client only ever holds the opaque token.

Contract notes are NOT password-protected and have no email delivery.

Normalized envelopes returned to the frontend:
  list     -> {"notes": [{"id","date","segment","badge","month"}, ...]}   (200)
              (empty / no-data both collapse to {"notes": []})
  download -> {"delivery": "download", "file": {...}, "fileToken": "<id>"}
  errors   -> 401 {"error": "AUTH_EXPIRED"} · 404 {"error": "NO_DATA"}
              · 502 {"error": "UPSTREAM_ERROR"}
"""

import datetime
import logging
import os
import re
import secrets
import time
from collections import Counter
from dataclasses import dataclass

import httpx
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator

from app import config
from app.finx.client import ResultKind, map_response
from app.finx.delivery import size_label
from app.finx.routing import AuthSource, BodyShape, RouteSpec

logger = logging.getLogger("app.reports.contract_notes")

router = APIRouter()

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_MON = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
_MONTHS_LONG = [
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
]

# --- segment / badge derivation (best-effort from upstream `group`) ----------
# The upstream ContractNote carries a `group` code (casing varies: Grp1/GRP1).
# Only "Grp1" (Equity & F&O) is confirmed live; the prototype shows a same-day
# Commodity note (MCX badge) whose group code is not confirmed. So: Grp1 (or an
# absent group) → Equity & F&O; any other group → Commodity. The exchange badge
# is shown ONLY to disambiguate a date that carries two notes; otherwise null.
_EQUITY_SEGMENT = "Equity & F&O"
_COMMODITY_SEGMENT = "Commodity"
_EQUITY_GROUPS = frozenset({"", "grp1"})
_SEGMENT_BADGE = {_EQUITY_SEGMENT: "NSE·BSE", _COMMODITY_SEGMENT: "MCX"}

# The Go contract-list envelope: PascalCase `StatusCode` (numeric), body in
# `Body`. Distinct from the .NET (Status/Response) and MIS (statusCode/body)
# shapes, so it is not in routing.py — we only need it to reuse map_response's
# two-layer error model (401 / 204-empty / non-2xx / body-status).
_CONTRACT_LIST_SPEC = RouteSpec(
    url="",  # unused: map_response only reads body_shape + transport status
    auth_source=AuthSource.SESSION_ID,
    extra_headers={},
    body_shape=BodyShape(
        status_field="StatusCode",
        success_values=frozenset({200}),
        response_field="Body",
    ),
)


def _middleware_base() -> str:
    return os.environ.get(
        "UPSTREAM_FINX_MIDDLEWARE_BASE",
        config.UPSTREAM_FINX_MIDDLEWARE_BASE_DEFAULT,
    )


def _contract_list_url() -> str:
    """Upstream contract-note list (override UPSTREAM_CONTRACT_LIST_URL)."""
    return os.environ.get(
        "UPSTREAM_CONTRACT_LIST_URL",
        f"{_middleware_base()}/middleware-go/report/contract",
    )


def _contract_download_url() -> str:
    """Upstream per-note PDF download (override UPSTREAM_CONTRACT_DOWNLOAD_URL)."""
    return os.environ.get(
        "UPSTREAM_CONTRACT_DOWNLOAD_URL",
        f"{_middleware_base()}/middleware-go/contract/download",
    )


# --- opaque-id ↔ file_id map (per session, short-TTL) -----------------------

@dataclass
class _NoteRef:
    file_id: str
    session_id: str
    filename_date: str  # compact date for the friendly filename, e.g. "16Sep2024"
    expires_at: float


class ContractNoteRefStore:
    """Maps an opaque, unguessable token → a sensitive upstream file_id.

    Each token is short-TTL and bound to the session that minted it (a lookup
    from another session returns nothing), so the ~88-char file_id never has to
    leave the server. Same posture as delivery.FileTokenStore.
    """

    def __init__(self, ttl_seconds: float = 600.0):
        self._ttl = ttl_seconds
        self._refs: dict[str, _NoteRef] = {}

    def _now(self) -> float:
        return time.monotonic()

    def _prune(self) -> None:
        now = self._now()
        for token in [t for t, r in self._refs.items() if r.expires_at <= now]:
            del self._refs[token]

    def put(self, *, file_id: str, session_id: str, filename_date: str) -> str:
        self._prune()
        token = secrets.token_urlsafe(18)
        self._refs[token] = _NoteRef(
            file_id=file_id,
            session_id=session_id,
            filename_date=filename_date,
            expires_at=self._now() + self._ttl,
        )
        return token

    def get(self, token: str, *, session_id: str) -> _NoteRef | None:
        ref = self._refs.get(token)
        if ref is None:
            return None
        if ref.expires_at <= self._now():
            del self._refs[token]
            return None
        # Session-bound: a token minted for one session is useless to another.
        if not secrets.compare_digest(ref.session_id, session_id):
            return None
        return ref


def _ref_store(request: Request) -> ContractNoteRefStore:
    """Per-app store, lazily created (main.py owns no contract-note state)."""
    store = getattr(request.app.state, "contract_note_refs", None)
    if store is None:
        store = ContractNoteRefStore()
        request.app.state.contract_note_refs = store
    return store


# --- request models ---------------------------------------------------------

class ContractNoteListRequest(BaseModel):
    # extra="ignore": any client-supplied client code in the body is dropped —
    # the client code comes ONLY from the session header (IDOR defense).
    model_config = ConfigDict(extra="ignore")

    fromDate: str
    toDate: str

    @field_validator("fromDate", "toDate")
    @classmethod
    def _valid_date(cls, v: str) -> str:
        if not _DATE_RE.match(v):
            raise ValueError("date must be YYYY-MM-DD")
        return v


class ContractNoteDownloadRequest(BaseModel):
    # Only the opaque token from the list is accepted; a smuggled file_id/
    # client code is ignored (never trusted from the body).
    model_config = ConfigDict(extra="ignore")

    id: str

    @field_validator("id")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("id must be non-empty")
        return v


# --- shared helpers ----------------------------------------------------------

def _missing_credentials() -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": "MISSING_CREDENTIALS"})


def _error_response(kind: ResultKind) -> JSONResponse:
    """Map an upstream result kind to the pinned client-facing error shape."""
    if kind is ResultKind.AUTH_EXPIRED:
        return JSONResponse(status_code=401, content={"error": "AUTH_EXPIRED"})
    if kind in (ResultKind.NO_DATA, ResultKind.EMPTY):
        return JSONResponse(status_code=404, content={"error": "NO_DATA"})
    return JSONResponse(status_code=502, content={"error": "UPSTREAM_ERROR"})


async def _upstream_post(
    http: httpx.AsyncClient, url: str, headers: dict, body: dict
) -> httpx.Response | None:
    """POST upstream; return the response, or None on a transport failure.

    PII-safe: only the exception class name is logged — never the URL, body, or
    credential (httpx error strings can embed the URL). The shared transport
    already retries slow connects (main.py binds IPv4 + retries=2).
    """
    started = time.perf_counter()
    try:
        resp = await http.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        logger.warning("contract upstream failed error=%s", type(exc).__name__)
        return None
    logger.info(
        "contract upstream status=%d elapsed_ms=%d",
        resp.status_code,
        int((time.perf_counter() - started) * 1000),
    )
    return resp


def _segment_for(group: object) -> str:
    g = (group if isinstance(group, str) else "").strip().lower()
    return _EQUITY_SEGMENT if g in _EQUITY_GROUPS else _COMMODITY_SEGMENT


def _parse_ddmmyyyy(value: object) -> datetime.date | None:
    if not isinstance(value, str) or len(value) != 8 or not value.isdigit():
        return None
    try:
        return datetime.date(
            int(value[4:8]), int(value[2:4]), int(value[0:2])
        )
    except ValueError:
        return None


def _build_notes(
    raw_notes: object, *, session_id: str, store: ContractNoteRefStore
) -> list[dict]:
    """Map upstream ContractNote rows → the client-facing, file_id-free list.

    Rows are sorted ascending by trade date; the exchange badge is set only when
    a date carries two notes (the disambiguation rule from the prototype).
    """
    if not isinstance(raw_notes, list):
        return []

    parsed: list[tuple[datetime.date, str, str]] = []
    for note in raw_notes:
        if not isinstance(note, dict):
            continue
        file_id = note.get("file_id")
        trade_date = _parse_ddmmyyyy(note.get("date"))
        if not isinstance(file_id, str) or not file_id or trade_date is None:
            continue  # unusable row — skip rather than surface a broken entry
        parsed.append((trade_date, file_id, _segment_for(note.get("group"))))

    parsed.sort(key=lambda p: p[0])
    per_date = Counter(p[0] for p in parsed)

    notes: list[dict] = []
    for trade_date, file_id, segment in parsed:
        multi = per_date[trade_date] >= 2
        opaque = store.put(
            file_id=file_id,
            session_id=session_id,
            filename_date=(
                f"{trade_date.day:02d}{_MON[trade_date.month - 1]}{trade_date.year}"
            ),
        )
        notes.append({
            "id": opaque,
            "date": f"{trade_date.day} {_MON[trade_date.month - 1]} {trade_date.year}",
            "segment": segment,
            "badge": _SEGMENT_BADGE[segment] if multi else None,
            "month": f"{_MONTHS_LONG[trade_date.month - 1]} {trade_date.year}",
        })
    return notes


# --- routes ------------------------------------------------------------------

@router.post("/api/report/contract-notes/list")
async def contract_notes_list(
    body: ContractNoteListRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    if not authorization or not x_session_id or not x_user_id:
        return _missing_credentials()

    # IDOR defense: client_id comes ONLY from the session header, never the body.
    upstream_body = {
        "client_id": x_user_id,
        "from_date": body.fromDate,
        "to_date": body.toDate,
    }
    headers = {
        "authorization": x_session_id,  # Go list endpoint: raw SessionId
        "from": config.finx_from_header(),
        "content-type": "application/json",
    }

    resp = await _upstream_post(
        request.app.state.http_client, _contract_list_url(), headers, upstream_body
    )
    if resp is None:
        return _error_response(ResultKind.UPSTREAM_ERROR)

    result = map_response(resp, _CONTRACT_LIST_SPEC)
    # "No notes for this range" is not an error — 204 (documented) and a body
    # no-data status both collapse to an empty list the frontend renders plainly.
    if result.kind in (ResultKind.EMPTY, ResultKind.NO_DATA):
        return {"notes": []}
    if result.kind is not ResultKind.OK:
        return _error_response(result.kind)

    payload_body = (result.payload or {}).get("Body") or {}
    raw_notes = payload_body.get("contractNotes") if isinstance(payload_body, dict) else None
    notes = _build_notes(
        raw_notes, session_id=x_session_id, store=_ref_store(request)
    )
    return {"notes": notes}


@router.post("/api/report/contract-notes/download")
async def contract_notes_download(
    body: ContractNoteDownloadRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    if not authorization or not x_session_id or not x_user_id:
        return _missing_credentials()

    # Resolve the opaque token → sensitive file_id, session-bound. Unknown or
    # expired tokens are indistinguishable and map to "no data".
    ref = _ref_store(request).get(body.id, session_id=x_session_id)
    if ref is None:
        return _error_response(ResultKind.NO_DATA)

    # IDOR defense: client_code from the session header; file_id resolved
    # server-side from the session-bound token — neither is trusted from the body.
    upstream_body = {"client_code": x_user_id, "file_id": ref.file_id}
    headers = {
        "authorization": f"Session {x_session_id}",  # note the "Session " prefix
        "content-type": "application/json",
    }

    resp = await _upstream_post(
        request.app.state.http_client,
        _contract_download_url(),
        headers,
        upstream_body,
    )
    if resp is None:
        return _error_response(ResultKind.UPSTREAM_ERROR)
    if resp.status_code == 401:
        return _error_response(ResultKind.AUTH_EXPIRED)
    if not 200 <= resp.status_code < 300 or not resp.content:
        return _error_response(ResultKind.UPSTREAM_ERROR)

    # Raw PDF bytes (no JSON envelope, no signed URL) — hand back an opaque,
    # session-bound token via the shared FileTokenStore and reuse the shared
    # GET /api/report/file/{token} download endpoint.
    filename = f"Contract_Note_{ref.filename_date}.pdf"
    token = request.app.state.report_files.put(
        data=resp.content,
        filename=filename,
        content_type="application/pdf",
        session_id=x_session_id,
    )
    return {
        "delivery": "download",
        "file": {
            "name": filename,
            "sizeLabel": size_label(len(resp.content)),
            "format": "PDF",
            "passwordProtected": False,  # contract notes are not PAN-protected
        },
        "fileToken": token,
    }
