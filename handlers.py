from flask import request, send_file
from PIL import Image
import io
from utils import ImageProcessor

from flask import request, jsonify
from selenium_utils import get_generated_image_url
from selenium_utils import SeleniumImageGenerator
import logging

logger = logging.getLogger(__name__)

class BackgroundRemovalHandler:
    @staticmethod
    def handle_request():
        """Handle background removal request with optional shadow and background replacement."""
        if 'image' not in request.files:
            return 'No image uploaded', 400
        
        try:
            # Get input image
            image_file = request.files['image']
            image = Image.open(image_file)
            
            # Process shadow parameters
            shadow_params = BackgroundRemovalHandler._get_shadow_params()
            
            # Remove background
            no_bg_image = ImageProcessor.remove_background_enhanced(image)
            
            # Apply shadow if requested
            if shadow_params['add_shadow']:
                no_bg_image = ImageProcessor.add_shadow(
                    no_bg_image,
                    offset=shadow_params['offset'],
                    blur_radius=shadow_params['blur'],
                    shadow_color=shadow_params['color']
                )
            
            # Handle background replacement
            result = BackgroundRemovalHandler._handle_background_replacement(no_bg_image)
            
            # Return processed image
            return BackgroundRemovalHandler._prepare_response(result)
            
        except Exception as e:
            return f'Error processing image: {str(e)}', 400

    @staticmethod
    def _get_shadow_params():
        """Extract shadow parameters from request."""
        return {
            'add_shadow': request.form.get('add_shadow', 'false').lower() == 'true',
            'offset': tuple(map(int, request.form.get('shadow_offset', '20,20').split(','))),
            'blur': int(request.form.get('shadow_blur', 30)),
            'color': tuple(map(int, request.form.get('shadow_color', '0,0,0,120').split(',')))
        }

    @staticmethod
    def _handle_background_replacement(image):
        """Handle background replacement if requested."""
        if 'background_image' in request.files:
            background_image = Image.open(request.files['background_image'])
            return ImageProcessor.replace_background(image, background_image)
        elif request.form.get('background'):
            return ImageProcessor.replace_background(image, request.form.get('background'))
        return image

    @staticmethod
    def _prepare_response(image):
        """Prepare image for response."""
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return send_file(img_byte_arr, mimetype='image/png')
    

class ImageGenerationHandler:
    @staticmethod
    def handle_request():
        try:
            # Get the prompt from the request
            data = request.get_json()
            if not data or 'prompt' not in data:
                return jsonify({'error': 'No prompt provided'}), 400
            
            prompt = data['prompt']
            
            # Initialize the image generator
            generator = SeleniumImageGenerator()
            
            # Generate the image
            image_url = generator.generate_image(prompt)
            
            if not image_url:
                return jsonify({'error': 'Failed to generate image'}), 500
                
            # Return the image URL
            return jsonify({
                'status': 'success',
                'image_url': image_url
            })
            
        except Exception as e:
            logger.error(f"Error in image generation handler: {str(e)}")
            return jsonify({'error': str(e)}), 500