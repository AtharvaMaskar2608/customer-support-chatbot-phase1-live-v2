"""GET /api/whats-new — remote-config announcement content.

Content lives in backend/content/whats_new.json (server-side only) so it can
be updated without a frontend/app release. Edit the JSON and bump "version"
(date-based, e.g. "2026-07-18.1" -> "2026-07-18.2") whenever content changes —
the version drives the frontend's unseen-dot indicator.

No credentials required: content is broadcast, non-personalized, non-PII.
When the chat shell has a session, optional auth headers let CHO-288 join the
observation to the FinX journey; identity is never required for the response.
"""

import json
from pathlib import Path

from fastapi import APIRouter, Header

from app.agent import tracing

router = APIRouter()

CONTENT_PATH = (
    Path(__file__).resolve().parent.parent / "content" / "whats_new.json"
)


@router.get("/api/whats-new")
async def whats_new(
    authorization: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    # Read per request so content edits go live without a server restart.
    with CONTENT_PATH.open(encoding="utf-8") as f:
        payload = json.load(f)
    version = payload.get("version") if isinstance(payload, dict) else None
    # CHO-288: best-effort journey observation. Headers are optional — content
    # stays public; identity is attached only when the shell forwards them.
    tracing.emit_journey_api(
        name="api.whats_new",
        finx_session_id=x_session_id if authorization and x_session_id else None,
        client_code=x_user_id if authorization and x_user_id else None,
        output={"ok": True, "version": version},
    )
    return payload
