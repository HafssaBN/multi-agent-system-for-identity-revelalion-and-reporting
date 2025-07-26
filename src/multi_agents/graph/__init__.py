from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from dataclasses import dataclass

@dataclass
class InstagramProfile:
    username: str
    user_id: str
    full_name: Optional[str]
    bio: Optional[str]
    followers: int
    following: int
    is_verified: bool
    profile_pic_url: Optional[str]
    external_url: Optional[str]
    posts: List[Dict[str, Any]]
    confidence_score: float
    match_reasons: List[str]

class GraphState(TypedDict):
    # Input
    airbnb_url: str
    query: str
    
    # Airbnb Data
    airbnb_profile_url: Optional[str]
    airbnb_host_info: Optional[Dict[str, Any]]
    airbnb_listings: Optional[List[Dict[str, Any]]]
    airbnb_reviews: Optional[List[Dict[str, Any]]]
    
    # Search Keywords
    search_keywords: List[str]
    location_keywords: List[str]
    
    # Instagram Data
    instagram_profiles: List[InstagramProfile]
    
    # Analysis Results
    final_report: Dict[str, Any]
    
    # Control
    current_step: str
    errors: List[str]