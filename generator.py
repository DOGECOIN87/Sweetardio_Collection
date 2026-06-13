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

# Optional character <-> background compatibility map built by
# asset_assessment/build_char_compat.py: blocks (character, plate) pairs the
# measured figure-ground rule flags as camouflage. Missing file = no limits.
CHAR_COMPAT_PATH = os.path.join(TRAITS_DIR, "char_compat.json")

def load_char_blocklist():
    try:
        with open(CHAR_COMPAT_PATH) as f:
            return json.load(f).get("blocked", {})
    except (OSError, ValueError):
        return {}

# Data-driven skin rarity weights (traits/skin_weights.json): higher = more
# common, matched by case-insensitive substring of the skin filename. Gold
# Foil is the very-rare legendary. Missing file falls back to FALLBACK_*.
SKIN_WEIGHTS_PATH = os.path.join(TRAITS_DIR, "skin_weights.json")
_FALLBACK_SKIN_WEIGHTS = {"White": 70, "Black": 70, "Cyan": 40, "Alien": 8,
                          "Gold": 1}
_FALLBACK_SKIN_DEFAULT = 40

def load_skin_weights():
    try:
        with open(SKIN_WEIGHTS_PATH) as f:
            d = json.load(f)
            return d.get("weights", {}), d.get("default", _FALLBACK_SKIN_DEFAULT)
    except (OSError, ValueError):
        return dict(_FALLBACK_SKIN_WEIGHTS), _FALLBACK_SKIN_DEFAULT

def skin_weight(skin_file, weights, default):
    """First tag whose (case-insensitive) text is in the filename wins."""
    return next((w for tag, w in weights.items()
                 if tag.lower() in skin_file.lower()), default)

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

# Characters that get Gorbhouse overlay. NOTE: the Gorbhouse trash-can
# slippers are a what_are_thosez (footwear) trait, so EXCLUDE_WAT_CHARS
# overrides this list — see gets_gorbhouse_overlay().
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
    "gummy_bear",
    "twinkie",
    "churro",
    "poptart",
]

# Character-specific armz: each file here may ONLY appear on characters
# whose name contains one of the listed substrings (individuals or groups,
# e.g. "ice_cream" covers every *_ice_cream character; "gummy_bear" covers
# all bear color variants). Armz files NOT in this map are generic and can
# pair with any character.
ARMZ_CHAR_LOCK = {
    "Armz_Gummy_Bear_Knives.png": ["gummy_bear"],
    "Armz_Gummy_worms_katana.png": ["gummy_worm"],
    "Armz_Katana_for_ice_cream_character.png": ["ice_cream"],
    "Armz_Marshmallow_knives.png": ["marshmallow"],
    "Armz_Oatmeal_Pie_Katana.png": ["oatmeal_cream_pie"],
    "Armz_Twinkie_Katana.png": ["twinkie"],
    "Armz_choc_cookie_katana.png": ["chocolate_chip_cookie"],
}

def armz_allowed(arm_file, char_name):
    """Generic armz pair with anyone; locked armz only with their character."""
    locks = ARMZ_CHAR_LOCK.get(arm_file)
    return locks is None or any(k in char_name.lower() for k in locks)

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
    # bears are drawn pre-placed (bottoms ~1123-1143, the churro/twinkie
    # zone); the +150 drop left them standing ~180px below everyone else
    "gummy_bear",
    # smores is a large square character pre-positioned at ~963; the +150
    # drop makes it look too low / off-centre when footwear-less
    "smores",
]

# Extra y-offset (px, +down) added to character-anchored layers when the
# background has a visible real-world floor that sits lower than the
# standard 1107 ground band. Only applied when apply_offset=True (i.e.
# footwear-less), so WAT footwear alignment is never disturbed.
# Tune per-background after visual review.
BG_CHAR_EXTRA_Y = {
    "Psychedelics.png": 80,   # Oval Office: visible floor ~1190+
}

