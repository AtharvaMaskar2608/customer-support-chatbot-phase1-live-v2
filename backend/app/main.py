"""FastAPI entrypoint for the Choice Jini backend.

Run from backend/:  uv run uvicorn app.main:app --port 8000
"""

import logging
from contextlib import asynccontextmanager

import asyncpg
import httpx
from fastapi import FastAPI

from app import config
from app.agent import tracing
from app.agent.router import router as chat_router
from app.agent.store import ThreadStore
from app.data.brokerage import router as brokerage_router
from app.data.holdings import router as holdings_router
from app.data.money import router as money_router
from app.finx.delivery import FileTokenStore
from app.greeting import router as greeting_router
from app.kb.router import router as kb_router
from app.report import router as report_router
from app.reports.contract_notes import router as contract_notes_router
from app.reports.ledger import router as ledger_router
from app.reports.tax import router as tax_router
from app.whats_new import router as whats_new_router

logger = logging.getLogger(__name__)


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
        # KB retrieval pool (CHO-212). min_size=0 keeps startup lazy, and any
        # failure leaves pg_pool=None so the app still boots for non-KB routes
        # (the KB endpoint then answers 503 KB_UNAVAILABLE).
        app.state.pg_pool = None
        dsn = config.database_url()
        if dsn:
            try:
                app.state.pg_pool = await asyncpg.create_pool(
                    dsn, min_size=0, max_size=5, timeout=8
                )
            except (OSError, asyncpg.PostgresError) as exc:
                logger.warning("KB pool unavailable: %s", type(exc).__name__)
        # Conversation store (CHO-213): in-memory authoritative thread cache
        # persisted by a single background writer over the shared pool. With
        # pg_pool=None it runs memory-only (chat works, persistence off).
        app.state.conversation_store = ThreadStore(pool=app.state.pg_pool)
        await app.state.conversation_store.start()
        # CHO-261: ensure the agent_traces table exists (guarded; no-op when
        # tracing is disabled or the pool is unavailable).
        await tracing.ensure_schema(app.state.pg_pool)
        try:
            yield
        finally:
            # Drain queued conversation writes BEFORE the pool goes away.
            await app.state.conversation_store.close()
            if app.state.pg_pool is not None:
                await app.state.pg_pool.close()


def create_app() -> FastAPI:
    # httpx logs every request line (method + full URL) at INFO. Those URLs
    # carry client codes and point at sensitive, effectively-unauthenticated
    # report artifacts — silence them so no URL or credential reaches the logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # CHO-261: initialise agent tracing once (config-gated + fault-isolated —
    # a no-op when AGENT_TRACING is off, and never raises into startup).
    tracing.configure()

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
    # Wave-1 report flows (each a self-contained per-flow router).
    app.include_router(ledger_router)
    app.include_router(tax_router)
    app.include_router(contract_notes_router)
    # CHO-211 data-card flows (the answer is data rendered in-chat, not a file).
    app.include_router(holdings_router)
    app.include_router(money_router)
    app.include_router(brokerage_router)
    app.include_router(kb_router)
    # CHO-213 agentic loop: free text → tool-orchestrated SSE chat.
    app.include_router(chat_router)
    return app


app = create_app()
