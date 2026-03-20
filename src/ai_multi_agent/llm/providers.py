from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


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
class DoubaoLLMClient:
    model: str
    api_key: str
    base_url: str

    async def ainvoke(self, *, agent_name: str, system_prompt: str, user_prompt: str) -> str:
        client = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=0.5,
        )
        response = await client.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        return str(response.content)

    async def astream(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[str]:
        _ = agent_name
        client = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=0.5,
            streaming=True,
        )
        async for chunk in client.astream(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        ):
            content = _normalize_chunk_content(chunk.content)
            if content:
                yield content


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
