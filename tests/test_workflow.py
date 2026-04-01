import json
from collections.abc import AsyncIterator, Callable
from datetime import date, timedelta

from fastapi.testclient import TestClient
from httpx import Response

from ai_multi_agent.api.dependencies import get_workflow_service
from ai_multi_agent.app import create_app
from ai_multi_agent.core.config import Settings
from ai_multi_agent.llm.providers import LLMClient
from ai_multi_agent.services.workflow import MultiAgentWorkflowService


class StubLLMClient:
    async def ainvoke(self, *, agent_name: str, system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        if agent_name == "parser_summarizer":
            return "- 历史对话已压缩摘要。"
        if agent_name == "parser":
            return _build_parser_answer(user_prompt)
        raise AssertionError(f"unexpected agent name: {agent_name}")

    async def astream(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[str]:
        yield await self.ainvoke(
            agent_name=agent_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )


class StubWorkflowService(MultiAgentWorkflowService):
    def __init__(self) -> None:
        super().__init__(settings=Settings(ark_api_key="stub-key"))

    def _resolve_llm(self) -> tuple[LLMClient, str]:
        return StubLLMClient(), "stub"


class FailingWorkflowService(MultiAgentWorkflowService):
    def __init__(self) -> None:
        super().__init__(settings=Settings(ark_api_key="stub-key"))

    def _resolve_llm(self) -> tuple[LLMClient, str]:
        raise RuntimeError("llm resolve failed")


def create_test_client_with_service(
    service_factory: Callable[[], MultiAgentWorkflowService],
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_workflow_service] = service_factory
    return TestClient(app)


def create_test_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_workflow_service] = lambda: StubWorkflowService()
    return TestClient(app)


def test_retail_parser_extracts_store_and_week_range() -> None:
    client = create_test_client()
    response = client.post(
        "/api/v1/workflows/multi-agent",
        json={
            "task": "星河店这周的销售额怎么样",
            "context": "",
            "max_revisions": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    assert payload["backend"] == "retail-parser/stub"
    assert payload["approved"] is True
    assert payload["revision_count"] == 0
    assert "parser: retail query parsed" in payload["trace"]
    assert "## 回复" in payload["final_answer"]
    assert "## 解析结果" in payload["final_answer"]
    assert "星河店" in payload["final_answer"]
    assert week_start.isoformat() in payload["final_answer"]
    assert week_end.isoformat() in payload["final_answer"]


def test_retail_parser_handles_normal_question() -> None:
    client = create_test_client()
    response = client.post(
        "/api/v1/workflows/multi-agent",
        json={
            "task": "今天是几月几号",
            "context": "",
            "max_revisions": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "retail-parser/stub"
    assert "今天是" in payload["final_answer"]
    assert "月" in payload["final_answer"]
    assert "号" in payload["final_answer"]


def test_retail_parser_can_inherit_context_from_history() -> None:
    client = create_test_client()
    response = client.post(
        "/api/v1/workflows/multi-agent",
        json={
            "task": "那上周呢",
            "context": "",
            "messages": [
                {
                    "role": "user",
                    "content": "星河店这周的销售额怎么样",
                },
                {
                    "role": "assistant",
                    "content": "我已经识别出你在问星河店本周销售额。",
                },
            ],
            "max_revisions": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()

    today = date.today()
    this_week_start = today - timedelta(days=today.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = last_week_start + timedelta(days=6)

    assert payload["backend"] == "retail-parser/stub"
    assert "星河店" in payload["final_answer"]
    assert "销售额" in payload["final_answer"]
    assert last_week_start.isoformat() in payload["final_answer"]
    assert last_week_end.isoformat() in payload["final_answer"]


def test_retail_parser_summarizes_long_history() -> None:
    client = create_test_client()
    messages = [
        {
            "role": "user" if index % 2 == 0 else "assistant",
            "content": (
                f"第 {index + 1} 轮对话，围绕星河店的销售额、营业额、利润、时间范围、"
                "用户意图和历史结论继续展开说明，并补充更多经营分析背景。"
            ),
        }
        for index in range(24)
    ]
    response = client.post(
        "/api/v1/workflows/multi-agent",
        json={
            "task": "继续结合刚才的内容总结一下",
            "context": "",
            "messages": messages,
            "max_revisions": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["backend"] == "retail-parser/stub"
    assert "较早历史已摘要" in payload["plan"]


def test_retail_parser_stream_returns_sse_events() -> None:
    client = create_test_client()
    with client.stream(
        "POST",
        "/api/v1/workflows/multi-agent/stream",
        json={
            "task": "星河店这周的销售额怎么样",
            "context": "",
            "max_revisions": 1,
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _collect_sse_events(response)

    event_names = [name for name, _ in events]
    assert event_names[0] == "run_started"
    assert "step_started" in event_names
    assert "step_completed" in event_names
    assert "answer_delta" in event_names
    assert event_names[-1] == "run_completed"

    step_completed_event = next(data for name, data in events if name == "step_completed")
    assert step_completed_event["step"] == "parser"

    completed_payload = events[-1][1]["response"]
    assert isinstance(completed_payload, dict)
    assert completed_payload["backend"] == "retail-parser/stub"
    assert "星河店" in completed_payload["final_answer"]


def test_retail_parser_falls_back_to_mock_when_ark_key_missing() -> None:
    client = create_test_client_with_service(
        lambda: MultiAgentWorkflowService(settings=Settings(ark_api_key=None))
    )
    response = client.post(
        "/api/v1/workflows/multi-agent",
        json={
            "task": "星河店这周的销售额怎么样",
            "context": "",
            "max_revisions": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "retail-parser/mock"
    assert "mock 回退模型输出" in payload["final_answer"]


def test_retail_parser_stream_returns_error_event_when_llm_resolve_fails() -> None:
    client = create_test_client_with_service(lambda: FailingWorkflowService())
    with client.stream(
        "POST",
        "/api/v1/workflows/multi-agent/stream",
        json={
            "task": "星河店这周的销售额怎么样",
            "context": "",
            "max_revisions": 1,
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _collect_sse_events(response)

    event_names = [name for name, _ in events]
    assert event_names == ["error"]
    assert "llm resolve failed" in str(events[0][1]["message"])


def _collect_sse_events(response: Response) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    current_event = ""
    current_data: list[str] = []

    for raw_line in response.iter_lines():
        line = raw_line if isinstance(raw_line, str) else raw_line.decode()
        if line == "":
            if current_event:
                events.append((current_event, json.loads("\n".join(current_data))))
            current_event = ""
            current_data = []
            continue

        if line.startswith("event: "):
            current_event = line.removeprefix("event: ")
            continue

        if line.startswith("data: "):
            current_data.append(line.removeprefix("data: "))

    return events


def _build_parser_answer(user_prompt: str) -> str:
    question = _extract_prompt_field(user_prompt, "User Question")
    question_type = _extract_prompt_field(user_prompt, "Question Type")
    current_date = _extract_prompt_field(user_prompt, "Current Date")
    keywords = _extract_prompt_field(user_prompt, "Keywords")
    metric = _extract_prompt_field(user_prompt, "Metric")
    store_name = _extract_prompt_field(user_prompt, "Store Name")
    start_date = _extract_prompt_field(user_prompt, "Start Date")
    end_date = _extract_prompt_field(user_prompt, "End Date")

    if question_type == "normal_chat":
        if "几月几号" in question or "什么日期" in question:
            year, month, day = current_date.split("-")
            return "\n".join(
                [
                    "## 回复",
                    f"今天是 **{int(month)} 月 {int(day)} 号**，"
                    f"完整日期是 **{year}-{month}-{day}**。",
                ]
            )

        return "\n".join(
            [
                "## 回复",
                f"我理解你的问题是：{question}",
                f"- 识别到的关键词：{keywords or '未识别'}",
            ]
        )

    return "\n".join(
        [
            "## 回复",
            f"你在问 **{store_name}** 的 **{metric}** 情况。",
            "当前阶段已经完成参数解析，但还没有接入真实零售数据查询接口。",
            "",
            "## 解析结果",
            f"- 店铺名称：{store_name}",
            f"- 指标：{metric}",
            f"- 开始时间：{start_date}",
            f"- 结束时间：{end_date}",
            f"- 关键词：{keywords}",
        ]
    )


def _extract_prompt_field(prompt: str, field_name: str) -> str:
    prefix = f"{field_name}: "
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""
