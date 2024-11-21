import os
import io
from flask import Flask, request, send_file
from rembg import remove
from PIL import Image, ImageColor, ImageOps

def replace_background(foreground, background):
    """
    Replace background of foreground image.
    
    Args:
        foreground (PIL.Image): Foreground image with transparent background.
        background (PIL.Image or str): Background image or color.
    
    Returns:
        PIL.Image: Image with replaced background.
    """
    # Ensure the foreground has an alpha channel
    foreground = foreground.convert('RGBA')
    
    # Handle background (color or image)
    if isinstance(background, Image.Image):
        # If background is an image, fit it to fill the foreground size
        background = background.convert('RGBA')
        background = ImageOps.fit(background, foreground.size, method=Image.Resampling.LANCZOS)
    elif isinstance(background, str):
        # If background is a color (hex or named)
        try:
            bg_color = ImageColor.getrgb(background)
            background = Image.new('RGBA', foreground.size, bg_color + (255,))
        except ValueError:
            # Default to white if color parsing fails
            background = Image.new('RGBA', foreground.size, (255, 255, 255, 255))
    else:
        # Default to white if background type is unrecognized
        background = Image.new('RGBA', foreground.size, (255, 255, 255, 255))
    
    # Combine the foreground and background
    result = Image.alpha_composite(background, foreground)
    
    return result

# Flask API Setup
app = Flask(__name__)

@app.route('/remove-background', methods=['POST'])
def remove_background_api():
    """
    API endpoint for background removal and replacement.
    
    Accepts multipart/form-data with:
    - image: Input image file.
    - background: Background color (optional, as string).
    - background_image: Background image file (optional).
    """
    if 'image' not in request.files:
        return 'No image uploaded', 400
    
    # Process the input image
    image_file = request.files['image']
    image = Image.open(image_file)
    
    # Remove background
    no_bg_image = remove(image)
    
    # Handle background replacement
    result = no_bg_image  # Default to the transparent image
    if 'background_image' in request.files:
        # If a background image is uploaded
        try:
            background_image_file = request.files['background_image']
            background_image = Image.open(background_image_file)
            result = replace_background(no_bg_image, background_image)
        except Exception as e:
            return f'Error processing background image: {str(e)}', 400
    elif request.form.get('background'):
        # If a background color is provided
        try:
            background_color = request.form.get('background')
            result = replace_background(no_bg_image, background_color)
        except Exception as e:
            return f'Error processing background color: {str(e)}', 400
    
    # Save the result to a byte stream
    img_byte_arr = io.BytesIO()
    result.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return send_file(img_byte_arr, mimetype='image/png')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
