import asyncio
from typing import List, Dict, Optional, Union, Any
from pydantic import BaseModel, Field
from langchain_core.tools import tool
import random
import time

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMExtractionStrategy, LLMConfig, BrowserConfig
from multi_agents.constants.constants import Constants

# Pydantic models for structured LLM extraction
# This tells the LLM exactly what data structure we want back.

class ListingSummary(BaseModel):
    url: Optional[str] = Field(description="Direct link to the listing page")
    title: str = Field(description="Property listing title/name")
    type: str = Field(description="Property type (e.g., 'Rental unit', 'Riad')")
    rating_text: Optional[str] = Field(description="Rating information (e.g., '4.85 out of 5')")

class HostResponse(BaseModel):
    responder_name: str = Field(description="Name of the person who responded (usually the host)")
    date: str = Field(description="Date of the host's response")
    text: str = Field(description="The content of the host's response")

class Review(BaseModel):
    reviewer_name: str = Field(description="Name of the guest who left the review")
    reviewer_location: Optional[str] = Field(description="Guest's location or 'N/A'")
    date: str = Field(description="Date the review was posted")
    text: str = Field(description="The full content/message of the review")
    host_response: Optional[HostResponse] = Field(description="The host's response to the review, if available")

class PlaceVisited(BaseModel):
    place: str = Field(description="Location name (e.g., 'London, United Kingdom')")
    details: str = Field(description="Visit information (e.g., 'June 2025', '4 trips')")

class AirbnbHostProfile(BaseModel):
    name: str = Field(description="The host's display name.")
    profile_picture_url: Optional[str] = Field(description="URL of the host's profile picture.")
    bio: Optional[str] = Field(description="The host's personal bio or description text.")
    about_details: List[str] = Field(description="A list of structured details from the 'About' section (work, pets, etc.).")
    places_visited: List[PlaceVisited] = Field(description="List of places the host has visited.")
    listings: List[ListingSummary] = Field(description="A list of all property listings by the host.")
    reviews: List[Review] = Field(description="A list of all reviews left for the host.")

class PriceDetails(BaseModel):
    display_price: Optional[str] = Field(description="The main price displayed for the listing (e.g., '$150 / night').")
    breakdown: Optional[Dict[str, Any]] = Field(description="A dictionary of the detailed price breakdown if available.")

class HostInfo(BaseModel):
    name: str = Field(description="The host's name.")
    details: Optional[str] = Field(description="Host status and experience (e.g., 'Superhost | 3 years hosting').")
    profile_url: Optional[str] = Field(description="Link to the host's profile page.")

class AirbnbListingDetails(BaseModel):
    apartment_name: str = Field(description="The title or name of the property listing.")
    listing_summary: str = Field(description="A brief summary including number of guests, bedrooms, beds, and baths.")
    rating: Optional[str] = Field(description="The overall rating score (e.g., '4.89').")
    reviews_count: Optional[str] = Field(description="The total number of reviews.")
    image_urls: List[str] = Field(description="A list of up to 5 URLs for the property's images.")
    description: str = Field(description="The full text description of the property.")
    host_info: HostInfo = Field(description="Information about the host of the listing.")
    amenities: List[str] = Field(description="A list of up to 10 key amenities available.")
    location_details: Dict[str, str] = Field(description="Location details, including address and neighborhood description.")
    price_details: Optional[PriceDetails] = Field(description="Detailed pricing information for the listing.")


