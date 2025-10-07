"""
OSINT Tools Module

Categories:
- Social Media Intelligence (SOCMINT)
- Technical Intelligence (TECHINT)
- Structured Data Intelligence
"""

import os
import re
import time
import random
import logging
from typing import Dict, List, Union, Optional, Any
from urllib.parse import urlparse
import json 
import os, sys, json, re, subprocess
from pathlib import Path
from urllib.parse import urlparse 
import requests
from serpapi import GoogleSearch, BaiduSearch  # SerpApi clients
import duckdb
from langchain_core.tools import tool
from apify_client import ApifyClient
# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# OSINT libs
import phonenumbers
from phonenumbers import geocoder, carrier
import whois
from waybackpy import WaybackMachineCDXServerAPI
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
import dns.resolver
import builtwith
import subprocess

# Project constants
from ..constants.constants import Constants, USER_AGENTS, SELENIUM_HOST

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from .insta_tools import (
    DB_PATH,
    instagram_scrape_and_load,
    instagram_db_get_posts,
    instagram_db_get_images,
    instagram_db_get_comments,
)
from dotenv import load_dotenv
load_dotenv()

# =========================
# SerpApi helper class
# =========================
class SearchTools:
    """
    A class that holds the implementation for search tools (SerpApi).
    This keeps the API and execution logic contained in one place.
    """
    def __init__(self):
        self.api_key = Constants.SERPAPI_API_KEY
        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY is not set in your .env/.constants. Search tools cannot function.")

    def _execute_search(self, params: Dict) -> Union[Dict, List]:
        """Execute a SerpApi search with robust error handling."""
        try:
            params['api_key'] = self.api_key
            # Inject a random user_agent into SerpApi calls
            if USER_AGENTS:
                params['user_agent'] = random.choice(USER_AGENTS)

            # Baidu has a specific client, all others use the general GoogleSearch client
            if params.get('engine') == 'baidu':
                search = BaiduSearch(params)
            else:
                search = GoogleSearch(params)

            results = search.get_dict()

            if isinstance(results, dict) and "error" in results:
                logger.error(f"SerpApi Error for engine {params.get('engine')}: {results['error']}")
                return {"error": results["error"]}

            return results

        except Exception as e:
            logger.error(f"Unexpected error during SerpApi search: {e}", exc_info=True)
            return {"error": f"Unexpected exception: {str(e)}"}


# Initialize a single instance for this module
search_tools_instance = SearchTools()


# =========================
# SOCMINT / Person helpers
# =========================
@tool
def phone_lookup(phone_number: str) -> Dict:
    """
    Validate and enrich a phone number (country, rough location text, carrier).

    INPUT:
    - phone_number: in international format (e.g., "+14155552671").

    OUTPUT:
    - dict with is_valid, country, location, carrier (or error).
    """
    logger.info(f"PHONE LOOKUP for {phone_number}")
    try:
        parsed = phonenumbers.parse(phone_number, None)
        if not phonenumbers.is_valid_number(parsed):
            return {"phone_number": phone_number, "is_valid": False, "error": "Invalid phone number format."}

        country = phonenumbers.region_code_for_number(parsed)
        location = geocoder.description_for_number(parsed, "en")
        service_provider = carrier.name_for_number(parsed, "en")

        return {
            "phone_number": phone_number,
            "is_valid": True,
            "country": country,
            "location": location,
            "carrier": service_provider
        }
    except Exception as e:
        logger.error(f"Phone lookup failed for '{phone_number}': {e}")
        return {"phone_number": phone_number, "error": str(e)}


# =========================
# Leak-Lookup (breaches)
# =========================
VALID_LEAK_LOOKUP_TYPES = {
    "email_address", "username", "ipaddress", "phone", "domain", "password", "fullname"
}

def _leak_lookup_request(payload: Dict[str, str], max_retries: int = 3, backoff_sec: float = 1.5) -> Dict[str, Any]:
    """
    Internal helper: POST to Leak-Lookup with minimal retry on burst/rate limits.
    """
    url = "https://leak-lookup.com/api/search"
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, data=payload, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Leak-Lookup non-200 status={resp.status_code}, body={resp.text[:200]}")
                if attempt < max_retries and resp.status_code in (429, 520, 522, 524, 503, 502):
                    time.sleep(backoff_sec * attempt)
                    continue
                return {"error": True, "message": f"HTTP {resp.status_code}", "raw": resp.text}
            data = resp.json()
            return data
        except Exception as e:
            logger.error(f"Leak-Lookup request error on attempt {attempt}: {e}")
            if attempt < max_retries:
                time.sleep(backoff_sec * attempt)
                continue
            return {"error": True, "message": str(e)}
    return {"error": True, "message": "Unknown error after retries"}

