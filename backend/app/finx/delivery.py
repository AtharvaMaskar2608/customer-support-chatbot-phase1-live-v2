"""Delivery / PII layer for report downloads and email confirmations.

Two hard rules (design decision 6, and the finx-report-backend spec):

  1. Download: the raw upstream report URL / signed link / file_id is fetched
     server-side and NEVER returned to the client or logged. We hand the client
     an opaque, short-TTL, session-bound token; the file bytes are held
     server-side and streamed on demand. The URL is not persisted at all.

  2. Email: the upstream confirmation string leaks the full registered email
     (uppercased). We mask it before it is ever returned.

Logs carry status + timing only — no URLs, no bodies, no credentials, no email.
"""

import logging
import re
import secrets
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger("app.finx.delivery")

# Matches a bare email so we can mask it out of the confirmation string.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+")


def mask_email(confirmation: object) -> str | None:
    """Mask the registered email leaked in an email-confirmation string.

    "PnL Report mail sent successfully to SANTOSH.HARSHA@GMAIL.COM"
        -> "san***@gmail.com"

    Keeps the first three characters of the local part, lowercased. Returns
    None if no email can be found (the string is never surfaced raw).
    """
    if not isinstance(confirmation, str):
        return None
    match = _EMAIL_RE.search(confirmation)
    if match is None:
        return None
    local, _, domain = match.group(0).partition("@")
    local = local.lower()
    domain = domain.lower()
    return f"{local[:3]}***@{domain}"


def size_label(n_bytes: int) -> str:
    """Human-friendly file size, e.g. 214 KB / 1.4 MB."""
    if n_bytes < 1024:
        return f"{n_bytes} B"
    kb = n_bytes / 1024
    if kb < 1024:
        return f"{round(kb)} KB"
    return f"{kb / 1024:.1f} MB"


async def fetch_artifact(
    http_client: httpx.AsyncClient, url: str
) -> bytes | None:
    """Fetch a report artifact server-side; return its bytes, or None on failure.

    The URL is treated as sensitive and effectively unauthenticated — it is
    never logged (httpx error messages, which can embed the URL, are reduced to
    the exception class name).
    """
    started = time.perf_counter()
    resp = None
    for attempt in (1, 2, 3):
        try:
            resp = await http_client.get(url)
            break
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            # Same intermittent slow-connect as the report endpoints; retry.
            logger.warning(
                "artifact connect failed error=%s attempt=%d elapsed_ms=%d",
                type(exc).__name__,
                attempt,
                int((time.perf_counter() - started) * 1000),
            )
            if attempt == 3:
                return None
        except httpx.HTTPError as exc:
            logger.warning(
                "artifact fetch failed error=%s elapsed_ms=%d",
                type(exc).__name__,
                int((time.perf_counter() - started) * 1000),
            )
            return None
    logger.info(
        "artifact fetch status=%d elapsed_ms=%d",
        resp.status_code,
        int((time.perf_counter() - started) * 1000),
    )
    if not 200 <= resp.status_code < 300:
        return None
    return resp.content


@dataclass
class _Entry:
    data: bytes
    filename: str
    content_type: str
    session_id: str
    expires_at: float


class FileTokenStore:
    """In-memory store of generated report files, keyed by an opaque token.

    Each token is short-TTL and bound to the session that created it; a lookup
    with a mismatched session returns nothing. In-memory is sufficient for
    Wave 0 (single-process); the interface leaves room for an external store.
    """

    def __init__(self, ttl_seconds: float = 300.0):
        self._ttl = ttl_seconds
        self._entries: dict[str, _Entry] = {}

    def _now(self) -> float:
        return time.monotonic()

    def _prune(self) -> None:
        now = self._now()
        expired = [t for t, e in self._entries.items() if e.expires_at <= now]
        for token in expired:
            del self._entries[token]

    def put(
        self,
        *,
        data: bytes,
        filename: str,
        content_type: str,
        session_id: str,
    ) -> str:
        self._prune()
        token = secrets.token_urlsafe(24)
        self._entries[token] = _Entry(
            data=data,
            filename=filename,
            content_type=content_type,
            session_id=session_id,
            expires_at=self._now() + self._ttl,
        )
        return token

    def get(self, token: str, session_id: str | None = None) -> _Entry | None:
        """Return the entry if it exists and is unexpired. When `session_id` is
        given, it must match the creating session; when omitted (token-only
        download links), the opaque short-TTL token is the sole credential."""
        entry = self._entries.get(token)
        if entry is None:
            return None
        if entry.expires_at <= self._now():
            del self._entries[token]
            return None
        if session_id is not None and not secrets.compare_digest(
            entry.session_id, session_id
        ):
            return None
        return entry
