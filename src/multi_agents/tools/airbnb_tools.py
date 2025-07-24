from bs4 import BeautifulSoup
from langchain_core.tools import tool
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
from typing import List, Dict, Optional, Union, Any


# Type definitions for better code clarity
ProfileDetails = Dict[str, Union[str, List[str], Optional[str]]]
PlaceVisited = Dict[str, str]
Listing = Dict[str, str]
HostResponse = Dict[str, str]
Review = Dict[str, Union[str, Optional[HostResponse]]]
ListingDetails = Dict[str, Union[str, Dict[str, Any], List[str]]]

@tool
def get_airbnb_profile_details(profile_url: str) -> Optional[ProfileDetails]:
    """
    Extracts comprehensive profile information from an Airbnb host's profile page.
    
    This tool scrapes the main profile details including the host's name, bio, and 
    structured "About" section details (work, interests, home features, pets, verification status).
    
    Args:
        profile_url (str): The complete URL to the Airbnb host's profile page
                          (e.g., "https://www.airbnb.com/users/show/123456789")
    
    Returns:
        Optional[ProfileDetails]: A dictionary containing profile information with the following structure:
            - name (str): Host's display name
            - about_details (List[str]): List of structured details from About section 
              (work, destinations, home features, pets, verification status)
            - bio (Optional[str]): Host's personal bio/description text, None if not available
        
        Returns None if the profile page cannot be accessed or parsed.
    
    Example:
        >>> get_airbnb_profile_details("https://www.airbnb.com/users/show/123456789")
        {
            'name': 'Abdel',
            'about_details': [
                'My work: Entrepreneur',
                "Where I've always wanted to go: The Moon",
                'What makes my home unique: Premium comfort, Local Experiences.',
                'Pets: Enzo, Malinois',
                'Identity verified'
            ],
            'bio': "I'm Abdel, a passionate entrepreneur and Airbnb host in Marrakech..."
        }
    """
    
    driver = initialize_driver()
    if not driver:
        return None
    
    html_content = get_profile_page_html(driver, profile_url)
    if not html_content:
        return None
    
    soup = BeautifulSoup(html_content, 'html.parser')

    driver.quit()
    profile_details = scrape_profile_details(soup)

    return profile_details

@tool
def get_airbnb_profile_places_visited(profile_url: str) -> Optional[List[PlaceVisited]]:
    """
    Extracts the list of places the host has visited from their Airbnb profile.
    
    This tool scrapes the "Where [host] has been" section, providing insights into
    the host's travel experience and geographic familiarity.
    
    Args:
        profile_url (str): The complete URL to the Airbnb host's profile page
    
    Returns:
        Optional[List[PlaceVisited]]: A list of dictionaries, each containing:
            - place (str): Location name (city, country format)
            - details (str): Visit information (date, number of trips, or other details)
        
        Returns None if the profile page cannot be accessed or parsed.
        Returns empty list if no places visited section is found.
    
    Example:
        >>> get_airbnb_profile_places_visited("https://www.airbnb.com/users/show/123456789")
        [
            {'place': 'London, United Kingdom', 'details': 'June 2025'},
            {'place': 'Casablanca, Morocco', 'details': '4 trips'},
            {'place': 'Ubud, Indonesia', 'details': '2 trips'}
        ]
    """
    driver = initialize_driver()
    if not driver:
        return None
    
    html_content = get_profile_page_html(driver, profile_url)
    if not html_content:
        return None
    
    soup = BeautifulSoup(html_content, 'html.parser')
    driver.quit()

    places_visited = scrape_places_visited(soup)
    
    return places_visited

@tool
def get_airbnb_profile_listings(profile_url: str) -> Optional[List[Listing]]:
    """
    Extracts all property listings hosted by the profile owner.
    
    This tool scrapes the listings section to gather information about all properties
    the host has available on Airbnb, including property types, titles, and ratings.
    
    Args:
        profile_url (str): The complete URL to the Airbnb host's profile page
    
    Returns:
        Optional[List[Listing]]: A list of dictionaries, each containing:
            - url (str): Direct link to the listing page
            - type (str): Property type (e.g., "Bed and breakfast", "Entire place", "Private room")
            - title (str): Property listing title/name
            - rating_text (str): Rating information or "N/A" if no rating available
        
        Returns None if the profile page cannot be accessed or parsed.
        Returns empty list if no listings are found.
    
    Example:
        >>> get_airbnb_profile_listings("https://www.airbnb.com/users/show/123456789")
        [
            {
                'url': 'https://www.airbnb.com/rooms/1471660459697865832',
                'type': 'Bed and breakfast',
                'title': 'Suite Prestige au Riad, 5 min from Jamaa El Fna',
                'rating_text': 'N/A'
            }
        ]
    """
    driver = initialize_driver()
    if not driver:
        return None
    
    html_content = get_profile_page_html(driver, profile_url)
    if not html_content:
        return None
    
    soup = BeautifulSoup(html_content, 'html.parser')

    driver.quit()
    listings = scrape_listings(soup, profile_url)

    
    return listings

