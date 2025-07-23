import requests
import random
import time
import json
from multi_agents.constants.constants import COOKIES  
from multi_agents.utils.utils import get_headers, handle_api_error # get_paginated_data
import os




def get_user_id(username: str) -> str | None:
    session = requests.Session()
    session.cookies.update(COOKIES)
    url = "https://www.instagram.com/web/search/topsearch/"
    params = {"query": username}

    try:
        time.sleep(random.uniform(1.5, 4.5))
        session.headers.update(get_headers())

        response = session.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        users = data.get("users", [])

        for user in users:
            if user.get("user", {}).get("username") == username:
                return user["user"]["pk"]  # Numeric user ID

        print(f"[!] User '{username}' not found in search results.")
        return None

    except requests.exceptions.HTTPError as e:
        print(f"[!] HTTP error: {e}")
        if response.status_code == 429:
            print("[!] Rate limited. Slow down your requests!")
        elif response.status_code == 403:
            print("[!] Access forbidden. Check cookies.")
        return None
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        return None


def get_following(user_id: str, limit: int = 100, batch_size: int = 50) -> list:
    session = requests.Session()
    session.cookies.update(COOKIES)
    following = []
    has_next_page = True
    after_cursor = None
    query_hash = "d04b0a864b4b54837c0d870b0e77e076"

    while has_next_page and len(following) < limit:
        to_fetch = min(batch_size, limit - len(following))

        variables = {
            "id": user_id,
            "include_reel": True,
            "fetch_mutual": False,
            "first": to_fetch,
        }
        if after_cursor:
            variables["after"] = after_cursor

        url = (
            f"https://www.instagram.com/graphql/query/?query_hash={query_hash}"
            f"&variables={json.dumps(variables)}"
        )

        try:
            time.sleep(random.uniform(1.5, 3.5))
            session.headers.update(get_headers())

            response = session.get(url)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError as e:
            print(f"[!] HTTP error: {e}")
            break
        except Exception as e:
            print(f"[!] Unexpected error: {e}")
            break

        user_data = data.get("data", {}).get("user")
        if not user_data:
            print("[!] No user data returned, stopping.")
            break

        edge_follow = user_data.get("edge_follow")
        if not edge_follow:
            print("[!] No 'edge_follow' data, stopping.")
            break

        edges = edge_follow.get("edges", [])
        for edge in edges:
            node = edge["node"]
            following.append(
                {
                    "id": node["id"],
                    "username": node["username"],
                    "full_name": node.get("full_name"),
                    "profile_pic_url": node.get("profile_pic_url"),
                    "is_private": node.get("is_private"),
                }
            )

        page_info = edge_follow.get("page_info", {})
        has_next_page = page_info.get("has_next_page", False)
        after_cursor = page_info.get("end_cursor")

        print(f"Fetched {len(following)} following so far...")

    return following[:limit]



def get_followers(user_id: str, limit: int = 100, batch_size: int = 50) -> list:
    session = requests.Session()
    session.cookies.update(COOKIES)
    followers = []
    has_next_page = True
    after_cursor = None
    query_hash = "c76146de99bb02f6415203be841dd25a"  # followers query hash

    while has_next_page and len(followers) < limit:
        to_fetch = min(batch_size, limit - len(followers))

        variables = {
            "id": user_id,
            "include_reel": True,
            "fetch_mutual": False,
            "first": to_fetch,
        }
        if after_cursor:
            variables["after"] = after_cursor

        url = (
            f"https://www.instagram.com/graphql/query/?query_hash={query_hash}"
            f"&variables={json.dumps(variables)}"
        )

        try:
            time.sleep(random.uniform(1.5, 3.5))
            session.headers.update(get_headers())

            response = session.get(url)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError as e:
            print(f"[!] HTTP error: {e}")
            break
        except Exception as e:
            print(f"[!] Unexpected error: {e}")
            break

        user_data = data.get("data", {}).get("user")
        if not user_data:
            print("[!] No user data returned, stopping.")
            break

        edge_followed_by = user_data.get("edge_followed_by")
        if not edge_followed_by:
            print("[!] No 'edge_followed_by' data, stopping.")
            break

        edges = edge_followed_by.get("edges", [])
        for edge in edges:
            node = edge["node"]
            followers.append(
                {
                    "id": node["id"],
                    "username": node["username"],
                    "full_name": node.get("full_name"),
                    "profile_pic_url": node.get("profile_pic_url"),
                    "is_private": node.get("is_private"),
                }
            )

        page_info = edge_followed_by.get("page_info", {})
        has_next_page = page_info.get("has_next_page", False)
        after_cursor = page_info.get("end_cursor")

        print(f"Fetched {len(followers)} followers so far...")

    return followers[:limit]



