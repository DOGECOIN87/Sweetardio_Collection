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
ARMZ = "armz"
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

# Characters that should NOT get what_are_thosez (footwear):
# churro, twinkie, poptarts and all ice creams
EXCLUDE_WAT_CHARS = [
    "cyan_sherbert_ice_cream",
    "neopolitan_ice_cream",
    "rainbow_sherbert_ice_cream",
    "vanilla_ice_cream",
    "rocky_road_ice_cream",
    "zaffre_sherbert_ice_cream",
    "mint_chocolate_chip_ice_cream",
    "pink_sherbert_ice_cream",
    "twinkie",
    "churro",
    "poptart",
]

# Characters that keep the raised (non-offset) position even without
# footwear. Kept separate from EXCLUDE_WAT_CHARS so making a character
# footwear-ineligible (e.g. poptarts) does not change where it stands.
NO_OFFSET_CHARS = [
    "cyan_sherbert_ice_cream",
    "neopolitan_ice_cream",
    "rainbow_sherbert_ice_cream",
    "vanilla_ice_cream",
    "rocky_road_ice_cream",
    "zaffre_sherbert_ice_cream",
    "mint_chocolate_chip_ice_cream",
    "pink_sherbert_ice_cream",
    "twinkie",
    "churro",
]

CANVAS_SIZE = 1393
VERTICAL_OFFSET = 150  # Pixels to lower the character if no footwear

def get_files(category):
    path = os.path.join(TRAITS_DIR, category)
    if not os.path.exists(path):
        return []
    return [f for f in os.listdir(path) if f.endswith(".png")]