@tool
def leak_lookup_search(search_type: str, query: str) -> Dict[str, Any]:
    """
    Search Leak-Lookup breach database (supports free public API key).

    PARAMETERS:
    - search_type: one of {"email_address","username","ipaddress","phone","domain","password","fullname"}
    - query: value to search (email/username/domain/etc.)

    RETURNS (normalized):
    {
      "error": false,
      "plan": "public" | "private" | "unknown",
      "hits": [
         {"breach": "breach_sitename", "records": [ ... ]},  # empty for public plan
         ...
      ],
      "raw": { ...original API response... }
    }
    """
    logger.info(f"LEAK-LOOKUP search: type={search_type} query={query!r}")

    api_key = getattr(Constants, "LEAK_LOOKUP_KEY", None)
    if not api_key:
        return {"error": True, "message": "Missing LEAK_LOOKUP_KEY in Constants."}

    st = (search_type or "").strip().lower()
    if st not in VALID_LEAK_LOOKUP_TYPES:
        return {"error": True, "message": f"Invalid search_type '{search_type}'. Allowed: {sorted(VALID_LEAK_LOOKUP_TYPES)}"}

    if not query or not str(query).strip():
        return {"error": True, "message": "Empty query."}

    payload = {"key": api_key, "type": st, "query": str(query).strip()}
    data = _leak_lookup_request(payload)

    if not isinstance(data, dict):
        return {"error": True, "message": "Unexpected response format", "raw": data}

    err_flag = str(data.get("error", "true")).lower() == "true"
    message = data.get("message", {})

    plan = "unknown"
    hits: List[Dict[str, Any]] = []
    if not err_flag and isinstance(message, dict):
        for breach, records in message.items():
            # Public: records = []
            # Private: records = list of dicts
            if isinstance(records, list) and records:
                if isinstance(records[0], dict):
                    plan = "private"
                else:
                    plan = "public" if plan == "unknown" else plan
            elif isinstance(records, list) and not records:
                plan = "public" if plan == "unknown" else plan

            hits.append({"breach": breach, "records": records if isinstance(records, list) else []})

    return {"error": err_flag, "plan": plan, "hits": hits, "raw": data}


# =========================
# Archive / Metadata / WHOIS
# =========================
@tool
def wayback_lookup(url: str, timestamp: Optional[str] = None) -> Dict:
    """
    Look up historical snapshots of a webpage from the Wayback Machine.

    - url: target webpage URL
    - timestamp (optional): YYYYMMDDhhmmss (we use the year for nearest snapshot)
    """
    logger.info(f"WAYBACK LOOKUP for {url} at {timestamp or 'latest'}")
    try:
        cdx = WaybackMachineCDXServerAPI(url, user_agent=random.choice(USER_AGENTS) if USER_AGENTS else None)
        if timestamp:
            year_int = int(timestamp[0:4])
            snapshot = cdx.near(year=year_int)
        else:
            snapshot = cdx.newest()

        return {
            "url": url,
            "snapshot_url": snapshot.archive_url,
            "timestamp": snapshot.timestamp,
            "available": True
        }
    except Exception as e:
        logger.error(f"Wayback lookup failed: {e}")
        return {"url": url, "snapshot_url": None, "available": False, "error": str(e)}

@tool
def extract_metadata(file_path: str) -> Dict:
    """
    Extract metadata (EXIF, PDF, Office properties) from a local file.
    """
    logger.info(f"EXTRACTING METADATA from {file_path}")
    try:
        parser = createParser(file_path)
        if not parser:
            return {"file": file_path, "error": "Unsupported or unreadable file"}
        with parser:
            metadata = extractMetadata(parser)
        if not metadata:
            return {"file": file_path, "error": "No metadata found"}

        # Prefer dictionary export if available; fallback to plaintext list
        mdict = {}
        if hasattr(metadata, "exportDictionary"):
            mdict = metadata.exportDictionary()
        else:
            lines = metadata.exportPlaintext()
            mdict = {"plaintext": lines}

        return {"file": file_path, "metadata": mdict}
    except Exception as e:
        logger.error(f"Metadata extraction failed: {e}")
        return {"file": file_path, "error": str(e)}

