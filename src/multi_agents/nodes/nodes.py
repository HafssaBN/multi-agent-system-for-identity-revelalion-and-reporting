import re
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from multi_agents.tools.airbnb_tools import (
    get_airbnb_profile_details,
    get_airbnb_profile_listings,
    get_airbnb_profile_reviews,
    get_listing_details
)
from multi_agents.tools.insta_tools import (
    get_instagram_user_id,
    get_instagram_user_info,
    get_instagram_user_posts
)
from multi_agents.constants.constants import (
    OPENROUTER_API_KEY, DEFAULT_MODEL, TEMPERATURE, MAX_TOKENS
)
from multi_agents.graph import GraphState, InstagramProfile
from multi_agents.prompts.prompts import (
    AIRBNB_ANALYZER_PROMPT,
    KEYWORD_EXTRACTOR_PROMPT,
    INSTAGRAM_SEARCHER_PROMPT,
    PROFILE_MATCHER_PROMPT,
    REPORT_GENERATOR_PROMPT
)
##################################
class AirbnbAnalyzerNode:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=DEFAULT_MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
    
    def __call__(self, state: GraphState) -> Dict[str, Any]:
        """Analyzes Airbnb profile/listing to extract host information."""
        try:
            airbnb_url = state["airbnb_url"]
            
            # Determine if it's a profile URL or listing URL
            if "/users/show/" in airbnb_url:
                profile_url = airbnb_url
            elif "/rooms/" in airbnb_url:
                # Extract listing details first to get host profile
                listing_details = get_listing_details(airbnb_url)
                if not listing_details or not listing_details.get("host_info"):
                    return {**state, "errors": state.get("errors", []) + ["Failed to extract host info from listing"]}
                profile_url = listing_details["host_info"].get("profile_url")
                if not profile_url:
                    return {**state, "errors": state.get("errors", []) + ["No host profile URL found in listing"]}
            else:
                return {**state, "errors": state.get("errors", []) + ["Invalid Airbnb URL format"]}
            
            # Get profile details
            profile_details = get_airbnb_profile_details(profile_url)
            listings = get_airbnb_profile_listings(profile_url)
            reviews = get_airbnb_profile_reviews(profile_url)
            
            if not profile_details:
                return {**state, "errors": state.get("errors", []) + ["Failed to extract Airbnb profile details"]}
            
            return {
                **state,
                "airbnb_profile_url": profile_url,
                "airbnb_host_info": profile_details,
                "airbnb_listings": listings or [],
                "airbnb_reviews": reviews or [],
                "current_step": "airbnb_analyzed"
            }
            
        except Exception as e:
            return {**state, "errors": state.get("errors", []) + [f"Airbnb analysis error: {str(e)}"]}

class KeywordExtractorNode:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=DEFAULT_MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
    
    def __call__(self, state: GraphState) -> Dict[str, Any]:
        """Extracts search keywords from Airbnb data for Instagram search."""
        try:
            host_info = state["airbnb_host_info"]
            listings = state["airbnb_listings"]
            reviews = state["airbnb_reviews"]
            user_query = state["query"]
            
            prompt = ChatPromptTemplate.from_template(KEYWORD_EXTRACTOR_PROMPT)
            
            response = self.llm.invoke(prompt.format(
                host_name=host_info.get("name", ""),
                host_bio=host_info.get("bio", ""),
                host_details=str(host_info.get("about_details", [])),
                listings_info=str(listings[:3]),  # First 3 listings
                reviews_sample=str(reviews[:5]),  # First 5 reviews
                user_query=user_query
            ))
            
            # Extract keywords from LLM response
            content = response.content
            search_keywords = self._extract_keywords_from_response(content, "SEARCH_KEYWORDS")
            location_keywords = self._extract_keywords_from_response(content, "LOCATION_KEYWORDS")
            
            return {
                **state,
                "search_keywords": search_keywords,
                "location_keywords": location_keywords,
                "current_step": "keywords_extracted"
            }
            
        except Exception as e:
            return {**state, "errors": state.get("errors", []) + [f"Keyword extraction error: {str(e)}"]}
    
    def _extract_keywords_from_response(self, content: str, section: str) -> List[str]:
        """Extract keywords from LLM response."""
        pattern = f"{section}:(.*?)(?=\\n[A-Z_]+:|$)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            keywords_text = match.group(1).strip()
            return [kw.strip().strip('-').strip() for kw in keywords_text.split('\n') if kw.strip() and not kw.strip().startswith('-')]
        return []

