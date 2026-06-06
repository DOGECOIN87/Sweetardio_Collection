import os
import glob
from PIL import Image, ImageFilter, ImageOps

def apply_sticker_style(input_path, output_path):
    # Load the image
    img = Image.open(input_path).convert("RGBA")
    
    # Define border and shadow parameters
    border_size = 15
    border_opacity = 180  # 0-255 (semi-opaque)
    shadow_offset = (10, 10)
    shadow_blur = 15
    shadow_opacity = 150  # 0-255
    
    # 1. Create the border mask
    # Get the alpha channel of the original image
    alpha = img.getchannel('A')
    
    # Dilate the alpha channel to create a border
    # We use a trick: blur then threshold to create a thick outline
    border_mask = alpha.filter(ImageFilter.MaxFilter(border_size * 2 + 1))
    
    # 2. Create the white border image
    white_border = Image.new("RGBA", img.size, (255, 255, 255, border_opacity))
    
    # 3. Create the shadow
    shadow_mask = alpha.filter(ImageFilter.GaussianBlur(shadow_blur))
    shadow_img = Image.new("RGBA", img.size, (0, 0, 0, shadow_opacity))
    
    # 4. Composite everything
    # Create a canvas larger than the original to accommodate shadow/border if needed
    # But since these are traits, we might want to keep the original size and just center it
    canvas = Image.new("RGBA", img.size, (0, 0, 0, 0))
    
    # Apply shadow with offset
    shadow_canvas = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_canvas.paste(shadow_img, shadow_offset, mask=shadow_mask)
    canvas.alpha_composite(shadow_canvas)
    
    # Apply white border
    canvas.paste(white_border, (0, 0), mask=border_mask)
    
    # Paste original image on top
    canvas.alpha_composite(img)
    
    # Save the result
    canvas.save(output_path)
    print(f"Processed: {os.path.basename(input_path)}")

def main():
    input_dir = "traits/stickerz"
    output_dir = "traits/stickerz_processed"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    sticker_files = glob.glob(os.path.join(input_dir, "*.png"))
    
    for sticker in sticker_files:
        output_path = os.path.join(output_dir, os.path.basename(sticker))
        apply_sticker_style(sticker, output_path)

if __name__ == "__main__":
    main()