@tool
def whois_lookup(domain: str) -> Dict:
    """
    Perform WHOIS lookup for a domain or IP.
    """
    logger.info(f"WHOIS LOOKUP for {domain}")
    try:
        w = whois.whois(domain)
        return {
            "domain": domain,
            "registrar": getattr(w, "registrar", None),
            "creation_date": str(getattr(w, "creation_date", None)),
            "expiration_date": str(getattr(w, "expiration_date", None)),
            "name_servers": getattr(w, "name_servers", None),
            "emails": getattr(w, "emails", None),
        }
    except Exception as e:
        logger.error(f"WHOIS lookup failed: {e}")
        return {"domain": domain, "error": str(e)}


# =========================
# SerpApi: General Web Search
# =========================
@tool
def google_search(query: str, location: Optional[str] = None) -> Union[List[Dict], Dict]:
    """
    Performs a standard Google search.
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


# =========================
# SerpApi: Regional Web Search
# =========================
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


# =========================
# SerpApi: Image / Reverse Image
# =========================
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

@tool
def google_lens_search(image_url: str) -> Dict[str, Any]:
    """
    Perform a Google Lens reverse/visual similarity search via SerpApi.
    Input: image_url (string) - URL to an image.
    Output: dict with engine, best_guess, and matches.
    """
    logger.info(f"GOOGLE LENS SEARCH for image: {image_url}")

    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return {"engine": "google_lens", "error": "SERPAPI_API_KEY not set"}

    params = {
        "engine": "google_lens",
        "url": image_url,
        "hl": "en",
        "api_key": api_key,
    }

    try:
        data = GoogleSearch(params).get_dict()
    except Exception as e:
        logger.exception("SerpApi request failed")
        return {"engine": "google_lens", "error": f"request_failed: {e}"}

    # Extract matches
    matches: List[Dict[str, str]] = []
    for m in data.get("visual_matches", []):
        matches.append({
            "title": m.get("title"),
            "link": m.get("link"),
            "thumbnail": m.get("thumbnail"),
            "source": m.get("source"),
        })

    # Handle best guess gracefully
    best_guess = (
        data.get("best_guess_label")
        or (data.get("search_metadata") or {}).get("google_lens_best_guess")
    )

    return {
        "engine": "google_lens",
        "best_guess": best_guess,
        "matches": matches,
    }

@tool
def google_reverse_image_search(image_url: str) -> Dict[str, Any]:
    """
    Traditional reverse image (exact/near-exact) via SerpApi (Google Reverse Image).
    Input:
      - image_url: direct URL to the image to reverse search
    Output:
      - dict with engine, best_guess, and matches (list of {title, link, thumbnail, source, original?})
    """
    logger.info(f"GOOGLE REVERSE IMAGE SEARCH for: {image_url}")

    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return {"engine": "google_reverse_image", "error": "SERPAPI_API_KEY not set"}

    if not image_url or not isinstance(image_url, str):
        return {"engine": "google_reverse_image", "error": "image_url must be a non-empty string"}

    params = {
        "engine": "google_reverse_image",
        "image_url": image_url,   # Use this for remote URLs. For uploads, SerpApi also supports 'image_content'.
        "hl": "en",
        "api_key": api_key,
    }

    try:
        data: Dict[str, Any] = GoogleSearch(params).get_dict()
    except Exception as e:
        logger.exception("SerpApi request failed")
        return {"engine": "google_reverse_image", "error": f"request_failed: {e}"}

    # Inline images are the primary matches for reverse image
    raw = data.get("inline_images") or []
    matches: List[Dict[str, Any]] = []
    for m in raw:
        # Common fields seen in inline_images: title, link, source, thumbnail, original
        item = {
            "title":     m.get("title"),
            "link":      m.get("link") or m.get("source"),
            "thumbnail": m.get("thumbnail"),
            "source":    m.get("source"),
        }
        # Keep the original (full-size) image URL if provided
        if m.get("original"):
            item["original"] = m.get("original")

        # Drop empty keys
        item = {k: v for k, v in item.items() if v}
        if item:
            matches.append(item)

    # Best guess may appear under different keys depending on response variant
    best_guess = (
        data.get("best_guess_label")
        or (data.get("search_metadata") or {}).get("google_reverse_image_best_guess")
    )

    out: Dict[str, Any] = {
        "engine": "google_reverse_image",
        "best_guess": best_guess,
        "matches": matches,
    }

    # Surface status if present and not "Success"
    status = (data.get("search_metadata") or {}).get("status")
    if status and status != "Success":
        out["warning"] = f"SerpApi status: {status}"

    return out

# =========================
# SerpApi: Specialized
# =========================
@tool
def google_maps_search(query: str, lat_long: Optional[str] = None) -> Union[List[Dict], Dict]:
    """Google Maps places search."""
    logger.info(f"GOOGLE MAPS SEARCH: '{query}'")
    params = {"engine": "google_maps", "q": query}
    if lat_long:
        params["ll"] = lat_long
    results = search_tools_instance._execute_search(params)
    if isinstance(results, dict) and "error" not in results:
        return results.get("local_results", [])
    return results

@tool
def google_hotels_search(query: str, check_in_date: str, check_out_date: str, adults: int = 1) -> Union[List[Dict], Dict]:
    """Google Hotels search (availability/pricing)."""
    logger.info(f"GOOGLE HOTELS SEARCH: '{query}' {check_in_date} -> {check_out_date}")
    params = {
        "engine": "google_hotels",
        "q": query,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "adults": str(adults),
    }
    results = search_tools_instance._execute_search(params)
    if isinstance(results, dict) and "error" not in results:
        return results.get("properties", [])
    return results

@tool
def google_news_search(query: str) -> Union[List[Dict], Dict]:
    """Google News search (structured)."""
    logger.info(f"GOOGLE NEWS SEARCH: '{query}'")
    results = search_tools_instance._execute_search({"engine": "google_news", "q": query})
    if isinstance(results, dict) and "error" not in results:
        return {"engine": "google_news", "news_results": results.get("news_results", [])}
    return results

@tool
def yelp_search(description: str, location: str) -> Union[List[Dict], Dict]:
    """Yelp search via SerpApi."""
    logger.info(f"YELP SEARCH: '{description}' in '{location}'")
    results = search_tools_instance._execute_search({"engine": "yelp", "find_desc": description, "find_loc": location})
    if isinstance(results, dict) and "error" not in results:
        return results.get("organic_results", [])
    return results




# =========================
# Utility: Selenium Scraper
# =========================

# insta-safe web_scraper (in search_tools.py or wherever your web_scraper lives)
from urllib.parse import urlparse
from shutil import which

BLOCKED_SITES = {
    "instagram.com", "www.instagram.com", "m.instagram.com",
    "facebook.com", "www.facebook.com", "m.facebook.com",
    "linkedin.com", "www.linkedin.com",
    "airbnb.com", "www.airbnb.com"
}

# --- Constants (centralize these) ---
BLOCKED_SITES = {"instagram.com", "facebook.com", "fb.com", "linkedin.com", "lnkd.in"}
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
]

@tool
def web_scraper(url: str) -> Dict[str, Any]:
    """
    Crawls and scrapes a URL, returning its text content. It uses a robust two-step process:
    1. Attempts to use the advanced Apify Web Scraper with residential proxies.
    2. If Apify fails or returns no content, it falls back to a local Selenium browser.
    RULE: Do not use for Instagram, Facebook, or LinkedIn URLs. Use specific tools for those.
    """
    logger.info(f"🚀 SCRAPER: Starting scrape for URL: {url}")

    # --- 1) Input Validation and Blocking ---
    try:
        if isinstance(url, str) and url.strip().startswith("{"):
            url = json.loads(url).get("url", url)
        
        parsed_url = urlparse(url)
        if not (parsed_url.scheme in ("http", "https) and parsed_url.netloc):
            return {"url": url, "error": f"Invalid URL format: {url}"}
        
        host = parsed_url.netloc.lower()
        if any(host.endswith(d) for d in BLOCKED_SITES):
            error_msg = f"This site ({host}) should be accessed with a specialized tool, not the generic web scraper."
            logger.warning(error_msg)
            return {"url": url, "error": error_msg}

    except (json.JSONDecodeError, AttributeError) as e:
        return {"url": str(url), "error": f"Bad input: {type(url).__name__}: {e}"}

    # --- 2) Attempt 1: Advanced Apify Scraper ---
    apify_token = os.getenv("APIFY_TOKEN")
    if apify_token:
        try:
            logger.info("Attempting scrape with Apify 'Web Scraper' actor...")
            client = ApifyClient(apify_token)
            
            run_input = {
                # The URL passed to this function is now the target
                "startUrls": [{"url": url}],
                
                # CRITICAL: Use residential proxies to appear like a real user
                "proxyConfiguration": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
                
                # GENERIC function to get all text from the page, which works for ANY website
                "pageFunction": """
                    async function pageFunction(context) {
                        const { request, log, jQuery: $ } = context;
                        const text = $('body').text();
                        log.info(`Extracted text from ${request.url}`);
                        return { url: request.url, text: text };
                    }
                """
            }
            
            # Use the official, powerful 'apify/web-scraper' actor
            run = client.actor("apify/web-scraper").call(run_input=run_input)
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            
            if items and items[0].get("text"):
                content = items[0]["text"].strip()
                logger.info(f"Apify scrape successful. Got {len(content)} characters.")
                return {"url": url, "content": content[:8000], "source": "apify"}
            else:
                logger.warning("Apify ran but returned no text content. Proceeding to Selenium fallback.")
        except Exception as e:
            logger.error(f"Apify actor failed: {e}. Proceeding to Selenium fallback.")

    # --- 3) Attempt 2: Selenium Fallback ---
    logger.info("Attempting scrape with Selenium fallback...")
    driver = None
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
        
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        driver.get(url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        body_element = driver.find_element(By.TAG_NAME, "body")
        page_text = body_element.text.strip()
        
        if page_text:
            logger.info(f"Selenium scrape successful. Got {len(page_text)} characters.")
            return {"url": url, "content": page_text[:8000], "source": "selenium"}
        else:
            logger.warning(f"Selenium loaded page, but no text was found for {url}.")
            return {"url": url, "content": "", "error": "Selenium found no text content.", "source": "selenium"}
            
    except Exception as e:
        error_msg = f"Selenium fallback failed for URL '{url}': {e}"
        logger.error(error_msg)
        return {"url": url, "content": "", "error": error_msg, "source": "selenium"}
    finally:
        if driver:
            driver.quit()


# =========================
# Tavily + Advanced Retriever
# =========================
@tool
def tavily_search(query: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Tavily API: fast factual retrieval with answer synthesis.
    """
    logger.info(f"TAVILY SEARCH: '{query}'")
    try:
        api_key = Constants.TAVILY_API_KEY
        if not api_key:
            raise ValueError("TAVILY_API_KEY is missing from Constants.")

        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "advanced",
            "include_answer": True,
            "include_raw_content": False,
            "max_results": max_results
        }
        headers = {'User-Agent': random.choice(USER_AGENTS) if USER_AGENTS else "osint-agent/1.0"}
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return {"answer": data.get("answer", ""), "results": data.get("results", [])}
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        return {"error": str(e)}