class InstagramSearcherNode:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=DEFAULT_MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
    
    def __call__(self, state: GraphState) -> Dict[str, Any]:
        """Searches for Instagram profiles using extracted keywords."""
        try:
            search_keywords = state["search_keywords"]
            location_keywords = state["location_keywords"]
            
            instagram_profiles = []
            searched_usernames = set()
            
            # Search using different keyword combinations
            all_keywords = search_keywords + location_keywords
            
            for keyword in all_keywords[:10]:  # Limit searches
                if not keyword or len(keyword) < 3:
                    continue
                    
                # Try to find user by username
                user_id = get_instagram_user_id(keyword)
                if user_id and keyword not in searched_usernames:
                    user_info = get_instagram_user_info(keyword)
                    if user_info:
                        posts = get_instagram_user_posts(user_id, limit=12)
                        profile = InstagramProfile(
                            username=keyword,
                            user_id=user_id,
                            full_name=user_info.get("full_name"),
                            bio=user_info.get("description"),
                            followers=user_info.get("followers", 0),
                            following=user_info.get("following", 0),
                            is_verified=user_info.get("is_verified", False),
                            profile_pic_url=user_info.get("profile_pic_url"),
                            external_url=user_info.get("external_url"),
                            posts=posts or [],
                            confidence_score=0.0,  # Will be calculated in next node
                            match_reasons=[]
                        )
                        instagram_profiles.append(profile)
                        searched_usernames.add(keyword)
            
            return {
                **state,
                "instagram_profiles": instagram_profiles,
                "current_step": "instagram_searched"
            }
            
        except Exception as e:
            return {**state, "errors": state.get("errors", []) + [f"Instagram search error: {str(e)}"]}

class ProfileMatcherNode:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=DEFAULT_MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
    
    def __call__(self, state: GraphState) -> Dict[str, Any]:
        """Analyzes Instagram profiles to match with Airbnb host."""
        try:
            airbnb_host = state["airbnb_host_info"]
            airbnb_listings = state["airbnb_listings"]
            instagram_profiles = state["instagram_profiles"]
            
            analyzed_profiles = []
            
            for profile in instagram_profiles:
                prompt = ChatPromptTemplate.from_template(PROFILE_MATCHER_PROMPT)
                
                response = self.llm.invoke(prompt.format(
                    airbnb_name=airbnb_host.get("name", ""),
                    airbnb_bio=airbnb_host.get("bio", ""),
                    airbnb_details=str(airbnb_host.get("about_details", [])),
                    airbnb_listings=str(airbnb_listings[:2]),
                    instagram_username=profile.username,
                    instagram_name=profile.full_name or "",
                    instagram_bio=profile.bio or "",
                    instagram_followers=profile.followers,
                    instagram_verified=profile.is_verified,
                    instagram_posts=str(profile.posts[:3])
                ))
                
                # Parse LLM response for confidence score and reasons
                content = response.content
                confidence_score = self._extract_confidence_score(content)
                match_reasons = self._extract_match_reasons(content)
                
                profile.confidence_score = confidence_score
                profile.match_reasons = match_reasons
                analyzed_profiles.append(profile)
            
            # Sort by confidence score
            analyzed_profiles.sort(key=lambda x: x.confidence_score, reverse=True)
            
            return {
                **state,
                "instagram_profiles": analyzed_profiles,
                "current_step": "profiles_matched"
            }
            
        except Exception as e:
            return {**state, "errors": state.get("errors", []) + [f"Profile matching error: {str(e)}"]}
    
    def _extract_confidence_score(self, content: str) -> float:
        """Extract confidence score from LLM response."""
        pattern = r"CONFIDENCE_SCORE:\s*(\d+(?:\.\d+)?)"
        match = re.search(pattern, content)
        if match:
            return float(match.group(1)) / 100.0  # Convert percentage to decimal
        return 0.0
    
    def _extract_match_reasons(self, content: str) -> List[str]:
        """Extract match reasons from LLM response."""
        pattern = r"MATCH_REASONS:(.*?)(?=\n[A-Z_]+:|$)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            reasons_text = match.group(1).strip()
            return [reason.strip().strip('-').strip() for reason in reasons_text.split('\n') if reason.strip() and not reason.strip().startswith('-')]
        return []

class ReportGeneratorNode:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=DEFAULT_MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
    
    def __call__(self, state: GraphState) -> Dict[str, Any]:
        """Generates final report with Instagram profiles and analysis."""
        try:
            airbnb_host = state["airbnb_host_info"]
            instagram_profiles = state["instagram_profiles"]
            user_query = state["query"]
            
            # Filter profiles above confidence threshold
            high_confidence_profiles = [p for p in instagram_profiles if p.confidence_score >= 0.3]
            
            prompt = ChatPromptTemplate.from_template(REPORT_GENERATOR_PROMPT)
            
            response = self.llm.invoke(prompt.format(
                user_query=user_query,
                airbnb_host_name=airbnb_host.get("name", ""),
                airbnb_profile_url=state["airbnb_profile_url"],
                total_profiles_found=len(instagram_profiles),
                high_confidence_count=len(high_confidence_profiles),
                top_profiles=str(high_confidence_profiles[:5])
            ))
            
            final_report = {
                "summary": response.content,
                "airbnb_host_info": airbnb_host,
                "total_instagram_profiles_found": len(instagram_profiles),
                "high_confidence_matches": len(high_confidence_profiles),
                "top_matches": [
                    {
                        "username": p.username,
                        "full_name": p.full_name,
                        "confidence_score": p.confidence_score,
                        "match_reasons": p.match_reasons,
                        "instagram_url": f"https://instagram.com/{p.username}",
                        "followers": p.followers,
                        "is_verified": p.is_verified,
                        "bio": p.bio
                    } for p in high_confidence_profiles[:10]
                ]
            }
            
            return {
                **state,
                "final_report": final_report,
                "current_step": "completed"
            }
            
        except Exception as e:
            return {**state, "errors": state.get("errors", []) + [f"Report generation error: {str(e)}"]}