CANVAS_SIZE = 1393
VERTICAL_OFFSET = 150  # Pixels to lower the character if no footwear

# Per-character vertical trim in px (+down, -up), applied on top of the
# offset rule to every character-anchored layer (body, skin, eyes, mouth,
# arms) — all layers share the same dy, so the face hole <-> skin ball
# alignment is preserved exactly. Values are measured by
# asset_assessment/audit_placement.py (main-body bottoms, sparkle-proof):
# standing characters align to bottom 957 (-> 1107 with the footwear-less
# drop, inside the approved 1084-1109 ground band), NO_OFFSET characters
# to the churro line (1111), ice-cream cone tips to 1290.
# poptart/twinkie keep their owner-tuned overshoot values (2026-06).
CHAR_Y_ADJUST = {
    "poptart": -65,
    "twinkie": 45,
    "pink_sherbert_ice_cream": -57,
    "rainbow_sherbert_ice_cream": -57,
    "chocolate_sandwich_cookie": 50,
    "sugar_cube": 42,
    "waffle": -38,
    "ding_dong": 34,
    "og_gummy_bear": -119,    # bears are CHAR_SCALE-enlarged; dy is measured
    "sugar_doughnut": -26,
    "zaffre_sherbert_ice_cream": -25,
    "brownie_bite": 22,
    "zebra_cake": -22,
    "cyan_gummy_bear": -105,   # scale-aware (enlarged about the ball center)
    "chocolate_doughnut": -18,
    "glazed_doughnut": -18,
    "gummy_worm": 18,
    "purple_gummy_bear": -100,  # scale-aware (enlarged about the ball center)
    "oatmeal_cream_pie": 14,
    "pink_gummy_bear": -96,    # scale-aware (enlarged about the ball center)
}

def char_y_adjust(char_name):
    return next((dy for k, dy in CHAR_Y_ADJUST.items()
                 if k in char_name.lower()), 0)

# ---- per-character scale (about the face-hole / ball center) ----
# A few characters were authored small relative to the family (gummy bears
# measure ~660px wide vs the ice-cream bodies' ~785px). CHAR_SCALE enlarges
# the character's body, arms AND skin ball about CHAR_SCALE_PIVOT (the ball
# center): the face hole and the ball grow together about the same point the
# eyes sit on, so the ball covers the enlarged hole exactly as at native size
# for ANY skin (no gap ring), while the eyes/mouth stay native size so the
# face style matches the rest of the collection. The extra foot-drop from
# enlarging is absorbed by CHAR_Y_ADJUST, which audit_placement.py measures
# scale-aware so the feet still land on the ground line.
CHAR_SCALE_PIVOT = (690, 601)   # == audit_placement.BALL_CENTER
CHAR_SCALE = {
    "gummy_bear": 1.16,   # -> ~766px wide, matching the ice-cream family
}

def char_scale(char_name):
    return next((s for k, s in CHAR_SCALE.items()
                 if k in char_name.lower()), 1.0)

# Characters whose face reads better with the skin ball drawn ON TOP of the
# body (like the before-skinz ice creams), even though their art is authored
# as an after-skinz "hole" file. The churro is a stack of pieces that
# otherwise hide the face peeking through the hole; treating it as
# skin-on-top draws the face cleanly over the dough.
SKIN_ON_TOP_CHARS = ["churro"]

def skin_on_top(char_name):
    return any(k in char_name.lower() for k in SKIN_ON_TOP_CHARS)

# Characters whose BODY should draw ON TOP of the skin ball (skin placed
# BEFORE the body, revealed through the body's face hole) even though their
# art is authored as a before-skinz file. Gummy bears read better with the
# bear body in front and the skin showing through the eye hole.
BODY_OVER_SKIN_CHARS = ["gummy_bear"]

def body_over_skin(char_name):
    return any(k in char_name.lower() for k in BODY_OVER_SKIN_CHARS)

