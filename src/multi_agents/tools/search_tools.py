import random
import logging
from typing import Dict, List, Union, Optional , Any
from serpapi import GoogleSearch, BaiduSearch 
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.tools import tool
import requests 

from selenium import webdriver

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ..constants.constants import Constants, USER_AGENTS , SELENIUM_HOST # Ensure USER_AGENTS is imported
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


from .serp_client import search_tools_instance
from .webscraping import advanced_retriver
class SearchTools:
    """
    A class that holds the implementation for search tools.
    This keeps the API and execution logic contained in one place.
    """
    def __init__(self):
        self.api_key = Constants.SERPAPI_API_KEY
        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY is not set in your .env file. Search tools cannot function.")

    def _execute_search(self, params: Dict) -> Union[Dict, List]:
        """A private helper method to execute a search with robust error handling."""
        try:
            params['api_key'] = self.api_key
            # --- FIX: Inject a random user_agent into SerpApi calls ---
            params['user_agent'] = random.choice(USER_AGENTS)
            
            # Baidu has a specific client, all others use the general GoogleSearch client
            if params.get('engine') == 'baidu':
                search = BaiduSearch(params)
            else:
                search = GoogleSearch(params)
            
            results = search.get_dict()

            if "error" in results:
                logger.error(f"SerpApi Error for engine {params.get('engine')}: {results['error']}")
                return {"error": results["error"]}
            
            return results

        except Exception as e:
            logger.error(f"An unexpected error occurred during SerpApi search: {e}", exc_info=True)
            return {"error": f"An unexpected exception occurred: {str(e)}"}

# --- Initialize a single instance of the class ---
search_tools_instance = SearchTools()

# --- General Web Search ---

@tool
def google_search(query: str, location: Optional[str] = None) -> Union[List[Dict], Dict]:
    """
    Performs a standard Google search. Best for general queries, finding articles, and official websites.
    Args:
        query (str): The search query.
        location (str, optional): The geographic location for the search (e.g., "Austin, Texas, United States"). Defaults to None.
    """
    logger.info(f"PERFORMING GOOGLE SEARCH FOR: '{query}'")
    params = {"engine": "google", "q": query}
    if location:
        params["location"] = location
    try:
        api_key = Constants.SERPAPI_API_KEY
        if not api_key:
          raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")
    
        results = search_tools_instance._execute_search(params)
        if isinstance(results, dict) and "error" not in results:
            organic_results = results.get("organic_results", [])
            logger.info(f"Google search returned {len(organic_results)} organic results.")
            return organic_results
        else:
            logger.warning(f"Google search returned an error or no organic results: {results}")
            return results
    except Exception as e:
        error_msg = f"Google search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}

@tool
def bing_search(query: str) -> Union[List[Dict], Dict]:
    """Performs a web search using the Bing search engine. A good alternative to Google for diverse results."""
    logger.info(f"PERFORMING BING SEARCH FOR: '{query}'")
    try:
        api_key = Constants.SERPAPI_API_KEY
        if not api_key:
          raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")
    
        results = search_tools_instance._execute_search({"engine": "bing", "q": query})
        if isinstance(results, dict) and "error" not in results:
            organic_results = results.get("organic_results", [])
            logger.info(f"Bing search returned {len(organic_results)} organic results.")
            return organic_results
        else:
            logger.warning(f"Bing search returned an error or no organic results: {results}")
            return results
    except Exception as e:
        error_msg = f"Bing search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}
        
@tool
def duckduckgo_search(query: str) -> Union[List[Dict], Dict]:
    """Performs a web search using the privacy-focused DuckDuckGo search engine."""
    logger.info(f"PERFORMING DUCKDUCKGO SEARCH FOR: '{query}'")
    try:
        api_key = Constants.SERPAPI_API_KEY
        if not api_key:
          raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")
    
        results = search_tools_instance._execute_search({"engine": "duckduckgo", "q": query})
        if isinstance(results, dict) and "error" not in results:
            organic_results = results.get("results", []) # Note: Key is 'results' not 'organic_results'
            logger.info(f"DuckDuckGo search returned {len(organic_results)} results.")
            return organic_results
        else:
            logger.warning(f"DuckDuckGo search returned an error or no results: {results}")
            return results
    except Exception as e:
        error_msg = f"DuckDuckGo search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}