def generate_random_combination():
    # 1. Select Character (MANDATORY)
    char_files = get_files(CHARACTERZ)
    if not char_files:
        raise ValueError("No character assets found in traits/characterz")
    
    base_names = set()
    for f in char_files:
        # strip the longest prefix first: "layer-after_skinz_" must go
        # before "after_skinz_", otherwise names like
        # "layer-after_skinz_churro" become "layer-churro" and never
        # match their own layer files again
        name = f.replace("layer-after_skinz_", "").replace("before_skinz_", "").replace("after_skinz_", "").replace(".png", "")
        import re
        name = re.sub(r'\s*\(\d+\)', '', name).strip()
        base_names.add(name)
    
    if not base_names:
        raise ValueError("No valid character names found")
    
    char_name = random.choice(list(base_names))
    
    # Check if this character should be excluded from what_are_thosez
    # Using lower() and checking for presence in char_name
    should_exclude_wat = False
    for ex in EXCLUDE_WAT_CHARS:
        if ex.lower() in char_name.lower():
            should_exclude_wat = True
            break
    
    # Check if this character gets gorbhouse overlay
    gets_gorbhouse = any(gc.lower() in char_name.lower() for gc in GORBHOUSE_CHARS)
    
    # 2. Select Required Traits
    bg_files = get_files(BACKGROUNDZ)
    if not bg_files:
        raise ValueError("No background assets found in traits/backgroundz")
    bg = random.choice(bg_files)
    
    skin_files = get_files(SKINZ)
    if not skin_files:
        raise ValueError("No skin assets found in traits/skinz")
    
    weights = []
    for f in skin_files:
        if "White" in f or "Black" in f:
            weights.append(10)
        elif "Alien" in f or "Gold" in f:
            weights.append(1)
        else:
            weights.append(5)
    skin = random.choices(skin_files, weights=weights, k=1)[0]
    
    eye_files = get_files(EYEZ)
    mouth_files = get_files(MOUTHZ)
    if not eye_files:
        raise ValueError("No eye assets found in traits/eyez")
    if not mouth_files:
        raise ValueError("No mouth assets found in traits/mouthz")
    
    eye = random.choice(eye_files)
    mouth = random.choice(mouth_files)
    
    arm_files = get_files(ARMZ)
    arm = random.choice(arm_files) if arm_files else None
    
    sticker_files = get_files(STICKERZ)
    sticker = random.choice(sticker_files) if sticker_files else None
    
    # Optional "What are thosez"
    chosen_wat = None
    wat_overlays = []
    if not should_exclude_wat:
        wat_files = get_files(WHAT_ARE_THOSEZ)
        wat_bases = [f.replace("_base.png", "").replace("_Base.png", "") for f in wat_files if f.lower().endswith("_base.png")]
        wat_bases = [b for b in wat_bases if "gorbhouse" not in b.lower()]
        
        # 70% chance to have footwear if not excluded
        if wat_bases and random.random() < 0.7:
            chosen_wat = random.choice(wat_bases)
            for f in wat_files:
                if f.lower().startswith(chosen_wat.lower()) and "overlay" in f.lower():
                    wat_overlays.append(os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f))
    
    # Layering Logic
    layers = []
    
    # 1. Background
    layers.append({"path": os.path.join(TRAITS_DIR, BACKGROUNDZ, bg), "offset": False})
    
    # 2. What Are Thosez BASE
    if chosen_wat:
        wat_files = get_files(WHAT_ARE_THOSEZ)
        for f in wat_files:
            if f.lower() == f"{chosen_wat.lower()}_base.png":
                layers.append({"path": os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f), "offset": False})
                break
    
    # Determine if we should apply offset
    # Rule: If no footwear AND (not ice cream, not twinkie, not churro)
    no_offset_char = any(ex.lower() in char_name.lower()
                         for ex in NO_OFFSET_CHARS)
    apply_offset = not chosen_wat and not no_offset_char
    
    # 3. Character
    char_found = False
    for f in char_files:
        if f.startswith("before_skinz_") and char_name.lower() in f.lower():
            layers.append({"path": os.path.join(TRAITS_DIR, CHARACTERZ, f), "offset": apply_offset})
            char_found = True
            break
            
    main_found = False
    patterns = [f"{char_name}.png", f"after_skinz_{char_name}.png", f"layer-after_skinz_{char_name}.png"]
    for p in patterns:
        for f in char_files:
            if f.lower() == p.lower() or (char_name.lower() in f.lower() and "after_skinz" in f.lower()):
                layers.append({"path": os.path.join(TRAITS_DIR, CHARACTERZ, f), "offset": apply_offset})
                main_found = True
                char_found = True
                break
        if main_found: break
        
    if not char_found:
        for f in char_files:
            if char_name.lower() in f.lower():
                layers.append({"path": os.path.join(TRAITS_DIR, CHARACTERZ, f), "offset": apply_offset})
                char_found = True
                break

    # 4. What Are Thosez OVERLAY
    for overlay_path in wat_overlays:
        layers.append({"path": overlay_path, "offset": False})
    
    # 5. Skinz
    layers.append({"path": os.path.join(TRAITS_DIR, SKINZ, skin), "offset": apply_offset})
    
    # 6. Eyez
    layers.append({"path": os.path.join(TRAITS_DIR, EYEZ, eye), "offset": apply_offset})
    
    # 7. Mouthz
    layers.append({"path": os.path.join(TRAITS_DIR, MOUTHZ, mouth), "offset": apply_offset})
    
    # 8. Armz
    if arm:
        layers.append({"path": os.path.join(TRAITS_DIR, ARMZ, arm), "offset": apply_offset})
        
    # 9. Gorbhouse special overlay
    if gets_gorbhouse:
        gorbhouse_path = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, "Gorbhouse_overlay.png")
        if not os.path.exists(gorbhouse_path):
            gorbhouse_path = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, "Gorbhouse_Overlay.png")
        if os.path.exists(gorbhouse_path):
            layers.append({"path": gorbhouse_path, "offset": apply_offset})
    
    # 10. Sticker - DON'T MOVE DOWN
    if sticker:
        layers.append({"path": os.path.join(TRAITS_DIR, STICKERZ, sticker), "offset": False})
    
    return layers, char_name

def create_image(layers, output_name=None):
    if output_name is None:
        import time
        if not os.path.exists("output"):
            os.makedirs("output")
        output_name = f"output/gen_{int(time.time())}_{random.randint(1000, 9999)}.png"
    
    base_img = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    
    for layer_info in layers:
        layer_path = layer_info["path"]
        should_offset = layer_info["offset"]
        
        if not os.path.exists(layer_path):
            print(f"Warning: Layer not found: {layer_path}")
            continue
            
        img = Image.open(layer_path).convert("RGBA")
        if img.size != (CANVAS_SIZE, CANVAS_SIZE):
            img = img.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.LANCZOS)
        
        if should_offset:
            # Create a new image for the offset layer
            offset_img = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
            # Paste the original image with vertical offset
            offset_img.paste(img, (0, VERTICAL_OFFSET))
            img = offset_img
            
        base_img.alpha_composite(img)
    
    base_img.save(output_name)
    return output_name

if __name__ == "__main__":
    if not os.path.exists("output"):
        os.makedirs("output")
    
    print("Starting generation with centering logic...")
    for i in range(10):
        try:
            layers, char_name = generate_random_combination()
            has_offset = any(l["offset"] for l in layers)
            status = "CENTERED" if has_offset else "NORMAL"
            print(f"Generating {i+1} for {char_name} ({status})...")
            create_image(layers, f"output/test_{i+1}_{char_name}_{status}.png")
        except Exception as e:
            print(f"Error: {e}")