def body_after_skin(char_name, fname):
    """True when the BODY draws AFTER (on top of) the skin ball — i.e. the
    skin is placed first and shows through the body's face hole. Defaults to
    the after_skinz_ filename marker; two per-character overrides win:
      SKIN_ON_TOP_CHARS  (churro)      -> skin on top  -> body BEFORE skin
      BODY_OVER_SKIN_CHARS (gummy bears) -> body on top -> body AFTER skin
    """
    if skin_on_top(char_name):
        return False
    if body_over_skin(char_name):
        return True
    return "after_skinz" in fname.lower()

# ---- per-arm intrinsic scale (about the hand line) ----
# Some arm art was exported larger than the character family. ARM_SCALE
# shrinks a specific arm file about ARM_SCALE_PIVOT (the held-weapon hand
# line) so the fists stay attached to the body while the weapon scales down.
# It composes on top of any character CHAR_SCALE, so a scaled character still
# gets a proportionally adjusted arm.
ARM_SCALE_PIVOT = (694, 1040)
ARM_SCALE = {
    "Sweetardio_115 (11).png": 0.8,   # dual Uzis: 861px span dwarfs small bodies
}

def arm_scale(arm_file):
    return ARM_SCALE.get(arm_file, 1.0)

def is_wat_excluded(char_name):
    """True when this character must never get what_are_thosez (footwear)."""
    return any(ex.lower() in char_name.lower() for ex in EXCLUDE_WAT_CHARS)

def gets_gorbhouse_overlay(char_name):
    """Gorbhouse slippers are footwear, so the WAT exclusion wins over
    GORBHOUSE_CHARS membership (twinkie/poptarts are in both lists)."""
    return (any(gc.lower() in char_name.lower() for gc in GORBHOUSE_CHARS)
            and not is_wat_excluded(char_name))

