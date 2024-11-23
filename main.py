import os
import io
import numpy as np
from flask import Flask, request, send_file
from rembg import remove
from PIL import Image, ImageColor, ImageOps, ImageFilter

def refine_edges(image, alpha_matting=True, alpha_matting_foreground_threshold=240,
                 alpha_matting_background_threshold=10, alpha_matting_erode_size=10):
    """
    Refine edges of the extracted foreground using multiple techniques.
    
    Args:
        image (PIL.Image): Input image with transparency
        alpha_matting: Whether to use alpha matting
        alpha_matting_foreground_threshold: Threshold for foreground in alpha matting
        alpha_matting_background_threshold: Threshold for background in alpha matting
        alpha_matting_erode_size: Size of erosion in alpha matting
    
    Returns:
        PIL.Image: Image with refined edges
    """
    # Convert to numpy array for processing
    img_array = np.array(image)
    
    # Split alpha channel
    rgb = img_array[:, :, :3]
    alpha = img_array[:, :, 3]
    
    # Apply bilateral filter to reduce noise while preserving edges
    filtered = Image.fromarray(rgb).filter(ImageFilter.SMOOTH_MORE)
    rgb = np.array(filtered)
    
    # Edge smoothing
    alpha = Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(radius=0.5))
    alpha = np.array(alpha)
    
    # Remove any remaining artifacts
    alpha[alpha < 25] = 0  # Remove very transparent pixels
    alpha[alpha > 235] = 255  # Make strong pixels fully opaque
    
    # Reconstruct image
    refined = np.dstack((rgb, alpha))
    return Image.fromarray(refined)

def remove_background_enhanced(image):
    """
    Enhanced background removal with better edge handling.
    
    Args:
        image (PIL.Image): Input image
    
    Returns:
        PIL.Image: Image with background removed and refined edges
    """
    # Initial background removal with rembg
    no_bg = remove(
        image,
        alpha_matting=True,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=10
    )
    
    # Apply edge refinement
    refined = refine_edges(no_bg)
    
    return refined

def replace_background(foreground, background):
    """
    Replace background of foreground image with enhanced edge handling.
    
    Args:
        foreground (PIL.Image): Foreground image with transparent background
        background (PIL.Image or str): Background image or color
    
    Returns:
        PIL.Image: Image with replaced background
    """
    # Ensure the foreground has an alpha channel
    foreground = foreground.convert('RGBA')
    
    # Apply additional edge refinement
    foreground = refine_edges(foreground)
    
    # Handle background (color or image)
    if isinstance(background, Image.Image):
        background = background.convert('RGBA')
        background = ImageOps.fit(background, foreground.size, method=Image.Resampling.LANCZOS)
    elif isinstance(background, str):
        try:
            bg_color = ImageColor.getrgb(background)
            background = Image.new('RGBA', foreground.size, bg_color + (255,))
        except ValueError:
            background = Image.new('RGBA', foreground.size, (255, 255, 255, 255))
    else:
        background = Image.new('RGBA', foreground.size, (255, 255, 255, 255))
    
    # Apply feathering to the edges
    foreground_blur = foreground.filter(ImageFilter.GaussianBlur(radius=0.5))
    alpha = foreground.split()[3]
    alpha_blur = alpha.filter(ImageFilter.GaussianBlur(radius=0.5))
    foreground.putalpha(alpha_blur)
    
    # Combine the foreground and background
    result = Image.alpha_composite(background, foreground)
    
    return result

# Flask API Setup
app = Flask(__name__)

@app.route('/remove-background', methods=['POST'])
def remove_background_api():
    """
    API endpoint for background removal and replacement with enhanced edge handling.
    """
    if 'image' not in request.files:
        return 'No image uploaded', 400
    
    # Process the input image
    image_file = request.files['image']
    image = Image.open(image_file)
    
    # Remove background with enhanced edge handling
    no_bg_image = remove_background_enhanced(image)
    
    # Handle background replacement
    result = no_bg_image
    if 'background_image' in request.files:
        try:
            background_image_file = request.files['background_image']
            background_image = Image.open(background_image_file)
            result = replace_background(no_bg_image, background_image)
        except Exception as e:
            return f'Error processing background image: {str(e)}', 400
    elif request.form.get('background'):
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