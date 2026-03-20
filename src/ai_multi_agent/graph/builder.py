from langgraph.graph import END, START, StateGraph

from ai_multi_agent.agents.critic import CriticAgent
from ai_multi_agent.agents.planner import PlannerAgent
from ai_multi_agent.agents.researcher import ResearchAgent
from ai_multi_agent.agents.synthesizer import SynthesizerAgent
from ai_multi_agent.graph.state import WorkflowState
from ai_multi_agent.llm.providers import LLMClient


def build_workflow_graph(llm: LLMClient) -> object:
    planner = PlannerAgent(
        name="planner",
        system_prompt="You are a senior planning specialist.",
        llm=llm,
    )
    researcher = ResearchAgent(
        name="researcher",
        system_prompt="You are a systems design and implementation specialist.",
        llm=llm,
    )
    critic = CriticAgent(
        name="critic",
        system_prompt="You are a rigorous reviewer focused on quality and risk.",
        llm=llm,
    )
    synthesizer = SynthesizerAgent(
        name="synthesizer",
        system_prompt="You are a solution architect producing executive-ready outputs.",
        llm=llm,
    )

    graph = StateGraph(WorkflowState)
    graph.add_node("planner", planner.run)
    graph.add_node("researcher", researcher.run)
    graph.add_node("critic", critic.run)
    graph.add_node("synthesizer", synthesizer.run)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "researcher")
    graph.add_edge("researcher", "critic")
    graph.add_conditional_edges(
        "critic",
        _route_after_review,
        {
            "researcher": "researcher",
            "synthesizer": "synthesizer",
        },
    )
    graph.add_edge("synthesizer", END)
    return graph.compile()


def _route_after_review(state: WorkflowState) -> str:
    if not state.get("approved", False) and state.get("revision_count", 0) <= state.get(
        "max_revisions", 0
    ):
        return "researcher"
    return "synthesizer"