@tool
def get_airbnb_profile_reviews(profile_url: str) -> Optional[List[Review]]:
    """
    Extracts all reviews and host responses from an Airbnb host's profile.
    
    This tool scrapes both guest reviews and host responses, providing insights into
    the host's reputation, guest satisfaction, and communication style.
    
    Args:
        profile_url (str): The complete URL to the Airbnb host's profile page
    
    Returns:
        Optional[List[Review]]: A list of dictionaries, each containing:
            - reviewer_name (str): Name of the guest who left the review
            - reviewer_location (str): Guest's location or "N/A" if not available
            - date (str): When the review was posted (relative format like "3 days ago")
            - rating (str): Rating information (e.g., "Rating 5 out of 5")
            - text (str): The review content/message
            - host_response (Optional[HostResponse]): Host's response if available, containing:
                * responder_name (str): Host's name
                * date (str): Response date
                * text (str): Response content
        
        Returns None if the profile page cannot be accessed or parsed.
        Returns empty list if no reviews are found.
    
    Example:
        >>> get_airbnb_profile_reviews("https://www.airbnb.com/users/show/123456789")
        [
            {
                'reviewer_name': 'El Mehdi',
                'reviewer_location': 'Tangier, Morocco',
                'date': '3 days ago',
                'rating': 'Rating 5 out of 5',
                'text': 'Thank you very much Lou and Mohammed...',
                'host_response': None
            }
        ]
    """

    driver = initialize_driver()
    if not driver:
        return None
    
    html_content = get_profile_page_html(driver, profile_url)
    if not html_content:
        return None
    
    soup = BeautifulSoup(html_content, 'html.parser')
    driver.quit()

    reviews = scrape_reviews(soup)
    
    return reviews

@tool
def get_listing_details(listing_url: str) -> Optional[ListingDetails]:
    """
    Extracts comprehensive details from a specific Airbnb property listing.
    
    This tool scrapes detailed information about a property listing including
    amenities, description, host information, location details, and pricing.
    
    Args:
        listing_url (str): The complete URL to the Airbnb listing page
                          (e.g., "https://www.airbnb.com/rooms/123456789")
    
    Returns:
        Optional[ListingDetails]: A dictionary containing detailed listing information:
            - apartment_name (str): Property title/name
            - listing_summary (str): Brief summary (guests, bedrooms, beds, baths)
            - rating (str): Overall rating score
            - reviews_count (str): Number of reviews and rating details
            - price_details (Dict[str, Any]): Pricing information (may contain parsing errors)
            - image_urls (List[str]): List of property image URLs
            - description (str): Full property description text
            - host_info (Dict[str, str]): Host details containing:
                * name (str): Host's name
                * details (str): Host status and experience (e.g., "Superhost | 3 years hosting")
                * profile_url (str): Link to host's profile
            - amenities (List[str]): List of available amenities and features
            - location_details (Dict[str, str]): Location information containing:
                * address (str): Property address
                * neighborhood_description (str): Area description and nearby amenities
        
        Returns None if the listing page cannot be accessed or parsed.
    
    Example:
        >>> get_listing_details("https://www.airbnb.com/rooms/123456789")
        {
            'apartment_name': 'Premium corniche apartment, parking',
            'listing_summary': '4 guests · 1 bedroom · 1 bed · 1 bath',
            'rating': '4.89',
            'reviews_count': '93 reviews Rated 4.89 out of 5 from 93 reviews.',
            'host_info': {
                'name': 'Nadia',
                'details': 'Superhost | 3 years hosting',
                'profile_url': 'https://www.airbnb.com/users/show/298782794'
            },
            'amenities': ['Garden view', 'Kitchen', 'Wifi', 'Free parking'],
            'location_details': {
                'address': 'Casablanca, Casablanca-Settat, Morocco',
                'neighborhood_description': 'Central area on Boulevard de la Corniche...'
            }
        }
    """
    driver = initialize_driver()
    if not driver:
        return None
    
    html_content = get_listing_page_html(driver, listing_url)
    if not html_content:
        return None
    
    soup = BeautifulSoup(html_content, 'html.parser')
    driver.quit()
    listing_details = scrape_listing_details(soup)

    return listing_details

