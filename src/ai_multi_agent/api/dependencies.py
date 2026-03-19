from typing import Annotated

from fastapi import Depends

from ai_multi_agent.core.config import Settings, get_settings
from ai_multi_agent.services.workflow import MultiAgentWorkflowService


def get_workflow_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> MultiAgentWorkflowService:
    return MultiAgentWorkflowService(settings=settings)
