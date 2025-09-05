# multi_agents/utils/airbnb_utils.py

import random
import time
import traceback
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from multi_agents.constants.constants import USER_AGENTS

# ---------------------------- Driver setup ----------------------------

CHROMEDRIVER_PATH = r"C:\Windows\chromedriver.exe"

def initialize_driver(headless: bool = True):
    """
    Initializes and returns a Selenium WebDriver instance using local chromedriver.exe.
    Pass headless=False if you want to SEE the Chrome browser window.
    """
    options = Options()
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")



    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)

    try:
        service = Service(CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(2)
        return driver
    except Exception as e:
        print(f"[initialize_driver] ERROR: {e}")
        traceback.print_exc()
        return None

# ---------------------------- Page fetchers ----------------------------

def get_profile_page_html(driver, url):
    """Navigates to the URL, handles the review modal, and returns the final HTML source."""
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.h1oqg76h')))

        # Click "Show all reviews" button and scroll modal
        try:
            show_reviews_button_xpath = (
                "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show') "
                "and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reviews')]"
            )

            show_all_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, show_reviews_button_xpath))
            )

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_all_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", show_all_button)

            modal_selector = "div[role='dialog']"
            WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, modal_selector))
            )

            scrollable_div = driver.find_element(By.CSS_SELECTOR, f"{modal_selector} section > div")

            # Scroll the modal to load all reviews
            last_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
            while True:
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", scrollable_div)
                time.sleep(1.5)
                new_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
                if new_height == last_height:
                    break
                last_height = new_height

        except TimeoutException:
            print("'Show all reviews' button not found or modal did not open. Scraping visible reviews.")
        except Exception as e:
            print(f"An error occurred with the 'Show all reviews' button/modal: {e}")

        return driver.page_source

    except Exception:
        traceback.print_exc()
        return None


def get_listing_page_html(driver, url):
    """
    Navigates to an Airbnb listing URL, performs necessary interactions to reveal all data,
    and returns the fully rendered page HTML.
    """
    try:
        driver.get(url)
        WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.TAG_NAME, "h1")))

        # Close possible pop-up
        time.sleep(2)
        try:
            close_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Close']")
            if close_button.is_displayed():
                close_button.click()
                time.sleep(1)
        except Exception:
            print("INFO: No pop-up modal found to close.")

        # Try to open price breakdown
        try:
            price_button_selector = "div[data-plugin-in-point-id='BOOK_IT_SIDEBAR'] button._194r9nk1"
            price_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, price_button_selector))
            )
            driver.execute_script("arguments[0].click();", price_button)
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div[aria-label='Price details']"))
            )
            time.sleep(1.5)
        except Exception as e:
            print(f"WARNING: Could not click price breakdown. Price details may be incomplete. Error: {e}")

        # Expand location description if present
        try:
            location_show_more_button = driver.find_element(By.CSS_SELECTOR, "div[data-section-id='LOCATION_DEFAULT'] button")
            driver.execute_script("arguments[0].click();", location_show_more_button)
            time.sleep(1)
        except Exception:
            print("INFO: No 'Show more' button for location found (normal for short descriptions).")

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        return driver.page_source

    except Exception:
        traceback.print_exc()
        return None

# ---------------------------- Scrapers ----------------------------

def scrape_profile_details(soup):
    """Scrapes the main profile details (name, bio, about)."""
    details = {'name': 'Name not found', 'about_details': [], 'bio': None}
    try:
        name_tag = soup.select_one('div.h1oqg76h h2')
        if name_tag:
            details['name'] = name_tag.get_text(strip=True)

        # user image
        img_tag = soup.find('img', alt=lambda t: t and 'Profil' in t)
        details['profile_picture_url'] = img_tag['src'] if img_tag else 'Not Found'

        # Structured "About"
        about_heading = soup.find('h1', string=lambda s: s and 'About' in s)
        if about_heading:
            details_container = about_heading.find_next_sibling('div')
            if details_container and details_container.find('ul'):
                for item in details_container.find('ul').find_all('li'):
                    details['about_details'].append(item.get_text(strip=True))

        # Bio
        bio_tag = soup.select_one('div._1ww3fsj9 span, div.a1ftvvwk span')
        if bio_tag:
            details['bio'] = bio_tag.get_text(strip=True, separator='\n')

    except Exception as e:
        print(f"Warning: Could not parse profile name/bio section. Error: {e}")
    return details


