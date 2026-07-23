"""Trace viewer dashboard API (CHO-262) — read-only endpoints over the
``agent_traces`` table (CHO-261) for an admin operator UI.

Everything here is already safe to expose: ``thread_id`` / ``user_id`` are HMAC
hashes, and span ``input`` / ``output`` and the turn ``input`` / ``output`` were
PII-masked at write time (see ``app.agent.tracing``). This module only reads.

Auth is a single shared admin token, NOT the per-user FinX session auth — a
viewer is an operator, not a chat user. The token gates the whole router:

* ``TRACES_ADMIN_TOKEN`` unset  -> every endpoint answers **404** (the dashboard
  is disabled and nothing is exposed by default).
* set                          -> the ``X-Traces-Token`` request header MUST
  match, else **401**.

The token and the query text are never logged. All DB access goes through
``app.state.pg_pool``; with no pool the endpoints answer **503** (same degraded
posture as the KB route).
"""

import hmac
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app import config

# --- auth + pool guards ------------------------------------------------------


def require_admin(request: Request) -> None:
    """Gate the router by the shared admin token.

    Unset token => 404 (dashboard disabled). Set => the ``X-Traces-Token``
    header must match (constant-time). Neither the token nor its comparison is
    logged.
    """
    token = config.traces_admin_token()
    if not token:
        raise HTTPException(status_code=404, detail="not found")
    provided = request.headers.get("X-Traces-Token", "")
    if not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="unauthorized")


def require_pool(request: Request) -> Any:
    """Return the DB pool, or 503 when the trace store is unavailable."""
    pool = getattr(request.app.state, "pg_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="trace store unavailable")
    return pool


# Router-level dependency: the token gate runs before any handler, so an unset
# token turns the whole dashboard off (404) and a bad token is 401 everywhere.
router = APIRouter(prefix="/api", dependencies=[Depends(require_admin)])


# --- helpers -----------------------------------------------------------------

# List columns kept deliberately light — NOT the spans (those are fetched only
# in the detail / thread views).
_LIST_COLS = (
    "id, created_at, thread_id, user_id, model, input_tokens, output_tokens, "
    "tools, had_error, latency_ms, input, output"
)


def _parse_dt(value: str, field: str) -> datetime:
    """Parse an ISO8601 ``since`` / ``until`` bound; naive values are read as
    UTC. A malformed value is a 400 (client error), not a 500."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"invalid {field} datetime"
        ) from exc
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_spans(value: Any) -> list:
    """``spans`` comes back from asyncpg as a JSON string (jsonb); tolerate an
    already-decoded value or junk."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return []
    return value


def _trace_dict(row: Any, *, spans: bool = False) -> dict:
    """Shape a trace row for the API (spans included only on demand)."""
    out = {
        "id": row["id"],
        "created_at": row["created_at"],
        "thread_id": row["thread_id"],
        "user_id": row["user_id"],
        "model": row["model"],
        "input_tokens": row["input_tokens"],
        "output_tokens": row["output_tokens"],
        "tools": list(row["tools"]) if row["tools"] is not None else [],
        "had_error": row["had_error"],
        "latency_ms": row["latency_ms"],
        "input": row["input"],
        "output": row["output"],
    }
    if spans:
        out["spans"] = _parse_spans(row["spans"])
    return out


def _build_filters(
    *,
    thread_id: str | None,
    model: str | None,
    had_error: bool | None,
    tool: str | None,
    since: str | None,
    until: str | None,
) -> tuple[str, list]:
    """Assemble a parameterised WHERE clause (never string-interpolate values).
    Returns ``(where_sql, args)`` where placeholders are ``$1..$n``."""
    clauses: list[str] = []
    args: list = []

    def add(template: str, value: Any) -> None:
        args.append(value)
        clauses.append(template.format(n=len(args)))

    if thread_id:
        add("thread_id = ${n}", thread_id)
    if model:
        add("model = ${n}", model)
    if had_error is not None:
        add("had_error = ${n}", had_error)
    if tool:
        add("${n} = ANY(tools)", tool)
    if since:
        add("created_at >= ${n}", _parse_dt(since, "since"))
    if until:
        add("created_at <= ${n}", _parse_dt(until, "until"))

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, args


# --- endpoints ---------------------------------------------------------------


@router.get("/traces")
async def list_traces(
    request: Request,
    limit: int = Query(50, ge=1),
    offset: int = Query(0, ge=0),
    thread_id: str | None = None,
    model: str | None = None,
    had_error: bool | None = None,
    tool: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> dict:
    """Recent-first trace list (no spans) + total match count for pagination."""
    pool = require_pool(request)
    limit = min(limit, 200)
    where, args = _build_filters(
        thread_id=thread_id,
        model=model,
        had_error=had_error,
        tool=tool,
        since=since,
        until=until,
    )
    total = await pool.fetchval(
        f"SELECT count(*) FROM agent_traces{where}", *args
    )
    rows = await pool.fetch(
        f"SELECT {_LIST_COLS} FROM agent_traces{where} "
        f"ORDER BY created_at DESC, id DESC "
        f"LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}",
        *args,
        limit,
        offset,
    )
    return {
        "traces": [_trace_dict(r) for r in rows],
        "total": int(total or 0),
    }


@router.get("/traces/{trace_id}")
async def get_trace(request: Request, trace_id: int) -> dict:
    """One trace row INCLUDING its parsed span tree."""
    pool = require_pool(request)
    row = await pool.fetchrow(
        f"SELECT {_LIST_COLS}, spans FROM agent_traces WHERE id = $1",
        trace_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return _trace_dict(row, spans=True)


@router.get("/threads")
async def list_threads(
    request: Request,
    limit: int = Query(50, ge=1),
    offset: int = Query(0, ge=0),
) -> dict:
    """Conversations rolled up from their turns, most-recently-active first."""
    pool = require_pool(request)
    limit = min(limit, 200)
    total = await pool.fetchval(
        "SELECT count(DISTINCT thread_id) FROM agent_traces "
        "WHERE thread_id IS NOT NULL"
    )
    rows = await pool.fetch(
        "SELECT thread_id, "
        "count(*) AS turns, "
        "max(created_at) AS last_at, "
        "coalesce(sum(input_tokens), 0) AS total_input_tokens, "
        "bool_or(had_error) AS had_error "
        "FROM agent_traces WHERE thread_id IS NOT NULL "
        "GROUP BY thread_id ORDER BY last_at DESC "
        "LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    threads = [
        {
            "thread_id": r["thread_id"],
            "turns": int(r["turns"]),
            "last_at": r["last_at"],
            "total_input_tokens": int(r["total_input_tokens"] or 0),
            "had_error": bool(r["had_error"]),
        }
        for r in rows
    ]
    return {"threads": threads, "total": int(total or 0)}


@router.get("/threads/{thread_id}")
async def get_thread(request: Request, thread_id: str) -> dict:
    """All of one thread's turns in chronological order, each with its spans —
    powers the thread view and the per-turn token trend."""
    pool = require_pool(request)
    rows = await pool.fetch(
        f"SELECT {_LIST_COLS}, spans FROM agent_traces "
        f"WHERE thread_id = $1 ORDER BY created_at ASC, id ASC",
        thread_id,
    )
    return {"traces": [_trace_dict(r, spans=True) for r in rows]}
