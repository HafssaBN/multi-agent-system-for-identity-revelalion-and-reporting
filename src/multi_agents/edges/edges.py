from multi_agents.graph import GraphState

def should_continue_after_airbnb_analysis(state: GraphState) -> str:
    """Decide next step after Airbnb analysis."""
    if state.get("errors"):
        return "error"
    if state.get("airbnb_host_info"):
        return "extract_keywords"
    return "error"

def should_continue_after_keyword_extraction(state: GraphState) -> str:
    """Decide next step after keyword extraction."""
    if state.get("errors"):
        return "error"
    if state.get("search_keywords"):
        return "search_instagram"
    return "error"

def should_continue_after_instagram_search(state: GraphState) -> str:
    """Decide next step after Instagram search."""
    if state.get("errors"):
        return "error"
    if state.get("instagram_profiles"):
        return "match_profiles"
    return "generate_report"  # Continue even if no profiles found

def should_continue_after_profile_matching(state: GraphState) -> str:
    """Decide next step after profile matching."""
    return "generate_report"