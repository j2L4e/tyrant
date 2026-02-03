from PIL import Image, ImageDraw


def create_idle_icon(size=64):
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Gray circle outline
    margin = size // 8
    draw.ellipse([margin, margin, size - margin, size - margin], outline="gray", width=size//16)
    
    return image


def create_muted_icon(size=64):
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Gray circle outline
    margin = size // 8
    draw.ellipse([margin, margin, size - margin, size - margin], outline="gray", width=size//16)
    
    # Gray cross inside (smaller than the circle)
    line_width = size // 16
    inner_margin = size // 3
    draw.line([inner_margin, inner_margin, size - inner_margin, size - inner_margin], fill="gray", width=line_width)
    draw.line([size - inner_margin, inner_margin, inner_margin, size - inner_margin], fill="gray", width=line_width)
    
    return image


def create_recording_icon(size=64):
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Red circle outline
    margin = size // 8
    draw.ellipse([margin, margin, size - margin, size - margin], outline="red", width=size//16)
    
    return image


def create_transcribing_icon(size=64):
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Orange circle outline
    margin = size // 8
    draw.ellipse([margin, margin, size - margin, size - margin], outline="orange", width=size//16)
    
    return image
