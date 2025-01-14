from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.chrome import ChromeType
import logging
import atexit
import time
import os
import subprocess
import shutil

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ChromeDriverSingleton:
    _instance = None
    _service = None
    
    @classmethod
    def ensure_chrome_installed(cls):
        """Ensure Chrome is installed on Ubuntu"""
        try:
            subprocess.run(['google-chrome', '--version'], 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE)
        except FileNotFoundError:
            logger.info("Chrome not found. Installing Chrome...")
            try:
                subprocess.run([
                    'wget', '-q', '-O', '-',
                    'https://dl-ssl.google.com/linux/linux_signing_key.pub',
                    '|', 'sudo', 'apt-key', 'add', '-'
                ], check=True)
                
                with open('/etc/apt/sources.list.d/google-chrome.list', 'w') as f:
                    f.write('deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main')
                
                subprocess.run(['sudo', 'apt-get', 'update'])
                subprocess.run(['sudo', 'apt-get', 'install', '-y', 'google-chrome-stable'])
                
            except Exception as e:
                logger.error(f"Failed to install Chrome: {str(e)}")
                raise

    @classmethod
    def get_instance(cls):
        if cls._instance is None or not cls._is_browser_healthy():
            cls.ensure_chrome_installed()
            cls._instance = cls._create_driver()
        return cls._instance
    
    @classmethod
    def _is_browser_healthy(cls):
        if not cls._instance:
            return False
        try:
            cls._instance.current_url
            cls._instance.execute_script('return document.readyState')
            return True
        except:
            logger.warning("Browser health check failed, recreating instance")
            return False
    
    @classmethod
    def _create_driver(cls):
        chrome_options = Options()
        
        # Enhanced server-specific Chrome options with fixed DevTools connection
        chrome_options.add_argument("--headless=chrome")  # Use Chrome-specific headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--remote-debugging-address=0.0.0.0")  # Allow remote debugging from any IP
        chrome_options.add_argument("--remote-debugging-port=9222")  # Use fixed debugging port
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.264 Safari/537.36")
        
        # DevTools specific settings
        chrome_options.add_experimental_option('w3c', True)  # Enable W3C compliance
        chrome_options.add_experimental_option("debuggerAddress", "0.0.0.0:9222")
        
        # Memory optimization
        chrome_options.add_argument("--memory-pressure-off")
        chrome_options.add_argument("--single-process")
        chrome_options.add_argument("--disable-application-cache")
        
        # Clear Chrome cache
        cache_dir = os.path.expanduser('~/.cache/google-chrome')
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
            except Exception as e:
                logger.warning(f"Failed to clear Chrome cache: {str(e)}")
        
        if cls._service is None:
            try:
                cls._service = Service(ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install())
            except Exception as e:
                logger.error(f"Failed to create Chrome service: {str(e)}")
                raise

        try:
            driver = webdriver.Chrome(service=cls._service, options=chrome_options)
            driver.set_script_timeout(30)
            driver.set_page_load_timeout(30)
            
            # Basic performance settings
            driver.execute_script("window.onbeforeunload = null;")
            
            return driver
            
            return driver
            
        except Exception as e:
            logger.error(f"Failed to create Chrome driver: {str(e)}")
            raise

    @classmethod
    def quit(cls):
        if cls._instance:
            try:
                cls._instance.quit()
            except:
                pass
            finally:
                cls._instance = None

def get_generated_image_url(prompt):
    """Generate image from text prompt and return URL"""
    driver = None
    url = None
    max_retries = 5
    retry_count = 0
    retry_delay = 2

    while retry_count < max_retries and not url:
        try:
            if driver is None:
                driver = ChromeDriverSingleton.get_instance()

            if retry_count > 0:
                driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                driver.execute_cdp_cmd('Network.clearBrowserCookies', {})
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 10)

            try:
                driver.get("https://deepai.org/machine-learning-model/text2img")
                input_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "model-input-text-input"))
                )
                
                driver.execute_script("arguments[0].value = '';", input_field)
                driver.execute_script(
                    "arguments[0].value = arguments[1];", 
                    input_field, 
                    prompt
                )
                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));",
                    input_field
                )

                for _ in range(3):
                    try:
                        driver.execute_script(
                            "document.getElementById('modelSubmitButton').click();"
                        )
                        break
                    except:
                        time.sleep(1)

                start_time = time.time()
                while time.time() - start_time < 45:
                    url = driver.execute_script("""
                        const img = document.querySelector('.try-it-result-area img');
                        return img && img.src && img.src.includes('api.deepai.org') ? img.src : null;
                    """)
                    if url and "https://" in url and "api.deepai.org" in url:
                        return url
                    time.sleep(0.5)

            except Exception as e:
                logger.warning(f"Interaction error: {str(e)}")
                raise

        except Exception as e:
            logger.error(f"Attempt {retry_count + 1} failed: {str(e)}")
            retry_count += 1
            
            ChromeDriverSingleton.quit()
            driver = None
            
            if retry_count < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("All retries exhausted")
                raise Exception("Failed to generate image after maximum retries")

    return url

# Register cleanup handler
atexit.register(ChromeDriverSingleton.quit)