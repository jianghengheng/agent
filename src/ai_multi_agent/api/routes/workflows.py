import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ai_multi_agent.api.dependencies import get_workflow_service
from ai_multi_agent.schemas.workflow import WorkflowRequest, WorkflowResponse, WorkflowStreamEvent
from ai_multi_agent.services.workflow import MultiAgentWorkflowService

router = APIRouter(prefix="/workflows")


@router.post("/multi-agent", response_model=WorkflowResponse)
async def run_multi_agent_workflow(
    request: WorkflowRequest,
    service: Annotated[MultiAgentWorkflowService, Depends(get_workflow_service)],
) -> WorkflowResponse:
    return await service.run(request)


@router.post("/multi-agent/stream")
async def run_multi_agent_workflow_stream(
    workflow_request: WorkflowRequest,
    http_request: Request,
    service: Annotated[MultiAgentWorkflowService, Depends(get_workflow_service)],
) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        async for event in service.stream(workflow_request):
            if await http_request.is_disconnected():
                break
            yield _format_sse_event(event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_sse_event(event: WorkflowStreamEvent) -> str:
    payload = json.dumps(event["data"], ensure_ascii=False)
    return f"event: {event['event']}\ndata: {payload}\n\n"