# You must provide advanced_retriver in your project: .webscraping.advanced_retriver
from .webscraping import advanced_retriver

@tool
def advanced_search_and_retrieve(query: str, subject_hint: Optional[str] = None) -> str:
    """
    Multi-stage deep retrieval & synthesis using your project's advanced_retriver.
    """
    logger.info(f"ADVANCED RETRIEVAL: '{query}' | hint='{subject_hint}'")
    try:
        ctx = advanced_retriver.retrieve_context(query, subject_hint=subject_hint)
        summary = advanced_retriver.synthesize_answer(ctx)

        answer = summary.get("answer", "No high-confidence context found.")
        citations = summary.get("citations", []) or []
        metrics = summary.get("metrics", {}) or {}

        cits_block = "\n".join(f"- {u}" for u in citations)
        budget = f"\n\n[retrieval: serp_calls_used={metrics.get('serp_calls_used', 0)}, urls_scraped={metrics.get('urls_scraped', 0)}]"

        return f"{answer}\n\nSources:\n{cits_block}{budget}" if cits_block else f"{answer}{budget}"

    except Exception as e:
        logger.error(f"Advanced retrieval failed: {e}", exc_info=True)
        return f"Error: {e}"


# =========================
# SOCMINT: Sherlock
# =========================
@tool
def sherlock_username_search(username: str) -> Dict:
    """
    Run Sherlock and return found profile URLs.
    Tries SHERLOCK_EXE → SHERLOCK_REPO → SHERLOCK_PATH.
    Returns {"username": str, "profiles": {...}} or {"username": str, "error": str}.
    """
    exe  = os.getenv("SHERLOCK_EXE", "").strip()
    repo = os.getenv("SHERLOCK_REPO", "").strip()
    path = os.getenv("SHERLOCK_PATH", "").strip()

    cmd, run_kwargs = None, {}

    if exe and os.path.isfile(exe):
        cmd = [exe, "--timeout", "15", "--print-found", username]
    elif repo and os.path.isdir(repo):
        # repo root must contain sherlock_project/
        if not os.path.isdir(os.path.join(repo, "sherlock_project")):
            return {"username": username, "error": f"SHERLOCK_REPO invalid (no sherlock_project/): {repo}"}
        cmd = [sys.executable, "-m", "sherlock_project", "--timeout", "15", "--print-found", username]
        run_kwargs["cwd"] = repo
    elif path and os.path.isfile(path):
        cmd = [sys.executable, path, "--timeout", "15", "--print-found", username]
    else:
        return {"username": username, "error": "Sherlock not found. Set SHERLOCK_EXE (preferred) or SHERLOCK_REPO/SHERLOCK_PATH."}

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, **run_kwargs)
    except Exception as e:
        return {"username": username, "error": f"Exec failed: {e}"}

    if proc.returncode != 0:
        # Sherlock sometimes prints guidance in stdout; include whichever has content
        msg = proc.stderr.strip() or proc.stdout.strip() or f"Exit code {proc.returncode}"
        return {"username": username, "error": msg}

    # Parse found URLs from output when --print-found is used
    url_re = re.compile(r"https?://\S+")
    found: Dict[str, str] = {}
    for line in proc.stdout.splitlines():
        m = url_re.search(line)
        if not m:
            continue
        url = m.group(0).rstrip(").,;")
        netloc = (urlparse(url).netloc or "").lower()
        platform = netloc.replace("www.", "").split(".")[0]
        if platform:
            found[platform] = url

    return {"username": username, "profiles": found}


