"""FastAPI entrypoint for the Choice Jini backend.

Run from backend/:  uv run uvicorn app.main:app --port 8000
"""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app import config
from app.greeting import router as greeting_router
from app.whats_new import router as whats_new_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(
        timeout=config.upstream_timeout_seconds()
    ) as client:
        app.state.http_client = client
        yield


def create_app() -> FastAPI:
    app = FastAPI(title="Choice Jini backend", lifespan=lifespan)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    app.include_router(greeting_router)
    app.include_router(whats_new_router)
    return app


app = create_app()
