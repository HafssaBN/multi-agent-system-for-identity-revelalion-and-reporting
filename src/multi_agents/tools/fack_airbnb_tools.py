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
    
    return {'name': 'Abdel',
            'about_details': ["Where I've always wanted to go: The Moon",
            'My work: Entrepreneur',
            'For guests, I always: Receive them in person',
            'Pets: Enzo, Malinois',
            'Identity verified'],
            'bio': "I'm Abdel, a passionate entrepreneur and Airbnb host in Marrakech. I offer apartments and riad ideally located (Izdihar, Gueliz, Medina, Palmeraie), combining modern comfort and Moroccan authenticity for a unique experience of the city.",
            'profile_picture_url': 'https://a0.muscache.com/im/pictures/user/User/original/213a678f-2d3c-4b11-886e-df873b318aa4.jpeg?im_w=720'}

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
    return [{'place': 'London, United Kingdom', 'details': 'June 2025'},
            {'place': 'Casablanca, Morocco', 'details': '4 trips'},
            {'place': 'Denpasar, Indonesia', 'details': 'September 2024'},
            {'place': 'Nusa Penida, Indonesia', 'details': 'September 2024'},
            {'place': 'Sukasada, Indonesia', 'details': 'September 2024'},
            {'place': 'Ubud, Indonesia', 'details': '2 trips'},
            {'place': 'Oujda, Morocco', 'details': 'September 2024'},
            {'place': 'Imi Quaddar, Morocco', 'details': 'August 2024'}]
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
    return [{'url': 'https://www.airbnb.com/rooms/1430288794722556873?source_impression_id=p3_1754183708_P3MvB73ec_TnOnG7',
            'type': 'Riad',
            'title': 'Luxury Private Riad, Air-Conditioned and Pool',
            'rating_text': 'N/A'},
            {'url': 'https://www.airbnb.com/rooms/1138999185890900352?source_impression_id=p3_1754183708_P3QKzc808Xd-5hTk',
            'type': 'Rental unit',
            'title': 'Cozy Flat near the city center, 1 Bedroom w/ A/C',
            'rating_text': '4.85 out of 5 average rating 4.85 , · 91 reviews'},
            {'url': 'https://www.airbnb.com/rooms/1199118327355501751?source_impression_id=p3_1754183708_P37oq5cS7ufBUPTo',
            'type': 'Bed and breakfast',
            'title': 'Charming Room in Riad, Just 2 mn from Jama el-Fna!',
            'rating_text': '4.93 out of 5 average rating 4.93 , · 28 reviews'},
            {'url': 'https://www.airbnb.com/rooms/1168655512551259276?source_impression_id=p3_1754183708_P3HHKj12lA7-GWKq',
            'type': 'Rental unit',
            'title': 'Cozy Flat near the city center, 2BR w/Netflix & AC',
            'rating_text': '4.76 out of 5 average rating 4.76 , · 75 reviews'},
            {'url': 'https://www.airbnb.com/rooms/1414517507728935918?source_impression_id=p3_1754183708_P3R6VhegUdtH70WD',
            'type': 'Rental unit',
            'title': 'Mykonos Apartment, Air-Conditioned, Netflix, Small Pool',
            'rating_text': '5.0 out of 5 average rating 5.0 , · 9 reviews'},
            {'url': 'https://www.airbnb.com/rooms/1362312529416292062?source_impression_id=p3_1754183708_P3Skl1aidlYoVdqp',
            'type': 'Condo',
            'title': 'Cosy Appartment w/ Pool, A/C, Tennis',
            'rating_text': '4.44 out of 5 average rating 4.44 , · 9 reviews'},
            {'url': 'https://www.airbnb.com/rooms/1471660459697865832?source_impression_id=p3_1754183708_P3jIlbdU63Kc5agn',
            'type': 'Bed and breakfast',
            'title': 'Suite Prestige au Riad, 5 min from Jamaa El Fna',
            'rating_text': 'N/A'},
            {'url': 'https://www.airbnb.com/rooms/1471588431390978827?source_impression_id=p3_1754183708_P35nafB6valrdER5',
            'type': 'Bed and breakfast',
            'title': 'Medina Prestige Suite, 5 min from Jamaa El Fna',
            'rating_text': 'N/A'},
            {'url': 'https://www.airbnb.com/rooms/1445689129766894859?source_impression_id=p3_1754183708_P3GM8v_jB0SajTW3',
            'type': 'Rental unit',
            'title': 'Relax Stay - Cosy 2BR, A/C, Terrace & Netflix',
            'rating_text': '5.0 out of 5 average rating 5.0 , · 5 reviews'},
            {'url': 'https://www.airbnb.com/rooms/1370331468964838238?source_impression_id=p3_1754183708_P3wK6HLuS_yF7HpI',
            'type': 'Condo',
            'title': '3 Bedroom Flat w/ Pool, Netflix and A/C',
            'rating_text': '4.43 out of 5 average rating 4.43 , · 7 reviews'}]

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

    return [{'reviewer_name': 'Zouheir',
            'reviewer_location': 'Casablanca, Morocco',
            'date': '1 week ago',
            'rating': 'Rating 5 out of 5',
            'text': 'Clean and helpful instructions',
            'host_response': None},
            {'reviewer_name': 'Hayat',
            'reviewer_location': 'N/A',
            'date': '1 week ago',
            'rating': 'Rating 5 out of 5',
            'text': 'The apartment corresponds exactly to the description. Abdel is super kind and is very helpful. Perfect communication. I will gladly return. Thank you for everything.\n🙏\n🙏',
            'host_response': None},
            {'reviewer_name': 'Shazmara',
            'reviewer_location': 'N/A',
            'date': '2 weeks ago',
            'rating': 'Rating 5 out of 5',
            'text': 'We had a fantastic stay at this Airbnb in Marrakech. The apartment was spotless, easy to locate, and access was completely hassle-free. The host’s communication was truly exceptional he was available around the clock, consistently checking in to make sure everything was going well for me and my husband.\nAlthough there was no washing machine, the host went above and beyond by personally washing, drying, and even folding our clothes something he absolutely didn’t have to do, but we really appreciated the extra care.\nThe location is also perfect  just a short walk (under 2 minutes) to shops and cafés, and very close to the city center. We couldn’t have asked for a better spot. We’ll 100% be booking this place again on our next visit to Marrakech!\n20 Mins from the AIRPORT!!',
            'host_response': None},
            {'reviewer_name': 'Eloise',
            'reviewer_location': 'N/A',
            'date': '2 weeks ago',
            'rating': 'Rating 5 out of 5',
            'text': 'Great hosting!\nThanks',
            'host_response': None},
            {'reviewer_name': 'Sarah',
            'reviewer_location': 'El Jadida, Morocco',
            'date': '2 weeks ago',
            'rating': 'Rating 5 out of 5',
            'text': 'We had a wonderful stay! The host was incredibly kind, understanding, and always willing to help. He was very responsive and made sure we had everything we needed at all times. What truly stood out was how welcoming he was . We truly felt at home. Every detail was thoughtfully taken care of, and his positive attitude made our stay even more enjoyable. It’s rare to find someone so generous and attentive. Thank you again for everything!',
            'host_response': None},
            {'reviewer_name': 'City Relay',
            'reviewer_location': 'London, United Kingdom',
            'date': 'June 2025',
            'rating': 'N/A',
            'text': 'Thanks for staying at our place! You took great care of my space, left it clean and tidy. It was a real pleasure hosting you and we hope to see you again soon!',
            'host_response': None},
            {'reviewer_name': 'Abdou',
            'reviewer_location': 'Casablanca, Morocco',
            'date': 'December 2024',
            'rating': 'N/A',
            'text': 'Perfect',
            'host_response': None},
            {'reviewer_name': 'Amine',
            'reviewer_location': 'Casablanca, Morocco',
            'date': 'October 2024',
            'rating': 'N/A',
            'text': 'Hosting Abdel was a wonderful experience. They followed all house rules and were very easy to communicate with. I would highly recommend them to any host. Hope to see you again at Modern & Cosy Condos!',
            'host_response': None},
            {'reviewer_name': 'Joshua',
            'reviewer_location': 'N/A',
            'date': 'September 2024',
            'rating': 'N/A',
            'text': 'A very wonderful and lovely guest, hope to keep hosting them again in the future.',
            'host_response': None},
            {'reviewer_name': 'Ronald',
            'reviewer_location': 'Denpasar, Indonesia',
            'date': 'September 2024',
            'rating': 'N/A',
            'text': 'Thankyou for staying in Aloka Penida',
            'host_response': None}]

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

    listings_url = {
        'https://www.airbnb.com/rooms/1168655512551259276?source_impression_id=p3_1754503729_P3A3dNF58M03-O2Z':{'apartment_name': 'Cozy Flat near the city center, 2BR w/Netflix & AC',
                                                                                                                'listing_summary': '5 guests · 2 bedrooms · 2 beds · 1 bath',
                                                                                                                'rating': 'Not Found',
                                                                                                                'reviews_count': 'Not Found',
                                                                                                                'price_details': {'error': "Could not parse price details - 'NoneType' object has no attribute 'get_text'"},
                                                                                                                'image_urls': ['https://a0.muscache.com/im/pictures/airflow/Hosting-1168655512551259276/original/877c7ce2-bafa-401d-8a3e-37f558175371.jpg',
                                                                                                                'https://a0.muscache.com/im/pictures/airflow/Hosting-1168655512551259276/original/58e4387d-a3c6-478e-918e-e2220a0e3730.jpg',
                                                                                                                'https://a0.muscache.com/im/pictures/airflow/Hosting-1168655512551259276/original/1a70a46a-5e66-45dd-bb27-85b1280c7555.jpg',
                                                                                                                'https://a0.muscache.com/im/pictures/airflow/Hosting-1168655512551259276/original/8f73ac4a-7bf8-480a-839f-161107ce3b16.jpg',
                                                                                                                'https://a0.muscache.com/im/pictures/airflow/Hosting-1168655512551259276/original/f2168058-a75f-49ac-96a0-e6f36a2e9839.jpg'],
                                                                                                                'description': 'Treat yourself to unforgettable moments with family or friends in this splendid accommodation in Marrakech. Equipped with all the necessary amenities, it invites you to experience moments of togetherness and joy in the beautiful red city. Make the most of this getaway to discover the charms of Marrakech and create precious memories in an enchanting setting.',
                                                                                                                'host_info': {'name': 'Abdel',
                                                                                                                'details': 'Superhost | 1 year hosting',
                                                                                                                'profile_url': 'https://www.airbnb.com/users/show/532236013',
                                                                                                                'cohosts': [{'name': 'Moussa',
                                                                                                                    'profile_url': 'https://www.airbnb.com/users/show/665678298'}]},
                                                                                                                'amenities': ['Kitchen',
                                                                                                                'Wifi',
                                                                                                                'Free parking on premises',
                                                                                                                'TV',
                                                                                                                'Washer',
                                                                                                                'Air conditioning',
                                                                                                                'Private patio or balcony',
                                                                                                                'Luggage dropoff allowed',
                                                                                                                'Unavailable: Carbon monoxide alarm',
                                                                                                                'Unavailable: Smoke alarm'],
                                                                                                                'location_details': {'address': 'Marrakesh, Marrakesh-Safi, Morocco',
                                                                                                                'neighborhood_description': 'Marrakesh, Marrakesh-Safi, Morocco\nThe Izdihar district in Marrakech is a peaceful oasis, perfect for those seeking tranquility and comfort. Both quiet and secure, it offers easy access to many attractions. There are several shopping malls, restaurants and coffee shops nearby, allowing you to savor the local cuisine and do some shopping. Well-lit streets and police presence reinforce the feeling of security. Izdihar combines the best of both worlds: a peaceful environment while being close to everything you need for a pleasant stay.'}},
        'https://www.airbnb.com/rooms/1238311445228997747?source_impression_id=p3_1754503729_P3UAygknML9oBEZd':{'apartment_name': 'Cozy Flat near the city center, 2 Rooms w/ A/C',
                                                                                                                'listing_summary': '5 guests · 2 bedrooms · 2 beds · 1 bath',
                                                                                                                'rating': 'Not Found',
                                                                                                                'reviews_count': 'Not Found',
                                                                                                                'price_details': {'error': "Could not parse price details - 'NoneType' object has no attribute 'get_text'"},
                                                                                                                'image_urls': ['https://a0.muscache.com/im/pictures/hosting/Hosting-1238311445228997747/original/948a8272-7296-4c1d-b94e-d9e26a30e884.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/airflow/Hosting-1238311445228997747/original/63215ad4-bdc8-478a-a4ab-96cbf10dfa6a.jpg',
                                                                                                                'https://a0.muscache.com/im/pictures/airflow/Hosting-1238311445228997747/original/3097349a-1b63-4a89-a27d-bf18619b802c.jpg',
                                                                                                                'https://a0.muscache.com/im/pictures/airflow/Hosting-1238311445228997747/original/f83e577a-68a9-468b-a22b-4247fa1bf48c.jpg',
                                                                                                                'https://a0.muscache.com/im/pictures/airflow/Hosting-1238311445228997747/original/7f64832f-180d-4ce1-9975-70afa6b156ac.jpg'],
                                                                                                                'description': 'Discover this charming apartment, a real treasure in the heart of the city. Ideally located, it immerses you in the center of all local attractions, restaurants and shops. Fully equipped for your comfort, it combines style and functionality. Enjoy a memorable stay in this unique place that combines convenience and charm.\nOther things to note\n50 meters from all amenities (dry cleaning, Carrefour supermarket, mosque, gym, hammam...)\n10 min (car) from Gueliz, (less than 3 euro by taxi)\n20 min (by car) from Jamaa el-Fnaa square (less than 4 euro by taxi)\n10 min (by car) to the train station (less than 3 euro by taxi)\nSecure, quiet and convenient neighborhood.',
                                                                                                                'host_info': {'name': 'Abdel',
                                                                                                                'details': 'Superhost | 1 year hosting',
                                                                                                                'profile_url': 'https://www.airbnb.com/users/show/532236013',
                                                                                                                'cohosts': [{'name': 'Moussa',
                                                                                                                    'profile_url': 'https://www.airbnb.com/users/show/665678298'}]},
                                                                                                                'amenities': ['Kitchen',
                                                                                                                'Wifi',
                                                                                                                'Free parking on premises',
                                                                                                                'TV',
                                                                                                                'Washer',
                                                                                                                'Air conditioning',
                                                                                                                'Patio or balcony',
                                                                                                                'Exterior security cameras on property',
                                                                                                                'Unavailable: Carbon monoxide alarm',
                                                                                                                'Unavailable: Smoke alarm'],
                                                                                                                'location_details': {'address': 'Marrakesh, Marrakesh-Safi, Morocco',
                                                                                                                'neighborhood_description': 'Marrakesh, Marrakesh-Safi, Morocco\nThe Izdihar district in Marrakech is a peaceful oasis, perfect for those seeking tranquility and comfort. Both quiet and secure, it offers easy access to many attractions. There are several shopping malls, restaurants and coffee shops nearby, allowing you to savor the local cuisine and do some shopping. Well-lit streets and police presence reinforce the feeling of security. Izdihar combines the best of both worlds: a peaceful environment while being close to everything you need for a pleasant stay.'}},
        'https://www.airbnb.com/rooms/1445689129766894859?source_impression_id=p3_1754503729_P3lfvhEmW-7vbmmZ':{'apartment_name': 'Relax Stay - Cosy 2BR, A/C, Terrace & Netflix',
                                                                                                                'listing_summary': '5 guests · 2 bedrooms · 2 beds · 1 bath',
                                                                                                                'rating': 'Not Found',
                                                                                                                'reviews_count': 'Not Found',
                                                                                                                'price_details': {'error': "Could not parse price details - 'NoneType' object has no attribute 'get_text'"},
                                                                                                                'image_urls': ['https://a0.muscache.com/im/pictures/hosting/Hosting-1445689129766894859/original/ae8e7daf-c0d2-40dc-b4a1-698c5c27f232.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1445689129766894859/original/a8397974-3e52-45aa-9088-370e4d2f6351.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1445689129766894859/original/84002855-1948-4cdf-b074-73cb8e1aa850.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1445689129766894859/original/8f4ee795-7ea9-4162-beb1-c44e08748e6b.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1445689129766894859/original/39d0bf00-800c-4a5b-8f92-7a5b07116b5d.jpeg'],
                                                                                                                'description': 'Enjoy a relaxing stay in this cozy 2-bedroom apartment with air conditioning, a private terrace, and free Netflix. Perfect for couples, families or remote workers. Fully equipped kitchen, comfy beds, and a bright living space. Located in a quiet area, close to shops and transport. Ideal for short or long stays!\nThe space\nBright apartment with 2 comfortable bedrooms, a modern bathroom, a cozy living room, and a sunny terrace perfect for relaxing.\nThe kitchen is fully equipped for all your cooking needs.\nLocated just 7 minutes from the city center and 15 minutes from the famous Jemaa el-Fna square. Ideal for a comfortable stay with family, friends, or as a couple, in a quiet and convenient area close to all amenities.',
                                                                                                                'host_info': {'name': 'Abdel',
                                                                                                                'details': 'Superhost | 1 year hosting',
                                                                                                                'profile_url': 'https://www.airbnb.com/users/show/532236013',
                                                                                                                'cohosts': [{'name': 'Moussa',
                                                                                                                    'profile_url': 'https://www.airbnb.com/users/show/665678298'}]},
                                                                                                                'amenities': ['Kitchen',
                                                                                                                'Wifi',
                                                                                                                'Free parking on premises',
                                                                                                                'TV',
                                                                                                                'Washer',
                                                                                                                'Air conditioning',
                                                                                                                'Luggage dropoff allowed',
                                                                                                                'Exterior security cameras on property',
                                                                                                                'Unavailable: Carbon monoxide alarm',
                                                                                                                'Unavailable: Smoke alarm'],
                                                                                                                'location_details': {'address': 'Not Found',
                                                                                                                'neighborhood_description': 'Not Found'}}, 
        'https://www.airbnb.com/rooms/1430288794722556873?source_impression_id=p3_1754503729_P3Te32VV9aRpVX7v':{'apartment_name': 'Luxury Private Riad, Air-Conditioned and Pool',
                                                                                                                'listing_summary': '6 guests · 3 bedrooms · 3 beds · 3 baths',
                                                                                                                'rating': 'Not Found',
                                                                                                                'reviews_count': 'Not Found',
                                                                                                                'price_details': {'error': "Could not parse price details - 'NoneType' object has no attribute 'get_text'"},
                                                                                                                'image_urls': ['https://a0.muscache.com/im/pictures/hosting/Hosting-1430288794722556873/original/4b51a951-c756-48b2-96f0-4f189cfd6c93.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1430288794722556873/original/f316702a-8002-4f95-8ed2-c93a3e814d73.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1430288794722556873/original/8246c0ac-50e5-4c5d-933b-536cf34a5263.png',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1430288794722556873/original/e183f3da-f6d2-487f-bfc6-08afa8023881.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1430288794722556873/original/ed836814-dd9d-4c6e-b4b4-9e1c144e1166.png'],
                                                                                                                'description': "Private Riad located in the prestigious Marrakech Palm Grove. It offers 3 bedrooms with bathrooms, a spacious living room, dining room, equipped kitchen, private pool with deckchairs. Daily cleaning included.\nBreakfast available upon request (not included). Perfect for a stay with family or friends, in a peaceful setting combining comfort, privacy and Moroccan charm.\nThe space\nThe Riad offers total privacy in the prestigious Marrakech Palm Grove. It has 3 bedrooms with private bathrooms, a spacious living room, a dining room, a fully-equipped kitchen, and a private pool and two terraces.\nYou will also find air conditioning in all rooms, a TV, high-speed Wi-Fi, as well as a wood-burning stove for your cool evenings on the ground floor and on the terrace.\nThe Riad is decorated in the traditional Moroccan style with all modern comforts for a peaceful and pleasant stay.\nGuest access\nGuests have full access to the entire Riad.\nI am always in touch with my guests, available to welcome you at any time, whether in the morning or late at night.\nAirport pick-up can be arranged upon request (paid service).\nOther things to note\nPassport declaration is mandatory for all travelers, according to Moroccan law.\nParties are forbidden after 11 p.m.\nStrictly no smoking inside (living room and bedrooms). Smoking is only allowed on the terrace or near the pool.\nA housekeeper is present every day to ensure cleaning.\nBreakfast, lunch and dinner are available on request (not included in the price).\nJust let us know your preferences in advance, and we'll take care of it, service with payment",
                                                                                                                'host_info': {'name': 'Moussa',
                                                                                                                'details': '8 months hosting',
                                                                                                                'profile_url': 'https://www.airbnb.com/users/show/665678298',
                                                                                                                'cohosts': [{'name': 'Abdel',
                                                                                                                    'profile_url': 'https://www.airbnb.com/users/show/532236013'}]},
                                                                                                                'amenities': ['Kitchen',
                                                                                                                'Wifi',
                                                                                                                'Free parking on premises',
                                                                                                                'Pool',
                                                                                                                'TV',
                                                                                                                'Washer',
                                                                                                                'Dryer',
                                                                                                                'Air conditioning',
                                                                                                                'Bathtub',
                                                                                                                'Private patio or balcony'],
                                                                                                                'location_details': {'address': 'Not Found',
                                                                                                                'neighborhood_description': 'Not Found'}},
        'https://www.airbnb.com/rooms/1370331468964838238?source_impression_id=p3_1754503729_P3wVNZTeL5-JRnC-':{'apartment_name': '3 Bedroom Flat w/ Pool, Netflix and A/C',
                                                                                                                'listing_summary': '6 guests · 3 bedrooms · 4 beds · 2 baths',
                                                                                                                'rating': 'Not Found',
                                                                                                                'reviews_count': 'Not Found',
                                                                                                                'price_details': {'error': "Could not parse price details - 'NoneType' object has no attribute 'get_text'"},
                                                                                                                'image_urls': ['https://a0.muscache.com/im/pictures/hosting/Hosting-1370331468964838238/original/f0b34871-df13-4323-aa6d-a76c583294b3.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1370331468964838238/original/87ef6c78-c754-4c37-9620-1ccc8591c1ce.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1370331468964838238/original/98b5d352-3cce-410d-9859-55e9ad0fcd2b.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1370331468964838238/original/d3f27552-a713-4080-9453-efb1a64ee745.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1370331468964838238/original/f1392584-5dc7-4aa6-a7c7-c0b6ef5e2357.jpeg'],
                                                                                                                'description': 'Located in a secure residence, this apartment offers 3 bedrooms, including a master suite with private bathrooms. Enjoy a modern living room with TV and Netflix, a friendly dining room, a balcony and a well-equipped kitchen. Only 5 minutes from Gueliz, it is ideal for a comfortable stay, close to shops and restaurants. Book now!',
                                                                                                                'host_info': {'name': 'Abdel',
                                                                                                                'details': 'Superhost | 1 year hosting',
                                                                                                                'profile_url': 'https://www.airbnb.com/users/show/532236013',
                                                                                                                'cohosts': [{'name': 'Moussa',
                                                                                                                    'profile_url': 'https://www.airbnb.com/users/show/665678298'}]},
                                                                                                                'amenities': ['Kitchen',
                                                                                                                'Wifi',
                                                                                                                'Free parking on premises',
                                                                                                                'Pool',
                                                                                                                'TV',
                                                                                                                'Washer',
                                                                                                                'Air conditioning',
                                                                                                                'Patio or balcony',
                                                                                                                'Unavailable: Carbon monoxide alarm',
                                                                                                                'Unavailable: Smoke alarm'],
                                                                                                                'location_details': {'address': 'Not Found',
                                                                                                                'neighborhood_description': 'Not Found'}},
        'https://www.airbnb.com/rooms/1199118327355501751?source_impression_id=p3_1754503729_P3cl2kHv3nBRaYRD':{'apartment_name': 'Charming Room in Riad, Just 2 mn from Jama el-Fna!',
                                                                                                                'listing_summary': '5 bedrooms · 5 beds · Private attached bathroom',
                                                                                                                'rating': 'Not Found',
                                                                                                                'reviews_count': 'Not Found',
                                                                                                                'price_details': {'error': "Could not parse price details - 'NoneType' object has no attribute 'get_text'"},
                                                                                                                'image_urls': ['https://a0.muscache.com/im/pictures/miso/Hosting-1199118327355501751/original/03be7311-ac50-4958-9073-82986131034a.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/miso/Hosting-1199118327355501751/original/172f59d1-2470-495d-b0de-8d47f4529a81.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/miso/Hosting-1199118327355501751/original/453ee272-d3e3-4ac3-ade8-f5e089220560.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/miso/Hosting-1199118327355501751/original/b8f8f7b4-4846-45db-b9f7-dfac0c36c304.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/miso/Hosting-1199118327355501751/original/5276736e-6cab-40e0-97d9-8924f7e1fbb7.jpeg'],
                                                                                                                'description': "About this place\nA real diamond nestled in the heart of the medina in Marrakech!\n5 min walk from Jemaa el-Fna square, We offer you 5 stylish and spotless rooms.\nEnjoy the impeccable cleanliness, a tasty Moroccan breakfast, and the proximity to local souks and attractions.\nWhether you're here to discover the wonders of Marrakech or relax in a refined setting, we look forward to welcoming you and making you live an exceptional stay!",
                                                                                                                'host_info': {'name': 'Stay with Abdel',
                                                                                                                'details': 'Superhost | 1 year hosting',
                                                                                                                'profile_url': 'https://www.airbnb.com/users/show/532236013',
                                                                                                                'cohosts': [{'name': 'Moussa',
                                                                                                                    'profile_url': 'https://www.airbnb.com/users/show/665678298'}]},
                                                                                                                'amenities': ['Lock on bedroom door',
                                                                                                                'Wifi',
                                                                                                                'Dedicated workspace',
                                                                                                                'Washer',
                                                                                                                'Air conditioning',
                                                                                                                'Shared patio or balcony',
                                                                                                                'Luggage dropoff allowed',
                                                                                                                'Crib',
                                                                                                                'Hair dryer',
                                                                                                                'Exterior security cameras on property'],
                                                                                                                'location_details': {'address': 'Not Found',
                                                                                                                'neighborhood_description': 'Not Found'}},
        'https://www.airbnb.com/rooms/1414517507728935918?source_impression_id=p3_1754503729_P3VZ9RAHqR67XD6h':{'apartment_name': 'Mykonos Apartment, Air-Conditioned, Netflix, Small Pool',
                                                                                                                'listing_summary': '2 guests · 1 bedroom · 1 bed · 1 bath',
                                                                                                                'rating': 'Not Found',
                                                                                                                'reviews_count': 'Not Found',
                                                                                                                'price_details': {'error': "Could not parse price details - 'NoneType' object has no attribute 'get_text'"},
                                                                                                                'image_urls': ['https://a0.muscache.com/im/pictures/airflow/Hosting-1414517507728935918/original/42b7f0e9-814b-4ef8-912f-a0149e63b8d1.jpg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1414517507728935918/original/1b6997e7-783a-4ddf-9575-7e919e860d81.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1414517507728935918/original/936cfa6c-9f4f-4359-b23f-cdfa8a7bb391.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1414517507728935918/original/6ffe8dea-e4f9-4662-9ed3-01b98fe59bf8.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1414517507728935918/original/c3d91118-7790-46f3-8678-758ce557d6dd.jpeg'],
                                                                                                                'description': 'Nestled in a white and blue Mykonos-inspired decor, this intimate retreat is ideal for a romantic getaway. Cozy bedroom, bright living room with equipped kitchen, elegant bathroom and small private pool for relaxing moments for two. An idyllic setting for getting together.\nThe space\nInspired by Mykonos, this cocoon for two offers a cozy bedroom, living room with equipped kitchen (oven, microwave, coffee machine, washing machine), elegant bathroom, air conditioning, Wi-Fi and private pool. Great for a comfortable and romantic stay. Book your getaway now!\nGuest access\nGuests have full access to the apartment.\nOther things to note\nIn accordance with local regulations, unmarried Moroccan couples without a marriage certificate are not allowed to access the accommodation.',
                                                                                                                'host_info': {'name': 'Abdel',
                                                                                                                'details': 'Superhost | 1 year hosting',
                                                                                                                'profile_url': 'https://www.airbnb.com/users/show/532236013',
                                                                                                                'cohosts': [{'name': 'Riham',
                                                                                                                    'profile_url': 'https://www.airbnb.com/users/show/592119294'},
                                                                                                                {'name': 'Moussa',
                                                                                                                    'profile_url': 'https://www.airbnb.com/users/show/665678298'}]},
                                                                                                                'amenities': ['Kitchen',
                                                                                                                'Wifi',
                                                                                                                'Free parking on premises',
                                                                                                                'Pool',
                                                                                                                'TV',
                                                                                                                'Free washer – In unit',
                                                                                                                'Air conditioning',
                                                                                                                'Exterior security cameras on property',
                                                                                                                'Unavailable: Carbon monoxide alarm',
                                                                                                                'Unavailable: Smoke alarm'],
                                                                                                                'location_details': {'address': 'Marrakesh, Marrakesh-Safi, Morocco',
                                                                                                                'neighborhood_description': 'Marrakesh, Marrakesh-Safi, Morocco\nJust 10 minutes from Guéliz, 15 minutes from the famous Jamaa El Fna square and the lively Hivernage district, Al Fadl offers a quiet setting while remaining close to the essentials. The neighborhood is well served by bus lines 7, 12, 13 and 18, making it easy for you to get around.\nEverything nearby (2–5 min walk):\n• \tGroceries & amenities: Carrefour Express, Caddy Express, Boucherie Le Cristal.\n• \tLocal delicacies: Pâtisserie Al Fadl and Jusmine Yummies, a gourmet pastry shop founded by the winner of "Best Pastry Chef" in Morocco.\nRestaurants & cafes to discover:\n• \tAhlam Pêcheur: fish specialties\n• \tMyBrunch: tasty brunches\n• \tHySushi: Asian cuisine\n• \tLa Flèche: Italian specialties'}},
        'https://www.airbnb.com/rooms/1362312529416292062?source_impression_id=p3_1754503729_P3k00Z7It2CcmJML':{'apartment_name': 'Cosy Appartment w/ Pool, A/C, Tennis',
                                                                                                                'listing_summary': '4 guests · 1 bedroom · 1 bed · 1 bath',
                                                                                                                'rating': 'Not Found',
                                                                                                                'reviews_count': 'Not Found',
                                                                                                                'price_details': {'error': "Could not parse price details - 'NoneType' object has no attribute 'get_text'"},
                                                                                                                'image_urls': ['https://a0.muscache.com/im/pictures/hosting/Hosting-1362312529416292062/original/e0a4d22f-1441-41df-a672-deea09a7239f.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1362312529416292062/original/76ded87e-efd3-4cdc-a15b-597a83629c98.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1362312529416292062/original/e7a63f27-0448-4b97-a6e4-1b6800f3ad8f.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1362312529416292062/original/275908ca-5e8d-4188-8e65-dcdc76ff7d33.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1362312529416292062/original/b8aee8a1-47f4-42d8-a756-e56ce3f40b67.jpeg'],
                                                                                                                'description': 'This luxury apartment, located in the heart of the Palmeraie in Marrakech, offers a peaceful and green setting, perfect for a relaxing stay. It is in a high-end residence with a pool, football, basketball, and tennis courts. Fully equipped, the studio features modern and elegant décor. Only 10 minutes from Gueliz, it’s ideal for a couple or solo stay. Free parking is available for added convenience. A perfect blend of relaxation and leisure in an exclusive setting.\nThe space\nStay in this stylish 5-star apartment located in a premium residence in the Palmeraie, just 10 minutes from Gueliz and 15 minutes from Jemaa el-Fna Square. The apartment features a spacious bedroom with views of the garden and pool, a bright living room, a dining area with an open view, a fully equipped kitchen, and a modern bathroom. The residence offers 3 pools, 2 tennis courts, a basketball court, and a football field, combining relaxation and recreation for an ideal stay.',
                                                                                                                'host_info': {'name': 'Abdel',
                                                                                                                'details': 'Superhost | 1 year hosting',
                                                                                                                'profile_url': 'https://www.airbnb.com/users/show/532236013',
                                                                                                                'cohosts': [{'name': 'Moussa',
                                                                                                                    'profile_url': 'https://www.airbnb.com/users/show/665678298'}]},
                                                                                                                'amenities': ['Kitchen',
                                                                                                                'Wifi',
                                                                                                                'Dedicated workspace',
                                                                                                                'Free parking on premises',
                                                                                                                'Pool',
                                                                                                                'TV',
                                                                                                                'Washer',
                                                                                                                'Air conditioning',
                                                                                                                'Private patio or balcony',
                                                                                                                'Luggage dropoff allowed'],
                                                                                                                'location_details': {'address': 'Not Found',
                                                                                                                'neighborhood_description': 'Not Found'}},
        'https://www.airbnb.com/rooms/1471660459697865832?source_impression_id=p3_1754503729_P3XQVYCiS5xO8SJy':{'apartment_name': 'Suite Prestige au Riad, 5 min from Jamaa El Fna',
                                                                                                                'listing_summary': '2 beds · No bathroom',
                                                                                                                'rating': 'Not Found',
                                                                                                                'reviews_count': 'Not Found',
                                                                                                                'price_details': {'error': "Could not parse price details - 'NoneType' object has no attribute 'get_text'"},
                                                                                                                'image_urls': ['https://a0.muscache.com/im/pictures/hosting/Hosting-1471660459697865832/original/3be6fce4-16e5-47fb-a8ab-f2eecb086ce5.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1471660459697865832/original/f298d410-673d-4db0-9ea3-888352a4798b.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1471660459697865832/original/6bf236ef-8dbe-47a5-9abb-74bdce89a323.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1471660459697865832/original/09973c3d-954e-4a07-bf01-c25be007719c.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1471660459697865832/original/cadfbe38-73c8-49ae-9a3f-c003a6e3e4f4.jpeg'],
                                                                                                                'description': 'About this place\nCharming room in an authentic riad 5 min from Jemaa el-Fna square.\nIt offers a comfortable bed, traditional Moroccan decor, air conditioning and a private bathroom with shower.\nCalm and privacy guaranteed in the heart of the medina.\nIdeal for a relaxing and exotic stay.\nNothing has been left to chance in this upscale charming accommodation.',
                                                                                                                'host_info': {'name': 'Abdel',
                                                                                                                'details': 'Superhost | 1 year hosting',
                                                                                                                'profile_url': 'https://www.airbnb.com/users/show/532236013'},
                                                                                                                'amenities': ['Lock on bedroom door',
                                                                                                                'Wifi',
                                                                                                                'Free parking on premises',
                                                                                                                'Air conditioning',
                                                                                                                'Private patio or balcony',
                                                                                                                'Luggage dropoff allowed',
                                                                                                                'Hair dryer',
                                                                                                                'Breakfast',
                                                                                                                'Smoking allowed',
                                                                                                                'Exterior security cameras on property'],
                                                                                                                'location_details': {'address': 'Not Found',
                                                                                                                'neighborhood_description': 'Not Found'}},
        'https://www.airbnb.com/rooms/1471588431390978827?source_impression_id=p3_1754503729_P3dtxJZ7HsK3ZnPK':{'apartment_name': 'Suite Prestige au Riad, 5 min from Jamaa El Fna',
                                                                                                                'listing_summary': '2 beds · No bathroom',
                                                                                                                'rating': 'Not Found',
                                                                                                                'reviews_count': 'Not Found',
                                                                                                                'price_details': {'error': "Could not parse price details - 'NoneType' object has no attribute 'get_text'"},
                                                                                                                'image_urls': ['https://a0.muscache.com/im/pictures/hosting/Hosting-1471660459697865832/original/3be6fce4-16e5-47fb-a8ab-f2eecb086ce5.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1471660459697865832/original/f298d410-673d-4db0-9ea3-888352a4798b.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1471660459697865832/original/6bf236ef-8dbe-47a5-9abb-74bdce89a323.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1471660459697865832/original/09973c3d-954e-4a07-bf01-c25be007719c.jpeg',
                                                                                                                'https://a0.muscache.com/im/pictures/hosting/Hosting-1471660459697865832/original/cadfbe38-73c8-49ae-9a3f-c003a6e3e4f4.jpeg'],
                                                                                                                'description': 'About this place\nCharming room in an authentic riad 5 min from Jemaa el-Fna square.\nIt offers a comfortable bed, traditional Moroccan decor, air conditioning and a private bathroom with shower.\nCalm and privacy guaranteed in the heart of the medina.\nIdeal for a relaxing and exotic stay.\nNothing has been left to chance in this upscale charming accommodation.',
                                                                                                                'host_info': {'name': 'Abdel',
                                                                                                                'details': 'Superhost | 1 year hosting',
                                                                                                                'profile_url': 'https://www.airbnb.com/users/show/532236013'},
                                                                                                                'amenities': ['Lock on bedroom door',
                                                                                                                'Wifi',
                                                                                                                'Free parking on premises',
                                                                                                                'Air conditioning',
                                                                                                                'Private patio or balcony',
                                                                                                                'Luggage dropoff allowed',
                                                                                                                'Hair dryer',
                                                                                                                'Breakfast',
                                                                                                                'Smoking allowed',
                                                                                                                'Exterior security cameras on property'],
                                                                                                                'location_details': {'address': 'Not Found',
                                                                                                                'neighborhood_description': 'Not Found'}},
    }
    if listing_url in listings_url:
        return listings_url[listing_url]
    else:
        return {'apartment_name': 'Premium corniche apartment, parking',
                'listing_summary': '4 guests · 1 bedroom · 1 bed · 1 bath',
                'rating': 'Not Found',
                'reviews_count': 'Not Found',
                'price_details': {'error': "Could not parse price details - 'NoneType' object has no attribute 'get_text'"},
                'image_urls': ['https://a0.muscache.com/im/pictures/7943613a-0dc2-4f9e-b0f9-33f60e6fbbee.jpg',
                'https://a0.muscache.com/im/pictures/a6065bab-a924-4e35-80c8-82f903b264de.jpg',
                'https://a0.muscache.com/im/pictures/8c8668aa-94ab-44fc-9b89-604b94750924.jpg',
                'https://a0.muscache.com/im/pictures/7a2b39dc-8b16-4dce-bcd8-b718f0696f1e.jpg',
                'https://a0.muscache.com/im/pictures/c049cc5b-4590-4573-9fcd-5dfcf6ab23d7.jpg'],
                'description': 'Enjoy elegant and central accommodation on Boulevard de la Corniche. My apartment is located in the best neighborhood of Casablanca on the new Promenade de la Corniche and close to the Grand Mosque Hassan 2. It is composed of a large living room , beautiful American kitchen, bedroom room, bathroom with shower and 2 terraces. A basement parking spot is offered for you to book.\nThe space\nThe apartment is 80m with a beautiful terrace of 12m where you can enjoy your coffee in the morning or your aperitif in the evening in the quiet of the residence. The living room is spacious and can accommodate 4 to 6 people, sofas are comfortable for 2 sleeping places.\nThe kitchen is fully equipped in terms of appliances and dishes and overlooks the living room. A second small terrace is in front of the kitchen could serve you in case of barbecue.\nThe bedroom overlooks the interior garden of the residence, furnished with a large queen size bed for 2 people, the built-in closet is bulky and has several types of storage.\nThe bathroom is spacious fully marbled with Italian shower, toilet and bidet, a hair dryer as well as hygiene products and towels. Everything has been put at your disposal for more comfort: summer and winter duvets, sheets, covers, pillows and cases.\nGuest access\nOnce in the apartment, you have access to all the spaces, enjoy the comfort.',
                'host_info': {'name': 'Nadia',
                'details': 'Superhost | 3 years hosting',
                'profile_url': 'https://www.airbnb.com/users/show/298782794'},
                'amenities': ['Garden view',
                'Beach access – Beachfront',
                'Kitchen',
                'Wifi',
                'Dedicated workspace',
                'Free parking on premises',
                '55 inch HDTV with Netflix',
                'Elevator',
                'Free washer – In unit',
                'Unavailable: Carbon monoxide alarm'],
                'location_details': {'address': 'Casablanca, Casablanca-Settat, Morocco',
                'neighborhood_description': 'Casablanca, Casablanca-Settat, Morocco\nCentral area on Boulevard de la Corniche, several shops, restaurants and amenities in the vicinity.'}}