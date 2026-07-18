"""GET /api/whats-new — remote-config announcement content.

Content lives in backend/content/whats_new.json (server-side only) so it can
be updated without a frontend/app release. Edit the JSON and bump "version"
(date-based, e.g. "2026-07-18.1" -> "2026-07-18.2") whenever content changes —
the version drives the frontend's unseen-dot indicator.

No credentials required: content is broadcast, non-personalized, non-PII.
"""

import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

CONTENT_PATH = (
    Path(__file__).resolve().parent.parent / "content" / "whats_new.json"
)


@router.get("/api/whats-new")
async def whats_new():
    # Read per request so content edits go live without a server restart.
    with CONTENT_PATH.open(encoding="utf-8") as f:
        return json.load(f)
