from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging
import atexit
import time
from selenium.webdriver.common.keys import Keys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChromeDriverSingleton:
    _instance = None
    _service = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None or not cls._is_browser_healthy():
            cls._instance = cls._create_driver()
        return cls._instance
    
    @classmethod
    def _is_browser_healthy(cls):
        """Check if browser is responsive"""
        if not cls._instance:
            return False
        try:
            # Quick health check
            cls._instance.current_url
            return True
        except:
            return False
    
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
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--blink-settings=imagesEnabled=true")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        if cls._service is None:
            cls._service = Service(ChromeDriverManager().install())

        driver = webdriver.Chrome(service=cls._service, options=chrome_options)
        driver.set_script_timeout(10)
        driver.set_page_load_timeout(15)
        
        # Make selenium faster with CDP
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setBypassServiceWorker", {"bypass": True})
        
        return driver
    
    @classmethod
    def quit(cls):
        if cls._instance:
            try:
                cls._instance.quit()
            except:
                pass
            cls._instance = None

atexit.register(ChromeDriverSingleton.quit)

class WaitForImageSrc:
    def __init__(self, locator):
        self.locator = locator
    
    def __call__(self, driver):
        try:
            # Fast JavaScript check
            result = driver.execute_script("""
                const img = document.querySelector('.try-it-result-area img');
                if (img && img.src && img.src.includes('api.deepai.org')) {
                    return img.src;
                }
                return null;
            """)
            return result
        except:
            return False

def get_generated_image_url(prompt):
    """Optimized version with aggressive retries and fast execution"""
    driver = ChromeDriverSingleton.get_instance()
    url = None
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries and not url:
        try:
            # Preload a warm-up URL to reduce initial latency on retries
            if retry_count == 0:
                driver.get("https://deepai.org/machine-learning-model/text2img")

            # Clear cache and cookies for fresh start
            if retry_count > 0:
                driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                driver.execute_cdp_cmd('Network.clearBrowserCookies', {})

            # Load page with preemptive JS injection
            driver.get("https://deepai.org/machine-learning-model/text2img")
            
            # Inject performance optimization JS
            driver.execute_script("""
                window.onbeforeunload = null;
                window.alert = function(){}; 
                window.confirm = function(){return true;};
                window.prompt = function(){return true;};
            """)

            try:
                # Fast input field detection and input
                input_field = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "model-input-text-input"))
                )

                # Fast input with JS
                driver.execute_script(
                    "arguments[0].value = arguments[1];", 
                    input_field, 
                    prompt
                )
                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));",
                    input_field
                )

                # Click generate button with JS
                driver.execute_script(
                    "document.getElementById('modelSubmitButton').click();"
                )

                # Fast image detection
                start_time = time.time()
                while time.time() - start_time < 30:
                    url = driver.execute_script("""
                        const img = document.querySelector('.try-it-result-area img');
                        return img && img.src && img.src.includes('api.deepai.org') ? img.src : null;
                    """)
                    if url:
                        # Verify URL is real
                        if "https://" in url and "api.deepai.org" in url:
                            return url
                    time.sleep(0.1)  # Tight polling interval

            except Exception as e:
                logger.warning(f"Error during execution: {str(e)}")

            retry_count += 1
            if retry_count < max_retries:
                # Reset browser state only if retrying
                driver.execute_script("window.localStorage.clear();")
                driver.execute_script("window.sessionStorage.clear();")
                ChromeDriverSingleton.quit()
                driver = ChromeDriverSingleton.get_instance()

        except Exception as e:
            logger.error(f"Critical error: {str(e)}")
            retry_count += 1
            ChromeDriverSingleton.quit()
            driver = ChromeDriverSingleton.get_instance()

    return url
