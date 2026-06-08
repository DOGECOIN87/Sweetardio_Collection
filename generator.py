import os
import random
from PIL import Image

TRAITS_DIR = "traits"

# Asset Categories
BACKGROUNDS = "background"
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

SPECIAL_BASE_ONLY_CHARS = [
    "sugar_cube", "gummy_worm", "zebra_cake", "waffle", "ding_dong", "brownie_bite", "glazed_doughnut"
]

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
    
    # 2. Select other traits
    bg = random.choice(get_files(BACKGROUNDS))
    skin_files = get_files(SKINZ)
    weights = []
    for f in skin_files:
        if "White" in f or "Black" in f:
            weights.append(10)  # Common
        elif "Alien" in f or "Gold" in f:
            weights.append(1)   # Rare
        else:
            weights.append(5)   # Uncommon
    skin = random.choices(skin_files, weights=weights, k=1)[0]
    eye = random.choice(get_files(EYEZ))
    mouth = random.choice(get_files(MOUTHZ))
    sticker = random.choice(get_files(STICKERZ)) if get_files(STICKERZ) else None
    
    # Layering Logic
    layers = []
    
    # Background is always first
    layers.append(os.path.join(TRAITS_DIR, BACKGROUNDS, bg))
    
    # Check for Background Overlay
    overlay_path = os.path.join(TRAITS_DIR, BACKGROUNDS, "Whitehouse_Lawn_Overlay.png")
    if bg == "Whitehouse_Lawn.png" and os.path.exists(overlay_path):
        # We'll place this later, after characters but before stickers
        has_bg_overlay = True
    else:
        has_bg_overlay = False

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
    else:
        # Others & Special Bases
        wat_files = get_files(WHAT_ARE_THOSEZ)
        wat_bases = [f.replace("_Base.png", "") for f in wat_files if f.endswith("_Base.png")]
        what_are_those = random.choice(wat_bases)
        
        # Base
        layers.append(os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f"{what_are_those}_Base.png"))
        
        # Character
        char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"before_skinz_{char_name}.png")
        if not os.path.exists(char_path):
            char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"after_skinz_{char_name}.png")
        layers.append(char_path)
        
        # Overlay
        # Some overlays might have 'layer-' prefix due to previous duplicate logic
        wat_overlay = f"{what_are_those}_Overlay.png"
        wat_overlay_path = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, wat_overlay)
        if not os.path.exists(wat_overlay_path):
            wat_overlay_path = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f"layer-{wat_overlay}")
            
        if os.path.exists(wat_overlay_path):
            layers.append(wat_overlay_path)

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
    
    for i in range(5):
        layers, char_name = generate_random_combination()
        print(f"Generating combination {i+1} for {char_name}...")
        create_image(layers, f"output/test_{i+1}_{char_name}.png")
