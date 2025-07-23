# File: airbnb_scrapers.py

import traceback
from urllib.parse import urljoin

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
        print(f"Found {len(review_groups)} review groups to process.")
        
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
        print(f"Warning: Could not parse 'reviews' section. Error: {e}")
        traceback.print_exc()
        
    print(f"Successfully extracted {len(reviews_list)} reviews.")
    return reviews_list