# ---- face composition rule (from measured asset geometry) ----
# The widest eyes (284-287px) are wider than the skin balls (268-303px).
# Eyes/mouth keep their ORIGINAL size and placement; instead the skin ball
# is enlarged about its own center just enough that the chosen eyes fit
# within BALL_FIT_MARGIN of the ball's width. The ball always sits on top
# of the body ("B everywhere").
BALL_FIT_MARGIN = 0.92
# Optional soft contact shadow around the skin ball's edge (set to None to
# disable). Rendered from the scaled ball's alpha, offset slightly downward,
# and clipped to the foreground so it never falls on the background plate.
SKIN_SHADOW = None  # e.g. {"blur": 14, "opacity": 0.55, "dx": 0, "dy": 8}

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
    # sorted so seeded runs are reproducible across processes
    return sorted(f for f in os.listdir(path) if f.endswith(".png"))

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
    
    # sorted: set iteration order varies per process (hash randomization),
    # which silently breaks seeded reproducibility
    char_name = random.choice(sorted(base_names))
    
    # Check if this character should be excluded from what_are_thosez
    should_exclude_wat = is_wat_excluded(char_name)

    # Check if this character gets gorbhouse overlay (WAT exclusion wins)
    gets_gorbhouse = gets_gorbhouse_overlay(char_name)
    
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
    # character <-> background compatibility: drop plates this character would
    # camouflage against (measured map; empty/missing entry = everything OK,
    # and we never strand a character with zero plates)
    char_blocked = load_char_blocklist().get(char_name, [])
    allowed_bgs = [f for f in bg_files if f not in char_blocked]
    bg = random.choice(allowed_bgs if allowed_bgs else bg_files)
    
    skin_files = get_files(SKINZ)
    if not skin_files:
        raise ValueError("No skin assets found in traits/skinz")
    
    sw_weights, sw_default = load_skin_weights()
    weights = [skin_weight(f, sw_weights, sw_default) for f in skin_files]
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
    
    # All arms are in the pool so any character can randomly get any arm
    # (including katanas/knives). After the draw, if this character has a
    # locked arm it overrides the pick with its own weapon.
    all_arm_files = get_files(ARMZ)
    arm = random.choice(all_arm_files) if all_arm_files else None
    locked_arms = [f for f in all_arm_files if f in ARMZ_CHAR_LOCK and armz_allowed(f, char_name)]
    if locked_arms:
        arm = random.choice(locked_arms)
    
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
    # Gorbhouse characters get trash-can slippers via a separate code path;
    # giving them regular WAT on top would produce a mismatched double pair.
    if not should_exclude_wat and not gets_gorbhouse:
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
    y_adjust = char_y_adjust(char_name)
    cscale = char_scale(char_name)
    # Background-aware extra drop: applied only when footwear-less so that
    # WAT footwear (which has no dy) stays perfectly aligned.
    bg_extra_y = BG_CHAR_EXTRA_Y.get(bg, 0) if apply_offset else 0

    # 3. Character layers split by z-order relative to the skin ball.
    # before_skinz_ files sit BELOW the skin (ice-cream body, sugar cube, etc).
    # after_skinz_ files sit ABOVE the skin (doughnut/brownie/cookie body with a
    # face hole — the hole reveals the skin ball beneath). Plain-name files
    # (Twinkie, Sweetardio) have no hole so they go below by default.
    before_char_layers = []
    after_char_layers = []
    char_found = False

    for f in char_files:
        if f.startswith("before_skinz_") and char_name.lower() in f.lower():
            layer = {"path": os.path.join(TRAITS_DIR, CHARACTERZ, f), "offset": apply_offset, "dy": y_adjust + bg_extra_y, "cscale": cscale, "ccenter": CHAR_SCALE_PIVOT}
            if body_after_skin(char_name, f):
                after_char_layers.append(layer)
            else:
                before_char_layers.append(layer)
            char_found = True
            break

    main_found = False
    patterns = [f"{char_name}.png", f"after_skinz_{char_name}.png", f"layer-after_skinz_{char_name}.png"]
    for p in patterns:
        for f in char_files:
            if f.lower() == p.lower() or (char_name.lower() in f.lower() and "after_skinz" in f.lower()):
                layer = {"path": os.path.join(TRAITS_DIR, CHARACTERZ, f), "offset": apply_offset, "dy": y_adjust + bg_extra_y, "cscale": cscale, "ccenter": CHAR_SCALE_PIVOT}
                if body_after_skin(char_name, f):
                    after_char_layers.append(layer)
                else:
                    before_char_layers.append(layer)
                main_found = True
                char_found = True
                break
        if main_found:
            break

    if not char_found:
        for f in char_files:
            if char_name.lower() in f.lower():
                layer = {"path": os.path.join(TRAITS_DIR, CHARACTERZ, f), "offset": apply_offset, "dy": y_adjust + bg_extra_y, "cscale": cscale, "ccenter": CHAR_SCALE_PIVOT}
                if body_after_skin(char_name, f):
                    after_char_layers.append(layer)
                else:
                    before_char_layers.append(layer)
                char_found = True
                break

    # 3. Before-skinz body layers (below skin ball)
    layers.extend(before_char_layers)

    # 5. Skinz: ball sits above before-skinz body, below after-skinz body.
    # The ball carries the per-character CHAR_SCALE too (cscale), so an
    # enlarged character's face hole and its skin ball grow together — the
    # ball always covers the hole exactly as it does at native size, for any
    # skin (without this the alien skin's small 269px ball leaves a gap on a
    # scaled bear). ball_fit (fscale) runs first about the ball center, then
    # cscale about the shared pivot; eyes/mouth stay native size.
    skin_path = os.path.join(TRAITS_DIR, SKINZ, skin)
    bfit, bcenter = ball_fit(skin_path, os.path.join(TRAITS_DIR, EYEZ, eye))
    skin_layer = {"path": skin_path, "offset": apply_offset,
                  "dy": y_adjust + bg_extra_y,
                  "fscale": bfit, "fcenter": bcenter,
                  "cscale": cscale, "ccenter": CHAR_SCALE_PIVOT}
    if SKIN_SHADOW:
        skin_layer["shadow"] = dict(SKIN_SHADOW)
    layers.append(skin_layer)

    # 4. After-skinz body layers (above skin ball — face hole reveals skin)
    layers.extend(after_char_layers)

    # 6. Eyez (original size and placement)
    layers.append({"path": os.path.join(TRAITS_DIR, EYEZ, eye), "offset": apply_offset, "dy": y_adjust + bg_extra_y})

    # 7. Mouthz
    layers.append({"path": os.path.join(TRAITS_DIR, MOUTHZ, mouth), "offset": apply_offset, "dy": y_adjust + bg_extra_y})

    # 8. What Are Thosez OVERLAY (footwear front piece) — placed BEFORE arms
    # so a held weapon (katana/knives) reads on top of the slippers instead
    # of being hidden behind them.
    for overlay_path in wat_overlays:
        layers.append({"path": overlay_path, "offset": False})

    # 9. Armz (after the footwear overlay; tracks the character's scale so a
    # bigger body gets a bigger arm)
    if arm:
        layers.append({"path": os.path.join(TRAITS_DIR, ARMZ, arm), "offset": apply_offset, "dy": y_adjust + bg_extra_y, "cscale": cscale, "ccenter": CHAR_SCALE_PIVOT, "ascale": arm_scale(arm), "acenter": ARM_SCALE_PIVOT})

    # 10. Gorbhouse special overlay
    if gets_gorbhouse:
        gorbhouse_path = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, "Gorbhouse_overlay.png")
        if not os.path.exists(gorbhouse_path):
            gorbhouse_path = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, "Gorbhouse_Overlay.png")
        if os.path.exists(gorbhouse_path):
            layers.append({"path": gorbhouse_path, "offset": apply_offset, "dy": y_adjust + bg_extra_y})
    
    # 11. Sticker
    if sticker:
        layers.append({"path": os.path.join(TRAITS_DIR, STICKERZ, sticker), "offset": False})

    # 12. Paired background overlay - always placed LAST, on top of everything
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
    from PIL import ImageChops, ImageFilter
    fg_mask = Image.new("L", (CANVAS_SIZE, CANVAS_SIZE), 0)
    layer_index = -1
    
    for layer_info in layers:
        layer_index += 1
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
        # per-character enlargement about the ball center (body + arms)
        if abs(layer_info.get("cscale", 1.0) - 1.0) > 0.001:
            img = scale_about(img, layer_info["cscale"], layer_info["ccenter"])
        # per-arm intrinsic scale about the hand line (oversized arm art)
        if abs(layer_info.get("ascale", 1.0) - 1.0) > 0.001:
            img = scale_about(img, layer_info["ascale"], layer_info["acenter"])

        # vertical placement: footwear-less offset rule + per-character trim
        dy = (VERTICAL_OFFSET if should_offset else 0) + layer_info.get("dy", 0)
        if dy:
            offset_img = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
            offset_img.paste(img, (0, dy))
            img = offset_img
            
        sh = layer_info.get("shadow")
        if sh:
            a = img.getchannel("A")
            blurred = a.filter(ImageFilter.GaussianBlur(sh["blur"]))
            moved = Image.new("L", a.size, 0)
            moved.paste(blurred, (sh.get("dx", 0), sh.get("dy", 0)))
            op = sh["opacity"]
            shadow_a = moved.point(lambda v: int(v * op))
            # clip to what is already drawn above the background plate
            shadow_a = ImageChops.multiply(shadow_a, fg_mask)
            shadow = Image.new("RGBA", a.size, (0, 0, 0, 255))
            shadow.putalpha(shadow_a)
            base_img.alpha_composite(shadow)
        base_img.alpha_composite(img)
        if layer_index > 0:  # everything except the background plate
            fg_mask = ImageChops.lighter(fg_mask, img.getchannel("A"))
    
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
