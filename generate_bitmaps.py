import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# DLP LightCrafter 4500 Native DMD Dimensions
WIDTH = 912
HEIGHT = 1140

def create_pattern_frame(frame_idx: int, total_frames: int = 8) -> Image.Image:
    """
    Generates a single 24-bit RGB bitmap frame with a moving checkerboard pattern,
    concentric rings, and frame index indicators.
    """
    # 1. Create coordinate grids
    x = np.arange(WIDTH)
    y = np.arange(HEIGHT)
    xx, yy = np.meshgrid(x, y)

    # 2. Base Pattern: Animated Horizontal & Vertical Grating (Checkerboard motion)
    grid_size = 60
    shift = int((frame_idx / total_frames) * grid_size)
    
    checker_x = ((xx + shift) // grid_size) % 2
    checker_y = ((yy + shift) // grid_size) % 2
    checkerboard = np.bitwise_xor(checker_x, checker_y) * 255

    # 3. Concentric Rings in center
    center_x, center_y = WIDTH // 2, HEIGHT // 2
    r = np.sqrt((xx - center_x)**2 + (yy - center_y)**2)
    ring_period = 80
    rings = (((r - (frame_idx * 10)) % ring_period) < (ring_period / 2)).astype(np.uint8) * 255

    # Combine checkerboard and rings (composite pattern)
    combined = np.where(rings > 0, 255 - checkerboard, checkerboard).astype(np.uint8)

    # Convert to 24-bit RGB image (required by DLPC350 GUI)
    img = Image.fromarray(combined, mode="L").convert("RGB")
    draw = ImageDraw.Draw(img)

    # 4. Add Crosshairs across the DMD center
    draw.line([(center_x, 0), (center_x, HEIGHT)], fill=(255, 0, 0), width=3) # Red vertical
    draw.line([(0, center_y), (WIDTH, center_y)], fill=(0, 255, 0), width=3) # Green horizontal

    # 5. Add Framed Borders (useful for alignment validation)
    draw.rectangle([5, 5, WIDTH - 5, HEIGHT - 5], outline=(255, 255, 255), width=4)

    # 6. Burn-in Sequence Number Text
    text = f"PATTERN #{frame_idx + 1}"
    # Simple fallback built-in text overlay
    draw.text((30, 30), text, fill=(255, 255, 255))

    return img


def generate_sequence(output_dir: str = "patterns", num_frames: int = 8):
    """
    Generates and saves the bitmap sequence into a designated directory.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Generating {num_frames} patterns @ {WIDTH}x{HEIGHT} resolution...")

    for i in range(num_frames):
        img = create_pattern_frame(frame_idx=i, total_frames=num_frames)
        filename = os.path.join(output_dir, f"pattern_{i+1:02d}.bmp")
        img.save(filename, format="BMP")
        print(f" Saved: {filename}")

    print("\nDone! Images are ready to be uploaded to DLPC350 GUI Firmware/Flash Memory.")


if __name__ == "__main__":
    generate_sequence(num_frames=8)