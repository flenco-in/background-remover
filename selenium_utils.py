# selenium_utils.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging
import atexit

logging.basicConfig(level=logging.ERROR)  # Only show errors
logger = logging.getLogger(__name__)

class ChromeDriverSingleton:
    _instance = None
    _service = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls._create_driver()
        return cls._instance
    
    @classmethod
    def _create_driver(cls):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--log-level=3")
        
        if cls._service is None:
            cls._service = Service(ChromeDriverManager().install())
        
        return webdriver.Chrome(service=cls._service, options=chrome_options)
    
    @classmethod
    def quit(cls):
        if cls._instance:
            cls._instance.quit()
            cls._instance = None

atexit.register(ChromeDriverSingleton.quit)

class WaitForImageSrc:
    def __init__(self, locator):
        self.locator = locator
        
    def __call__(self, driver):
        try:
            element = driver.find_element(*self.locator)
            if element.get_attribute("src") and "api.deepai.org" in element.get_attribute("src"):
                return element
        except:
            pass
        return False

def get_generated_image_url(prompt):
    """Simplified version more similar to original script."""
    driver = ChromeDriverSingleton.get_instance()
    wait = WebDriverWait(driver, 30)
    
    try:
        driver.get("https://deepai.org/machine-learning-model/text2img")
        
        input_field = wait.until(EC.presence_of_element_located(
            (By.CLASS_NAME, "model-input-text-input")))
        input_field.send_keys(prompt)
        
        submit_button = wait.until(EC.element_to_be_clickable(
            (By.ID, "modelSubmitButton")))
        submit_button.click()
        
        img_element = wait.until(WaitForImageSrc((By.CSS_SELECTOR, ".try-it-result-area img")))
        return img_element.get_attribute("src")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        ChromeDriverSingleton.quit()  # Reset driver on error
        return None