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
    
    # Smooth RGB channels with a bilateral filter for edge-preserving blur
    rgb_image = Image.fromarray(rgb)
    rgb_smoothed = rgb_image.filter(ImageFilter.GaussianBlur(radius=1.5))  # Slightly stronger blur for smoother transitions
    
    # Refine alpha channel
    alpha_image = Image.fromarray(alpha)
    alpha_blurred = alpha_image.filter(ImageFilter.GaussianBlur(radius=2.5))  # More aggressive blur on alpha channel
    alpha_blurred = np.array(alpha_blurred)
    
    # Remove weak alpha values (transparency cleanup)
    alpha_blurred[alpha_blurred < 30] = 0  # Threshold to remove very low alpha values
    alpha_blurred[alpha_blurred > 230] = 255  # Make strong alpha values fully opaque
    
    # Feather edges for better blending
    alpha_feathered = Image.fromarray(alpha_blurred).filter(ImageFilter.GaussianBlur(radius=2))  # Final softening pass
    
    # Reconstruct image with smoothed RGB and alpha channels
    refined = np.dstack((np.array(rgb_smoothed), np.array(alpha_feathered)))
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

import numpy as np
from PIL import Image, ImageFilter
from rembg import remove

def refine_edges(image, alpha_matting=True, alpha_matting_foreground_threshold=240,
                 alpha_matting_background_threshold=10, alpha_matting_erode_size=10):
    """
    Refine edges of the extracted foreground with improved preservation of image details.
    """
    # Convert to numpy array for processing
    img_array = np.array(image)
    
    # Split alpha channel
    rgb = img_array[:, :, :3]
    alpha = img_array[:, :, 3]
    
    # Preserve original RGB channels
    rgb_image = Image.fromarray(rgb)
    
    # Refine alpha channel
    alpha_image = Image.fromarray(alpha)
    alpha_blurred = alpha_image.filter(ImageFilter.GaussianBlur(radius=1))  # Reduced blur radius
    alpha_blurred = np.array(alpha_blurred)
    
    # Adjust alpha values more conservatively
    alpha_blurred[alpha_blurred < 20] = 0  # Only remove very low alpha values
    alpha_blurred[alpha_blurred > 240] = 255  # Make strong alpha values fully opaque
    
    # Feather edges for better blending, but with a smaller radius
    alpha_feathered = Image.fromarray(alpha_blurred).filter(ImageFilter.GaussianBlur(radius=1))
    
    # Reconstruct image with original RGB and refined alpha channels
    refined = np.dstack((np.array(rgb_image), np.array(alpha_feathered)))
    return Image.fromarray(refined)

def remove_background_enhanced(image):
    """
    Enhanced background removal with better preservation of image details.
    """
    # Initial background removal with rembg
    no_bg = remove(
        image,
        alpha_matting=True,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=10
    )
    
    # Apply edge refinement with more conservative parameters
    refined = refine_edges(no_bg, 
                           alpha_matting_foreground_threshold=240,
                           alpha_matting_background_threshold=10,
                           alpha_matting_erode_size=5)  # Reduced erode size
    
    return refined

def replace_background(foreground, background):
    """
    Replace background of foreground image with enhanced edge handling and detail preservation.
    """
    # Ensure the foreground has an alpha channel
    foreground = foreground.convert('RGBA')
    
    # Apply additional edge refinement with more conservative parameters
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
    
    # Apply minimal feathering to the edges
    alpha = foreground.split()[3]
    alpha_blur = alpha.filter(ImageFilter.GaussianBlur(radius=0.5))  # Reduced blur radius
    foreground.putalpha(alpha_blur)
    
    # Combine the foreground and background
    result = Image.alpha_composite(background, foreground)
    
    return result
# Flask API Setup
app = Flask(__name__)

@app.route('/remove-background', methods=['POST'])
def remove_background_api():
    if 'image' not in request.files:
        return 'No image uploaded', 400
    
    # Process the input image
    image_file = request.files['image']
    image = Image.open(image_file)
    
    # Get edge refinement intensity (default to 1.0 if not provided)
    edge_refinement_intensity = float(request.form.get('edge_refinement_intensity', 1.0))
    
    # Remove background with enhanced edge handling and custom intensity
    no_bg_image = remove_background_enhanced(image)
    no_bg_image = refine_edges(no_bg_image, alpha_matting_erode_size=int(5 * edge_refinement_intensity))
    
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