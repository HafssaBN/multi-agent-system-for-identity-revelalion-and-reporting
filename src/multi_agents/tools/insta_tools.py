import requests
import random
import time
import json
from multi_agents.constants.constants import COOKIES  
from multi_agents.utils.insta_utils import get_headers, handle_api_error # get_paginated_data
import os
from langchain_core.tools import tool
from typing import List, Dict, Optional, Union, Any


# Type definitions for better code clarity
InstagramUser = Dict[str, Union[str, bool, Optional[str]]]
InstagramPost = Dict[str, Union[str, int, Optional[str]]]
ProfileInfo = Dict[str, Union[str, int, bool, Optional[str]]]

@tool
def get_instagram_user_id(username: str) -> Optional[str]:
    """
    Retrieves the numeric user ID for a given Instagram username using Instagram's search API.
    
    This tool performs a search query to find the user's profile and extracts their internal
    numeric user ID, which is required for other Instagram API calls.
    
    Args:
        username (str): The Instagram username to look up (without @ symbol)
                       Example: "saraabujad" (not "@saraabujad")
    
    Returns:
        Optional[str]: The numeric user ID as a string, or None if:
            - User not found in search results
            - API request fails (rate limiting, forbidden access, etc.)
            - Network or parsing errors occur
    
    Rate Limiting:
        - Includes random delays (1.5-4.5 seconds) between requests
        - May return None if rate limited (429 status code)
    
    Example:
        >>> get_instagram_user_id("saraabujad")
        '3271951350'
        
        >>> get_instagram_user_id("nonexistent_user")
        None
    """
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

        # print(f"[!] User '{username}' not found in search results.")
        return None

    except requests.exceptions.HTTPError as e:
        # print(f"[!] HTTP error: {e}")
        if response.status_code == 429:
            print("[!] Rate limited. Slow down your requests!")
        elif response.status_code == 403:
            print("[!] Access forbidden. Check cookies.")
        return None
    except Exception as e:
        # print(f"[!] Unexpected error: {e}")
        return None

@tool
def get_instagram_user_following(user_id: str, limit: int = 100, batch_size: int = 50) -> List[InstagramUser]:
    """
    Retrieves the list of accounts that a user is following on Instagram.
    
    This tool uses Instagram's GraphQL API to fetch following data with pagination support
    for handling large following lists efficiently.
    
    Args:
        user_id (str): The numeric Instagram user ID (obtained from get_instagram_user_id)
        limit (int, optional): Maximum number of following accounts to retrieve. Defaults to 100.
        batch_size (int, optional): Number of accounts to fetch per API request. Defaults to 50.
                                   Smaller batches may be more reliable for rate limiting.
    
    Returns:
        List[InstagramUser]: A list of dictionaries, each containing:
            - id (str): Numeric user ID of the followed account
            - username (str): Username of the followed account
            - full_name (Optional[str]): Display name, may be None
            - profile_pic_url (Optional[str]): URL to profile picture
            - is_private (bool): Whether the account is private
        
        Returns empty list if user has no following or if API requests fail.
    
    Rate Limiting:
        - Includes random delays (1.5-3.5 seconds) between requests
        - Automatically handles pagination with cursor-based navigation
    
    Example:
        >>> get_instagram_user_following("3271951350", limit=5)
        [
            {
                'id': '39914875436',
                'username': 'hafssa_karbane',
                'full_name': 'Hafssa karbane',
                'profile_pic_url': 'https://instagram.frba2-1.fna.fbcdn.net/...',
                'is_private': False
            },
            # ... more users
        ]
    """
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
            # print(f"[!] HTTP error: {e}")
            break
        except Exception as e:
            # print(f"[!] Unexpected error: {e}")
            break

        user_data = data.get("data", {}).get("user")
        if not user_data:
            # print("[!] No user data returned, stopping.")
            break

        edge_follow = user_data.get("edge_follow")
        if not edge_follow:
            # print("[!] No 'edge_follow' data, stopping.")
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

        # print(f"Fetched {len(following)} following so far...")

    return following[:limit]

