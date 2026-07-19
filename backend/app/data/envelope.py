"""Shared client-facing envelope for the data-card endpoints (CHO-211).

Success answers are data, not files, so unlike the report flows the 200 body
carries a `kind` discriminator the card branches on:

  ok    -> {"kind": "ok", ...flow-specific payload...}
  empty -> {"kind": "empty"}   (a valid answer: nothing to show)

Errors reuse the pinned two-layer error shapes from the report flows:
  401 {"error": "AUTH_EXPIRED"} · 404 {"error": "NO_DATA"}
  · 502 {"error": "UPSTREAM_ERROR"} · 400 {"error": "MISSING_CREDENTIALS"}
"""

from fastapi.responses import JSONResponse

from app.finx.client import ResultKind

KIND_OK = "ok"
KIND_EMPTY = "empty"


def missing_credentials() -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": "MISSING_CREDENTIALS"})


def error_response(kind: ResultKind) -> JSONResponse:
    """Map an upstream result kind to the pinned client-facing error shape.

    EMPTY is deliberately NOT here — for data flows an empty payload is a
    renderable answer ({"kind": "empty"}), handled by each flow before this.
    """
    if kind is ResultKind.AUTH_EXPIRED:
        return JSONResponse(status_code=401, content={"error": "AUTH_EXPIRED"})
    if kind in (ResultKind.NO_DATA, ResultKind.EMPTY):
        return JSONResponse(status_code=404, content={"error": "NO_DATA"})
    return JSONResponse(status_code=502, content={"error": "UPSTREAM_ERROR"})