# =========================
# TECHINT
# =========================
@tool
def dns_lookup(domain: str) -> Dict:
    """
    Query DNS records (A, MX, TXT, NS) with timeouts.
    """
    logger.info(f"DNS LOOKUP: {domain}")
    record_types = ['A', 'MX', 'TXT', 'NS']
    results = {"domain": domain, "records": {}}
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 3.0
        resolver.lifetime = 5.0
        for rtype in record_types:
            try:
                answers = resolver.resolve(domain, rtype)
                results["records"][rtype] = [str(rdata) for rdata in answers]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
                results["records"][rtype] = []
            except Exception as e:
                results["records"][rtype] = [f"Error querying {rtype}: {str(e)}"]
        return results
    except Exception as e:
        logger.error(f"DNS lookup failed: {e}")
        return {"domain": domain, "error": str(e)}

@tool
def ip_geolocation(ip_address: str) -> Dict:
    """
    Free IP geolocation via ip-api.com (best-effort, rate-limited).
    """
    logger.info(f"IP GEOLOCATION: {ip_address}")
    try:
        r = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=10)
        if r.status_code != 200:
            return {"ip_address": ip_address, "error": f"HTTP {r.status_code}", "raw": r.text[:200]}
        return r.json()
    except Exception as e:
        logger.error(f"IP geolocation failed: {e}")
        return {"ip_address": ip_address, "error": str(e)}

