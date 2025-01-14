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

def create_driver():
    """Create a new Chrome driver instance"""
    kill_chrome_processes()  # Clean up before creating new instance
    
    chrome_options = Options()
    
    # Basic settings
    chrome_options.add_argument('--headless=new')  # Using new headless mode
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Memory optimization
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--window-size=1200,900')
    
    # DevTools stability
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--no-startup-window')
    chrome_options.add_argument('--enable-logging')
    chrome_options.add_argument('--v=1')
    
    # Additional stability options
    chrome_options.add_argument('--disable-background-networking')
    chrome_options.add_argument('--disable-default-apps')
    chrome_options.add_argument('--disable-sync')
    chrome_options.add_argument('--disable-translate')
    chrome_options.add_argument('--metrics-recording-only')
    chrome_options.add_argument('--mute-audio')
    chrome_options.add_argument('--no-first-run')
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        logger.error(f"Failed to create Chrome driver: {str(e)}")
        raise

def get_generated_image_url(prompt, max_retries=3):
    """Generate image from text prompt"""
    for attempt in range(max_retries):
        driver = None
        try:
            driver = create_driver()
            logger.info("Chrome driver created successfully")
            
            # Load page
            logger.info("Loading webpage...")
            driver.get("https://deepai.org/machine-learning-model/text2img")
            time.sleep(2)  # Allow page to stabilize
            
            # Find and fill input
            logger.info("Entering prompt...")
            input_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "model-input-text-input"))
            )
            
            # Use JavaScript to set value and trigger input event
            driver.execute_script("""
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            """, input_field, prompt)
            
            # Wait a moment for input to be registered
            time.sleep(1)
            
            # Click submit using JavaScript
            logger.info("Submitting prompt...")
            driver.execute_script("""
                const button = document.getElementById('modelSubmitButton');
                if (button) button.click();
            """)
            
            # Wait for result with timeout
            logger.info("Waiting for image generation...")
            start_time = time.time()
            while time.time() - start_time < 30:
                try:
                    url = driver.execute_script("""
                        const img = document.querySelector('.try-it-result-area img');
                        return img && img.src && img.src.includes('api.deepai.org') ? img.src : null;
                    """)
                    if url:
                        logger.info("Image URL generated successfully")
                        return url
                except:
                    pass
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
            kill_chrome_processes()

# Register cleanup on exit
atexit.register(kill_chrome_processes)