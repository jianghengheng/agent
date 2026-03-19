from ai_multi_agent.agents.base import BaseAgent
from ai_multi_agent.graph.state import WorkflowState


class PlannerAgent(BaseAgent):
    async def run(self, state: WorkflowState) -> dict[str, object]:
        prompt = (
            "You are the planning agent in a multi-agent AI system.\n"
            "Create a concise execution plan with these sections:\n"
            "1. Objective\n2. Key steps\n3. Risks\n4. Deliverables\n\n"
            f"{self.summarize_state(state)}"
        )
        plan = await self.complete(prompt)
        return {
            "plan": plan,
            "trace": [f"{self.name}: execution plan created"],
        }

