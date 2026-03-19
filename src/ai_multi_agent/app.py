from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai_multi_agent.api.router import api_router
from ai_multi_agent.core.config import get_settings
from ai_multi_agent.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app

