# handlers.py
from flask import request, send_file, current_app
import io
import logging
import threading
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import tempfile
import os
from werkzeug.utils import secure_filename
import json
from utils import ImageProcessor

# Configure thread pool for parallel processing
executor = ThreadPoolExecutor(max_workers=4)

class BackgroundRemovalHandler:
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    
    @staticmethod
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in BackgroundRemovalHandler.ALLOWED_EXTENSIONS

    @staticmethod
    def handle_request():
        """Optimized background removal handler with improved error handling and memory management"""
        if 'image' not in request.files:
            return {'error': 'No image uploaded'}, 400
        
        image_file = request.files['image']
        if not image_file or not BackgroundRemovalHandler.allowed_file(image_file.filename):
            return {'error': 'Invalid file format'}, 400

        try:
            # Save uploaded file to temporary location
            temp_dir = tempfile.mkdtemp(dir=current_app.config['UPLOAD_FOLDER'])
            temp_path = os.path.join(temp_dir, secure_filename(image_file.filename))
            image_file.save(temp_path)

            # Process image in thread pool
            future = executor.submit(BackgroundRemovalHandler._process_image, temp_path)
            result = future.result(timeout=30)  # 30 second timeout

            return send_file(
                io.BytesIO(result),
                mimetype='image/png',
                as_attachment=True,
                download_name='processed.png'
            )

        except TimeoutError:
            logging.error("Image processing timeout")
            return {'error': 'Processing timeout'}, 408
        except Exception as e:
            logging.error(f"Background removal error: {str(e)}")
            return {'error': str(e)}, 500
        finally:
            # Cleanup temporary files
            try:
                os.remove(temp_path)
                os.rmdir(temp_dir)
            except Exception:
                pass

    @staticmethod
    def _process_image(image_path):
        """Process image with memory-efficient approach"""
        try:
            with Image.open(image_path) as image:
                # Convert image to RGB if necessary
                if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                    image = image.convert('RGBA')
                else:
                    image = image.convert('RGB')

                # Process image
                processed = ImageProcessor.remove_background_enhanced(image)
                
                # Save to bytes
                img_byte_arr = io.BytesIO()
                processed.save(img_byte_arr, format='PNG', optimize=True)
                return img_byte_arr.getvalue()

        except Exception as e:
            logging.error(f"Image processing error: {str(e)}")
            raise

class ImageGenerationHandler:
    def __init__(self):
        self._generator = None
        self._generator_lock = threading.Lock()

    def get_generator(self):
        """Lazy initialization of SeleniumImageGenerator"""
        if self._generator is None:
            with self._generator_lock:
                if self._generator is None:
                    from selenium_utils import SeleniumImageGenerator
                    self._generator = SeleniumImageGenerator()
        return self._generator

    @staticmethod
    def handle_request():
        """Optimized image generation handler with improved error handling"""
        try:
            data = request.get_json()
            if not data or 'prompt' not in data:
                return {'error': 'No prompt provided'}, 400

            prompt = data['prompt']
            if not isinstance(prompt, str) or len(prompt) > 1000:
                return {'error': 'Invalid prompt'}, 400

            handler = ImageGenerationHandler()
            generator = handler.get_generator()
            
            # Generate image with timeout
            future = executor.submit(generator.generate_image, prompt)
            image_url = future.result(timeout=60)  # 60 second timeout

            if not image_url:
                return {'error': 'Failed to generate image'}, 500

            return {
                'status': 'success',
                'image_url': image_url
            }

        except TimeoutError:
            logging.error("Image generation timeout")
            return {'error': 'Generation timeout'}, 408
        except Exception as e:
            logging.error(f"Image generation error: {str(e)}")
            return {'error': str(e)}, 500