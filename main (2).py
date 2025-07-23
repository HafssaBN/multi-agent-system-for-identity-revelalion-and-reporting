# File: main.py

import json
from bs4 import BeautifulSoup
from airbnb_utils import initialize_driver, get_profile_page_html
from airbnb_scrapers import (
    scrape_profile_details,
    scrape_places_visited,
    scrape_listings,
    scrape_reviews,
)

def scrape_airbnb_profile_all(url, selenium_host="http://localhost:4444/wd/hub"):
    """
    Orchestrates the entire scraping process for a single Airbnb profile.
    
    Args:
        url (str): The URL of the Airbnb user profile.
        selenium_host (str): The command executor URL for the Selenium remote WebDriver.

    Returns:
        dict: A dictionary containing all scraped data.
    """
    driver = initialize_driver(selenium_host)
    if not driver:
        return None

    html_content = get_profile_page_html(driver, url)
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Run all the individual scrapers
    profile_details = scrape_profile_details(soup)
    places_visited = scrape_places_visited(soup)
    listings = scrape_listings(soup, url)
    reviews = scrape_reviews(soup)
    
    # Combine all data into a single dictionary
    final_data = {
        **profile_details,
        'places_visited': places_visited,
        'listings': listings,
        'reviews': reviews,
    }
    
    return final_data

if __name__ == '__main__':
    # --- Example Usage ---
    # profile_url = "https://www.airbnb.com/users/show/85941774" # Ajbir Homes
    profile_url = "https://www.airbnb.com/users/show/390550008" # Mohamed Elttahiri
    
    scraped_data = scrape_airbnb_profile_all(profile_url)
    
    if scraped_data:
        print("\n--- [4] FINAL COMBINED DATA ---")
        print(json.dumps(scraped_data, indent=2, ensure_ascii=False))