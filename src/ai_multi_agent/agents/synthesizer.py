from ai_multi_agent.agents.base import BaseAgent
from ai_multi_agent.graph.state import WorkflowState


class SynthesizerAgent(BaseAgent):
    async def run(self, state: WorkflowState) -> dict[str, object]:
        prompt = (
            "You are the final synthesis agent.\n"
            "Produce a polished final answer for the end user.\n"
            "Include an executive summary, proposed architecture, engineering checklist, "
            "and next implementation steps.\n\n"
            f"{self.summarize_state(state)}"
        )
        final_answer = await self.complete(prompt)
        return {
            "final_answer": final_answer,
            "trace": [f"{self.name}: final answer generated"],
        }