@tool
def yahoo_search(query: str) -> Union[List[Dict], Dict]:
    """Performs a web search using the Yahoo search engine."""
    logger.info(f"PERFORMING YAHOO SEARCH FOR: '{query}'")
    try:
        api_key = Constants.SERPAPI_API_KEY
        if not api_key:
          raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")
    
        results = search_tools_instance._execute_search({"engine": "yahoo", "p": query})
        if isinstance(results, dict) and "error" not in results:
            organic_results = results.get("organic_results", [])
            logger.info(f"Yahoo search returned {len(organic_results)} organic results.")
            return organic_results
        else:
            logger.warning(f"Yahoo search returned an error or no organic results: {results}")
            return results
    except Exception as e:
        error_msg = f"Yahoo search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}

# --- Regional Web Search ---

@tool
def yandex_search(query: str) -> Union[List[Dict], Dict]:
    """Performs a web search using Yandex. Crucial for topics and entities related to Russia and Eastern Europe."""
    logger.info(f"PERFORMING YANDEX SEARCH FOR: '{query}'")
    try:
        api_key = Constants.SERPAPI_API_KEY
        if not api_key:
          raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")
    
        results = search_tools_instance._execute_search({"engine": "yandex", "text": query})
        if isinstance(results, dict) and "error" not in results:
            organic_results = results.get("organic_results", [])
            logger.info(f"Yandex search returned {len(organic_results)} organic results.")
            return organic_results
        else:
            logger.warning(f"Yandex search returned an error or no organic results: {results}")
            return results
    except Exception as e:
        error_msg = f"Yandex search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}

@tool
def baidu_search(query: str) -> Union[List[Dict], Dict]:
    """Performs a web search using Baidu. Crucial for topics and entities related to China."""
    logger.info(f"PERFORMING BAIDU SEARCH FOR: '{query}'")
    try:
        api_key = Constants.SERPAPI_API_KEY
        if not api_key:
          raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")
    
        results = search_tools_instance._execute_search({"engine": "baidu", "q": query})
        if isinstance(results, dict) and "error" not in results:
            organic_results = results.get("organic_results", [])
            logger.info(f"Baidu search returned {len(organic_results)} organic results.")
            return organic_results
        else:
            logger.warning(f"Baidu search returned an error or no organic results: {results}")
            return results
    except Exception as e:
        error_msg = f"Baidu search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}

# --- Image Search ---

@tool
def google_image_search(query: str) -> Union[List[Dict], Dict]:
    """Performs a Google Image search. Useful for finding images of a person, place, or thing."""
    logger.info(f"PERFORMING GOOGLE IMAGE SEARCH FOR: '{query}'")
    try:
        api_key = Constants.SERPAPI_API_KEY
        if not api_key:
          raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")
    
        results = search_tools_instance._execute_search({"engine": "google_images", "q": query})
        if isinstance(results, dict) and "error" not in results:
            images_results = results.get("images_results", [])
            logger.info(f"Google Image search returned {len(images_results)} image results.")
            return images_results
        else:
            logger.warning(f"Google Image search returned an error or no image results: {results}")
            return results
    except Exception as e:
        error_msg = f"Google Image search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}

@tool
def bing_images_search(query: str) -> Union[List[Dict], Dict]:
    """Performs an image search using the Bing Images engine."""
    logger.info(f"PERFORMING BING IMAGES SEARCH FOR: '{query}'")
    try:
        api_key = Constants.SERPAPI_API_KEY
        if not api_key:
          raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")
    
        results = search_tools_instance._execute_search({"engine": "bing_images", "q": query})
        if isinstance(results, dict) and "error" not in results:
            images_results = results.get("images_results", [])
            logger.info(f"Bing Images search returned {len(images_results)} image results.")
            return images_results
        else:
            logger.warning(f"Bing Images search returned an error or no image results: {results}")
            return results
    except Exception as e:
        error_msg = f"Bing Images search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}

