# main.py
from flask import Flask
from waitress import serve
from handlers import BackgroundRemovalHandler, ImageGenerationHandler
import multiprocessing
import logging.handlers
import os

# Configure logging with rotation
def setup_logging():
    log_dir = '/var/log/imageapp'
    os.makedirs(log_dir, exist_ok=True)
    
    handler = logging.handlers.RotatingFileHandler(
        f'{log_dir}/app.log',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

# Initialize Flask with optimal settings
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = '/tmp/image_uploads'

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Rate limiting and caching setup
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

cache = Cache(app, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': '/tmp/flask_cache',
    'CACHE_DEFAULT_TIMEOUT': 300
})

# Routes with rate limiting and error handling
@app.route('/remove-background', methods=['POST'])
@limiter.limit("30 per minute")
def remove_background_api():
    try:
        return BackgroundRemovalHandler.handle_request()
    except Exception as e:
        logging.error(f"Background removal error: {str(e)}")
        return {'error': str(e)}, 500

@app.route('/generate-image', methods=['POST'])
@limiter.limit("10 per minute")
def generate_image_api():
    try:
        return ImageGenerationHandler.handle_request()
    except Exception as e:
        logging.error(f"Image generation error: {str(e)}")
        return {'error': str(e)}, 500

# Health check endpoint
@app.route('/health', methods=['GET'])
@cache.cached(timeout=60)
def health_check():
    return {'status': 'healthy'}, 200

if __name__ == '__main__':
    setup_logging()
    # Use Waitress as production WSGI server
    num_threads = multiprocessing.cpu_count() * 2
    serve(app, host='0.0.0.0', port=5001, threads=num_threads)