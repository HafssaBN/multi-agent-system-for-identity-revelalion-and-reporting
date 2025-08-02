from typing import TypedDict, List, Dict, Any, Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    original_query: str
    plan: List[Dict[str, Any]]
    past_steps: List[Dict[str, Any]]
    aggregated_results: Dict[str, Any]
    final_report: str
    messages: Annotated[List[Dict[str, Any]], add_messages]