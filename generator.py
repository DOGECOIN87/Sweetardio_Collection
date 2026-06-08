import os
import random
from PIL import Image

TRAITS_DIR = "traits"

# Asset Categories
BACKGROUNDZ = "backgroundz"
SKINZ = "skinz"
CHARACTERZ = "characterz"
EYEZ = "eyez"
MOUTHZ = "mouthz"
WHAT_ARE_THOSEZ = "what_are_thosez"
STICKERZ = "stickerz"

def get_files(category):
    path = os.path.join(TRAITS_DIR, category)
    if not os.path.exists(path):
        return []
    return [f for f in os.listdir(path) if f.endswith(".png")]

def generate_random_combination():
    # 1. Select Character
    char_files = get_files(CHARACTERZ)
    if not char_files:
        raise ValueError("No character assets found in traits/characterz")
    
    # Identify base characters by looking at files
    # Files are now like: Oreo.png, after_skinz_brownie_bite.png, before_skinz_zebra_cake.png
    base_names = set()
    for f in char_files:
        name = f.replace("before_skinz_", "").replace("after_skinz_", "").replace(".png", "")
        base_names.add(name)
    
    char_name = random.choice(list(base_names))
    
    # 2. Select Required Traits
    # Background
    bg_files = get_files(BACKGROUNDZ)
    if not bg_files:
        raise ValueError("No background assets found in traits/backgroundz")
    bg = random.choice(bg_files)
    
    # Skin (Required)
    skin_files = get_files(SKINZ)
    if not skin_files:
        raise ValueError("No skin assets found in traits/skinz")
    
    # Basic weighting for skins
    weights = []
    for f in skin_files:
        if "White" in f or "Black" in f:
            weights.append(10)  # Common
        elif "Alien" in f or "Gold" in f:
            weights.append(1)   # Rare
        else:
            weights.append(5)   # Uncommon
    skin = random.choices(skin_files, weights=weights, k=1)[0]
    
    # Eyez and Mouthz (Required)
    eye_files = get_files(EYEZ)
    mouth_files = get_files(MOUTHZ)
    if not eye_files or not mouth_files:
        raise ValueError("Missing eyes or mouth assets")
    eye = random.choice(eye_files)
    mouth = random.choice(mouth_files)
    
    # Optional Sticker
    sticker_files = get_files(STICKERZ)
    sticker = random.choice(sticker_files) if sticker_files else None
    
    # 3. Layering Logic
    # Order: Background -> Footwear Base -> Character (before) -> Character (base/after) -> Skinz -> Footwear Overlay -> Eyez -> Mouthz -> Sticker
    layers = []
    
    # Background
    layers.append(os.path.join(TRAITS_DIR, BACKGROUNDZ, bg))
    
    # Footwear Base (if any)
    wat_files = get_files(WHAT_ARE_THOSEZ)
    wat_bases = [f.replace("_Base.png", "") for f in wat_files if f.endswith("_Base.png")]
    chosen_wat = None
    if wat_bases:
        chosen_wat = random.choice(wat_bases)
        layers.append(os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f"{chosen_wat}_Base.png"))
    
    # Character - "before_skinz" part if it exists
    before_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"before_skinz_{char_name}.png")
    if os.path.exists(before_path):
        layers.append(before_path)
    
    # Character - main part or "after_skinz" part
    # If it's a simple name like "Oreo.png", use that.
    main_char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"{char_name}.png")
    if not os.path.exists(main_char_path):
        main_char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"after_skinz_{char_name}.png")
    
    if os.path.exists(main_char_path):
        layers.append(main_char_path)
    
    # Skinz - ALWAYS AFTER CHARACTER now
    layers.append(os.path.join(TRAITS_DIR, SKINZ, skin))
    
    # Footwear Overlay
    if chosen_wat:
        overlay_path = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f"{chosen_wat}_Overlay.png")
        if os.path.exists(overlay_path):
            layers.append(overlay_path)
        # Handle Shiba specific overlays
        if chosen_wat == "Shiba":
            for side in ["Left", "Right"]:
                side_overlay = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f"Shiba_Overlay_{side}.png")
                if os.path.exists(side_overlay):
                    layers.append(side_overlay)
    
    # Eyez and Mouthz
    layers.append(os.path.join(TRAITS_DIR, EYEZ, eye))
    layers.append(os.path.join(TRAITS_DIR, MOUTHZ, mouth))
    
    # Sticker
    if sticker:
        layers.append(os.path.join(TRAITS_DIR, STICKERZ, sticker))
    
    return layers, char_name

def create_image(layers, output_name=None):
    if output_name is None:
        import time
        if not os.path.exists("output"):
            os.makedirs("output")
        output_name = f"output/gen_{int(time.time())}_{random.randint(1000, 9999)}.png"
    
    base_img = None
    for layer_path in layers:
        if not os.path.exists(layer_path):
            print(f"Warning: Layer not found: {layer_path}")
            continue
        img = Image.open(layer_path).convert("RGBA")
        if base_img is None:
            base_img = img
        else:
            base_img.alpha_composite(img)
    
    if base_img:
        base_img.save(output_name)
        return output_name
    return None

if __name__ == "__main__":
    if not os.path.exists("output"):
        os.makedirs("output")
    
    print("Starting generation with updated logic (Skinz always after Character)...")
    for i in range(5):
        try:
            layers, char_name = generate_random_combination()
            print(f"Generating combination {i+1} for {char_name}...")
            out_file = create_image(layers, f"output/test_{i+1}_{char_name}.png")
            if out_file:
                print(f"Saved to {out_file}")
        except Exception as e:
            print(f"Error generating combination {i+1}: {e}")