def get_user_info(username: str) -> dict | None:
    """
    Fetches comprehensive user information (ID, full name, bio, etc.)
    using Instagram's internal web API. This is the most reliable method.

    Args:
        username: The Instagram username to look up.

    Returns:
        A dictionary containing the user's profile information, or None if
        the request fails or the user is not found.
    """

    session = requests.Session()
    session.cookies.update(COOKIES)
    api_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    print(f"[*] Fetching all info for '{username}' from API: {api_url}")

    try:
        # Add a random delay to mimic human behavior and avoid rate limiting
        time.sleep(random.uniform(2.0, 5.0))
        
        # Update the session headers for this specific request
        session.headers.update(get_headers(add_x_ig=True))

        response = session.get(api_url)
        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        data = response.json()

        # Navigate through the JSON to find the user data
        if "user" not in data.get("data", {}):
            print(f"[!] User '{username}' not found in API response. The profile may be private, non-existent, or there was an issue with the request.")
            return None

        user_data = data["data"]["user"]

        # Extract all the desired information into a structured dictionary
        profile_info = {
            "user_id": user_data.get("id"),
            "full_name": user_data.get("full_name"),
            "description": user_data.get("biography"),
            "followers": user_data.get("edge_followed_by", {}).get("count"),
            "following": user_data.get("edge_follow", {}).get("count"),
            "post_count": user_data.get("edge_owner_to_timeline_media", {}).get("count"),
            "is_private": user_data.get("is_private"),
            "is_verified": user_data.get("is_verified"),
            "profile_pic_url": user_data.get("profile_pic_url_hd"),
            "external_url": user_data.get("external_url"),
        }
        return profile_info

    except requests.exceptions.HTTPError as e:
        print(f"[!] HTTP Error: {e}")
        if e.response.status_code == 404:
            print(f"[-] Profile '{username}' not found (404).")
        elif e.response.status_code == 403:
             print("[-] Access Forbidden (403). Your cookies are likely invalid or expired. Please get new ones.")
        elif e.response.status_code == 429:
            print("[-] Rate limited by Instagram (429). Please wait before trying again.")
        return None
        
    except json.JSONDecodeError:
        print("[!] Critical Error: Failed to decode JSON from response.")
        print("[-] This usually means Instagram blocked the request and sent an HTML login page instead.")
        print("[-] Please double-check that your cookies are correct, fresh, and complete.")
        # You can uncomment the lines below to save the failed response for debugging
        # with open(f"error_response_{username}.html", "w", encoding="utf-8") as f:
        #     f.write(response.text)
        # print(f"[-] The invalid response has been saved to error_response_{username}.html")
        return None
        
    except Exception as e:
        print(f"[!] An unexpected error occurred: {e}")
        return None




def get_user_posts(user_id: str, limit: int = 24) -> list | None:
    """Fetches a user's posts."""
    
    def get_paginated_data(endpoint: str, limit: int, context: str) -> list | None:
        """Generic function to scrape paginated data like posts, followers, or following."""
        
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
    
    session = requests.Session()
    session.headers.update(get_headers(user_id))

    print(f"\n[*] Preparing to fetch posts for user_id: {user_id}")
    endpoint = f"https://www.instagram.com/api/v1/feed/user/{user_id}/?count=12"
    posts_data = get_paginated_data(endpoint, limit, "posts")
    if not posts_data: return None

    # Clean up the post data to be more readable
    cleaned_posts = []
    for post in posts_data:
        cleaned_posts.append({
            "id": post.get("id"),
            "shortcode": post.get("code"),
            "timestamp": post.get("taken_at"),
            "like_count": post.get("like_count"),
            "comment_count": post.get("comment_count"),
            "caption": post.get("caption", {}).get("text") if post.get("caption") else "",
            "media_type": post.get("media_type"), # 1: Image, 2: Video, 8: Carousel
            "image_url": post.get("image_versions2", {}).get("candidates", [{}])[0].get("url"),
            "video_url": post.get("video_versions", [{}])[0].get("url") if post.get("video_versions") else None,
        })
    return cleaned_posts


def download_image(image_url, save_path='profile_pic.jpg'):
    """Downloads an image from a URL and returns its absolute path."""
    print(f"[+] Downloading image from URL...")
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        
        # Get the absolute path for the file
        absolute_path = os.path.abspath(save_path)
        with open(absolute_path, 'wb') as f:
            f.write(response.content)
        print(f"[+] Image saved to {absolute_path}")
        return absolute_path
    except requests.exceptions.RequestException as e:
        print(f"[!] Failed to download image: {e}")
        return None