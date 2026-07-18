"""FastAPI entrypoint for the Choice Jini backend.

Run from backend/:  uv run uvicorn app.main:app --port 8000
"""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app import config
from app.finx.delivery import FileTokenStore
from app.greeting import router as greeting_router
from app.report import router as report_router
from app.whats_new import router as whats_new_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # FinX hosts publish only A (IPv4) records, but httpx's async resolver also
    # issues an AAAA (IPv6) query that intermittently hangs against their DNS —
    # the cause of the phantom ConnectTimeouts (curl, which we compared against,
    # never stalls). Binding the socket to 0.0.0.0 forces AF_INET, so resolution
    # is IPv4-only and the AAAA lookup is never made. `retries` adds a
    # transport-level connect retry on top of FinxClient's own.
    transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0", retries=2)
    async with httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(config.upstream_timeout_seconds(), connect=8.0),
    ) as client:
        app.state.http_client = client
        yield


def create_app() -> FastAPI:
    # httpx logs every request line (method + full URL) at INFO. Those URLs
    # carry client codes and point at sensitive, effectively-unauthenticated
    # report artifacts — silence them so no URL or credential reaches the logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    app = FastAPI(title="Choice Jini backend", lifespan=lifespan)

    # In-memory store for generated-report download tokens (opaque, short-TTL,
    # session-bound). Per-app instance so tests are isolated.
    app.state.report_files = FileTokenStore(
        ttl_seconds=config.report_file_ttl_seconds()
    )

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    app.include_router(greeting_router)
    app.include_router(whats_new_router)
    app.include_router(report_router)
    return app


app = create_app()
