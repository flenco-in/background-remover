# main.py
from flask import Flask
from gevent.pywsgi import WSGIServer
from handlers import BackgroundRemovalHandler, ImageGenerationHandler
import logging.handlers
import os
import signal
import gevent
from gevent import monkey
monkey.patch_all()

# Configure logging based on PM2 environment
def setup_logging():
    log_dir = os.getenv('LOG_DIR', '/var/log/imageapp')
    os.makedirs(log_dir, exist_ok=True)
    
    formatter = logging.Formatter(
        '%(asctime)s - [Instance %(instance_id)s] - %(levelname)s - %(message)s'
    )
    
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    handler.setFormatter(formatter)
    
    # Add instance ID to log records
    old_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.instance_id = os.getenv('INSTANCE_ID', '0')
        return record
    logging.setLogRecordFactory(record_factory)
    
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

# Initialize Flask with PM2 optimized settings
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = os.getenv('TEMP_UPLOAD_DIR', '/tmp/image_uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Routes with PM2-aware error handling
@app.route('/remove-background', methods=['POST'])
def remove_background_api():
    instance_id = os.getenv('INSTANCE_ID', '0')
    try:
        logging.info(f"[Instance {instance_id}] Processing background removal request")
        return BackgroundRemovalHandler.handle_request()
    except Exception as e:
        logging.error(f"[Instance {instance_id}] Background removal error: {str(e)}")
        return {'error': str(e)}, 500

@app.route('/generate-image', methods=['POST'])
def generate_image_api():
    instance_id = os.getenv('INSTANCE_ID', '0')
    try:
        logging.info(f"[Instance {instance_id}] Processing image generation request")
        return ImageGenerationHandler.handle_request()
    except Exception as e:
        logging.error(f"[Instance {instance_id}] Image generation error: {str(e)}")
        return {'error': str(e)}, 500

# Health check endpoint for PM2 monitoring
@app.route('/health', methods=['GET'])
def health_check():
    instance_id = os.getenv('INSTANCE_ID', '0')
    return {
        'status': 'healthy',
        'instance': instance_id,
        'memory_usage': gevent.get_memory_usage()
    }

def cleanup_handler(signum, frame):
    """Graceful shutdown handler for PM2"""
    logging.info(f"[Instance {os.getenv('INSTANCE_ID', '0')}] Shutting down gracefully...")
    try:
        # Cleanup temporary files
        temp_dir = app.config['UPLOAD_FOLDER']
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logging.error(f"Error cleaning up {file_path}: {str(e)}")
    except Exception as e:
        logging.error(f"Error during cleanup: {str(e)}")
    
    # Give ongoing requests time to complete
    gevent.sleep(2)
    exit(0)

if __name__ == '__main__':
    # Set up signal handlers
    signal.signal(signal.SIGTERM, cleanup_handler)
    signal.signal(signal.SIGINT, cleanup_handler)
    
    setup_logging()
    
    # Get port from environment or default
    port = int(os.getenv('PORT', 5001))
    
    # Use gevent WSGI server for better performance with PM2
    http_server = WSGIServer(('0.0.0.0', port), app)
    
    logging.info(f"[Instance {os.getenv('INSTANCE_ID', '0')}] Starting server on port {port}")
    try:
        http_server.serve_forever()
    except Exception as e:
        logging.error(f"Server error: {str(e)}")
        exit(1)