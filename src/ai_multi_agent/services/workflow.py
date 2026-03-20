import logging

from ai_multi_agent.core.config import Settings
from ai_multi_agent.graph.builder import build_workflow_graph
from ai_multi_agent.graph.state import WorkflowState
from ai_multi_agent.llm.providers import DoubaoLLMClient, MockLLMClient
from ai_multi_agent.schemas.workflow import WorkflowRequest, WorkflowResponse

logger = logging.getLogger(__name__)


class MultiAgentWorkflowService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, request: WorkflowRequest) -> WorkflowResponse:
        llm, backend = self._resolve_llm(force_mock=request.force_mock_llm)
        graph = build_workflow_graph(llm)

        initial_state: WorkflowState = {
            "task": request.task,
            "context": request.context,
            "plan": "",
            "research": "",
            "critique": "",
            "final_answer": "",
            "approved": False,
            "revision_count": 0,
            "max_revisions": request.max_revisions,
            "trace": [],
        }

        logger.info("running multi-agent workflow with backend=%s", backend)
        result = await graph.ainvoke(initial_state)
        return WorkflowResponse(
            backend=backend,
            approved=result.get("approved", False),
            revision_count=result.get("revision_count", 0),
            plan=result.get("plan", ""),
            research=result.get("research", ""),
            critique=result.get("critique", ""),
            final_answer=result.get("final_answer", ""),
            trace=result.get("trace", []),
        )

    def _resolve_llm(self, *, force_mock: bool) -> tuple[MockLLMClient | DoubaoLLMClient, str]:
        if force_mock or not self.settings.ark_api_key:
            return MockLLMClient(), "mock"
        return (
            DoubaoLLMClient(
                model=self.settings.doubao_model,
                api_key=self.settings.ark_api_key,
                base_url=self.settings.ark_base_url,
            ),
            "doubao",
        )
