from ai_multi_agent.agents.base import BaseAgent
from ai_multi_agent.graph.state import WorkflowState


def _is_approved(output: str) -> bool:
    first_line = output.splitlines()[0].strip().lower()
    return "approved: yes" in first_line


class CriticAgent(BaseAgent):
    async def run(self, state: WorkflowState) -> dict[str, object]:
        prompt = (
            "You are the review agent.\n"
            "Review the current plan and research.\n"
            "Respond with exactly this format:\n"
            "APPROVED: yes|no\n"
            "RATIONALE: ...\n"
            "NEXT_ACTION: ...\n\n"
            f"{self.summarize_state(state)}"
        )
        critique = await self.complete(prompt)
        approved = _is_approved(critique)
        revision_count = state.get("revision_count", 0) + (0 if approved else 1)
        return {
            "critique": critique,
            "approved": approved,
            "revision_count": revision_count,
            "trace": [f"{self.name}: review {'approved' if approved else 'requested changes'}"],
        }

