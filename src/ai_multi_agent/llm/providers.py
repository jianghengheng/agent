from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


class LLMClient(Protocol):
    async def ainvoke(self, *, agent_name: str, system_prompt: str, user_prompt: str) -> str: ...


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
