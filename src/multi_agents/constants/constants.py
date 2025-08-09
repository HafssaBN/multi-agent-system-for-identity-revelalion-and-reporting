import os
from typing import List, Dict
from dotenv import load_dotenv
from urllib.parse import unquote
load_dotenv()


class Constants:
    #OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    #OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    #DEFAULT_MODEL = "openai/gpt-4o"
    #MAX_ITERATIONS = 10

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    MODEL_FOR_WORKER = "llama-3.3-70b-versatile"
    MODEL = "llama-3.3-70b-versatile"
    
    # Tool names
    TOOLS = {
        "airbnb": ["get_airbnb_profile_details", "get_airbnb_profile_places_visited", 
                  "get_airbnb_profile_listings", "get_airbnb_profile_reviews", "get_listing_details"],
        "instagram": ["get_instagram_user_id", "get_instagram_user_info", 
                     "get_instagram_user_followers", "get_instagram_user_following",
                     "get_instagram_user_posts", "download_image"],
        "search": ["tavily_search", "google_search", "web_scraper"],
        "vision": ["compare_profile_pictures"]
    }


# API Keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# LLM Configuration
DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"
TEMPERATURE = 0.1
MAX_TOKENS = 4000000000

# Search Configuration
MAX_INSTAGRAM_PROFILES = 10
CONFIDENCE_THRESHOLD = 0.3




# === Your Instagram cookies here (replace with valid values) ===
COOKIES = {
    "sessionid": unquote(os.getenv("INSTA_SESSIONID", "")),
    "ds_user_id": os.getenv("INSTA_DS_USER_ID", ""),
    "csrftoken": os.getenv("INSTA_CSRFTOKEN", ""),
}


# List of user agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_2) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:109.0) Gecko/20100101 Firefox/115.0",
    ]

AIRBNB_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]


SELENIUM_HOST = "http://localhost:4444/wd/hub"


TWITTER_USER_1 = os.getenv("TWITTER_USER_1", "")
TWITTER_PASS_1 = os.getenv("TWITTER_PASS_1", "")