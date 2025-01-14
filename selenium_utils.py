from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import logging
import os
import subprocess

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def install_chrome_dependencies():
    """
    Install Chrome and its dependencies on Ubuntu
    """
    try:
        # Update package list
        subprocess.run(['sudo', 'apt-get', 'update'], check=True)
        
        # Install dependencies
        dependencies = [
            'wget',
            'unzip',
            'chromium-browser',
            'chromium-chromedriver',
            'xvfb',  # Virtual display
            'libgconf-2-4',  # Required dependency
        ]
        
        subprocess.run(['sudo', 'apt-get', 'install', '-y'] + dependencies, check=True)
        logger.info("Successfully installed Chrome dependencies")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install dependencies: {str(e)}")
        raise

def setup_virtual_display():
    """
    Set up virtual display for headless browsing
    """
    try:
        os.environ['DISPLAY'] = ':99'
        subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1920x1080x24', '-ac'])
        time.sleep(2)  # Wait for virtual display to start
        logger.info("Virtual display started successfully")
    except Exception as e:
        logger.error(f"Failed to start virtual display: {str(e)}")
        raise

def setup_driver():
    """
    Configure and return Chrome WebDriver with optimized settings for Ubuntu server
    """
    try:
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
        chrome_options.add_argument("--remote-debugging-port=9222")
        
        # Use ChromeDriverManager to handle driver installation
        service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        return driver
        
    except WebDriverException as e:
        logger.error(f"Failed to initialize Chrome driver: {str(e)}")
        raise

def wait_for_image_src(driver, locator):
    """
    Custom wait condition for checking if image source is available
    """
    try:
        element = driver.find_element(*locator)
        src = element.get_attribute("src")
        return element if src and "api.deepai.org" in src else False
    except:
        return False

def handle_cookie_popup(driver):
    """
    Handle any cookie consent popup that might appear
    """
    try:
        cookie_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'Accept') or contains(text(), 'I agree')]")
        for button in cookie_buttons:
            if button.is_displayed():
                button.click()
                time.sleep(1)
                break
    except:
        pass

def remove_overlays(driver):
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
            element = driver.find_element(By.ID, element_id)
            driver.execute_script("arguments[0].remove();", element)
        except:
            continue

def safe_click(driver, element):
    """
    Try multiple methods to click an element
    """
    methods = [
        lambda: element.click(),
        lambda: ActionChains(driver).move_to_element(element).click().perform(),
        lambda: driver.execute_script("arguments[0].click();", element),
        lambda: driver.execute_script("arguments[0].dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));", element)
    ]

    for method in methods:
        try:
            method()
            return True
        except Exception as e:
            logger.debug(f"Click method failed: {str(e)}")
            continue
    return False

def get_generated_image_url(prompt, max_retries=3):
    """
    Generate image from text prompt and return the image URL
    """
    driver = None
    retry_count = 0

    while retry_count < max_retries:
        try:
            driver = setup_driver()
            wait = WebDriverWait(driver, 30)

            # Load the page
            logger.info("Loading website...")
            driver.get("https://deepai.org/machine-learning-model/text2img")
            time.sleep(2)  # Allow page to stabilize

            # Handle any popups and overlays
            handle_cookie_popup(driver)
            remove_overlays(driver)

            # Enter prompt
            logger.info(f"Entering prompt: {prompt}")
            input_field = wait.until(EC.presence_of_element_located(
                (By.CLASS_NAME, "model-input-text-input")))
            input_field.clear()
            input_field.send_keys(prompt)

            # Find and click submit button
            logger.info("Attempting to click submit button...")
            submit_button = wait.until(EC.presence_of_element_located(
                (By.ID, "modelSubmitButton")))

            # Scroll button into view
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_button)
            time.sleep(1)

            if not safe_click(driver, submit_button):
                raise Exception("Failed to click submit button using all methods")

            # Wait for image generation
            logger.info("Waiting for image generation...")
            img_element = wait.until(lambda d: wait_for_image_src(d, (By.CSS_SELECTOR, ".try-it-result-area img")))

            # Get and verify image URL
            image_url = img_element.get_attribute("src")
            if not image_url or "api.deepai.org" not in image_url:
                raise Exception("Invalid image URL generated")

            logger.info("Successfully generated image")
            return image_url

        except Exception as e:
            retry_count += 1
            logger.error(f"Attempt {retry_count} failed: {str(e)}")
            if retry_count >= max_retries:
                logger.error("Max retries reached")
                return None
            time.sleep(2)  # Wait before retrying

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

def initialize_server():
    """
    Initialize server requirements
    """
    try:
        install_chrome_dependencies()
        setup_virtual_display()
        logger.info("Server initialization completed successfully")
    except Exception as e:
        logger.error(f"Failed to initialize server: {str(e)}")
        raise