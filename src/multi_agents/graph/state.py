# src/multi_agents/graph/state.py

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    # User request
    original_query: str

    # Planning & history
    plan: List[Dict[str, Any]]
    past_steps: List[Dict[str, Any]]

    # Aggregated outputs from workers
    aggregated_results: Dict[str, Any]

    # Final report (filled by ReportSynthesizer)
    final_report: str

    # Conversation buffer for the graph
    messages: Annotated[List[BaseMessage], add_messages]

    # Transient values passed between nodes
    last_step_result: Optional[Dict[str, Any]]
    last_step_message: Optional[BaseMessage]

    # Human-in-the-loop (HITL)
    awaiting_user_confirmation: bool
    candidate_options: List[Dict[str, Any]]
    selected_candidate: Optional[Dict[str, Any]]
