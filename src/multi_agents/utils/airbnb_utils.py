import random
import time
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import traceback
from urllib.parse import urljoin
from multi_agents.constants.constants import USER_AGENTS, SELENIUM_HOST

def initialize_driver(selenium_host=SELENIUM_HOST):
    """Initializes and returns a Selenium WebDriver instance."""
    # print("--- [1] Connecting to Selenium Remote WebDriver ---")
    options = Options()
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    try:
        driver = webdriver.Remote(command_executor=selenium_host, options=options)
        return driver
    except Exception as e:
        # print(f"!!!!!! ERROR initializing WebDriver: {e} !!!!!!")
        traceback.print_exc()
        return None

def get_profile_page_html(driver, url):
    """Navigates to the URL, handles the review modal, and returns the final HTML source."""
    # print(f"\n--- [2] Navigating to URL: {url} ---")
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.h1oqg76h')))
        # print("SUCCESS: Page loaded.")
        
        # Click "Show all reviews" button and scroll modal
        try:
            show_all_button_xpath = "//button[contains(., 'Show all') and contains(., 'reviews')]"
            show_all_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, show_all_button_xpath))
            )
            # print("Found 'Show all reviews' button. Clicking...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_all_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", show_all_button)

            modal_selector = "div[role='dialog']"
            WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, modal_selector))
            )
            # print("Reviews modal is now visible.")
            
            scrollable_div = driver.find_element(By.CSS_SELECTOR, f"{modal_selector} section > div")
            
            # print("Scrolling review modal to load all content...")
            last_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
            while True:
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", scrollable_div)
                time.sleep(1.5)
                new_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
                if new_height == last_height:
                    break
                last_height = new_height
            # print("Finished scrolling.")

        except TimeoutException:
            print("'Show all reviews' button not found or modal did not open. Scraping visible reviews.")
        except Exception as e:
            print(f"An error occurred with the 'Show all reviews' button/modal: {e}")

        return driver.page_source

    except Exception as e:
        # print(f"!!!!!! ERROR during page navigation or interaction: {e} !!!!!!")
        traceback.print_exc()
        return None
    
def scrape_profile_details(soup):
    """Scrapes the main profile details (name, bio, about)."""
    details = {'name': 'Name not found', 'about_details': [], 'bio': None}
    try:
        # More reliable selector for the name within the top-left profile card
        name_tag = soup.select_one('div.h1oqg76h h2')
        if name_tag:
            details['name'] = name_tag.get_text(strip=True)
        
        # Scrape structured "About" details
        about_heading = soup.find('h1', string=lambda s: s and 'About' in s)
        if about_heading:
            details_container = about_heading.find_next_sibling('div')
            if details_container and details_container.find('ul'):
                for item in details_container.find('ul').find_all('li'):
                    details['about_details'].append(item.get_text(strip=True))

        # Scrape bio paragraph
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
        # print(f"Found {len(review_groups)} review groups to process.")
        
        for group in review_groups:
            review_data = {}
            
            # --- Scrape Guest Review ---
            reviewer_info_block = group.select_one('div.c10or9ri')
            if not reviewer_info_block: continue
            
            review_data['reviewer_name'] = reviewer_info_block.select_one('div.t126ex63').get_text(strip=True)
            location_tag = reviewer_info_block.select_one('div.s17vloqa span')
            review_data['reviewer_location'] = location_tag.get_text(strip=True) if location_tag and location_tag.get_text() else 'N/A'
            
            date_rating_block = group.select_one('div.sv3k0pp')
            review_data['date'] = date_rating_block.get_text(strip=True).split('·')[-1].strip()
            rating_tag = date_rating_block.select_one('span.a8jt5op')
            review_data['rating'] = rating_tag.get_text(strip=True) if rating_tag else 'N/A'
            
            review_text_block = group.select_one('div[id^="review-"] > div')
            review_data['text'] = review_text_block.get_text(separator='\n', strip=True) if review_text_block else 'N/A'
            
            # --- Scrape Host Response ---
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
            
    except Exception as e:
        # print(f"Warning: Could not parse 'reviews' section. Error: {e}")
        traceback.print_exc()
        
    # print(f"Successfully extracted {len(reviews_list)} reviews.")
    return reviews_list


