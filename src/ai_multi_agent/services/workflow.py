import logging
from collections.abc import AsyncIterator
from typing import cast

from ai_multi_agent.agents.retail_parser import RetailParserAgent
from ai_multi_agent.core.config import Settings
from ai_multi_agent.graph.state import WorkflowState
from ai_multi_agent.llm.providers import DoubaoLLMClient, LLMClient
from ai_multi_agent.schemas.workflow import (
    WorkflowRequest,
    WorkflowResponse,
    WorkflowStreamEvent,
)

logger = logging.getLogger(__name__)


class MultiAgentWorkflowService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, request: WorkflowRequest) -> WorkflowResponse:
        async for event in self.stream(request):
            if event["event"] == "run_completed":
                return WorkflowResponse.model_validate(event["data"]["response"])
            if event["event"] == "error":
                raise RuntimeError(str(event["data"].get("message", "workflow execution failed")))

        raise RuntimeError("workflow execution ended without a completion event")

    async def stream(self, request: WorkflowRequest) -> AsyncIterator[WorkflowStreamEvent]:
        llm, llm_backend = self._resolve_llm()
        backend = f"retail-parser/{llm_backend}"
        parser = RetailParserAgent(
            name="parser",
            system_prompt=(
                "You are a retail operations assistant focused on question understanding and "
                "high-quality direct answers."
            ),
            llm=llm,
        )
        state = self._build_initial_state(request)

        logger.info("running retail parser workflow with backend=%s", backend)

        try:
            yield {
                "event": "run_started",
                "data": {
                    "backend": backend,
                    "task": request.task,
                    "max_revisions": 0,
                },
            }

            yield {
                "event": "step_started",
                "data": {
                    "step": "parser",
                    "iteration": 1,
                    "message": "parser started",
                },
            }

            execution = await parser.prepare(state)
            plan_markdown = parser.build_plan_markdown(execution)
            state["plan"] = plan_markdown
            state["trace"] = [*state.get("trace", []), "parser: retail query parsed"]

            yield {
                "event": "step_completed",
                "data": {
                    "step": "parser",
                    "iteration": 1,
                    "trace_entry": "parser: retail query parsed",
                    "content": str(state.get("plan", "")),
                },
            }

            answer_chunks: list[str] = []
            async for chunk in parser.stream_complete(execution.answer_prompt):
                if not chunk:
                    continue
                answer_chunks.append(chunk)
                yield {
                    "event": "answer_delta",
                    "data": {
                        "delta": chunk,
                    },
                }

            final_answer = "".join(answer_chunks).strip()
            self._merge_state(
                state,
                {
                    "plan": plan_markdown,
                    "final_answer": final_answer,
                    "approved": True,
                    "revision_count": 0,
                },
            )

            yield {
                "event": "run_completed",
                "data": {
                    "response": self._build_response(backend=backend, state=state).model_dump(
                        mode="json"
                    )
                },
            }
        except Exception as exc:  # pragma: no cover
            logger.exception("streaming retail parser execution failed")
            yield {
                "event": "error",
                "data": {
                    "message": str(exc),
                },
            }

    def _resolve_llm(self) -> tuple[LLMClient, str]:
        if not self.settings.ark_api_key:
            raise RuntimeError("ARK_API_KEY 未配置，无法调用真实模型。")

        return (
            DoubaoLLMClient(
                model=self.settings.doubao_model,
                api_key=self.settings.ark_api_key,
                base_url=self.settings.ark_base_url,
            ),
            "doubao",
        )

    @staticmethod
    def _build_initial_state(request: WorkflowRequest) -> WorkflowState:
        return {
            "task": request.task,
            "context": request.context,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in request.messages
            ],
            "plan": "",
            "research": "",
            "critique": "",
            "final_answer": "",
            "approved": True,
            "revision_count": 0,
            "max_revisions": 0,
            "trace": [],
        }

    @staticmethod
    def _merge_state(state: WorkflowState, result: dict[str, object]) -> None:
        state_mapping = cast(dict[str, object], state)
        for key, value in result.items():
            if key == "trace":
                state["trace"] = [*state.get("trace", []), *cast(list[str], value)]
                continue

            state_mapping[key] = value

    @staticmethod
    def _build_response(*, backend: str, state: WorkflowState) -> WorkflowResponse:
        return WorkflowResponse(
            backend=backend,
            approved=bool(state.get("approved", True)),
            revision_count=int(state.get("revision_count", 0)),
            plan=str(state.get("plan", "")),
            research=str(state.get("research", "")),
            critique=str(state.get("critique", "")),
            final_answer=str(state.get("final_answer", "")),
            trace=list(state.get("trace", [])),
        )
