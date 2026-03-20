from pydantic import BaseModel, Field


class WorkflowRequest(BaseModel):
    task: str = Field(..., min_length=1, description="End-user task for the multi-agent workflow.")
    context: str = Field(default="", description="Additional business context.")
    max_revisions: int = Field(default=1, ge=0, le=5)
    force_mock_llm: bool = Field(
        default=False,
        description="Use the deterministic mock LLM even when Doubao credentials are available.",
    )


class WorkflowResponse(BaseModel):
    backend: str
    approved: bool
    revision_count: int
    plan: str
    research: str
    critique: str
    final_answer: str
    trace: list[str]
