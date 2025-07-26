from langgraph.graph import StateGraph, END
from multi_agents.graph import GraphState
from multi_agents.nodes.nodes import (
    AirbnbAnalyzerNode,
    KeywordExtractorNode,
    InstagramSearcherNode,
    ProfileMatcherNode,
    ReportGeneratorNode
)
from multi_agents.edges.edges import (
    should_continue_after_airbnb_analysis,
    should_continue_after_keyword_extraction,
    should_continue_after_instagram_search,
    should_continue_after_profile_matching
)

def create_multi_agent_graph():
    """Create the multi-agent graph for Airbnb host identity discovery."""
    
    # Initialize nodes
    airbnb_analyzer = AirbnbAnalyzerNode()
    keyword_extractor = KeywordExtractorNode()
    instagram_searcher = InstagramSearcherNode()
    profile_matcher = ProfileMatcherNode()
    report_generator = ReportGeneratorNode()
    
    # Create the graph
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("analyze_airbnb", airbnb_analyzer)
    workflow.add_node("extract_keywords", keyword_extractor)
    workflow.add_node("search_instagram", instagram_searcher)
    workflow.add_node("match_profiles", profile_matcher)
    workflow.add_node("generate_report", report_generator)
    workflow.add_node("error", lambda state: {**state, "current_step": "error"})
    
    # Set entry point
    workflow.set_entry_point("analyze_airbnb")
    
    # Add edges
    workflow.add_conditional_edges(
        "analyze_airbnb",
        should_continue_after_airbnb_analysis,
        {
            "extract_keywords": "extract_keywords",
            "error": "error"
        }
    )
    
    workflow.add_conditional_edges(
        "extract_keywords",
        should_continue_after_keyword_extraction,
        {
            "search_instagram": "search_instagram",
            "error": "error"
        }
    )
    
    workflow.add_conditional_edges(
        "search_instagram",
        should_continue_after_instagram_search,
        {
            "match_profiles": "match_profiles",
            "generate_report": "generate_report",
            "error": "error"
        }
    )
    
    workflow.add_conditional_edges(
        "match_profiles",
        should_continue_after_profile_matching,
        {
            "generate_report": "generate_report"
        }
    )
    
    # End points
    workflow.add_edge("generate_report", END)
    workflow.add_edge("error", END)
    
    return workflow.compile()