@tool
def builtwith_lookup(url: str) -> Dict:
    """
    Detect technologies used by a website via builtwith.
    """
    logger.info(f"BUILTWITH: {url}")
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        tech_info = builtwith.builtwith(url)
        return {"url": url, "technologies": tech_info}
    except Exception as e:
        logger.error(f"BuiltWith failed: {e}")
        return {"url": url, "error": str(e)}



# =========================
# SOCMINT
# =========================
@tool
def youtube_search(query: str) -> Union[List[Dict], Dict]:
    """YouTube search via SerpApi."""
    logger.info(f"YOUTUBE SEARCH: '{query}'")
    results = search_tools_instance._execute_search({"engine": "youtube", "search_query": query})
    if isinstance(results, dict) and "error" not in results:
        return results.get("video_results", [])
    return results
@tool
def linkedin_people_search(
    firstname: str,
    lastname: str,
    location: Optional[str] = None,
    current_job_title: Optional[str] = None,
    include_email: bool = False,
) -> Dict[str, Any]:
    """
    Search LinkedIn profiles by first/last name (optionally location/title) using an Apify actor.

    Auth:
      - Reads APIFY_API_TOKEN from Constants.APIFY_API_TOKEN or env "APIFY_API_TOKEN".
      - **Do NOT** hardcode tokens in code.

    Parameters
    ----------
    firstname : str
    lastname  : str
    location  : Optional[str]   (e.g., "Morocco" or "Paris, France")
    current_job_title : Optional[str] (e.g., "Data Scientist")
    include_email : bool         (actor must support email enrichment)

    Returns
    -------
    Dict[str, Any]
      {
        "error": False,
        "count": <int>,
        "items": [
          {
            "search_criteria": {...},
            "basic_info": {...},
            "experience": [...],
            "education": [...]
          },
          ...
        ]
      }
      or {"error": True, "message": "..."} on failure.
    """
  
    # ---- config / auth
    api_token = (
    getattr(Constants, "APIFY_API_TOKEN", None)
    or os.getenv("APIFY_API_TOKEN")
    or os.getenv("APIFY_TOKEN")   
      )
    if not api_token:
        return {"error": True, "message": "Missing APIFY_API_TOKEN in Constants or environment."}

    # Your actor ID (keep it configurable)
    actor_id = getattr(Constants, "APIFY_LINKEDIN_ACTOR_ID", None) or os.getenv("APIFY_LINKEDIN_ACTOR_ID", "pIyH7237rHZBxoO7q")

    # Build actor input (only include optional fields when provided)
    run_input: Dict[str, Any] = {
        "firstname": firstname,
        "lastname": lastname,
        "include_email": bool(include_email),
    }
    if location:
        run_input["location"] = location
    if current_job_title:
        run_input["current_job_title"] = current_job_title

    try:
        client = ApifyClient(api_token)
        # Start and wait for the run to finish
        run = client.actor(actor_id).call(run_input=run_input)

        # Fetch items from the default dataset
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return {"error": True, "message": "Apify run completed but no defaultDatasetId was returned."}

        items_iter = client.dataset(dataset_id).iterate_items()
        items = list(items_iter)

        # Normalize (keep original fields; light pass-through)
        # If you want to aggressively normalize, do it here.
        return {"error": False, "count": len(items), "items": items}

    except Exception as e:
        # Include a short snippet if Apify returns structured errors
        msg = str(e)
        return {"error": True, "message": f"LinkedIn search via Apify failed: {msg}"}

