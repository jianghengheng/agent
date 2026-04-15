import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_multi_agent.api.router import api_router
from ai_multi_agent.core.config import get_settings
from ai_multi_agent.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


def _get_cors_origins() -> list[str]:
    """Build CORS origins list from settings + direct env var fallback."""
    settings = get_settings()
    origins = list(settings.cors_allow_origins)
    if cors_env := os.getenv("CORS_ALLOW_ORIGINS"):
        for raw in cors_env.strip("[]").split(","):
            origin = raw.strip().strip('"').strip("'")
            if origin and origin not in origins:
                origins.append(origin)
    return origins


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app
