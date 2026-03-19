from typing import Annotated

from fastapi import APIRouter, Depends

from ai_multi_agent.api.dependencies import get_workflow_service
from ai_multi_agent.schemas.workflow import WorkflowRequest, WorkflowResponse
from ai_multi_agent.services.workflow import MultiAgentWorkflowService

router = APIRouter(prefix="/workflows")


@router.post("/multi-agent", response_model=WorkflowResponse)
async def run_multi_agent_workflow(
    request: WorkflowRequest,
    service: Annotated[MultiAgentWorkflowService, Depends(get_workflow_service)],
) -> WorkflowResponse:
    return await service.run(request)
