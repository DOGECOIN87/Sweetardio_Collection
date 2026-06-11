import json
import os
import random
from PIL import Image

TRAITS_DIR = "traits"

# Background overlays are NOT standalone plates: they ride on top of the
# whole stack (placed last) whenever their parent plate is the background.
# Whitehouse_Lawn_Overlay is the foreground figure for the Whitehouse_Lawn
# scene (NOT Candy_Land / Sweetardio_11314, which was a mis-pairing).
BG_OVERLAY_PAIRS = {
    "Whitehouse_Lawn.png": "Whitehouse_Lawn_Overlay.png",
}

# Optional eye <-> background compatibility map built by
# asset_assessment/build_eyez_compat.py. Missing file = no restrictions.
EYEZ_COMPAT_PATH = os.path.join(TRAITS_DIR, "eyez_compat.json")

def load_eyez_blocklist():
    try:
        with open(EYEZ_COMPAT_PATH) as f:
            return json.load(f).get("blocked", {})
    except (OSError, ValueError):
        return {}

# Asset Categories
# traits/backgroundz holds the GRADED plates (sources preserved in
# traits/backgroundz_originals; regrade with background_pop_studies/grade.py)
BACKGROUNDZ = "backgroundz"
BACKGROUNDZ_FALLBACK = "backgroundz_originals"
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

# ---- face composition rule (from measured asset geometry) ----
# The widest eyes (284-287px) are wider than the skin balls (268-303px).
# Eyes/mouth keep their ORIGINAL size and placement; instead the skin ball
# is enlarged about its own center just enough that the chosen eyes fit
# within BALL_FIT_MARGIN of the ball's width. The ball always sits on top
# of the body ("B everywhere").
BALL_FIT_MARGIN = 0.92

_bbox_cache = {}

def _opaque_bbox(path, thresh=128):
    """Bounding box of pixels with alpha >= thresh, in canvas coordinates."""
    if path not in _bbox_cache:
        im = Image.open(path).convert("RGBA")
        if im.size != (CANVAS_SIZE, CANVAS_SIZE):
            im = im.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.LANCZOS)
        mask = im.getchannel("A").point(lambda a: 255 if a >= thresh else 0)
        _bbox_cache[path] = mask.getbbox()
    return _bbox_cache[path]

def ball_fit(skin_path, eye_path):
    """Enlargement factor + pivot so the skin ball contains the eyes."""
    sx0, sy0, sx1, sy1 = _opaque_bbox(skin_path)
    ex0, _, ex1, _ = _opaque_bbox(eye_path)
    ball_w = max(sx1 - sx0, 1)
    eye_w = max(ex1 - ex0, 1)
    factor = max(1.0, eye_w / (BALL_FIT_MARGIN * ball_w))
    return factor, ((sx0 + sx1) / 2.0, (sy0 + sy1) / 2.0)

