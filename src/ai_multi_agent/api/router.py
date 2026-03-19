from fastapi import APIRouter

from ai_multi_agent.api.routes.health import router as health_router
from ai_multi_agent.api.routes.workflows import router as workflows_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(workflows_router, tags=["workflows"])

