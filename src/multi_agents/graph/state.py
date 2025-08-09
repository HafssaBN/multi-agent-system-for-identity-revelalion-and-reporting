from typing import TypedDict, List, Dict, Any, Annotated, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage # Use BaseMessage for broader compatibility

class AgentState(TypedDict):
    original_query: str
    plan: List[Dict[str, Any]]
    past_steps: List[Dict[str, Any]]
    aggregated_results: Dict[str, Any]
    final_report: str
    messages: Annotated[list, add_messages]

    # --- ADD THESE NEW KEYS ---
    # These are transient states to pass data between worker and supervisor
    last_step_result: Optional[Dict[str, Any]]
    last_step_message: Optional[BaseMessage]