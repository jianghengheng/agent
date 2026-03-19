import operator
from typing import Annotated

from typing_extensions import TypedDict


class WorkflowState(TypedDict, total=False):
    task: str
    context: str
    plan: str
    research: str
    critique: str
    final_answer: str
    approved: bool
    revision_count: int
    max_revisions: int
    trace: Annotated[list[str], operator.add]