def scale_about(img, factor, center):
    """Scale an RGBA canvas-sized layer about a fixed point."""
    if abs(factor - 1.0) < 0.001:
        return img
    w, h = img.size
    scaled = img.resize((max(1, round(w * factor)), max(1, round(h * factor))),
                        Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cx, cy = center
    out.paste(scaled, (round(cx * (1 - factor)), round(cy * (1 - factor))),
              scaled)
    return out

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
    bg_dir = BACKGROUNDZ
    bg_files = get_files(bg_dir)
    if not bg_files:
        print(f"Warning: traits/{BACKGROUNDZ} is empty; falling back to "
              f"the ungraded traits/{BACKGROUNDZ_FALLBACK}")
        bg_dir = BACKGROUNDZ_FALLBACK
        bg_files = get_files(bg_dir)
    # overlays pair with their parent plate; they are never a background
    bg_files = [f for f in bg_files if f not in BG_OVERLAY_PAIRS.values()]
    if not bg_files:
        raise ValueError("No background assets found")
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
    
    # eye <-> background compatibility (optional, measured blocklist)
    eyez_blocked = load_eyez_blocklist().get(bg, [])
    allowed_eyes = [f for f in eye_files if f not in eyez_blocked]
    eye = random.choice(allowed_eyes if allowed_eyes else eye_files)
    mouth = random.choice(mouth_files)
    
    arm_files = get_files(ARMZ)
    arm = random.choice(arm_files) if arm_files else None
    
    sticker_files = get_files(STICKERZ)
    sticker = random.choice(sticker_files) if sticker_files else None
    
    # Optional "What are thosez"
    # base files look like "layer-Bunny_Slippers_Base (1).png": match the
    # "_base" marker with an optional " (n)" suffix, case-insensitively
    import re as _re
    def wat_base_name(f):
        m = _re.match(r"(.+?)_base(?:\s*\(\d+\))?\.png$", f, _re.IGNORECASE)
        return m.group(1) if m else None

    chosen_wat = None
    wat_overlays = []
    if not should_exclude_wat:
        wat_files = get_files(WHAT_ARE_THOSEZ)
        wat_bases = [wat_base_name(f) for f in wat_files]
        wat_bases = [b for b in wat_bases if b and "gorbhouse" not in b.lower()]
        
        # 70% chance to have footwear if not excluded
        if wat_bases and random.random() < 0.7:
            chosen_wat = random.choice(wat_bases)
            for f in wat_files:
                if f.lower().startswith(chosen_wat.lower()) and "overlay" in f.lower():
                    wat_overlays.append(os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f))
    
    # Layering Logic
    layers = []
    
    # 1. Background
    layers.append({"path": os.path.join(TRAITS_DIR, bg_dir, bg), "offset": False})
    
    # 2. What Are Thosez BASE (placed before characterz)
    if chosen_wat:
        wat_files = get_files(WHAT_ARE_THOSEZ)
        for f in wat_files:
            base = wat_base_name(f)
            if base and base.lower() == chosen_wat.lower():
                layers.append({"path": os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f), "offset": False})
                break
    
    # Determine if we should apply offset
    # Rule: If no footwear AND (not ice cream, not twinkie, not churro)
    no_offset_char = any(ex.lower() in char_name.lower()
                         for ex in NO_OFFSET_CHARS)
    apply_offset = not chosen_wat and not no_offset_char
    
    # 3. Character (collected first: skin z-order depends on the body type)
    char_layers = []
    char_found = False
    for f in char_files:
        if f.startswith("before_skinz_") and char_name.lower() in f.lower():
            char_layers.append({"path": os.path.join(TRAITS_DIR, CHARACTERZ, f), "offset": apply_offset})
            char_found = True
            break
            
    main_found = False
    patterns = [f"{char_name}.png", f"after_skinz_{char_name}.png", f"layer-after_skinz_{char_name}.png"]
    for p in patterns:
        for f in char_files:
            if f.lower() == p.lower() or (char_name.lower() in f.lower() and "after_skinz" in f.lower()):
                char_layers.append({"path": os.path.join(TRAITS_DIR, CHARACTERZ, f), "offset": apply_offset})
                main_found = True
                char_found = True
                break
        if main_found: break
        
    if not char_found:
        for f in char_files:
            if char_name.lower() in f.lower():
                char_layers.append({"path": os.path.join(TRAITS_DIR, CHARACTERZ, f), "offset": apply_offset})
                char_found = True
                break

    layers.extend(char_layers)

    # 4. What Are Thosez OVERLAY
    for overlay_path in wat_overlays:
        layers.append({"path": overlay_path, "offset": False})
    
    # 5. Skinz: ball on top, enlarged so the chosen eyes fit inside it
    skin_path = os.path.join(TRAITS_DIR, SKINZ, skin)
    bfit, bcenter = ball_fit(skin_path, os.path.join(TRAITS_DIR, EYEZ, eye))
    layers.append({"path": skin_path, "offset": apply_offset,
                   "fscale": bfit, "fcenter": bcenter})
    
    # 6. Eyez (original size and placement)
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

    # 11. Paired background overlay - always placed LAST, on top of everything
    if bg in BG_OVERLAY_PAIRS:
        ov_path = os.path.join(TRAITS_DIR, bg_dir, BG_OVERLAY_PAIRS[bg])
        if os.path.exists(ov_path):
            layers.append({"path": ov_path, "offset": False})

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
        
        if abs(layer_info.get("fscale", 1.0) - 1.0) > 0.001:
            img = scale_about(img, layer_info["fscale"], layer_info["fcenter"])
        
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
