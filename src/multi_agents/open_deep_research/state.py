# src/multi_agents/open_deep_research/state.py

import operator
from typing import Annotated, Optional, List, Dict
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState

# -------- Structured outputs --------
class ConductResearch(BaseModel):
    research_topic: str = Field(
        description=(
            "The topic to research. Should be a single topic, and should be "
            "described in high detail (at least a paragraph)."
        )
    )

class ResearchComplete(BaseModel):
    """Signal that research is complete."""

class Summary(BaseModel):
    summary: str
    key_excerpts: str

class ClarifyWithUser(BaseModel):
    need_clarification: bool = Field(description="Whether a clarifying question is needed.")
    question: str = Field(description="Question to ask the user.")
    verification: str = Field(description="Confirmation message before starting research.")

class ResearchQuestion(BaseModel):
    research_brief: str = Field(description="Guiding research brief/question.")

# -------- Reducer --------
def override_reducer(current_value, new_value):
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    return operator.add(current_value, new_value)

# -------- State definitions --------
class AgentInputState(MessagesState):
    """Input state is only 'messages' (via MessagesState)."""

class AgentState(MessagesState):
    """
    Deep-research main state. NOTE: Annotations only — no defaults here.
    Initialize values when creating the state.
    """
    # Supervisor planning/control within the subgraph
    supervisor_messages: Annotated[List[MessageLikeRepresentation], override_reducer]
    research_brief: Optional[str]

    # Notes
    raw_notes: Annotated[List[str], override_reducer]
    notes: Annotated[List[str], override_reducer]

    # Final synthesis
    final_report: str

    # Optional / extra
    image_url: Optional[str]
    serp_calls_used: int

    # Human-in-the-loop (candidate disambiguation inside subgraph)
    awaiting_user_confirmation: bool
    candidate_options: Annotated[List[Dict], override_reducer]
    selected_candidate: Optional[Dict]

class SupervisorState(TypedDict, total=False):
    supervisor_messages: Annotated[List[MessageLikeRepresentation], override_reducer]
    research_brief: str
    notes: Annotated[List[str], override_reducer]
    research_iterations: int
    raw_notes: Annotated[List[str], override_reducer]

class ResearcherState(TypedDict, total=False):
    researcher_messages: Annotated[List[MessageLikeRepresentation], operator.add]
    tool_call_iterations: int
    research_topic: str
    compressed_research: str
    raw_notes: Annotated[List[str], override_reducer]

class ResearcherOutputState(BaseModel):
    compressed_research: str
    raw_notes: List[str]
