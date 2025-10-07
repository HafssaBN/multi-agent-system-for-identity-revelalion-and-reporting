import requests
import random
import time
import json
from multi_agents.constants.constants import COOKIES  , AIRBNB_USER_AGENTS


def get_headers(username=None, add_x_ig=None, referer_path: str | None = None):
    ua = random.choice(AIRBNB_USER_AGENTS)
    header = {
        "User-Agent": ua,
        "X-CSRFToken": COOKIES["csrftoken"],        # <-- canonical casing
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Connection": "keep-alive",
        "X-Requested-With": "XMLHttpRequest",       # <-- important for web endpoints
        "X-ASBD-ID": "129477",                      # <-- commonly required
        "X-IG-WWW-Claim": "0",                      # <-- safe default
    }
    if add_x_ig:
        header["X-IG-App-ID"] = "936619743392459"  # <-- IG web app ID
    # Good referers: /followers/ or /following/ pages
    if referer_path and username:
        header["Referer"] = f"https://www.instagram.com/{username}/{referer_path}/"
    elif username:
        header["Referer"] = f"https://www.instagram.com/{username}/"
    else:
        header["Referer"] = "https://www.instagram.com/"
    return header


def handle_api_error(response, context=""):
    """Central function to handle common API errors."""
    print(f"[!] Error in {context}: Status Code {response.status_code}")
    if response.status_code == 403:
        print("[-] Access Forbidden. Your cookies are likely invalid or expired.")
    elif response.status_code == 429:
        print("[-] Rate limited by Instagram. Please wait before trying again.")
    elif response.status_code == 404:
        print("[-] Resource not found (404).")
    else:
        print(f"[-] Response Text: {response.text[:200]}") # Print first 200 chars of response
    return None



def get_paginated_data(endpoint: str, limit: int, context: str) -> list | None:
    """Generic function to scrape paginated data like posts, followers, or following."""
    session = requests.Session()
    session.cookies.update(COOKIES)
    all_items = []
    next_max_id = None
    
    while True:
        url = endpoint
        if next_max_id:
            url += f"&max_id={next_max_id}"
        
        print(f"[*] Scraping {context}: Current count: {len(all_items)}...")
        
        try:
            time.sleep(random.uniform(2.5, 5.5)) # Respectful delay
            response = session.get(url)
            if response.status_code != 200:
                return handle_api_error(response, f"get_paginated_data ({context})")
            
            data = response.json()
            
            items_key = "users" if "users" in data else "items"
            if not data.get(items_key):
                break

            all_items.extend(data[items_key])
            
            if len(all_items) >= limit:
                print(f"[*] Reached limit of {limit} for {context}.")
                return all_items[:limit]

            # Check for more pages
            if data.get("next_max_id"):
                next_max_id = data["next_max_id"]
            else:
                break # No more pages

        except requests.exceptions.RequestException as e:
            return handle_api_error(e.response, f"get_paginated_data ({context})")
        except (KeyError, json.JSONDecodeError):
            print(f"[!] Failed to parse JSON for paginated {context}.")
            break

    print(f"[*] Finished scraping {context}. Total items found: {len(all_items)}")
    return all_items