@tool
def get_instagram_user_followers(user_id: str, limit: int = 100, batch_size: int = 50) -> List[InstagramUser]:
    """
    Retrieves the list of accounts following a specific Instagram user.
    
    This tool uses Instagram's GraphQL API to fetch follower data with pagination support.
    Note that private accounts may not return follower information.
    
    Args:
        user_id (str): The numeric Instagram user ID (obtained from get_instagram_user_id)
        limit (int, optional): Maximum number of followers to retrieve. Defaults to 100.
        batch_size (int, optional): Number of followers to fetch per API request. Defaults to 50.
    
    Returns:
        List[InstagramUser]: A list of dictionaries, each containing:
            - id (str): Numeric user ID of the follower
            - username (str): Username of the follower
            - full_name (Optional[str]): Display name, may be None
            - profile_pic_url (Optional[str]): URL to profile picture
            - is_private (bool): Whether the follower's account is private
        
        Returns empty list if user has no followers, account is private, or API requests fail.
    
    Rate Limiting:
        - Includes random delays (1.5-3.5 seconds) between requests
        - Handles pagination automatically using cursor-based navigation
    
    Privacy Notes:
        - May return limited or no data for private accounts
        - Some users may have restricted follower visibility
    
    Example:
        >>> get_instagram_user_followers("3271951350", limit=3)
        [
            {
                'id': '76120869150',
                'username': 'youssef1239051',
                'full_name': 'Youssef123',
                'profile_pic_url': 'https://instagram.famm3-1.fna.fbcdn.net/...',
                'is_private': False
            },
            # ... more followers
        ]
    """
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
            # print(f"[!] HTTP error: {e}")
            break
        except Exception as e:
            # print(f"[!] Unexpected error: {e}")
            break

        user_data = data.get("data", {}).get("user")
        if not user_data:
            # print("[!] No user data returned, stopping.")
            break

        edge_followed_by = user_data.get("edge_followed_by")
        if not edge_followed_by:
            # print("[!] No 'edge_followed_by' data, stopping.")
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

        # print(f"Fetched {len(followers)} followers so far...")

    return followers[:limit]

@tool
def get_instagram_user_info(username: str) -> Optional[ProfileInfo]:
    """
    Fetches comprehensive profile information for an Instagram user.
    
    This tool retrieves detailed user data including bio, follower counts, verification status,
    and other profile metadata using Instagram's web profile API.
    
    Args:
        username (str): The Instagram username to look up (without @ symbol)
    
    Returns:
        Optional[ProfileInfo]: A dictionary containing comprehensive profile data:
            - user_id (str): Numeric user ID
            - full_name (Optional[str]): User's display name
            - description (Optional[str]): Bio/description text with contact info
            - followers (int): Number of followers
            - following (int): Number of accounts being followed
            - post_count (int): Total number of posts
            - is_private (bool): Whether the account is private
            - is_verified (bool): Whether the account has a verified badge
            - profile_pic_url (Optional[str]): High-resolution profile picture URL
            - external_url (Optional[str]): Link in bio (website, YouTube, etc.)
        
        Returns None if:
            - User not found (404 error)
            - Access forbidden due to invalid cookies (403 error)
            - Rate limited by Instagram (429 error)
            - JSON parsing fails (usually indicates blocked request)
    
    Error Handling:
        - Handles various HTTP status codes with specific error messages
        - Includes random delays (2.0-5.0 seconds) to mimic human behavior
        - Provides detailed error context for troubleshooting
    
    Example:
        >>> get_instagram_user_info("saraabujad")
        {
            'user_id': '3271951350',
            'full_name': 'سارة',
            'description': 'Good vibes only🔥\\nFounder of @saraabujad_beauty_center',
            'followers': 5231283,
            'following': 589,
            'post_count': 352,
            'is_private': False,
            'is_verified': True,
            'profile_pic_url': 'https://scontent-bcn1-1.cdninstagram.com/...',
            'external_url': 'http://www.youtube.com/saraabujad'
        }
    """

    session = requests.Session()
    session.cookies.update(COOKIES)
    api_url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    # print(f"[*] Fetching all info for '{username}' from API: {api_url}")

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
            # print(f"[!] User '{username}' not found in API response. The profile may be private, non-existent, or there was an issue with the request.")
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
        # print(f"[!] HTTP Error: {e}")
        if e.response.status_code == 404:
            print(f"[-] Profile '{username}' not found (404).")
        elif e.response.status_code == 403:
            print("[-] Access Forbidden (403). Your cookies are likely invalid or expired. Please get new ones.")
        elif e.response.status_code == 429:
            print("[-] Rate limited by Instagram (429). Please wait before trying again.")
        return None
        
    except json.JSONDecodeError:
        # print("[!] Critical Error: Failed to decode JSON from response.")
        # print("[-] This usually means Instagram blocked the request and sent an HTML login page instead.")
        # print("[-] Please double-check that your cookies are correct, fresh, and complete.")
        # You can uncomment the lines below to save the failed response for debugging
        # with open(f"error_response_{username}.html", "w", encoding="utf-8") as f:
        #     f.write(response.text)
        # # print(f"[-] The invalid response has been saved to error_response_{username}.html")
        return None
        
    except Exception as e:
        # print(f"[!] An unexpected error occurred: {e}")
        return None

