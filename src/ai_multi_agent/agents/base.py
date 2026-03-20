from collections.abc import AsyncIterator
from dataclasses import dataclass

from ai_multi_agent.graph.state import WorkflowState
from ai_multi_agent.llm.providers import LLMClient


@dataclass(slots=True)
class BaseAgent:
    name: str
    system_prompt: str
    llm: LLMClient

    async def complete(self, prompt: str) -> str:
        return await self.llm.ainvoke(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            user_prompt=prompt,
        )

    async def stream_complete(self, prompt: str) -> AsyncIterator[str]:
        async for chunk in self.llm.astream(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            user_prompt=prompt,
        ):
            yield chunk

    @staticmethod
    def summarize_state(state: WorkflowState) -> str:
        return (
            f"Task:\n{state['task']}\n\n"
            f"Context:\n{state.get('context', 'N/A')}\n\n"
            f"Plan:\n{state.get('plan', 'N/A')}\n\n"
            f"Research:\n{state.get('research', 'N/A')}\n\n"
            f"Critique:\n{state.get('critique', 'N/A')}\n\n"
            f"Revision Count: {state.get('revision_count', 0)} / "
            f"{state.get('max_revisions', 0)}"
        )