@tool(description="Google Lens visual search on a given image URL.")
def google_lens_search(image_url: str) -> Dict:
    logger.info(f"PERFORMING GOOGLE LENS SEARCH FOR IMAGE: {image_url}")
    params = {"engine": "google_lens", "url": image_url,"num": 50, "api_key": Constants.SERPAPI_API_KEY}
    data = GoogleSearch(params).get_dict()

    matches = data.get("visual_matches") or []
    out = []
    for m in matches:
        out.append({
            "title": m.get("title"),
            "link": m.get("link"),
            "thumbnail": m.get("thumbnail"),
            "source": m.get("source"),
        })
    result = {
        "engine": "google_lens",
        "best_guess": data.get("best_guess_label"),
        "matches": out,
    }
    logger.info("Google Lens best_guess=%r, matches=%d", data.get("best_guess_label"), len(out))
    return result


        
@tool(description="Reverse image via Google Images on a given image URL.")
def google_reverse_image_search(image_url: str) -> Dict:
    logger.info(f"PERFORMING GOOGLE REVERSE IMAGE SEARCH FOR: {image_url}")
    params = {"engine": "google_reverse_image", "image_url": image_url,"num": 50,  "api_key": Constants.SERPAPI_API_KEY}
    data = GoogleSearch(params).get_dict()

    # Normalize keys
    matches = data.get("inline_images") or data.get("image_results") or []
    out = []
    for m in matches:
        out.append({
            "title": m.get("title"),
            "link": m.get("link") or m.get("source"),
            "thumbnail": m.get("thumbnail"),
            "source": m.get("source"),
        })
    result = {
        "engine": "google_reverse_image",
        "best_guess": data.get("best_guess_label"),
        "matches": out,
    }
    logger.info(f"Google Reverse Image normalized matches: {len(out)}")
    return result




# --- Specialized Search ---

@tool
def google_maps_search(query: str, lat_long: Optional[str] = None) -> Union[List[Dict], Dict]:
    """
    Searches for places on Google Maps.
    Args:
        query (str): The search query (e.g., 'Coffee', 'Restaurants near Eiffel Tower').
        lat_long (str, optional): The latitude/longitude for the search center, formatted as '@lat,long,zoom' (e.g., '@40.7455,-74.0083,14z').
    """
    # ✅ Make sure API key is present
    api_key = Constants.SERPAPI_API_KEY
    if not api_key:
        raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")

    logger.info(f"PERFORMING GOOGLE MAPS SEARCH FOR: '{query}'")
    params = {"engine": "google_maps", "q": query}
    if lat_long:
        params["ll"] = lat_long
    try:
        results = search_tools_instance._execute_search(params)
        if isinstance(results, dict) and "error" not in results:
            local_results = results.get("local_results", [])
            logger.info(f"Google Maps search returned {len(local_results)} local results.")
            return local_results
        else:
            logger.warning(f"Google Maps search returned an error or no local results: {results}")
            return results
    except Exception as e:
        error_msg = f"Google Maps search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}

@tool
def google_hotels_search(query: str, check_in_date: str, check_out_date: str, adults: int = 1) -> Union[List[Dict], Dict]:
    """
    Searches for hotels on Google Hotels. Crucial for travel planning and finding accommodations.
    Args:
        query (str): The destination or hotel name (e.g., 'Bali Resorts', 'Hilton New York').
        check_in_date (str): The check-in date in YYYY-MM-DD format.
        check_out_date (str): The check-out date in YYYY-MM-DD format.
        adults (int): The number of adults.
    """
    api_key = Constants.SERPAPI_API_KEY
    if not api_key:
        raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")
    logger.info(f"PERFORMING GOOGLE HOTELS SEARCH FOR: '{query}' from {check_in_date} to {check_out_date}")
    params = {"engine": "google_hotels", "q": query, "check_in_date": check_in_date, "check_out_date": check_out_date, "adults": str(adults)}
    try:
        results = search_tools_instance._execute_search(params)
        if isinstance(results, dict) and "error" not in results:
            properties = results.get("properties", [])
            logger.info(f"Google Hotels search returned {len(properties)} properties.")
            return properties
        else:
            logger.warning(f"Google Hotels search returned an error or no properties: {results}")
            return results
    except Exception as e:
        error_msg = f"Google Hotels search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}

