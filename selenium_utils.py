from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException, StaleElementReferenceException
import time
import logging
from typing import Optional
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SeleniumImageGenerator:
    """
    A class to handle Selenium-based image generation using DeepAI's text2img model
    """
    def __init__(self):
        self.driver = None
        self.wait = None
        self.long_wait = None

    def setup_driver(self) -> None:
        """
        Configure Chrome WebDriver with optimized settings
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--ignore-certificate-errors")  # Handle SSL issues
        chrome_options.add_argument("--allow-insecure-localhost")  # Handle localhost SSL issues

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)
            self.wait = WebDriverWait(self.driver, 30)
            self.long_wait = WebDriverWait(self.driver, 60)  # Extended timeout for image generation
        except WebDriverException as e:
            logger.error(f"Failed to initialize Chrome driver: {str(e)}")
            raise

    def cleanup(self) -> None:
        """
        Clean up Selenium driver
        """
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error during driver cleanup: {str(e)}")
            finally:
                self.driver = None
                self.wait = None
                self.long_wait = None

    def handle_cookie_popup(self) -> None:
        """
        Handle any cookie consent popup that might appear
        """
        try:
            cookie_buttons = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Accept') or contains(text(), 'I agree')]")
            for button in cookie_buttons:
                if button.is_displayed():
                    button.click()
                    time.sleep(1)
                    break
        except Exception as e:
            logger.debug(f"Cookie popup handling failed: {str(e)}")

    def remove_overlays(self) -> None:
        """
        Remove any overlay elements that might interfere with clicking
        """
        overlay_elements = [
            "fs-sticky-footer",
            "cookie-banner",
            "ad-overlay"
        ]

        for element_id in overlay_elements:
            try:
                element = self.driver.find_element(By.ID, element_id)
                self.driver.execute_script("arguments[0].remove();", element)
            except Exception:
                continue

    def safe_click(self, element) -> bool:
        """
        Try multiple methods to click an element
        """
        methods = [
            lambda: element.click(),
            lambda: ActionChains(self.driver).move_to_element(element).click().perform(),
            lambda: self.driver.execute_script("arguments[0].click();", element),
            lambda: self.driver.execute_script(
                "arguments[0].dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));", 
                element
            )
        ]

        for method in methods:
            try:
                method()
                return True
            except Exception as e:
                logger.debug(f"Click method failed: {str(e)}")
                continue
        return False

    def is_valid_image_url(self, url: str) -> bool:
        """
        Validate if the URL is a proper DeepAI image URL
        """
        try:
            parsed = urlparse(url)
            return all([
                parsed.scheme in ['http', 'https'],
                'api.deepai.org' in parsed.netloc,
                parsed.path.endswith(('.jpg', '.jpeg', '.png'))
            ])
        except Exception:
            return False

    def wait_for_image_src(self, element, timeout: int = 60) -> str:
        """
        Wait for a valid image URL to be available and return it
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if element.is_displayed():
                    src = element.get_attribute("src")
                    if src and self.is_valid_image_url(src):
                        return src
            except StaleElementReferenceException:
                element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".try-it-result-area img"))
                )
            except Exception as e:
                logger.debug(f"Waiting for image: {str(e)}")
            time.sleep(1)
        raise TimeoutException("Timeout waiting for valid image URL")

    def generate_image(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """
        Generate image from text prompt and return the image URL
        """
        retry_count = 0
        image_url = None

        while retry_count < max_retries:
            try:
                self.setup_driver()
                logger.info("Loading website...")
                self.driver.get("https://deepai.org/machine-learning-model/text2img")
                time.sleep(2)

                self.handle_cookie_popup()
                self.remove_overlays()

                logger.info(f"Entering prompt: {prompt}")
                input_field = self.wait.until(EC.presence_of_element_located(
                    (By.CLASS_NAME, "model-input-text-input")))
                input_field.clear()
                input_field.send_keys(prompt)

                # Click the HD button
                logger.info("Clicking the HD button...")
                hd_button = self.wait.until(EC.element_to_be_clickable((By.ID, "modelHdButton")))
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", hd_button)
                time.sleep(1)

                if not self.safe_click(hd_button):
                    raise Exception("Failed to click HD button using all methods")

                logger.info("Attempting to click submit button...")
                submit_button = self.wait.until(EC.element_to_be_clickable((By.ID, "modelSubmitButton")))
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_button)
                time.sleep(1)

                if not self.safe_click(submit_button):
                    raise Exception("Failed to click submit button using all methods")

                logger.info("Waiting for initial image element...")
                img_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".try-it-result-area img")))

                logger.info("Waiting for valid image URL...")
                image_url = self.wait_for_image_src(img_element)

                logger.info(f"Successfully generated image: {image_url}")
                return image_url

            except Exception as e:
                retry_count += 1
                logger.error(f"Attempt {retry_count} failed: {str(e)}")
                if retry_count >= max_retries:
                    logger.error("Max retries reached. Returning None.")
                    return None
                time.sleep(2 ** retry_count)  # Exponential backoff

            finally:
                print('done')