@tool
def facebook_pages_lookup(
    profiles: Union[str, List[str]]
) -> Dict[str, Any]:
    """
    Fetch public Facebook Page/Profile metadata via an Apify actor.

    Auth:
      - Reads APIFY_API_TOKEN from Constants.APIFY_API_TOKEN or env "APIFY_API_TOKEN".
      - Actor ID from Constants.APIFY_FACEBOOK_ACTOR_ID or env "APIFY_FACEBOOK_ACTOR_ID".
        (Defaults to the actor you tested: "zQt0UcNu0fsd98YAw")

    Parameters
    ----------
    profiles : str | List[str]
        One or more Facebook page/profile handles (without the domain). You can pass:
          - "nasaearth" or "ChrisBrecheensWritingAboutWriting"
          - newline-separated string: "nasaearth\\nChrisBrecheensWritingAboutWriting"
          - ["nasaearth", "ChrisBrecheensWritingAboutWriting"]

    Returns
    -------
    Dict[str, Any]
      {
        "error": False,
        "count": <int>,
        "items": [ ... raw Apify items ... ]
      }
      or {"error": True, "message": "..."} on failure.

    Notes
    -----
    - Do NOT hardcode API tokens in code.
    - Output is a pass-through of Apify dataset items, which typically include:
      facebookUrl, title, pageName, pageId, facebookId, categories, likes, followers,
      email, website, intro, profilePictureUrl, coverPhotoUrl, creation_date, verified,
      ad_status, info, extractedAt, dataSource, etc.
    """
   
    # ---- config / auth
    api_token = getattr(Constants, "APIFY_API_TOKEN", None) or os.getenv("APIFY_API_TOKEN")
    if not api_token:
        return {"error": True, "message": "Missing APIFY_API_TOKEN in Constants or environment."}

    actor_id = (
        getattr(Constants, "APIFY_FACEBOOK_ACTOR_ID", None)
        or os.getenv("APIFY_FACEBOOK_ACTOR_ID", "zQt0UcNu0fsd98YAw")
    )

    # Normalize input to the actor's expected newline-separated string
    if isinstance(profiles, list):
        handles = [str(p).strip() for p in profiles if str(p).strip()]
        if not handles:
            return {"error": True, "message": "No valid profiles provided."}
        profiles_str = "\n".join(handles)
    else:
        profiles_str = str(profiles).strip()
        if not profiles_str:
            return {"error": True, "message": "Empty 'profiles' input."}

    try:
        client = ApifyClient(api_token)
        run_input = {"profiles": profiles_str}
        run = client.actor(actor_id).call(run_input=run_input)

        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return {"error": True, "message": "Apify run completed but no defaultDatasetId returned."}

        items = list(client.dataset(dataset_id).iterate_items())
        return {"error": False, "count": len(items), "items": items}

    except Exception as e:
        return {"error": True, "message": f"Facebook lookup via Apify failed: {e}"}


