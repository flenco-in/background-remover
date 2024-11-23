import os
import io
from flask import Flask, request, send_file
from rembg import remove
from PIL import Image, ImageColor, ImageOps, ImageFilter
import numpy as np

app = Flask(__name__)

def refine_edges(image, alpha_matting_foreground_threshold=240, 
                 alpha_matting_background_threshold=10, alpha_matting_erode_size=5):
    """
    Refine edges of the extracted foreground with improved preservation of details.
    """
    img_array = np.array(image)
    rgb = img_array[:, :, :3]
    alpha = img_array[:, :, 3]
    
    # Refine alpha channel
    alpha_image = Image.fromarray(alpha)
    alpha_blurred = alpha_image.filter(ImageFilter.GaussianBlur(radius=1))
    alpha_blurred = np.array(alpha_blurred)
    alpha_blurred[alpha_blurred < 20] = 0
    alpha_blurred[alpha_blurred > 240] = 255
    alpha_feathered = Image.fromarray(alpha_blurred).filter(ImageFilter.GaussianBlur(radius=1))
    
    # Combine refined alpha with original RGB
    refined = np.dstack((rgb, np.array(alpha_feathered)))
    return Image.fromarray(refined)

def remove_background_enhanced(image):
    """
    Remove the background with edge refinement.
    """
    no_bg = remove(
        image,
        alpha_matting=True,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=10
    )
    return refine_edges(no_bg)

def add_shadow(image, offset=(20, 20), blur_radius=30, shadow_color=(0, 0, 0, 120)):
    """
    Add a soft, realistic shadow behind the image.
    
    Args:
    - image: PIL Image object.
    - offset: Tuple (x, y) for shadow offset.
    - blur_radius: Blur radius to soften shadow edges.
    - shadow_color: RGBA color of the shadow.
    
    Returns:
    - Image with shadow effect applied.
    """
    # Ensure image has alpha channel
    image = image.convert("RGBA")
    width, height = image.size

    # Create a base shadow layer
    shadow_layer = Image.new("RGBA", (width + abs(offset[0]), height + abs(offset[1])), (0, 0, 0, 0))
    
    # Create a shadow from the alpha channel of the image
    alpha = image.split()[3]
    shadow = Image.new("RGBA", (width, height), shadow_color)
    
    # Paste shadow at the original position with the alpha mask
    shadow_layer.paste(shadow, (max(offset[0], 0), max(offset[1], 0)), mask=alpha)
    
    # Apply blur to create soft shadow edges
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur_radius))
    
    # Composite the shadow and the original image
    final_image = Image.new("RGBA", shadow_layer.size, (0, 0, 0, 0))
    final_image.paste(shadow_layer, (0, 0))
    final_image.paste(image, (max(-offset[0], 0), max(-offset[1], 0)), mask=image.split()[3])
    
    return final_image

def replace_background(foreground, background):
    """
    Replace background of an image with optional shadow addition.
    """
    # Ensure the foreground has an alpha channel
    foreground = foreground.convert('RGBA')
    
    # Handle background
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
    
    # Combine foreground and background
    result = Image.alpha_composite(background, foreground)
    return result

@app.route('/remove-background', methods=['POST'])
def remove_background_api():
    if 'image' not in request.files:
        return 'No image uploaded', 400
    
    # Process input image
    image_file = request.files['image']
    image = Image.open(image_file)
    
    # Shadow parameters
    add_shadow_flag = request.form.get('add_shadow', 'false').lower() == 'true'
    shadow_offset = tuple(map(int, request.form.get('shadow_offset', '20,20').split(',')))
    shadow_blur = int(request.form.get('shadow_blur', 30))
    shadow_color = request.form.get('shadow_color', '0,0,0,120').split(',')
    shadow_color = tuple(map(int, shadow_color))
    
    # Remove background
    no_bg_image = remove_background_enhanced(image)
    
    # Apply shadow if requested
    if add_shadow_flag:
        no_bg_image = add_shadow(no_bg_image, offset=shadow_offset, blur_radius=shadow_blur, shadow_color=shadow_color)
    
    # Handle background replacement (optional)
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
    
    # Save result to a byte stream
    img_byte_arr = io.BytesIO()
    result.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return send_file(img_byte_arr, mimetype='image/png')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