@tool
def google_news_search(query: str) -> Union[List[Dict], Dict]:
    """Searches Google News. Returns a labeled dict, not a bare list."""
    logger.info(f"PERFORMING GOOGLE NEWS SEARCH FOR: '{query}'")
    try:
        api_key = Constants.SERPAPI_API_KEY
        if not api_key:
            raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")

        results = search_tools_instance._execute_search({"engine": "google_news", "q": query})
        if isinstance(results, dict) and "error" not in results:
            news_results = results.get("news_results", [])
            logger.info(f"Google News search returned {len(news_results)} news results.")
            # ⬇️ IMPORTANT: return a dict so downstream can recognize 'google_news'
            return {"engine": "google_news", "news_results": news_results}
        else:
            logger.warning(f"Google News search returned an error or no news results: {results}")
            return results
    except Exception as e:
        error_msg = f"Google News search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}


@tool
def yelp_search(description: str, location: str) -> Union[List[Dict], Dict]:
    """
    Searches for businesses on Yelp. Very useful for finding information on local businesses, restaurants, and services.
    Args:
        description (str): The type of business to search for (e.g., 'Coffee', 'Pizza').
        location (str): The location to search within (e.g., 'New York, NY', '78704').
    """
    logger.info(f"PERFORMING YELP SEARCH FOR: '{description}' in '{location}'")
    params = {"engine": "yelp", "find_desc": description, "find_loc": location}
    try:
        api_key = Constants.SERPAPI_API_KEY
        if not api_key:
          raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")
    
        results = search_tools_instance._execute_search(params)
        if isinstance(results, dict) and "error" not in results:
            organic_results = results.get("organic_results", [])
            logger.info(f"Yelp search returned {len(organic_results)} organic results.")
            return organic_results
        else:
            logger.warning(f"Yelp search returned an error or no organic results: {results}")
            return results
    except Exception as e:
        error_msg = f"Yelp search failed for '{description}' in '{location}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}
        
# --- Utility ---

@tool
def web_scraper(url: str) -> Dict[str, str]:
    """
    A robust, browser-powered web scraper that can handle JavaScript-heavy websites.
    It reads the main text content from a given URL.
    Args:
        url (str): The URL of the webpage to scrape.
    """
    logger.info(f"🚀 Activating browser-powered scraper for URL: {url}")
    
    # --- Setup a "headless" Chrome browser ---
    # Headless means it runs in the background without a visible window.
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Rotate user agents to appear more human-like
    if USER_AGENTS:
        chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")

    driver = None
    try:
        # Connect to your Selenium Docker container
        
        service = Service(r"C:\Windows\chromedriver.exe")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)

        # --- Wait intelligently for the page to load ---
        # We wait up to 15 seconds for the main content (the <body> tag) to be present.
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # --- Extract cleaner text ---
        # Instead of all page content, we grab the text from the main body, which is usually cleaner.
        body_element = driver.find_element(By.TAG_NAME, "body")
        page_text = body_element.text

        if not page_text:
            content = "No text content found on the page after loading."
            logger.warning(f"No text content found at {url}")
        else:
            content = page_text
            logger.info(f"Successfully scraped {len(content)} characters from {url}")

        return {"url": url, "content": content[:8000]} # Increased limit slightly for richer context

    except Exception as e:
        error_msg = f"Browser-powered scraping failed for URL '{url}': {e}"
        logger.error(error_msg)
        return {"url": url, "content": "", "error": error_msg}
    finally:
        # --- CRITICAL: Always close the browser ---
        # This prevents "zombie" browser processes from consuming memory.
        if driver:
            driver.quit()
