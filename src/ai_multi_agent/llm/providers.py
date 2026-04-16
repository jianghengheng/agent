from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

STREAM_BATCH_CHARACTER_LIMIT = 1


class LLMClient(Protocol):
    async def ainvoke(self, *, agent_name: str, system_prompt: str, user_prompt: str) -> str: ...
    def astream(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[str]: ...


@dataclass(slots=True)
class ArkLLMClient:
    model: str
    api_key: str
    base_url: str

    async def ainvoke(self, *, agent_name: str, system_prompt: str, user_prompt: str) -> str:
        _ = agent_name
        client = _get_chat_client(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            streaming=False,
        )
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = await client.ainvoke(messages)
        return str(response.content)

    async def astream(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[str]:
        _ = agent_name
        client = _get_chat_client(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            streaming=True,
        )
        buffered_chunks: list[str] = []
        buffered_length = 0
        async for chunk in client.astream(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        ):
            content = _normalize_chunk_content(chunk.content)
            if content:
                buffered_chunks.append(content)
                buffered_length += len(content)
                if buffered_length >= STREAM_BATCH_CHARACTER_LIMIT:
                    yield "".join(buffered_chunks)
                    buffered_chunks.clear()
                    buffered_length = 0

        if buffered_chunks:
            yield "".join(buffered_chunks)


@dataclass(slots=True)
class MockLLMClient:
    async def ainvoke(self, *, agent_name: str, system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        if agent_name == "parser_summarizer":
            return "- 较早历史已摘要。\n- 关键信息已保留：门店、指标、时间范围、未解决问题。"

        if agent_name == "date_extractor":
            return _build_mock_date_json(user_prompt)

        return _build_mock_parser_answer(user_prompt)

    async def astream(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[str]:
        content = await self.ainvoke(
            agent_name=agent_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        for index in range(0, len(content), 40):
            yield content[index : index + 40]


@lru_cache(maxsize=8)
def _get_chat_client(
    *,
    model: str,
    api_key: str,
    base_url: str,
    streaming: bool,
) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
        streaming=streaming,
    )


def _build_mock_parser_answer(user_prompt: str) -> str:
    question = _extract_prompt_field(user_prompt, "User Question")
    question_type = _extract_prompt_field(user_prompt, "Question Type")
    current_date = _extract_prompt_field(user_prompt, "Current Date")
    keywords = _extract_prompt_field(user_prompt, "Keywords")
    metric = _extract_prompt_field(user_prompt, "Metric")
    store_name = _extract_prompt_field(user_prompt, "Store Name")
    start_date = _extract_prompt_field(user_prompt, "Start Date")
    end_date = _extract_prompt_field(user_prompt, "End Date")
    comparison_type = _extract_prompt_field(user_prompt, "Comparison Type")
    comparison_start_date = _extract_prompt_field(user_prompt, "Comparison Start Date")
    comparison_end_date = _extract_prompt_field(user_prompt, "Comparison End Date")

    if question_type == "normal_chat":
        if ("几月几号" in question or "什么日期" in question) and current_date:
            year, month, day = current_date.split("-")
            return "\n".join(
                [
                    "## 回复",
                    (
                        f"今天是 **{int(month)} 月 {int(day)} 号**，"
                        f"完整日期是 **{year}-{month}-{day}**。"
                    ),
                    "",
                    "_当前为 mock 回退模型输出。_",
                ]
            )

        return "\n".join(
            [
                "## 回复",
                f"我理解你的问题是：{question or '未提供问题'}",
                f"- 识别到的关键词：{keywords or '未识别'}",
                "",
                "_当前为 mock 回退模型输出。_",
            ]
        )

    metric_value = metric or "销售额"
    store_value = store_name or "未识别门店"
    return "\n".join(
        [
            "## 回复",
            f"你在问 **{store_value}** 的 **{metric_value}** 情况。",
            "当前阶段完成了参数解析，但未接入真实零售数据查询接口。",
            "",
            "## 解析结果",
            f"- 店铺名称：{store_value}",
            f"- 指标：{metric_value}",
            f"- 开始时间：{start_date or '未识别'}",
            f"- 结束时间：{end_date or '未识别'}",
            f"- 对比方式：{comparison_type or '未识别'}",
            f"- 对比开始时间：{comparison_start_date or '未识别'}",
            f"- 对比结束时间：{comparison_end_date or '未识别'}",
            f"- 关键词：{keywords or '未识别'}",
            "",
            "_当前为 mock 回退模型输出。_",
        ]
    )


def _extract_prompt_field(prompt: str, field_name: str) -> str:
    pattern = re.compile(rf"^{re.escape(field_name)}:\s*(.*)$", re.MULTILINE)
    match = pattern.search(prompt)
    if not match:
        return ""
    return match.group(1).strip()


def _normalize_chunk_content(content: object) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue

            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)

        return "".join(parts)

    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text

    if content:
        return str(content)

    return ""


def _build_mock_date_json(user_prompt: str) -> str:
    import json
    from datetime import date as _date
    from datetime import timedelta as _timedelta

    today = _date.today()
    task = ""
    for line in user_prompt.splitlines():
        if line.startswith("用户问题："):
            task = line.removeprefix("用户问题：").strip()
            break

    if "今天" in task or "今日" in task:
        d = today.isoformat()
        return json.dumps({"start_date": d, "end_date": d, "comparison_type": "同比"})

    if "昨天" in task or "昨日" in task:
        d = (today - _timedelta(days=1)).isoformat()
        return json.dumps({"start_date": d, "end_date": d, "comparison_type": "同比"})

    if "本周" in task or "这周" in task:
        ws = today - _timedelta(days=today.weekday())
        we = ws + _timedelta(days=6)
        return json.dumps({"start_date": ws.isoformat(), "end_date": we.isoformat(), "comparison_type": "同比"})

    return json.dumps({"start_date": None, "end_date": None, "comparison_type": "同比"})


# Backward compatibility for older imports.
DoubaoLLMClient = ArkLLMClient
