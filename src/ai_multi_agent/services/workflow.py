import asyncio
import logging
from collections.abc import AsyncIterator
from typing import cast

from ai_multi_agent.agents.data_fetcher import DataFetcherAgent
from ai_multi_agent.agents.retail_parser import RetailParserAgent
from ai_multi_agent.core.config import Settings
from ai_multi_agent.graph.state import WorkflowState
from ai_multi_agent.llm.providers import ArkLLMClient, LLMClient, MockLLMClient
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
        state = self._build_initial_state(request)

        try:
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

            logger.info("running retail parser workflow with backend=%s", backend)

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

            # Step 1: resolve dates (LLM call)
            resolved_result = await parser.resolve_dates_only(state)

            # Step 2: run API fetch + conversation context in parallel
            data_fetcher = DataFetcherAgent(
                name="data_fetcher",
                system_prompt=(
                    "You are a retail data analyst. Analyze real business data and provide "
                    "professional insights with specific numbers and comparisons."
                ),
                llm=llm,
            )

            fetcher_result: dict[str, object] = {}
            if resolved_result.query_type == "retail_metric_query":
                from ai_multi_agent.agents.retail_parser import RetailParserExecution

                # Build a temporary execution for data_fetcher (it only needs result)
                temp_execution = RetailParserExecution(
                    result=resolved_result,
                    conversation_bundle=None,  # type: ignore[arg-type]
                    answer_prompt="",
                )

                context_task = asyncio.create_task(
                    parser.prepare_context_only(state, resolved_result)
                )
                fetcher_task = asyncio.create_task(
                    data_fetcher.run(state, temp_execution)
                )

                fetcher_result, execution = await asyncio.gather(
                    fetcher_task, context_task
                )
            else:
                execution = await parser.prepare_context_only(state, resolved_result)

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

            if fetcher_result and resolved_result.query_type == "retail_metric_query":
                if fetcher_result.get("api_request"):
                    yield {
                        "event": "api_request",
                        "data": fetcher_result["api_request"],
                    }

                if fetcher_result.get("api_response") is not None:
                    yield {
                        "event": "api_response",
                        "data": {
                            "record_count": len(fetcher_result["api_response"]),
                            "records": fetcher_result["api_response"],
                        },
                    }

                self._merge_state(state, fetcher_result)

                yield {
                    "event": "step_completed",
                    "data": {
                        "step": "data_fetcher",
                        "iteration": 1,
                        "trace_entry": fetcher_result.get("trace", ["data_fetcher: done"])[0]
                            if fetcher_result else "data_fetcher: skipped",
                        "content": str(state.get("research", "")),
                    },
                }

            # --- Answer Generation ---
            if state.get("research") and execution.result.query_type == "retail_metric_query":
                answer_prompt = _build_final_answer_prompt(
                    task=state.get("task", ""),
                    context=state.get("context", ""),
                    execution=execution,
                    research=state.get("research", ""),
                )
            else:
                answer_prompt = execution.answer_prompt

            yield {
                "event": "answer_started",
                "data": {
                    "step": "parser",
                    "message": "answer stream requested",
                },
            }

            answer_chunks: list[str] = []
            async for chunk in parser.stream_complete(answer_prompt):
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
            logger.warning("ARK_API_KEY not configured, fallback to mock llm backend")
            return MockLLMClient(), "mock"

        return (
            ArkLLMClient(
                model=self.settings.ark_model,
                api_key=self.settings.ark_api_key,
                base_url=self.settings.ark_base_url,
            ),
            f"ark/{self.settings.ark_model}",
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


def _build_final_answer_prompt(
    *,
    task: str,
    context: str,
    execution: "RetailParserExecution",
    research: str,
) -> str:
    from ai_multi_agent.agents.retail_parser import _format_messages

    result = execution.result
    conversation_bundle = execution.conversation_bundle
    metric_hint = f"用户关注的指标：{result.metric}" if result.metric else "用户未指定具体指标，请综合分析所有经营数据"

    sections = [
        "你是零售经营助手，已获取到真实经营数据。",
        "请严格根据下方「接口返回数据」回答用户问题。",
        "",
        "## 核心原则",
        "- **只使用下方接口返回的数据**，所有数值必须能在数据中找到出处。",
        "- **严禁编造、推测或补充任何不在数据中的数字**。",
        "- 如果数据中缺少某个指标或某家店铺的信息，明确告知用户「该数据暂未获取到」，不要自行填充。",
        "- 增长率直接使用数据中提供的增长率字段，不要自行计算。",
        "",
        f"业务上下文：{context or '无'}",
        f"用户问题：{task}",
        f"当前日期：{result.current_date}",
        metric_hint,
        f"店铺名称：{result.store_name or '全部'}",
        f"时间范围：{result.start_date} ~ {result.end_date or result.start_date}",
        f"对比方式：{result.comparison_type or '同比'}",
        f"对比时间：{result.comparison_start_date} ~ {result.comparison_end_date or result.comparison_start_date}",
        "",
        "## 接口返回数据",
        research,
    ]

    if conversation_bundle.summary:
        sections.extend([
            "",
            "## 历史对话摘要",
            conversation_bundle.summary,
        ])

    sections.extend([
        "",
        "## 近期对话",
        _format_messages(conversation_bundle.recent_messages),
        "",
        "## 回答要求",
        "- 结合上下文和近期对话理解用户意图，优先回答追问。",
        "- 直接回答用户问题，引用数据中的具体数值。",
        "- 综合分析销售额、毛利、会员、客流、人效等多个维度。",
        "- 对比分析要清晰，增长率用百分比表示。",
        "- 主动发现数据中的异常和亮点。",
        "- 金额保留两位小数，百分比保留一位小数。",
        "- 结尾给出简短经营建议。",
        "- 输出中文 Markdown 格式。",
    ])

    return "\n".join(sections)

