from ai_multi_agent.agents.base import BaseAgent
from ai_multi_agent.graph.state import WorkflowState


class ResearchAgent(BaseAgent):
    async def run(self, state: WorkflowState) -> dict[str, object]:
        prompt = (
            "You are the research and solution-design agent.\n"
            "Expand the plan with concrete implementation guidance.\n"
            "Focus on architecture, component boundaries, engineering considerations, "
            "and delivery tradeoffs.\n\n"
            f"{self.summarize_state(state)}"
        )
        research = await self.complete(prompt)
        return {
            "research": research,
            "trace": [f"{self.name}: research completed"],
        }

