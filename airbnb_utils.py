import random
import time
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

def initialize_driver(selenium_host="http://localhost:4444/wd/hub"):
    """Initializes and returns a Selenium WebDriver instance."""
    print("--- [1] Connecting to Selenium Remote WebDriver ---")
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
        print(f"!!!!!! ERROR initializing WebDriver: {e} !!!!!!")
        traceback.print_exc()
        return None

def get_profile_page_html(driver, url):
    """Navigates to the URL, handles the review modal, and returns the final HTML source."""
    print(f"\n--- [2] Navigating to URL: {url} ---")
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.h1oqg76h')))
        print("SUCCESS: Page loaded.")
        
        # Click "Show all reviews" button and scroll modal
        try:
            show_all_button_xpath = "//button[contains(., 'Show all') and contains(., 'reviews')]"
            show_all_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, show_all_button_xpath))
            )
            print("Found 'Show all reviews' button. Clicking...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_all_button)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", show_all_button)

            modal_selector = "div[role='dialog']"
            WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, modal_selector))
            )
            print("Reviews modal is now visible.")
            
            scrollable_div = driver.find_element(By.CSS_SELECTOR, f"{modal_selector} section > div")
            
            print("Scrolling review modal to load all content...")
            last_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
            while True:
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", scrollable_div)
                time.sleep(1.5)
                new_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
                if new_height == last_height:
                    break
                last_height = new_height
            print("Finished scrolling.")

        except TimeoutException:
            print("'Show all reviews' button not found or modal did not open. Scraping visible reviews.")
        except Exception as e:
            print(f"An error occurred with the 'Show all reviews' button/modal: {e}")

        return driver.page_source

    except Exception as e:
        print(f"!!!!!! ERROR during page navigation or interaction: {e} !!!!!!")
        traceback.print_exc()
        return None