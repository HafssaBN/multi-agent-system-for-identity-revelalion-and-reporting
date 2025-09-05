# airbnb_tools.py

from bs4 import BeautifulSoup
from langchain_core.tools import tool
from typing import List, Dict, Union, Any

from multi_agents.utils.airbnb_utils import (
    initialize_driver,
    get_profile_page_html,
    get_listing_page_html,
    scrape_profile_details,
    scrape_places_visited,
    scrape_listings,
    scrape_reviews,
    scrape_listing_details,
)

# ---------- Pylance-friendly JSON-ish typing ----------
JSONScalar = Union[str, int, float, bool, None]
JSONValue = Union[JSONScalar, Dict[str, Any], List[Any]]

ProfileDetails = Dict[str, JSONValue]
PlaceVisited   = Dict[str, str]
Listing        = Dict[str, str]
HostResponse   = Dict[str, str]
Review         = Dict[str, JSONValue]
ListingDetails = Dict[str, JSONValue]
ErrorDict      = Dict[str, str]


def _ensure_not_none(data: Any, msg: str) -> Union[Any, ErrorDict]:
    """
    Convert None results into a consistent error dict.
    Keeps tool outputs JSON-serializable and avoids Optional returns.
    """
    if data is None:
        return {"error": msg}
    return data


@tool
def get_airbnb_profile_details(profile_url: str) -> Union[ProfileDetails, ErrorDict]:
    """
    Extract profile information from an Airbnb host's profile page.
    Returns ProfileDetails or {'error': <message>}.
    """
    driver = None
    try:
        driver = initialize_driver()
        if not driver:
            return {"error": "Failed to initialize Selenium WebDriver."}

        html = get_profile_page_html(driver, profile_url)
        if not html:
            return {
                "error": (
                    f"Failed to get HTML content for {profile_url}. "
                    "The page may be inaccessible, behind a CAPTCHA, or the structure changed."
                )
            }

        soup = BeautifulSoup(html, "html.parser")
        details = scrape_profile_details(soup)
        return _ensure_not_none(details, "Could not parse profile details from the page.")
    except Exception as e:
        return {"error": f"Unexpected error in get_airbnb_profile_details: {e}"}
    finally:
        if driver:
            driver.quit()


@tool
def get_airbnb_profile_places_visited(
    profile_url: str,
) -> Union[List[PlaceVisited], ErrorDict]:
    """
    Extract the 'Where [host] has been' section.
    Returns List[PlaceVisited] (possibly empty) or {'error': <message>}.
    """
    driver = None
    try:
        driver = initialize_driver()
        if not driver:
            return {"error": "Failed to initialize Selenium WebDriver."}

        html = get_profile_page_html(driver, profile_url)
        if not html:
            return {"error": f"Failed to get HTML content for {profile_url}."}

        soup = BeautifulSoup(html, "html.parser")
        places = scrape_places_visited(soup)
        parsed = _ensure_not_none(places, "No 'places visited' section found or it could not be parsed.")
        if isinstance(parsed, dict) and "error" in parsed:
            return parsed
        return list(parsed)  # type: ignore[arg-type]
    except Exception as e:
        return {"error": f"Unexpected error in get_airbnb_profile_places_visited: {e}"}
    finally:
        if driver:
            driver.quit()


@tool
def get_airbnb_profile_listings(
    profile_url: str,
) -> Union[List[Listing], ErrorDict]:
    """
    Extract all property listings hosted by the profile owner.
    Returns List[Listing] (possibly empty) or {'error': <message>}.
    """
    driver = None
    try:
        driver = initialize_driver()
        if not driver:
            return {"error": "Failed to initialize Selenium WebDriver."}

        html = get_profile_page_html(driver, profile_url)
        if not html:
            return {"error": f"Failed to get HTML content for {profile_url}."}

        soup = BeautifulSoup(html, "html.parser")
        listings = scrape_listings(soup, profile_url)
        parsed = _ensure_not_none(listings, "No listings found or listings section could not be parsed.")
        if isinstance(parsed, dict) and "error" in parsed:
            return parsed
        return list(parsed)  # type: ignore[arg-type]
    except Exception as e:
        return {"error": f"Unexpected error in get_airbnb_profile_listings: {e}"}
    finally:
        if driver:
            driver.quit()


@tool
def get_airbnb_profile_reviews(
    profile_url: str,
) -> Union[List[Review], ErrorDict]:
    """
    Extract guest reviews and host responses.
    Returns List[Review] (possibly empty) or {'error': <message>}.
    """
    driver = None
    try:
        driver = initialize_driver()
        if not driver:
            return {"error": "Failed to initialize Selenium WebDriver."}

        html = get_profile_page_html(driver, profile_url)
        if not html:
            return {"error": f"Failed to get HTML content for {profile_url}."}

        soup = BeautifulSoup(html, "html.parser")
        reviews = scrape_reviews(soup)
        parsed = _ensure_not_none(reviews, "No reviews found or reviews could not be parsed.")
        if isinstance(parsed, dict) and "error" in parsed:
            return parsed
        return list(parsed)  # type: ignore[arg-type]
    except Exception as e:
        return {"error": f"Unexpected error in get_airbnb_profile_reviews: {e}"}
    finally:
        if driver:
            driver.quit()


@tool
def get_listing_details(listing_url: str) -> Union[ListingDetails, ErrorDict]:
    """
    Extract comprehensive details for a specific listing.
    Returns ListingDetails or {'error': <message>}.
    """
    driver = None
    try:
        driver = initialize_driver()
        if not driver:
            return {"error": "Failed to initialize Selenium WebDriver."}

        html = get_listing_page_html(driver, listing_url)
        if not html:
            return {"error": f"Failed to get HTML content for listing {listing_url}."}

        soup = BeautifulSoup(html, "html.parser")
        details = scrape_listing_details(soup)
        return _ensure_not_none(details, "Could not parse listing details from the page.")
    except Exception as e:
        return {"error": f"Unexpected error in get_listing_details: {e}"}
    finally:
        if driver:
            driver.quit()
