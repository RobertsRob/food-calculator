from PIL import Image
import base64
import io

def resize_image(image_file, target_size_kb=250):
    # Open image
    img = Image.open(image_file)
    
    # Get current dimensions
    width, height = img.size
    
    # Calculate aspect ratio
    aspect_ratio = width / height
    
    # Target max size (in bytes)
    target_size_bytes = target_size_kb * 1024
    
    # Resize the image to keep the aspect ratio, reducing until it's under the target size
    for i in range(1, 5):  # Try 4 different sizes (arbitrary adjustment for reasonable compression)
        new_width = int(width / i)
        new_height = int(new_width / aspect_ratio)
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save the resized image to an in-memory buffer
        buffer = io.BytesIO()
        img_resized.save(buffer, format="JPEG", quality=85)  # Save as JPEG with compression quality
        buffer.seek(0)
        
        # Check size in KB
        image_size = len(buffer.getvalue()) / 1024  # Convert to KB
        if image_size <= target_size_kb:
            break
    
    # Return the resized image in base64
    image_bytes = buffer.getvalue()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    return image_base64