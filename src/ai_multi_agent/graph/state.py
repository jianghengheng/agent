import operator
from typing import Annotated, Literal

from typing_extensions import TypedDict


class ConversationMessage(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str


class WorkflowState(TypedDict, total=False):
    task: str
    context: str
    messages: list[ConversationMessage]
    plan: str
    research: str
    critique: str
    final_answer: str
    approved: bool
    revision_count: int
    max_revisions: int
    trace: Annotated[list[str], operator.add]
