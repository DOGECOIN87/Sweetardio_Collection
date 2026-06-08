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

# Character groups
ICE_CREAM_CHARS = [
    "cyan_sherbert_ice_cream", "neopolitan_ice_cream", "rainbow_sherbert_ice_cream",
    "vanilla_ice_cream", "rocky_road_ice_cream", "zaffre_sherbert_ice_cream",
    "mint_chocolate_chip_ice_cream", "pink_sherbert_ice_cream"
]

GUMMY_BEAR_CHARS = ["gummy_bear"]

SPECIAL_BASE_ONLY_CHARS = [
    "sugar_cube", "gummy_worm", "zebra_cake", "waffle", "ding_dong", "brownie_bite"
]

def get_files(category):
    path = os.path.join(TRAITS_DIR, category)
    if not os.path.exists(path):
        return []
    return [f for f in os.listdir(path) if f.endswith(".png")]

def generate_random_combination():
    # 1. Select Character
    char_files = get_files(CHARACTERZ)
    # Filter to get unique base names
    base_names = set()
    for f in char_files:
        name = f.replace("before_skinz_", "").replace("after_skinz_", "").replace(".png", "")
        base_names.add(name)
    
    char_name = random.choice(list(base_names))
    
    # 2. Select other traits
    bg = random.choice(get_files(BACKGROUNDS))
    skin = random.choice(get_files(SKINZ))
    eye = random.choice(get_files(EYEZ))
    mouth = random.choice(get_files(MOUTHZ))
    
    # 3. Select "What are those" if applicable
    what_are_those = None
    if char_name in SPECIAL_BASE_ONLY_CHARS:
        wat_files = get_files(WHAT_ARE_THOSEZ)
        # Group by full base name (e.g., Bunny_Slippers, Shiba)
        # Bases end with _Base.png
        wat_bases = [f.replace("_Base.png", "") for f in wat_files if f.endswith("_Base.png")]
        what_are_those = random.choice(wat_bases)

    # Layering Logic
    layers = []
    
    # Background is always first
    layers.append(os.path.join(TRAITS_DIR, BACKGROUNDS, bg))
    
    is_ice_cream = any(ic in char_name for ic in ICE_CREAM_CHARS)
    is_gummy_bear = char_name == "gummy_bear"
    
    if is_ice_cream:
        # Ice Cream: Character (before) -> Skinz -> Character (after) -> Eyez -> Mouthz
        layers.append(os.path.join(TRAITS_DIR, CHARACTERZ, f"before_skinz_{char_name}.png"))
        layers.append(os.path.join(TRAITS_DIR, SKINZ, skin))
        # Note: Usually there's an after_skinz for ice cream too if it's following the pattern
        after_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"after_skinz_{char_name}.png")
        if os.path.exists(after_path):
            layers.append(after_path)
    elif is_gummy_bear:
        # Gummy Bear: Character (before) -> Skinz -> Eyez -> Mouthz
        layers.append(os.path.join(TRAITS_DIR, CHARACTERZ, f"before_skinz_{char_name}.png"))
        layers.append(os.path.join(TRAITS_DIR, SKINZ, skin))
    else:
        # Others
        if char_name in SPECIAL_BASE_ONLY_CHARS:
            # Special Base: What Are Those (Base) -> Character -> What Are Those (Overlay) -> Eyez -> Mouthz
            layers.append(os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f"{what_are_those}_Base.png"))
            char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"before_skinz_{char_name}.png")
            if not os.path.exists(char_path):
                char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"after_skinz_{char_name}.png")
            layers.append(char_path)
            layers.append(os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f"{what_are_those}_Overlay.png"))
        else:
            # General: What Are Those (Base) -> Character -> What Are Those (Overlay) -> Eyez -> Mouthz
            # (Wait, user said "all other characters (if not ice cream, gummy bear) get bases placed before characterz and gets the overlay placed of the same asset after characterz.")
            # This implies "What are those" applies to everyone else too?
            wat_files = get_files(WHAT_ARE_THOSEZ)
            wat_bases = [f.replace("_Base.png", "") for f in wat_files if f.endswith("_Base.png")]
            what_are_those = random.choice(wat_bases)
            
            layers.append(os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f"{what_are_those}_Base.png"))
            char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"before_skinz_{char_name}.png")
            if not os.path.exists(char_path):
                char_path = os.path.join(TRAITS_DIR, CHARACTERZ, f"after_skinz_{char_name}.png")
            layers.append(char_path)
            layers.append(os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f"{what_are_those}_Overlay.png"))

    # Eyez and Mouthz always last
    layers.append(os.path.join(TRAITS_DIR, EYEZ, eye))
    layers.append(os.path.join(TRAITS_DIR, MOUTHZ, mouth))
    
    return layers, char_name

def create_image(layers, output_name):
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
