import os
import random
from PIL import Image

TRAITS_DIR = "traits"

# Asset Categories
BACKGROUNDZ = "backgroundz"
BACKGROUNDS_POP = "backgrounds_pop"
SKINZ = "skinz"
CHARACTERZ = "characterz"
EYEZ = "eyez"
MOUTHZ = "mouthz"
WHAT_ARE_THOSEZ = "what_are_thosez"
STICKERZ = "stickerz"

# Character groups
ICE_CREAM_CHARS = [
    "cyan_sherbert_ice_cream", "neopolitan_ice_cream", "rainbow_sherbert_ice_cream",
    "vanilla_ice_cream", "rocky_road_ice_cream", "zaffre_sherbert_ice_cream",
    "mint_chocolate_chip_ice_cream", "pink_sherbert_ice_cream"
]

GUMMY_BEAR_CHARS = ["gummy_bear"]

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
    
    # 2. Select Required Traits
    # Background
    bg_folders = [BACKGROUNDZ, BACKGROUNDS_POP]
    chosen_folder = random.choice(bg_folders)
    bg_files = get_files(chosen_folder)
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
    layers.append(os.path.join(TRAITS_DIR, chosen_folder, bg))
    
    # Check for Background Overlay
    overlay_path = None
    possible_overlay_paths = [
        os.path.join(TRAITS_DIR, chosen_folder, "Whitehouse_Lawn_Overlay.png"),
        os.path.join(TRAITS_DIR, "background", "Whitehouse_Lawn_Overlay.png")
    ]
    for p in possible_overlay_paths:
        if os.path.exists(p):
            overlay_path = p
            break
            
    has_bg_overlay = "Whitehouse_Lawn" in bg and overlay_path

    is_ice_cream = any(ic in char_name for ic in ICE_CREAM_CHARS)
    is_gummy_bear = char_name == "gummy_bear"
    
    if is_ice_cream:
        # Ice Cream: Character (before) -> Skinz -> Character (after)
        layers.append(os.path.join(TRAITS_DIR, CHARACTERZ, f"before_skinz_{char_name}.png"))
        layers.append(os.path.join(TRAITS_DIR, SKINZ, skin))
        after_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"after_skinz_{char_name}.png")
        if os.path.exists(after_path):
            layers.append(after_path)
    elif is_gummy_bear:
        # Gummy Bear: Character (before) -> Skinz
        layers.append(os.path.join(TRAITS_DIR, CHARACTERZ, f"before_skinz_{char_name}.png"))
        layers.append(os.path.join(TRAITS_DIR, SKINZ, skin))
    elif "churro" in char_name:
        # Churro: Skinz -> Character
        layers.append(os.path.join(TRAITS_DIR, SKINZ, skin))
        char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"before_skinz_{char_name}.png")
        if not os.path.exists(char_path):
            char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"after_skinz_{char_name}.png")
        layers.append(char_path)
    else:
        # Others & Footwear (what_are_thosez)
        wat_files = get_files(WHAT_ARE_THOSEZ)
        wat_bases = [f.replace("_Base.png", "") for f in wat_files if f.endswith("_Base.png")]
        
        if wat_bases:
            what_are_those = random.choice(wat_bases)
            # Footwear Base
            layers.append(os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f"{what_are_those}_Base.png"))
            
            # Character Skin (Always required now)
            layers.append(os.path.join(TRAITS_DIR, SKINZ, skin))
            
            # Character
            char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"before_skinz_{char_name}.png")
            if not os.path.exists(char_path):
                char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"after_skinz_{char_name}.png")
            layers.append(char_path)
            
            # Footwear Overlay
            wat_overlay = f"{what_are_those}_Overlay.png"
            wat_overlay_path = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, wat_overlay)
            if os.path.exists(wat_overlay_path):
                layers.append(wat_overlay_path)
            
            # Handle Shiba specific overlays
            if what_are_those == "Shiba":
                for side in ["Left", "Right"]:
                    side_overlay = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f"Shiba_Overlay_{side}.png")
                    if os.path.exists(side_overlay):
                        layers.append(side_overlay)
        else:
            # Fallback if no footwear found
            layers.append(os.path.join(TRAITS_DIR, SKINZ, skin))
            char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"before_skinz_{char_name}.png")
            if not os.path.exists(char_path):
                char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"after_skinz_{char_name}.png")
            layers.append(char_path)

    # Eyez and Mouthz
    layers.append(os.path.join(TRAITS_DIR, EYEZ, eye))
    layers.append(os.path.join(TRAITS_DIR, MOUTHZ, mouth))
    
    # Background Overlay (if applicable) - before sticker
    if has_bg_overlay:
        layers.append(overlay_path)
        
    # Sticker
    if sticker:
        layers.append(os.path.join(TRAITS_DIR, STICKERZ, sticker))
    
    return layers, char_name

def create_image(layers, output_name=None):
    if output_name is None:
        import time
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
        print(f"Generated: {output_name}")

if __name__ == "__main__":
    if not os.path.exists("output"):
        os.makedirs("output")
    
    print("Starting generation with updated logic...")
    for i in range(5):
        try:
            layers, char_name = generate_random_combination()
            print(f"Generating combination {i+1} for {char_name}...")
            create_image(layers, f"output/test_{i+1}_{char_name}.png")
        except Exception as e:
            print(f"Error generating combination {i+1}: {e}")