def get_listing_page_html(driver, url):
    """
    Navigates to an Airbnb listing URL, performs necessary interactions to reveal all data,
    and returns the fully rendered page HTML.
    """
    try:
        # print(f"--- [Step 2] Navigating to URL: {url} ---")
        driver.get(url)

        # print("--- [Step 3] Waiting for key page content to load ---")
        WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.TAG_NAME, "h1")))
        # print("SUCCESS: Key content (H1) is visible.")

        # Give page a moment to settle and check for pop-ups
        time.sleep(2)
        try:
            close_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Close']")
            if close_button.is_displayed():
                close_button.click()
                # print("INFO: Closed a pop-up modal.")
                time.sleep(1)
        except Exception:
            print("INFO: No pop-up modal found to close.")

        # print("--- [Step 4] Clicking price to reveal breakdown ---")
        try:
            # Use a more specific selector for the price button
            price_button_selector = "div[data-plugin-in-point-id='BOOK_IT_SIDEBAR'] button._194r9nk1"
            price_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, price_button_selector))
            )
            driver.execute_script("arguments[0].click();", price_button)
            # print("SUCCESS: Clicked the price breakdown button.")
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div[aria-label='Price details']")))
            # print("SUCCESS: Price details modal is visible.")
            time.sleep(1.5) # Allow modal content to fully render
        except Exception as e:
            print(f"WARNING: Could not click price breakdown. Price details may be incomplete. Error: {e}")

        # print("--- [Step 5] Expanding location description (if available) ---")
        try:
            location_show_more_button = driver.find_element(By.CSS_SELECTOR, "div[data-section-id='LOCATION_DEFAULT'] button")
            driver.execute_script("arguments[0].click();", location_show_more_button)
            # print("SUCCESS: Clicked 'Show more' for location description.")
            time.sleep(1)
        except Exception:
            print("INFO: No 'Show more' button for location found (normal for short descriptions).")

        # print("--- [Step 6] Scrolling to load all content ---")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3) # Wait for lazy-loaded content to appear

        # print("--- [Step 7] Extracting fully rendered HTML ---")
        return driver.page_source
        
    except Exception as e:
        # print(f"!!!!!! ERROR during browser interaction: {e} !!!!!!")
        traceback.print_exc()
        return None
    

