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

# Characters that get Gorbhouse overlay
GORBHOUSE_CHARS = [
    "Twinkie",
    "waffle",
    "glazed_doughnut",
    "chocolate_doughnut",
    "sugar_doughnut",
    "og_poptart",
    "chocolate_frosted_poptart",
    "cyan_frosted_poptart",
    "zebra_cake",
]

# Ice cream characters that should NOT get what_are_thosez
ICE_CREAM_CHARS = [
    "cyan_sherbert_ice_cream",
    "neopolitan_ice_cream",
    "rainbow_sherbert_ice_cream",
    "vanilla_ice_cream",
    "rocky_road_ice_cream",
    "zaffre_sherbert_ice_cream",
    "mint_chocolate_chip_ice_cream",
    "pink_sherbert_ice_cream",
]

CANVAS_SIZE = 1393

def get_files(category):
    path = os.path.join(TRAITS_DIR, category)
    if not os.path.exists(path):
        return []
    return [f for f in os.listdir(path) if f.endswith(".png")]

def generate_random_combination():
    # 1. Select Character
    char_files = get_files(CHARACTERZ)
    base_names = set()
    for f in char_files:
        name = f.replace("before_skinz_", "").replace("after_skinz_", "").replace(".png", "")
        base_names.add(name)
    
    char_name = random.choice(list(base_names))
    
    # Check if this is an ice cream character
    is_ice_cream = any(ic in char_name for ic in ICE_CREAM_CHARS)
    # Check if this character gets gorbhouse overlay
    gets_gorbhouse = any(gc in char_name for gc in GORBHOUSE_CHARS)
    
    # 2. Select Required Traits
    # Background
    bg_files = get_files(BACKGROUNDZ)
    bg = random.choice(bg_files)
    
    # Skin (Required)
    skin_files = get_files(SKINZ)
    if not skin_files:
        raise ValueError("No skin assets found in traits/skinz")
    
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
    eye = random.choice(eye_files)
    mouth = random.choice(mouth_files)
    
    # Optional Sticker
    sticker_files = get_files(STICKERZ)
    sticker = random.choice(sticker_files) if sticker_files else None
    
    # Layering Logic
    layers = []
    
    # Background is always first
    layers.append(os.path.join(TRAITS_DIR, BACKGROUNDZ, bg))
    
    # Footwear base (optional) - ONLY if not ice cream
    wat_files = get_files(WHAT_ARE_THOSEZ)
    wat_bases = [f.replace("_Base.png", "") for f in wat_files if f.endswith("_Base.png")]
    
    chosen_wat = None
    if not is_ice_cream and wat_bases:
        chosen_wat = random.choice(wat_bases)
        layers.append(os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f"{chosen_wat}_Base.png"))
    
    # Character - before_skinz part if it exists
    before_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"before_skinz_{char_name}.png")
    if os.path.exists(before_path):
        layers.append(before_path)
    
    # Character - main part or after_skinz part
    main_char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"{char_name}.png")
    if not os.path.exists(main_char_path):
        main_char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"after_skinz_{char_name}.png")
    
    if os.path.exists(main_char_path):
        layers.append(main_char_path)
    
    # Skinz - ALWAYS AFTER CHARACTER
    layers.append(os.path.join(TRAITS_DIR, SKINZ, skin))
    
    # Eyez and Mouthz
    layers.append(os.path.join(TRAITS_DIR, EYEZ, eye))
    layers.append(os.path.join(TRAITS_DIR, MOUTHZ, mouth))
    
    # Footwear overlay - PLACED AFTER CHARACTER AND EYEZ/MOUTHZ
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
    
    # Gorbhouse overlay for specific characters (added before sticker)
    # Note: Using Gorbhouse_Base.png since Overlay doesn't exist for it
    if gets_gorbhouse:
        gorbhouse_path = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, "Gorbhouse_Base.png")
        if os.path.exists(gorbhouse_path):
            layers.append(gorbhouse_path)
    
    # Sticker (added after gorbhouse overlay)
    if sticker:
        layers.append(os.path.join(TRAITS_DIR, STICKERZ, sticker))
    
    return layers, char_name

def create_image(layers, output_name=None):
    if output_name is None:
        import time
        if not os.path.exists("output"):
            os.makedirs("output")
        output_name = f"output/gen_{int(time.time())}_{random.randint(1000, 9999)}.png"
    
    base_img = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    
    for layer_path in layers:
        if not os.path.exists(layer_path):
            print(f"Warning: Layer not found: {layer_path}")
            continue
        img = Image.open(layer_path).convert("RGBA")
        # Resize to canvas size if needed
        if img.size != (CANVAS_SIZE, CANVAS_SIZE):
            img = img.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.LANCZOS)
        base_img.alpha_composite(img)
    
    base_img.save(output_name)
    print(f"Generated: {output_name}")
    return output_name

if __name__ == "__main__":
    if not os.path.exists("output"):
        os.makedirs("output")
    
    print("Starting generation with updated logic...")
    print("Rules:")
    print("- Skinz always after character")
    print("- Ice cream characters: NO what_are_thosez")
    print("- Gorbhouse overlay for: Twinkie, Waffle, Doughnuts, Poptarts, Zebra Cake")
    print("- Canvas size: 1393x1393")
    print()
    
    for i in range(20):
        try:
            layers, char_name = generate_random_combination()
            print(f"Generating combination {i+1} for {char_name}...")
            create_image(layers, f"output/test_{i+1}_{char_name}.png")
        except Exception as e:
            print(f"Error generating combination {i+1}: {e}")
