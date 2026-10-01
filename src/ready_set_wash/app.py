from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from strawberry.fastapi import GraphQLRouter

from ready_set_wash.config import Settings
from ready_set_wash.providers import PriceProvider
from ready_set_wash.schema import schema
from ready_set_wash.security import SecurityMiddleware

STATIC = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
            app.state.provider = PriceProvider(settings, client)
            yield

    app = FastAPI(title="Ready, Set, Wash", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )

    app.add_middleware(SecurityMiddleware)

    async def context(request: Request) -> dict[str, Any]:
        return {"provider": request.app.state.provider, "now": datetime.now(UTC)}

    app.include_router(
        GraphQLRouter[dict[str, Any], None](schema, context_getter=context, graphql_ide=None),
        prefix="/graphql",
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="frontend")
    return app