@tool
def get_instagram_user_posts(user_id: str, limit: int = 24) -> Optional[List[InstagramPost]]:
    """
    Retrieves recent posts from an Instagram user's profile feed.
    
    This tool fetches post data including media URLs, engagement metrics, captions,
    and metadata using Instagram's internal feed API with pagination support.
    
    Args:
        user_id (str): The numeric Instagram user ID (obtained from get_instagram_user_id)
        limit (int, optional): Maximum number of posts to retrieve. Defaults to 24.
    
    Returns:
        Optional[List[InstagramPost]]: A list of dictionaries, each containing:
            - id (str): Unique post identifier in format "POST_ID_USER_ID"
            - shortcode (str): Instagram shortcode for the post (used in URLs)
            - timestamp (int): Unix timestamp when post was created
            - like_count (int): Number of likes on the post
            - comment_count (int): Number of comments on the post
            - caption (str): Post caption text (empty string if no caption)
            - media_type (int): Media type (1: Image, 2: Video, 8: Carousel/Multiple)
            - image_url (Optional[str]): URL to the main image/thumbnail
            - video_url (Optional[str]): URL to video file (None for images)
        
        Returns None if:
            - User's posts are not accessible (private account)
            - API request fails or user not found
            - Pagination or JSON parsing errors occur
    
    Rate Limiting:
        - Includes random delays (2.5-5.5 seconds) between paginated requests
        - Uses respectful request timing to avoid triggering rate limits
    
    Privacy Notes:
        - Private accounts may return no posts or limited data
        - Some posts may have restricted visibility
    
    Example:
        >>> get_instagram_user_posts("3271951350", limit=2)
        [
            {
                'id': '3683230471836572107_3271951350',
                'shortcode': 'DMddpl7tpnL',
                'timestamp': 1753295733,
                'like_count': 3601,
                'comment_count': 81,
                'caption': 'جبنا ليهم الساحر باش يبهرهم صدقو هما لي باهرينو 😂',
                'media_type': 2,
                'image_url': 'https://scontent.cdninstagram.com/v/t51.82787-15/...',
                'video_url': 'https://instagram.frba3-2.fna.fbcdn.net/o1/v/t2/...'
            }
        ]
    """
    
    def get_paginated_data(endpoint: str, limit: int, context: str) -> list | None:
        """Generic function to scrape paginated data like posts, followers, or following."""
        
        all_items = []
        next_max_id = None
        
        while True:
            url = endpoint
            if next_max_id:
                url += f"&max_id={next_max_id}"
            
            # print(f"[*] Scraping {context}: Current count: {len(all_items)}...")
            
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
                    # print(f"[*] Reached limit of {limit} for {context}.")
                    return all_items[:limit]

                # Check for more pages
                if data.get("next_max_id"):
                    next_max_id = data["next_max_id"]
                else:
                    break # No more pages

            except requests.exceptions.RequestException as e:
                return handle_api_error(e.response, f"get_paginated_data ({context})")
            except (KeyError, json.JSONDecodeError):
                # print(f"[!] Failed to parse JSON for paginated {context}.")
                break

        # print(f"[*] Finished scraping {context}. Total items found: {len(all_items)}")
        return all_items
    
    session = requests.Session()
    session.headers.update(get_headers(user_id))

    # print(f"\n[*] Preparing to fetch posts for user_id: {user_id}")
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

@tool
def download_image(image_url: str, save_path: str = 'profile_pic.jpg') -> Optional[str]:
    """
    Downloads an image from a URL and saves it to the local filesystem.
    
    This utility tool downloads images (typically profile pictures) from Instagram
    or other sources and returns the absolute path to the saved file.
    
    Args:
        image_url (str): The complete URL to the image to download
                        Example: "https://instagram.com/.../profile_pic.jpg"
        save_path (str, optional): Local filename/path where image will be saved.
                                  Defaults to 'profile_pic.jpg'
    
    Returns:
        Optional[str]: The absolute path to the downloaded image file, or None if:
            - Download request fails (network error, invalid URL, etc.)
            - HTTP error occurs (404, 403, etc.)
            - File system write errors occur
    
    File Handling:
        - Creates the file at the specified path, overwriting if it exists
        - Returns absolute path for cross-platform compatibility
        - Preserves original image format and quality
    
    Error Handling:
        - Handles network timeouts and connection errors
        - Provides error logging for troubleshooting failed downloads
        - Gracefully handles invalid URLs or server errors
    
    Example:
        >>> download_image("https://instagram.com/profile.jpg", "user_profile.jpg")
        'C:\\Users\\username\\Desktop\\project\\user_profile.jpg'
        
        >>> download_image("https://invalid-url.com/image.jpg")
        None
    """
    # print(f"[+] Downloading image from URL...")
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        
        # Get the absolute path for the file
        absolute_path = os.path.abspath(save_path)
        with open(absolute_path, 'wb') as f:
            f.write(response.content)
        # print(f"[+] Image saved to {absolute_path}")
        return absolute_path
    except requests.exceptions.RequestException as e:
        # print(f"[!] Failed to download image: {e}")
        return None