from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class WorkflowMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1, description="Conversation message content.")


class WorkflowRequest(BaseModel):
    task: str = Field(..., min_length=1, description="End-user task for the multi-agent workflow.")
    context: str = Field(default="", description="Additional business context.")
    messages: list[WorkflowMessage] = Field(
        default_factory=list,
        description="Prior conversation history excluding the current task.",
    )
    max_revisions: int = Field(default=1, ge=0, le=5)


class WorkflowResponse(BaseModel):
    backend: str
    approved: bool
    revision_count: int
    plan: str
    research: str
    critique: str
    final_answer: str
    trace: list[str]


WorkflowStreamEventName = Literal[
    "run_started",
    "step_started",
    "step_completed",
    "answer_started",
    "answer_delta",
    "run_completed",
    "error",
]


class WorkflowStreamEvent(TypedDict):
    event: WorkflowStreamEventName
    data: dict[str, Any]