def scrape_listing_details(soup):
    """
    Parses the HTML source of an Airbnb listing page using BeautifulSoup
    and extracts all key information into a dictionary.
    """
    if not soup:
        # print("ERROR: Cannot parse details from empty HTML source.")
        return None

    # print("\n--- [Step 8] Parsing HTML with BeautifulSoup ---")
    final_data = {}

    # Each section is in its own try/except block for maximum robustness
    try:
        final_data['apartment_name'] = soup.find('h1').get_text(strip=True)
        # print("SUCCESS: Apartment name found.")
    except:
        final_data['apartment_name'] = "Not Found"

    try:
        items = [li.get_text(strip=True).replace('·', '').strip() for li in soup.select('div[data-section-id="OVERVIEW_DEFAULT_V2"] ol > li')]
        final_data['listing_summary'] = ' · '.join(filter(None, items))
        # print("SUCCESS: Listing summary found.")
    except:
        final_data['listing_summary'] = "Not Found"
        
    try:
        rating_header = soup.find('span', class_='_19wll60c')
        if rating_header:
            rating_parts = rating_header.get_text(strip=True, separator=' ').split('·')
            final_data['rating'] = rating_parts[0].strip() if rating_parts else "Not Found"
            final_data['reviews_count'] = rating_parts[1].strip() if len(rating_parts) > 1 else "Not Found"
            # print("SUCCESS: Rating and reviews count found.")
        else:
             final_data['rating'] = "Not Found"
             final_data['reviews_count'] = "Not Found"
    except Exception as e:
        final_data['rating'] = "Not Found"
        final_data['reviews_count'] = "Not Found"
        # print(f"ERROR: Could not find rating - {e}")
        
    try:
        price_details = {}
        sidebar = soup.find('div', {'data-plugin-in-point-id': 'BOOK_IT_SIDEBAR'})
        price_details['display_price'] = sidebar.select_one('button._194r9nk1 span.umg93v9').get_text(strip=True)
        price_details['duration_text'] = sidebar.find('span', class_='q1vzye7p').get_text(strip=True)
        
        modal = soup.find('div', {'aria-label': 'Price details'})
        if modal:
            breakdown = {}
            for row in modal.select('section > div > div'):
                label_el = row.find('span')
                value_container = row.select_one('span:last-child')
                if label_el and value_container:
                    label = label_el.get_text(strip=True).replace(' x ', '_x_')
                    price_span = value_container.find('span', {'aria-hidden': 'true'}) or value_container
                    value = price_span.get_text(strip=True).split(' ')[0]
                    breakdown[label] = value
            price_details['breakdown'] = breakdown
            # print("SUCCESS: Parsed detailed price breakdown.")
        else:
            print("WARNING: Price breakdown modal not found in HTML.")
        
        final_data['price_details'] = price_details
    except Exception as e:
        final_data['price_details'] = {"error": f"Could not parse price details - {e}"}
        
    try:
        urls = {src.split('?')[0] for img in soup.select('div[data-section-id="HERO_DEFAULT"] img') if (src := (img.get('data-original-uri') or img.get('src'))) and 'a0.muscache.com/im/pictures' in src}
        final_data['image_urls'] = list(urls)[:5]
        # print(f"SUCCESS: Found {len(final_data['image_urls'])} image URLs.")
    except:
        final_data['image_urls'] = []

    try:
        desc_div = soup.find('div', {'data-section-id': 'DESCRIPTION_DEFAULT'})
        if desc_div.find('button'): desc_div.find('button').decompose()
        for br in desc_div.find_all("br"): br.replace_with("\n")
        final_data['description'] = desc_div.get_text(separator='\n', strip=True)
        # print("SUCCESS: Description found.")
    except:
        final_data['description'] = "Not Found"

    try:
        host_info = {}
        host_overview = soup.find('div', {'data-section-id': 'HOST_OVERVIEW_DEFAULT'})
        if host_overview:
            host_info['name'] = host_overview.find('div', class_='t1lpv951').get_text(strip=True).replace('Hosted by ', '')
            details = [li.get_text(strip=True).replace('·', '').strip() for li in host_overview.select('ol li')]
            host_info['details'] = ' | '.join(filter(None, details))
        meet_host_section = soup.find('div', {'data-section-id': 'MEET_YOUR_HOST'})
        if meet_host_section:
            profile_link = meet_host_section.find('a', href=lambda h: h and '/users/show/' in h)
            if profile_link: host_info['profile_url'] = f"https://www.airbnb.com{profile_link['href']}"
            cohosts = []
            for item in meet_host_section.select('ul.ato18ul li'):
                link = item.find('a', href=lambda h: h and '/users/show/' in h)
                if link: cohosts.append({"name": item.get_text(strip=True), "profile_url": f"https://www.airbnb.com{link['href']}"})
            if cohosts: host_info['cohosts'] = cohosts
        final_data['host_info'] = host_info
        # print("SUCCESS: Host info found.")
    except:
        final_data['host_info'] = "Not Found"

    try:
        amenities = []
        for amenity in soup.select('div[data-section-id="AMENITIES_DEFAULT"] ._19xnuo97'):
            if deleted := amenity.find('del'):
                amenities.append(f"Unavailable: {deleted.get_text(strip=True)}")
            else:
                amenities.append(amenity.get_text(strip=True))
        final_data['amenities'] = amenities[:10]
        # print(f"SUCCESS: Found {len(final_data['amenities'])} amenities.")
    except:
        final_data['amenities'] = []

    try:
        location_details = {}
        location_section = soup.find('div', {'data-section-id': 'LOCATION_DEFAULT'})
        if location_section:
            address_tag = location_section.find('h3')
            location_details['address'] = address_tag.get_text(strip=True) if address_tag else "Not Found"
            desc_container = location_section.find('div', class_='pfvk6c5')
            if desc_container:
                if desc_container.find('button'): 
                    desc_container.find('button').decompose()
                location_details['neighborhood_description'] = desc_container.get_text(separator='\n', strip=True)
            else:
                location_details['neighborhood_description'] = "Not Found"
            final_data['location_details'] = location_details
            # print("SUCCESS: Full location details found.")
        else:
            final_data['location_details'] = "Not Found"
            # print("ERROR: Could not find the main location section in the HTML.")
    except Exception as e:
        final_data['location_details'] = "Not Found"
        # print(f"ERROR: An exception occurred while parsing location details - {e}")
        
    return final_data