@tool("download_image")
def download_image_tool(image_url: str, save_path: str = 'profile_pic.jpg') -> str:
    """Downloads image to local path; returns absolute path or error JSON string."""
    try:
        import os, requests
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        absolute_path = os.path.abspath(save_path)
        with open(absolute_path, 'wb') as f:
            f.write(response.content)
        return absolute_path
    except requests.exceptions.RequestException as e:
        return json.dumps({"error": f"Failed to download image from {image_url}: {e}"})
    except Exception as e:
        return json.dumps({"error": f"An unexpected error occurred in download_image: {e}"})



@tool
def extract_and_download_image_from_url(page_url: str, save_path: str = 'profile_pic.jpg') -> str:
    """
    Scrapes a given page URL to find the primary image, then downloads it to a local path.
    This is the preferred tool for social media pages (Facebook, Instagram, etc.) where the image URL is not direct.
    Returns the absolute path to the downloaded file or an error JSON string.
    """
    logger.info(f"IMAGE EXTRACTOR: Scraping {page_url} to find and download the main image.")
    
    try:
        # Initialize Apify Client
        api_token = Constants.APIFY_API_TOKEN or os.getenv("APIFY_API_TOKEN")
        if not api_token:
            return json.dumps({"error": "Missing APIFY_API_TOKEN."})
        client = ApifyClient(api_token)

        # Prepare and run the Apify Actor for image extraction
        run_input = {"inputUrls": [{"url": page_url}]}
        actor_id = "2woNCOq54N2v7Kjb6"  # Website Image Downloader Pro
        run = client.actor(actor_id).call(run_input=run_input)

        # Fetch results and find the most relevant image URL
        image_to_download = None
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            img_url = item.get("image_url")
            # Heuristic: find the first non-SVG, high-resolution image.
            # Facebook often uses 'scontent' for primary images.
            if img_url and 'scontent' in img_url and not img_url.endswith('.svg'):
                image_to_download = img_url
                break # Found a good candidate

        if not image_to_download:
            return json.dumps({"error": f"No suitable image found on page {page_url}"})

        logger.info(f"Found image URL to download: {image_to_download}")

        # Now, download the extracted image URL
        response = requests.get(image_to_download, timeout=15)
        response.raise_for_status()
        
        absolute_path = os.path.abspath(save_path)
        with open(absolute_path, 'wb') as f:
            f.write(response.content)
        
        return f"Successfully downloaded image from {page_url} to {absolute_path}"

    except Exception as e:
        logger.error(f"An unexpected error occurred in extract_and_download_image_from_url: {e}", exc_info=True)
        return json.dumps({"error": str(e)})



# =========================
# Public module exports
# =========================
__all__ = [
    # SOCMINT / person-finding helpers
    "phone_lookup",
    "sherlock_username_search",

    # Breach / structured data
    "leak_lookup_search",

    # General Web Search
    "google_search",
    "bing_search",
    "duckduckgo_search",
    "yahoo_search",

    # Regional Web Search
    "yandex_search",
    "baidu_search",

    # Image search
    "google_image_search",
    "bing_images_search",
    "google_lens_search",
    "google_reverse_image_search",

    # Specialized search
    "google_maps_search",
    "google_hotels_search",
    "google_news_search",
    "youtube_search",
    "yelp_search",

    # Utility
    "web_scraper",
    "wayback_lookup",
    "extract_metadata",
    "whois_lookup",

    # Research
    "tavily_search",
    "advanced_search_and_retrieve",

    # TECHINT
    "dns_lookup",
    "ip_geolocation",
    "builtwith_lookup",

    #SOCMINT
    "linkedin_people_search",
    "facebook_pages_lookup",
    "instagram_scrape_and_load",
    "instagram_db_get_posts",
    "instagram_db_get_images",
    "instagram_db_get_comments",

    "download_image_tool",
    "extract_and_download_image_from_url"

]
