from PIL import Image, ImageColor, ImageOps, ImageFilter
from rembg import remove
import numpy as np

class ImageProcessor:
    @staticmethod
    def refine_edges(image, alpha_matting_foreground_threshold=240,
                     alpha_matting_background_threshold=10, alpha_matting_erode_size=5):
        """Refine edges of the extracted foreground with improved preservation of details."""
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

    @staticmethod
    def remove_background_enhanced(image):
        """Remove the background with edge refinement."""
        no_bg = remove(
            image,
            alpha_matting=True,
            alpha_matting_foreground_threshold=240,
            alpha_matting_background_threshold=10,
            alpha_matting_erode_size=10
        )
        return ImageProcessor.refine_edges(no_bg)

    @staticmethod
    def add_shadow(image, offset=(20, 20), blur_radius=30, shadow_color=(0, 0, 0, 120)):
        """Add a soft, realistic shadow behind the image."""
        image = image.convert("RGBA")
        width, height = image.size

        shadow_layer = Image.new("RGBA", (width + abs(offset[0]), height + abs(offset[1])), (0, 0, 0, 0))
        alpha = image.split()[3]
        shadow = Image.new("RGBA", (width, height), shadow_color)
        
        shadow_layer.paste(shadow, (max(offset[0], 0), max(offset[1], 0)), mask=alpha)
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur_radius))
        
        final_image = Image.new("RGBA", shadow_layer.size, (0, 0, 0, 0))
        final_image.paste(shadow_layer, (0, 0))
        final_image.paste(image, (max(-offset[0], 0), max(-offset[1], 0)), mask=image.split()[3])
        
        return final_image

    @staticmethod
    def replace_background(foreground, background):
        """Replace background of an image with optional shadow addition."""
        foreground = foreground.convert('RGBA')
        
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
        
        return Image.alpha_composite(background, foreground)