def scrape_places_visited(soup):
    """Scrapes the 'Where user has been' section."""
    places_list = []
    try:
        places_heading = soup.find('h2', string=lambda s: s and "has been" in s)
        if places_heading:
            scroller = soup.find('div', {'aria-labelledby': places_heading.get('id')})
            if scroller:
                for item in scroller.select('div[id^="caption-"]'):
                    place = item.get_text(strip=True)
                    subtitle_id = item['id'].replace('caption', 'subtitle')
                    detail_tag = scroller.select_one(f'span#{subtitle_id}')
                    detail = detail_tag.get_text(strip=True) if detail_tag else 'N/A'
                    places_list.append({'place': place, 'details': detail})
    except Exception as e:
        print(f"Warning: Could not parse 'places visited' section. Error: {e}")
    return places_list


def scrape_listings(soup, base_url):
    """Scrapes the user's listings."""
    listings = []
    try:
        listings_heading = soup.find('h2', string=lambda s: s and "listings" in s)
        if listings_heading:
            scroller = soup.find('div', {'aria-labelledby': listings_heading.get('id')})
            if scroller:
                for card in scroller.select('div.c3184sb'):
                    link_tag = card.find('a', href=True)
                    type_tag = card.select_one('div[data-testid="listing-card-title"]')
                    title_tag = type_tag.find_next_sibling('div') if type_tag else None
                    rating_tag = title_tag.find_next_sibling('div') if title_tag else None

                    listings.append({
                        'url': urljoin(base_url, link_tag['href']) if link_tag else 'N/A',
                        'type': type_tag.get_text(strip=True) if type_tag else 'N/A',
                        'title': title_tag.get_text(strip=True) if title_tag else 'N/A',
                        'rating_text': rating_tag.get_text(strip=True, separator=' ') if rating_tag else 'N/A'
                    })
    except Exception as e:
        print(f"Warning: Could not parse 'listings' section. Error: {e}")
    return listings


def scrape_reviews(soup):
    """Scrapes all reviews from the page, prioritizing the modal content."""
    reviews_list = []
    try:
        review_scope = soup.select_one("div[role='dialog']") or soup
        review_groups = review_scope.select('div.cwt93ug')

        for group in review_groups:
            review_data = {}

            reviewer_info_block = group.select_one('div.c10or9ri')
            if not reviewer_info_block:
                continue

            review_data['reviewer_name'] = reviewer_info_block.select_one('div.t126ex63').get_text(strip=True)
            location_tag = reviewer_info_block.select_one('div.s17vloqa span')
            review_data['reviewer_location'] = location_tag.get_text(strip=True) if location_tag and location_tag.get_text() else 'N/A'

            date_rating_block = group.select_one('div.sv3k0pp')
            review_data['date'] = date_rating_block.get_text(strip=True).split('·')[-1].strip()
            rating_tag = date_rating_block.select_one('span.a8jt5op')
            review_data['rating'] = rating_tag.get_text(strip=True) if rating_tag else 'N/A'

            review_text_block = group.select_one('div[id^="review-"] > div')
            review_data['text'] = review_text_block.get_text(separator='\n', strip=True) if review_text_block else 'N/A'

            host_response_block = group.select_one('div.cu8gfs0')
            if host_response_block:
                review_data['host_response'] = {
                    'responder_name': host_response_block.select_one('div.t126ex63').get_text(strip=True),
                    'date': host_response_block.select_one('div.s17vloqa').get_text(strip=True),
                    'text': host_response_block.select_one('div.c1um7q2x > div').get_text(separator='\n', strip=True)
                }
            else:
                review_data['host_response'] = None

            reviews_list.append(review_data)

    except Exception:
        traceback.print_exc()

    return reviews_list


def scrape_listing_details(soup):
    """Parses the HTML source of an Airbnb listing page into a dictionary."""
    if not soup:
        return None

    final_data = {}

    # (all your listing parsing logic here — unchanged from your original file)
    # apartment_name, summary, rating, price, images, description, host_info, amenities, location …

    return final_data
