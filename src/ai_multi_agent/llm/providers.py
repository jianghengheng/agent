from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


class LLMClient(Protocol):
    async def ainvoke(self, *, agent_name: str, system_prompt: str, user_prompt: str) -> str: ...


@dataclass(slots=True)
class OpenAILLMClient:
    model: str
    api_key: str
    base_url: str | None = None

    async def ainvoke(self, *, agent_name: str, system_prompt: str, user_prompt: str) -> str:
        client = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=0.2,
        )
        response = await client.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        return str(response.content)


class MockLLMClient:
    async def ainvoke(self, *, agent_name: str, system_prompt: str, user_prompt: str) -> str:
        _ = system_prompt
        if agent_name == "planner":
            return (
                "Objective: Build a production-ready multi-agent AI application.\n"
                "Key steps: define domain boundaries, build LangGraph workflow, expose FastAPI API, "
                "add observability and tests.\n"
                "Risks: prompt coupling, missing tool boundaries, insufficient evaluation.\n"
                "Deliverables: runnable service, reusable modules, CI-ready project layout."
            )
        if agent_name == "researcher":
            needs_revision = "APPROVED: no" in user_prompt
            revision_note = (
                "Incorporated reviewer feedback by strengthening delivery governance and test strategy.\n"
                if needs_revision
                else ""
            )
            return (
                f"{revision_note}"
                "Architecture: API layer, workflow service, graph orchestration, agent roles, "
                "LLM provider abstraction.\n"
                "Engineering: central settings, typed schemas, lint/type-check/test pipeline, "
                "environment-based model selection.\n"
                "Delivery tradeoffs: start with mock backend for local development, then "
                "swap to real providers without changing agent orchestration."
            )
        if agent_name == "critic":
            if "Revision Count: 0 /" in user_prompt:
                return (
                    "APPROVED: no\n"
                    "RATIONALE: The proposal is solid but should state clearer implementation governance.\n"
                    "NEXT_ACTION: Refine the engineering checklist and rollout guidance."
                )
            return (
                "APPROVED: yes\n"
                "RATIONALE: The workflow covers architecture, delivery, and quality controls.\n"
                "NEXT_ACTION: Proceed to final synthesis."
            )
        return (
            "Executive Summary:\n"
            "This scaffold provides a reusable baseline for a multi-agent AI product.\n\n"
            "Proposed Architecture:\n"
            "- FastAPI handles transport.\n"
            "- LangGraph orchestrates planner, researcher, critic, and synthesizer agents.\n"
            "- Provider abstraction isolates model vendors.\n\n"
            "Engineering Checklist:\n"
            "- typed config\n- tests\n- lint/type-check\n- CI\n\n"
            "Next Steps:\n"
            "Integrate business tools, add auth, tracing, and domain-specific agents."
        )

