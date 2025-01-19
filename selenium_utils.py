# selenium_utils.py
import time
import logging
from typing import Optional
from urllib.parse import urlparse
import chromedriver_autoinstaller
import threading
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException, StaleElementReferenceException

class SeleniumImageGenerator:
    """Optimized Selenium-based image generation using DeepAI's text2img model"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SeleniumImageGenerator, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.driver = None
            self.wait = None
            self.long_wait = None
            self._driver_lock = threading.Lock()
            self._initialized = True

    def setup_driver(self) -> None:
        """Configure Chrome WebDriver with optimized settings for Ubuntu server"""
        if self.driver:
            return

        with self._driver_lock:
            if self.driver:
                return

            try:
                # Auto-install correct chromedriver version
                chromedriver_autoinstaller.install()

                chrome_options = Options()
                chrome_options.add_argument("--headless=new")  # Use new headless mode
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--disable-software-rasterizer")
                chrome_options.add_argument("--disable-extensions")
                chrome_options.add_argument("--window-size=1920,1080")
                chrome_options.add_argument("--start-maximized")
                chrome_options.add_argument("--disable-notifications")
                chrome_options.add_argument("--disable-popup-blocking")
                chrome_options.add_argument("--ignore-certificate-errors")
                chrome_options.add_argument("--allow-insecure-localhost")
                
                # Performance optimizations
                chrome_options.add_argument("--disable-dev-tools")
                chrome_options.add_argument("--dns-prefetch-disable")
                chrome_options.add_argument("--disable-features=TranslateUI")
                chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
                chrome_options.add_argument("--disable-site-isolation-trials")
                chrome_options.add_argument("--disable-web-security")
                
                # Memory optimizations
                chrome_options.add_argument("--aggressive-cache-discard")
                chrome_options.add_argument("--disable-cache")
                chrome_options.add_argument("--disable-application-cache")
                chrome_options.add_argument("--disable-offline-load-stale-cache")
                chrome_options.add_argument("--disk-cache-size=0")
                chrome_options.add_argument("--media-cache-size=0")
                
                service = Service()
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.driver.set_page_load_timeout(30)
                self.wait = WebDriverWait(self.driver, 15)
                self.long_wait = WebDriverWait(self.driver, 60)

            except WebDriverException as e:
                logging.error(f"Failed to initialize Chrome driver: {str(e)}")
                raise

    def cleanup(self) -> None:
        """Clean up Selenium driver with proper error handling"""
        if self.driver:
            with self._driver_lock:
                try:
                    self.driver.quit()
                except Exception as e:
                    logging.error(f"Error during driver cleanup: {str(e)}")
                finally:
                    self.driver = None
                    self.wait = None
                    self.long_wait = None

    def _handle_overlays(self) -> None:
        """Handle overlays and popups with improved reliability"""
        try:
            # Handle cookie consent
            cookie_selectors = [
                "//button[contains(text(), 'Accept')]",
                "//button[contains(text(), 'I agree')]",
                "//div[contains(@class, 'cookie-consent')]//button",
            ]
            
            for selector in cookie_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if element.is_displayed():
                            self.driver.execute_script("arguments[0].click();", element)
                            time.sleep(0.5)
                except Exception:
                    continue

            # Remove overlay elements
            overlay_scripts = [
                "document.querySelectorAll('[class*=\"cookie\"]').forEach(e => e.remove());",
                "document.querySelectorAll('[class*=\"popup\"]').forEach(e => e.remove());",
                "document.querySelectorAll('[class*=\"overlay\"]').forEach(e => e.remove());",
                "document.querySelectorAll('[class*=\"modal\"]').forEach(e => e.remove());"
            ]
            
            for script in overlay_scripts:
                try:
                    self.driver.execute_script(script)
                except Exception:
                    continue

        except Exception as e:
            logging.debug(f"Non-critical error in overlay handling: {str(e)}")

    def _click_button(self, button_id: str, max_attempts: int = 3) -> bool:
        """Click button with multiple fallback methods and retry logic"""
        for attempt in range(max_attempts):
            try:
                # Wait for button to be clickable
                button = self.wait.until(EC.element_to_be_clickable((By.ID, button_id)))
                
                # Scroll into view with smooth scrolling
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                    button
                )
                time.sleep(0.5)

                # Try different click methods
                click_methods = [
                    lambda: button.click(),
                    lambda: ActionChains(self.driver).move_to_element(button).click().perform(),
                    lambda: self.driver.execute_script("arguments[0].click();", button),
                    lambda: self.driver.execute_script(
                        "arguments[0].dispatchEvent(new MouseEvent('click', "
                        "{bubbles: true, cancelable: true, view: window}));",
                        button
                    )
                ]

                for method in click_methods:
                    try:
                        method()
                        time.sleep(0.5)
                        return True
                    except Exception:
                        continue

            except Exception as e:
                logging.debug(f"Click attempt {attempt + 1} failed for {button_id}: {str(e)}")
                time.sleep(1)
                
        return False

    def _wait_for_image_result(self, timeout: int = 60) -> Optional[str]:
        """Wait for and validate image result with improved reliability"""
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    # Check for error messages
                    error_elements = self.driver.find_elements(
                        By.XPATH,
                        "//*[contains(text(), 'error') or contains(text(), 'Error')]"
                    )
                    for error in error_elements:
                        if error.is_displayed():
                            error_text = error.text
                            if "try again" in error_text.lower():
                                return None

                    # Look for image element
                    img_elements = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        ".try-it-result-area img"
                    )
                    
                    for img in img_elements:
                        if img.is_displayed():
                            src = img.get_attribute("src")
                            if src and self._is_valid_image_url(src):
                                # Verify image is fully loaded
                                img_status = self.driver.execute_script(
                                    "return arguments[0].complete && "
                                    "typeof arguments[0].naturalWidth != 'undefined' && "
                                    "arguments[0].naturalWidth > 0",
                                    img
                                )
                                
                                if img_status:
                                    return src

                except StaleElementReferenceException:
                    continue

                time.sleep(1)

            logging.error("Timeout waiting for image result")
            return None

        except Exception as e:
            logging.error(f"Error waiting for image result: {str(e)}")
            return None

    def _is_valid_image_url(self, url: str) -> bool:
        """Validate image URL with improved checks"""
        try:
            parsed = urlparse(url)
            
            # Verify URL structure
            if not all([
                parsed.scheme in ['http', 'https'],
                'api.deepai.org' in parsed.netloc,
                parsed.path.endswith(('.jpg', '.jpeg', '.png'))
            ]):
                return False
                
            # Additional validation
            if len(url) > 2000:  # Standard URL length limit
                return False
                
            if not url.startswith('https://'):  # Enforce HTTPS
                return False
                
            return True
            
        except Exception:
            return False

    def generate_image(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Generate image from text prompt with optimized retry logic"""
        retry_count = 0
        last_error = None

        while retry_count < max_retries:
            try:
                self.setup_driver()
                
                # Load website with error handling
                self.driver.get("https://deepai.org/machine-learning-model/text2img")
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

                # Handle potential overlays and popups
                self._handle_overlays()
                
                # Input prompt
                input_field = self.wait.until(EC.presence_of_element_located(
                    (By.CLASS_NAME, "model-input-text-input")))
                self.driver.execute_script(
                    "arguments[0].value = arguments[1]; "
                    "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));",
                    input_field, prompt
                )

                # Click HD button with retry logic
                if not self._click_button("modelHdButton"):
                    raise Exception("Failed to click HD button")

                # Click submit button with retry logic
                if not self._click_button("modelSubmitButton"):
                    raise Exception("Failed to click submit button")

                # Wait for image with optimized checking
                img_url = self._wait_for_image_result()
                if img_url:
                    return img_url

                raise Exception("Failed to get valid image URL")

            except Exception as e:
                retry_count += 1
                last_error = str(e)
                logging.error(f"Attempt {retry_count} failed: {last_error}")
                
                if retry_count >= max_retries:
                    logging.error(f"Max retries reached. Last error: {last_error}")
                    return None
                
                # Exponential backoff with jitter
                wait_time = min(30, (2 ** retry_count) + random.uniform(0, 1))
                time.sleep(wait_time)
                
                # Cleanup and recreate driver on retry
                self.cleanup()

            except Exception as e:
                logging.error(f"Unexpected error in generate_image: {str(e)}")
                return None