@tool
def youtube_search(query: str) -> Union[List[Dict], Dict]:
    """
    Searches for videos on YouTube. Useful for finding interviews, vlogs, tutorials, or user-created content about a topic.
    Args:
        query (str): The search query.
    """
    api_key = Constants.SERPAPI_API_KEY
    if not api_key:
          raise ValueError("Missing SERPAPI_API_KEY. Please add it to your .env file.")
    
    logger.info(f"PERFORMING YOUTUBE SEARCH FOR: '{query}'")
    params = {"engine": "youtube", "search_query": query}
    try:
        results = search_tools_instance._execute_search(params)
        if isinstance(results, dict) and "error" not in results:
            video_results = results.get("video_results", [])
            logger.info(f"YouTube search returned {len(video_results)} video results.")
            return video_results
        else:
            logger.warning(f"YouTube search returned an error or no video results: {results}")
            return results
    except Exception as e:
        error_msg = f"YouTube search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}

@tool
def tavily_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Uses Tavily API to perform a fast and factual web search.
    Args:
        query (str): Search query string.
        max_results (int): Maximum number of results to return. Default is 5.
    Returns:
        Dict with search results or error.
    """
    logger.info(f"PERFORMING TAVILY SEARCH FOR: '{query}'")

    try:
        api_key = Constants.TAVILY_API_KEY
        if not api_key:
            raise ValueError("TAVILY_API_KEY is missing from environment.")

        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "advanced",
            "include_answer": True,
            "include_raw_content": False,
            "max_results": max_results
        }
        # --- FIX: Inject a random user_agent into Tavily API calls ---
        headers = {'User-Agent': random.choice(USER_AGENTS)}

        response = requests.post(url, json=payload, headers=headers) # Pass headers here
        response.raise_for_status()

        data = response.json()

        # Return both the answer and the list of links
        return {
            "answer": data.get("answer", ""),
            "results": data.get("results", [])
        }

    except Exception as e:
        error_msg = f"Tavily search failed for query '{query}': {e}"
        logger.error(error_msg)
        return {"error": error_msg}




@tool
def advanced_search_and_retrieve(query: str, subject_hint: Optional[str] = None) -> str:
    """
    Deep retrieval (bounded) + cheap synthesis. Honors ADVANCED_SERP_BUDGET.
    """
    logger.info(f"PERFORMING ADVANCED RETRIEVAL FOR: '{query}' with hint '{subject_hint}'")
    try:
        ctx = advanced_retriver.retrieve_context(query, subject_hint=subject_hint)
        summary = advanced_retriver.synthesize_answer(ctx)

        # keep the final string shape stable for downstream display
        answer = summary.get("answer", "No high-confidence context found.")
        citations = summary.get("citations", []) or []
        metrics = summary.get("metrics", {}) or {}

        cits_block = "\n".join(f"- {u}" for u in citations)
        budget = f"\n\n[retrieval: serp_calls_used={metrics.get('serp_calls_used', 0)}, urls_scraped={metrics.get('urls_scraped', 0)}]"

        if cits_block:
            return f"{answer}\n\nSources:\n{cits_block}{budget}"
        else:
            return f"{answer}{budget}"

    except Exception as e:
        error_msg = f"Advanced retrieval failed for query '{query}': {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"

# --- Make all tools available for import ---
__all__ = [
    # General Web Search
    'google_search',
    'bing_search',
    'duckduckgo_search',
    'yahoo_search',
    # Regional Web Search
    'yandex_search',
    'baidu_search',
    # Image Search
    'google_image_search',
    'bing_images_search',
    'google_lens_search',
    'google_reverse_image_search',
    # Specialized Search
    'google_maps_search',
    'google_hotels_search',
    'google_news_search',
    'youtube_search',
    'yelp_search',
    # Utility
    'web_scraper',
    #tavily
    'tavily_search',
    'advanced_search_and_retrieve'
]