# --- Helper function to run async tool from sync Langchain context ---
def run_async_tool(tool_coro):
    """Execute an async tool from a synchronous context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # This is for environments like Jupyter notebooks that have a running event loop
        return asyncio.ensure_future(tool_coro)
    else:
        # For standard synchronous execution
        return asyncio.run(tool_coro)

def get_random_user_agents():
    """Return a list of realistic user agents to rotate through"""
    return [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
    ]

@tool
def get_airbnb_profile_data(profile_url: str, max_retries: int = 3) -> Dict[str, Any]:
    """
    Extracts comprehensive data from an Airbnb host's profile page using Crawl4AI.
    This single tool scrapes all key sections: profile details, listings, reviews, and places visited.
    It handles dynamic content like modals and scrolling to get all data.
    Enhanced with anti-detection measures and retry logic.

    Args:
        profile_url (str): The complete URL to the Airbnb host's profile page.
                           (e.g., "https://www.airbnb.com/users/show/123456789")
        max_retries (int): Maximum number of retry attempts (default: 3)

    Returns:
        Dict[str, Any]: A dictionary containing all scraped profile information, structured
                        according to the AirbnbHostProfile model, or an error dictionary.
    """
    async def ascrape():
        user_agents = get_random_user_agents()
        
        for attempt in range(max_retries):
            try:
                # Random delay between attempts
                if attempt > 0:
                    delay = random.uniform(5, 15)
                    print(f"Retry attempt {attempt + 1} after {delay:.1f}s delay...")
                    await asyncio.sleep(delay)
                
                # JavaScript to handle interactions with better error handling
                js_click_reviews = """
                (() => {
                    try {
                        const buttons = Array.from(document.querySelectorAll('button, a, div[role="button"]'));
                        const reviewButton = buttons.find(btn => {
                            const text = btn.textContent || btn.innerText || '';
                            return text.toLowerCase().includes('show all') && text.toLowerCase().includes('reviews');
                        });
                        if (reviewButton) {
                            reviewButton.click();
                            console.log('Successfully clicked show all reviews button');
                            return true;
                        }
                        console.log('Review button not found');
                        return false;
                    } catch (e) {
                        console.log('Error clicking reviews button:', e);
                        return false;
                    }
                })();
                """

                # Enhanced modal scrolling with better detection
                js_scroll_modal = """
                (async () => {
                    try {
                        await new Promise(resolve => setTimeout(resolve, 2000)); // Wait for modal to open
                        
                        const modal = document.querySelector("div[role='dialog'], div[aria-modal='true'], .modal");
                        if (!modal) {
                            console.log('No modal found');
                            return;
                        }
                        
                        // Find scrollable container within modal
                        const scrollableSelectors = [
                            'section > div',
                            'div[data-testid*="scroll"]',
                            'div[style*="overflow"]',
                            '.scrollable',
                            'div[tabindex="0"]'
                        ];
                        
                        let scrollableDiv = null;
                        for (const selector of scrollableSelectors) {
                            scrollableDiv = modal.querySelector(selector);
                            if (scrollableDiv) break;
                        }
                        
                        if (!scrollableDiv) {
                            console.log('No scrollable div found in modal');
                            return;
                        }

                        console.log('Starting modal scroll...');
                        let lastHeight = 0;
                        let scrollAttempts = 0;
                        const maxScrollAttempts = 10;
                        
                        while (scrollAttempts < maxScrollAttempts) {
                            scrollableDiv.scrollTop = scrollableDiv.scrollHeight;
                            await new Promise(resolve => setTimeout(resolve, 2000)); // Wait for content to load
                            
                            let newHeight = scrollableDiv.scrollHeight;
                            console.log(`Scroll attempt ${scrollAttempts + 1}: height ${newHeight}`);
                            
                            if (newHeight === lastHeight) {
                                console.log('No new content loaded, stopping scroll');
                                break;
                            }
                            lastHeight = newHeight;
                            scrollAttempts++;
                        }
                        console.log('Modal scrolling complete');
                    } catch (e) {
                        console.log('Error in modal scrolling:', e);
                    }
                })();
                """

                # Enhanced browser configuration with anti-detection
                browser_config = BrowserConfig(
                    headless=True,  # Set to False for debugging
                    extra_args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-extensions",
                        "--disable-plugins",
                        "--disable-images",  # Faster loading
                        "--disable-javascript-harmony-shipping",
                        "--disable-background-timer-throttling",
                        "--disable-renderer-backgrounding",
                        "--disable-backgrounding-occluded-windows",
                        "--disable-ipc-flooding-protection",
                        "--window-size=1920,1080",
                        f"--user-agent={random.choice(user_agents)}"
                    ]
                )

                llm_config = LLMConfig(
                    provider=f"groq/{Constants.MODEL}",
                    api_token=Constants.GROQ_API_KEY,
                    temperature=0.1  # Lower temperature for more consistent extraction
                )

                config = CrawlerRunConfig(
                    js_code=[js_click_reviews, js_scroll_modal],
                    wait_until="domcontentloaded",  # Less strict than networkidle
                    page_timeout=60000,  # Increased timeout
                    delay_before_return_html=3.0,  # Wait before extracting
                    extraction_strategy=LLMExtractionStrategy(
                        llm_config=llm_config,
                        schema=AirbnbHostProfile.model_json_schema(),
                        extraction_type="schema",
                        instruction=(
                            "Extract all available information from the Airbnb host profile page. "
                            "Pay close attention to all sections: bio, listings, all loaded reviews "
                            "(including host responses), and places visited. Be comprehensive. "
                            "If some information is not available, mark it as null or empty list. "
                            "Focus on extracting what is visible on the page."
                        )
                    )
                )

                async with AsyncWebCrawler(config=browser_config) as crawler:
                    print(f"Attempting to scrape {profile_url} (attempt {attempt + 1}/{max_retries})")
                    result = await crawler.arun(url=profile_url, config=config)
                    
                    if result.success and result.extracted_content:
                        print("Successfully extracted content!")
                        return result.extracted_content
                    else:
                        error_msg = result.error_message if hasattr(result, 'error_message') else "Unknown error"
                        print(f"Attempt {attempt + 1} failed: {error_msg}")
                        
                        if attempt == max_retries - 1:
                            return {
                                "error": f"Failed to scrape profile {profile_url} after {max_retries} attempts. Last error: {error_msg}",
                                "attempts": max_retries
                            }
                        
            except Exception as e:
                error_msg = str(e)
                print(f"Attempt {attempt + 1} failed with exception: {error_msg}")
                
                if attempt == max_retries - 1:
                    return {
                        "error": f"Failed to scrape profile {profile_url} after {max_retries} attempts. Last exception: {error_msg}",
                        "attempts": max_retries
                    }
        return {
    "error": "The scraping process completed all retries without a definitive success or failure return.",
    "attempts": max_retries
     }

    return run_async_tool(ascrape())


@tool
def get_listing_details(listing_url: str, max_retries: int = 3) -> Dict[str, Any]:
    """
    Extracts comprehensive details from a specific Airbnb property listing using Crawl4AI.
    It handles dynamic elements like clicking to reveal price breakdowns.
    Enhanced with anti-detection measures and retry logic.

    Args:
        listing_url (str): The complete URL to the Airbnb listing page.
        max_retries (int): Maximum number of retry attempts (default: 3)

    Returns:
        Dict[str, Any]: A dictionary containing structured details of the listing,
                        or an error dictionary.
    """
    async def ascrape():
        user_agents = get_random_user_agents()
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = random.uniform(3, 8)
                    print(f"Retry attempt {attempt + 1} after {delay:.1f}s delay...")
                    await asyncio.sleep(delay)

                # Enhanced JS interactions with better error handling
                js_interactions = """
                (async () => {
                    try {
                        console.log('Starting interactions...');
                        
                        // Click price to reveal breakdown
                        const priceSelectors = [
                            "div[data-plugin-in-point-id='BOOK_IT_SIDEBAR'] button",
                            "button[data-testid*='price']",
                            "button._194r9nk1",
                            "div[data-section-id*='PRICING'] button"
                        ];
                        
                        for (const selector of priceSelectors) {
                            try {
                                const priceButton = document.querySelector(selector);
                                if (priceButton) {
                                    priceButton.click();
                                    console.log('Clicked price button:', selector);
                                    await new Promise(r => setTimeout(r, 1500));
                                    break;
                                }
                            } catch (e) {
                                console.log('Could not click price button:', selector, e);
                            }
                        }

                        // Click to expand location description
                        const locationSelectors = [
                            "div[data-section-id='LOCATION_DEFAULT'] button",
                            "button[data-testid*='location']",
                            "div[data-section-id*='LOCATION'] button"
                        ];
                        
                        for (const selector of locationSelectors) {
                            try {
                                const locationButton = document.querySelector(selector);
                                if (locationButton) {
                                    locationButton.click();
                                    console.log('Clicked location button:', selector);
                                    await new Promise(r => setTimeout(r, 1000));
                                    break;
                                }
                            } catch (e) {
                                console.log('Could not click location button:', selector, e);
                            }
                        }
                        
                        console.log('Interactions complete');
                    } catch (e) {
                        console.log('Error in interactions:', e);
                    }
                })();
                """

                browser_config = BrowserConfig(
                    headless=True,
                    extra_args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-extensions",
                        "--disable-plugins",
                        "--disable-images",
                        "--window-size=1920,1080",
                        f"--user-agent={random.choice(user_agents)}"
                    ]
                )

                llm_config = LLMConfig(
                    provider=f"groq/{Constants.MODEL}",
                    api_token=Constants.GROQ_API_KEY,
                    temperature=0.1
                )

                config = CrawlerRunConfig(
                    js_code=[js_interactions],
                    wait_until="domcontentloaded",
                    page_timeout=45000,
                    delay_before_return_html=2.0,
                    extraction_strategy=LLMExtractionStrategy(
                        llm_config=llm_config,
                        schema=AirbnbListingDetails.model_json_schema(),
                        extraction_type="schema",
                        instruction=(
                            "Extract all available details from the Airbnb listing page. "
                            "This includes the apartment name, summary, ratings, amenities, "
                            "host information, location details, image URLs, and pricing. "
                            "If certain information is not visible or available, mark it as null or empty. "
                            "Focus on what is actually present on the page."
                        )
                    )
                )

                async with AsyncWebCrawler(config=browser_config) as crawler:
                    print(f"Attempting to scrape listing {listing_url} (attempt {attempt + 1}/{max_retries})")
                    result = await crawler.arun(url=listing_url, config=config)
                    
                    if result.success and result.extracted_content:
                        print("Successfully extracted listing content!")
                        return result.extracted_content
                    else:
                        error_msg = result.error_message if hasattr(result, 'error_message') else "Unknown error"
                        print(f"Attempt {attempt + 1} failed: {error_msg}")
                        
                        if attempt == max_retries - 1:
                            return {
                                "error": f"Failed to scrape listing {listing_url} after {max_retries} attempts. Last error: {error_msg}",
                                "attempts": max_retries
                            }

            except Exception as e:
                error_msg = str(e)
                print(f"Attempt {attempt + 1} failed with exception: {error_msg}")
                
                if attempt == max_retries - 1:
                    return {
                        "error": f"Failed to scrape listing {listing_url} after {max_retries} attempts. Last exception: {error_msg}",
                        "attempts": max_retries
                    }
        return {
            "error": "The scraping process completed all retries without a definitive success or failure return.",
            "attempts": max_retries
        }
    return run_async_tool(ascrape())


# Additional helper function for testing with different approaches
#tool
def test_airbnb_access(url: str) -> Dict[str, Any]:
    """
    Test basic access to an Airbnb URL to check for blocking or accessibility issues.
    
    Args:
        url (str): The Airbnb URL to test
        
    Returns:
        Dict[str, Any]: Status information about the URL access
    """
    async def test_access():
        try:
            browser_config = BrowserConfig(
                headless=True,
                extra_args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1920,1080",
                    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                ]
            )

            config = CrawlerRunConfig(
                wait_until="domcontentloaded",
                page_timeout=30000,
                delay_before_return_html=2.0
            )

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=config)
                
                return {
                    "success": result.success,
                    "status_code": getattr(result, 'status_code', 'Unknown'),
                    "url": url,
                    "title": getattr(result, 'title', 'No title'),
                    "content_length": len(result.html) if result.html else 0,
                    "error": result.error_message if hasattr(result, 'error_message') else None
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "url": url
            }
    
    return run_async_tool(test_access())