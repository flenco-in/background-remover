# utils.py
from PIL import Image, ImageFilter
import numpy as np
from rembg import remove
import io

class ImageProcessor:
    @staticmethod
    def remove_background_enhanced(image: Image.Image) -> Image.Image:
        """
        Remove background from image using rembg with enhanced pre/post processing
        """
        try:
            # Convert to bytes for rembg processing
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            # Remove background
            output = remove(img_byte_arr)
            
            # Convert back to PIL Image
            return Image.open(io.BytesIO(output))
            
        except Exception as e:
            logging.error(f"Background removal error: {str(e)}")
            raise

    @staticmethod
    def add_shadow(
        image: Image.Image,
        offset: tuple = (20, 20),
        blur_radius: int = 30,
        shadow_color: tuple = (0, 0, 0, 120)
    ) -> Image.Image:
        """
        Add a shadow effect to an image with transparency
        """
        try:
            # Ensure image has alpha channel
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            # Create mask from alpha channel
            alpha = image.split()[-1]
            mask = Image.new('RGBA', image.size, (0, 0, 0, 0))
            shadow = Image.new('RGBA', image.size, shadow_color)
            
            # Create shadow mask
            shadow.putalpha(alpha)
            
            # Create output image with space for shadow
            output = Image.new(
                'RGBA',
                (
                    image.size[0] + abs(offset[0]),
                    image.size[1] + abs(offset[1])
                ),
                (0, 0, 0, 0)
            )
            
            # Apply blur to shadow
            shadow = shadow.filter(ImageFilter.GaussianBlur(blur_radius))
            
            # Compose final image
            output.paste(
                shadow,
                (
                    max(offset[0], 0),
                    max(offset[1], 0)
                ),
                shadow
            )
            output.paste(
                image,
                (
                    max(-offset[0], 0),
                    max(-offset[1], 0)
                ),
                image
            )
            
            return output
            
        except Exception as e:
            logging.error(f"Shadow addition error: {str(e)}")
            raise

    @staticmethod
    def replace_background(
        image: Image.Image,
        background: Image.Image or str,
        resize_method: str = 'cover'
    ) -> Image.Image:
        """
        Replace the background of an image with another image or solid color
        """
        try:
            # Ensure image has alpha channel
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            # Create background
            if isinstance(background, str):
                # Solid color background
                bg_image = Image.new('RGBA', image.size, background)
            else:
                # Image background
                bg_image = background
                
                # Resize background
                if resize_method == 'cover':
                    bg_ratio = bg_image.size[0] / bg_image.size[1]
                    img_ratio = image.size[0] / image.size[1]
                    
                    if bg_ratio > img_ratio:
                        new_width = image.size[0]
                        new_height = int(new_width / bg_ratio)
                    else:
                        new_height = image.size[1]
                        new_width = int(new_height * bg_ratio)
                        
                    bg_image = bg_image.resize(
                        (new_width, new_height),
                        Image.Resampling.LANCZOS
                    )
                    
                    # Crop to fit
                    left = (bg_image.size[0] - image.size[0]) // 2
                    top = (bg_image.size[1] - image.size[1]) // 2
                    bg_image = bg_image.crop((
                        left,
                        top,
                        left + image.size[0],
                        top + image.size[1]
                    ))
                else:
                    # Simple resize
                    bg_image = bg_image.resize(
                        image.size,
                        Image.Resampling.LANCZOS
                    )
            
            # Compose final image
            result = Image.new('RGBA', image.size, (0, 0, 0, 0))
            result.paste(bg_image, (0, 0))
            result.paste(image, (0, 0), image)
            
            return result
            
        except Exception as e:
            logging.error(f"Background replacement error: {str(e)}")
            raise