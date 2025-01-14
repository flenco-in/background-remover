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
import os
import signal
import psutil

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def kill_chrome_processes():
    """Kill any existing Chrome processes"""
    try:
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and ('chrome' in proc.info['name'].lower()):
                try:
                    os.kill(proc.pid, signal.SIGKILL)
                except:
                    pass
    except:
        pass

class ChromeManager:
    @staticmethod
    def create_driver():
        """Create a new Chrome driver instance with minimal memory usage"""
        kill_chrome_processes()  # Ensure no lingering processes
        
        chrome_options = Options()
        
        # Essential options only
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Memory-specific options
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-javascript")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--single-process")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--aggressive-cache-discard")
        chrome_options.add_argument("--disable-cache")
        chrome_options.add_argument("--disable-application-cache")
        chrome_options.add_argument("--disable-offline-load-stale-cache")
        chrome_options.add_argument("--disk-cache-size=0")
        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--disable-sync")
        chrome_options.add_argument("--disable-translate")
        chrome_options.add_argument("--hide-scrollbars")
        chrome_options.add_argument("--metrics-recording-only")
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--safebrowsing-disable-auto-update")
        chrome_options.add_argument("--window-size=1200,900")  # Reduced window size
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(30)
            driver.command_executor._commands["send_command"] = ("POST", '/session/$sessionId/chromium/send_command')
            return driver
        except Exception as e:
            logger.error(f"Failed to create Chrome driver: {str(e)}")
            raise

def get_generated_image_url(prompt, max_retries=3):
    """Generate image from text prompt with minimal memory usage"""
    for attempt in range(max_retries):
        driver = None
        try:
            driver = ChromeManager.create_driver()
            
            # Load page
            driver.get("https://deepai.org/machine-learning-model/text2img")
            
            # Find and fill input
            input_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "model-input-text-input"))
            )
            driver.execute_script("arguments[0].value = arguments[1];", input_field, prompt)
            
            # Click submit
            submit_button = driver.find_element(By.ID, "modelSubmitButton")
            driver.execute_script("arguments[0].click();", submit_button)
            
            # Wait for result with timeout
            start_time = time.time()
            while time.time() - start_time < 30:
                try:
                    img_element = driver.find_element(By.CSS_SELECTOR, ".try-it-result-area img")
                    url = img_element.get_attribute("src")
                    if url and "api.deepai.org" in url:
                        return url
                except:
                    time.sleep(0.5)
            
            raise Exception("Timeout waiting for image generation")
            
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise Exception("Failed to generate image after all retries")
            time.sleep(2)
            
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            kill_chrome_processes()  # Ensure cleanup

# Register cleanup on exit
atexit.register(kill_chrome_processes)