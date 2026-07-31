import json
import os
import random
from PIL import Image

TRAITS_DIR = "traits"

# Background overlays are NOT standalone plates: they ride on top of the
# whole stack (placed last) whenever their parent plate is the background.
# Whitehouse_Lawn_Overlay is the foreground figure for the Whitehouse_Lawn
# scene (NOT Candy_Land / Sweetardio_11314, which was a mis-pairing).
# Mars_Overlay is the foreground spectator for the Mars/SpaceX octagon plate
# Sweetardio_116 (20).png (owner-provided transparent cutout), so only the
# figure rides in front, like the Whitehouse spectators.
BG_OVERLAY_PAIRS = {
    "Whitehouse_Lawn.png": "Whitehouse_Lawn_Overlay.png",
    "Sweetardio_116 (20).png": "Mars_Overlay.png",
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

def load_eyez_weights():
    """Per-background soft eye weights (plate -> {eye_file: weight}, higher =
    better colour complement). Built by build_eyez_compat.py alongside the
    blocklist. Missing file/entry -> uniform (1.0)."""
    try:
        with open(EYEZ_COMPAT_PATH) as f:
            return json.load(f).get("weights", {})
    except (OSError, ValueError):
        return {}

# Optional footwear (what_are_thosez) <-> background compatibility map built by
# asset_assessment/build_wat_compat.py: blocks camouflaging/clashing
# (footwear, plate) pairs and softly biases the rest. Keyed by plate (the
# footwear is picked after the background). Missing file = no restrictions.
WAT_COMPAT_PATH = os.path.join(TRAITS_DIR, "wat_compat.json")
_wat_compat_cache = None

def _wat_compat():
    global _wat_compat_cache
    if _wat_compat_cache is None:
        try:
            with open(WAT_COMPAT_PATH) as f:
                _wat_compat_cache = json.load(f)
        except (OSError, ValueError):
            _wat_compat_cache = {}
    return _wat_compat_cache

def load_wat_blocklist():
    """plate -> [footwear base-name, ...] blocked as camouflage/clash."""
    return _wat_compat().get("blocked", {})

def load_wat_weights():
    """plate -> {footwear base-name: weight}. Missing entry -> uniform (1.0)."""
    return _wat_compat().get("weights", {})

# Optional character <-> background compatibility map built by
# asset_assessment/build_char_compat.py: blocks (character, plate) pairs the
# measured figure-ground rule flags as camouflage. Missing file = no limits.
CHAR_COMPAT_PATH = os.path.join(TRAITS_DIR, "char_compat.json")
_char_compat_cache = None

def _char_compat():
    global _char_compat_cache
    if _char_compat_cache is None:
        try:
            with open(CHAR_COMPAT_PATH) as f:
                _char_compat_cache = json.load(f)
        except (OSError, ValueError):
            _char_compat_cache = {}
    return _char_compat_cache

def load_char_blocklist():
    return _char_compat().get("blocked", {})

def load_char_weights():
    """Per-character soft pairing weights over backgrounds (higher = preferred
    pairing). Missing entry -> uniform (1.0)."""
    return _char_compat().get("weights", {})

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
# Legendary_* plates live in backgroundz but are 1/1-style rares minted via a
# fixed per-plate quota (build_mint.py), never the normal random pick.
LEGENDARY_BG_PREFIX = "Legendary_"

def is_legendary_bg(filename):
    return os.path.basename(filename).startswith(LEGENDARY_BG_PREFIX)
SKINZ = "skinz"
CHARACTERZ = "characterz"
EYEZ = "eyez"
MOUTHZ = "mouthz"
WHAT_ARE_THOSEZ = "what_are_thosez"
ARMZ = "armz"
STICKERZ = "stickerz"

# Secret rares are finished, full-canvas 1/1 artworks. They are NOT composited
# with any other trait: each is minted exactly once as a standalone token via a
# fixed slot in build_mint.py, never the normal random pipeline.
SECRET_RAREZ = "secret_rarez"
SECRET_RARE_PREFIX = "Secret_"

def is_secret_rare(path):
    return os.path.basename(path).startswith(SECRET_RARE_PREFIX)

def secret_rare_combination(filename):
    """Return a (layers, char_name) pair for a single 1/1 secret rare so it
    flows through create_image()/extract_metadata() like any other token. The
    art is a complete scene, so it is the sole (background) layer."""
    path = os.path.join(TRAITS_DIR, SECRET_RAREZ, filename)
    name = trait_name(SECRET_RAREZ, filename)
    return [{"path": path, "offset": False}], name

def secret_rare_number(filename):
    """Stable 1-based index (#1..#N) of a secret rare within the set, ordered
    by filename so it never shifts run to run."""
    keys = sorted(TRAIT_NAMES.get(SECRET_RAREZ, {}).keys())
    base = os.path.basename(filename)
    return keys.index(base) + 1 if base in keys else 0

def secret_rare_token_name(filename):
    """Drop-ready token name, e.g. 'Secret Rarez #1 — Milk Dunk'."""
    return (f"Secret Rarez #{secret_rare_number(filename)} — "
            f"{trait_name(SECRET_RAREZ, os.path.basename(filename))}")

# ---- Human-readable display names for every trait asset ----
# Keys for CHARACTERZ: the internal char_name (prefix-stripped, no .png).
# Keys for WHAT_ARE_THOSEZ: the base-name returned by wat_base_name()
#   (e.g. "layer-Bunny_Slippers"), or the string "Gorbhouse" for the
#   gorbhouse trash-can slippers.
# Keys for all other categories: the bare filename (with .png).
TRAIT_NAMES = {
    CHARACTERZ: {
        "Twinkie":                          "Twinkie",
        "brownie_bite":                     "Brownie Bite",
        "chocolate_chip_cookie":            "Chocolate Chip Cookie",
        "chocolate_doughnut":               "Chocolate Doughnut",
        "chocolate_frosted_poptart":        "Chocolate Frosted Pop Tart",
        "chocolate_sandwich_cookie":        "Chocolate Sandwich Cookie",
        "churro":                           "Churro",
        "cyan_frosted_poptart":             "Cyan Frosted Pop Tart",
        "cyan_gummy_bear":                  "Cyan Gummy Bear",
        "cyan_sherbert_ice_cream":          "Cyan Sherbert Ice Cream",
        "ding_dong":                        "Ding Dong",
        "glazed_doughnut":                  "Glazed Doughnut",
        "gold_waffle":                      "Gold Waffle",
        "gummy_worm":                       "Gummy Worm",
        "marshmallow":                      "Marshmallow",
        "mint_chocolate_chip_ice_cream":    "Mint Choc Chip Ice Cream",
        "neopolitan_ice_cream":             "Neapolitan Ice Cream",
        "oatmeal_cream_pie":                "Oatmeal Cream Pie",
        "og_gummy_bear":                    "OG Gummy Bear",
        "og_poptart":                       "OG Pop Tart",
        "pink_gummy_bear":                  "Pink Gummy Bear",
        "pink_sherbert_ice_cream":          "Pink Sherbert Ice Cream",
        "purple_gummy_bear":                "Purple Gummy Bear",
        "rainbow_sherbert_ice_cream":       "Rainbow Sherbert Ice Cream",
        "rice_crispy_treat":                "Rice Crispy Treat",
        "rocky_road_ice_cream":             "Rocky Road Ice Cream",
        "smores":                           "S'mores",
        "sugar_cube":                       "Sugar Cube",
        "sugar_doughnut":                   "Sugar Doughnut",
        "vanilla_ice_cream":                "Vanilla Ice Cream",
        "waffle":                           "Waffle",
        "zaffre_sherbert_ice_cream":        "Zaffre Sherbert Ice Cream",
        "zebra_cake":                       "Zebra Cake",
    },
    BACKGROUNDZ: {
        "Ayotollah.png":                    "Ayotollah",
        "Baked.png":                        "Baked",
        "Ben_dot_Eth.png":                  "Ben dot Eth",
        "Bubble_Trouble.png":               "Bubble Trouble",
        "Cabaret_Alley.png":                "Cabaret Alley",
        "Candy_Tundra.png":                 "Candy Tundra",
        "Celestial.png":                    "Celestial",
        "Cereal_Killer.png":                "Cereal Killer",
        "Choco_Falls.png":                  "Choco Falls",
        "Coder_Chick.png":                  "Coder Chick",
        "Cookboy.png":                      "Cookboy",
        "Crumble_Trail.png":                "Crumble Trail",
        "Drained_The_Swamp.png":            "Drained The Swamp",
        "Druski.png":                       "Druski",
        "Flavor_Explosion.png":             "Flavor Explosion",
        "Goo_Lagoon.png":                   "Goo Lagoon",
        "Gummy_Bears.png":                  "Gummy Bears",
        "He_Needs_Some_Milk.png":           "He Needs Some Milk",
        "Im_Not_Sorry.png":                 "I'm Not Sorry",
        "Legendary_Just_Aliens.png":        "Legendary Just Aliens",
        "Legendary_Opengotchi.png":         "Legendary Opengotchi",
        "Legendary_Simplex.png":            "Legendary Simplex",
        "Legendary_Tenders.png":            "Legendary Tenders",
        "M&Ms.png":                         "M&Ms",
        "Midnight_Snack (1).png":           "Midnight Snack",
        "Nabisco.png":                      "Nabisco",
        "Tampa_Bay_Pete.png":               "Tampa Bay Pete",
        "Pink_Abyss.png":                   "Pink Abyss",
        "Pixie_Stix.png":                   "Pixie Stix",
        "Psychedelics.png":                 "Psychedelics",
        "RIP_Gorbagana.png":                "RIP Gorbagana",
        "Smuckers_Blue.png":                "Smuckers Blue",
        "Snack_Pack.png":                   "Snack Pack",
        "Straight_of_America (1).png":      "Straight of America",
        "Sugar.png":                        "Sugar",
        "Sweet_Castle_2.png":               "Sweet Castle 2",
        "Sweet_Shop.png":                   "Sweet Shop",
        "Sweetardio (16).png":              "Sweet Store",
        "Sweetardio.png":                   "Sweetardio",
        "Sweetardio_116 (20).png":          "Mars",
        "The_Set.png":                      "The Set",
        "Toasted.png":                      "Toasted",
        "Tootsie_Blue.png":                 "Tootsie Blue",
        "Tootsie_Cerise.png":               "Tootsie Cerise",
        "UAP_Taskforce.png":                "UAP Taskforce",
        "Vanilla_Lane (1).png":             "Vanilla Lane",
        "Wheres_My_$_B1tch (1).png":        "Where's My $ B1tch",
        "Whitehouse_Lawn.png":              "Whitehouse Lawn",
        "Why_So_Cereal.png":                "Why So Cereal",
        "Winning.png":                      "Winning",
        "art_mattrick_001-1-2 (1).png":     "Cookie Money",
        "art_mattrick_001-15-2 (1).png":    "In Cook We Trust",
        "soft_serve.png":                   "Soft Serve",
        "Abduction.png":                    "Abduction",
        "Bored_Apes.png":                   "Bored Apes",
        "Bouquet_Drip.png":                 "Bouquet Drip",
        "Empty_Fridge.png":                 "Empty Fridge",
        "Graham.png":                       "Graham",
        "Hurshey.png":                      "Hurshey",
        "Neon_Backroom.png":                "Neon Backroom",
        "Neon_Strip.png":                   "Neon Strip",
        "Cookboy_Chocolate.png":            "Cookboy Chocolate",
        "Cookboy_Gold.png":                 "Cookboy Gold",
        "Cookboy_Black_Enamel.png":         "Cookboy Black Enamel",
        "Cookboy_Silver.png":               "Cookboy Silver",
        "Starburst.png":                    "Starburst",
        "Emblem.png":                       "Emblem",
        "Store.png":                        "Store",
    },
    SKINZ: {
        "layer-Skin_Alien (2).png":                 "Alien",
        "layer-Skin_Black (3).png":                 "Black",
        "layer-Skin_Fluorescent_Cyan (2).png":       "Fluorescent Cyan",
        "layer-Skin_Gold_Foil (1).png":             "Gold Foil",
        "layer-layer-layer-Skin_White (2).png":     "White",
    },
    EYEZ: {
        "Blue.png":                                             "Blue",
        "Cerise.png":                                           "Cerise",
        "layer-Sweetardio_nft (9) (1).png":                     "Retardio",
        "layer-Sweetardio_nft (15).png":                        "Alien",
        "layer-Eyes_Cyan (1).png":                              "Cyan",
        "layer-Eyes_Googly (1).png":                            "Googly",
        "layer-Eyes_Side_Eye (1).png":                          "Side Eye",
        "layer-art_mattrick_011.png":                           "Beady",
        "layer-file_000000001e1c71fd9d410745ea63114e (1).png":  "Cyborg",
        "layer-file_0000000062b071f8b3d115704b04609c (1).png":  "Clueless",
        "layer-file_00000000a21871f894573a9d4ee67519 (2).png":  "Smug",
    },
    MOUTHZ: {
        "Awkward_smile.png":                    "Awkward Smile",
        "layer-Mouth_Diamond_Grill (1).png":    "Diamond Grill",
        "layer-Mouth_Fang (1).png":             "Fang",
        "layer-Mouth_Flat (1).png":             "Flat",
        "layer-Mouth_Lollipop (1).png":         "Lollipop",
        "layer-Mouth_Smirk (1).png":            "Smirk",
        "layer-Mouth_Smoke (1).png":            "Smoke",
        "layer-Mouth_Tasty-1.png":              "Tasty",
        "layer-layer-layer-Mouth_Sad (1).png":  "Sad",
    },
    ARMZ: {
        "Arms_Cash.png":                                "Cash",
        "Armz_Gummy_Bear_Knives.png":                   "Gummy Bear Knives",
        "Armz_Gummy_worms_katana.png":                  "Gummy Worm Katana",
        "Armz_Katana_for_ice_cream_character.png":      "Ice Cream Katana",
        "Armz_Marshmallow_knives.png":                  "Marshmallow Knives",
        "Armz_Oatmeal_Pie_Katana.png":                  "Oatmeal Pie Katana",
        "Armz_Twinkie_Katana.png":                      "Twinkie Katana",
        "Armz_choc_cookie_katana.png":                  "Choc Cookie Katana",
        "Sweetardio_114 (4).png":                       "Blue Saber",
        "Sweetardio_114 (5).png":                       "Pink Saber",
        "Sweetardio_114 (6).png":                       "Cyan Saber",
        "Sweetardio_115 (11).png":                      "Dual Uzis",
        "layer-layer-layer-layer-AK15.png":             "AK15",
        "layer-layer-layer-layer-AR47.png":             "AR47",
        "layer-layer-layer-layer-Military_Brat.png":    "Military Brat",
        "layer-layer-layer-layer-Nerf_Blaster.png":     "Nerf Blaster",
    },
    # Keyed by wat_base_name() result, plus "Gorbhouse" for trash-can slippers.
    WHAT_ARE_THOSEZ: {
        "Cookie_Monster_Slippers":  "Monster",
        "Gorbhouse":                "Gorbhouse",
        "layer-Bunny_Slippers":     "Bunny",
        "layer-Pepe":               "Pepe",
        "layer-Shiba":              "Shiba",
    },
    STICKERZ: {
        "01_Peppermint_Butler.png":         "Peppermint Butler",
        "02_Mr_Owl.png":                    "Mr Owl",
        "03_Benson.png":                    "Benson",
        "04_Marshmallow_Man.png":           "Marshmallow Man",
        "05_American_Pie.png":              "American Pie",
        "06_Dude_Sweet.png":                "Dude Sweet",
        "07_Rare_Candy.png":                "Rare Candy",
        "10_Candy_Shop.png":                "Candy Shop",
        "12_Candy_Land.png":                "Candy Land",
        "13_Box_of_Chocolates.png":         "Box of Chocolates",
        "15_Calvin_Candie.png":             "Calvin Candie",
        "16_The_Bunny.png":                 "The Bunny",
        "17_Hunny_Pot.png":                 "Hunny Pot",
        "18_Pwease_Lollipop.png":           "Pwease Lollipop",
        "20_The_meme_is_the_tech.png":      "The Meme is the Tech",
        "21_Straight_outta_Gulag.png":      "Straight Outta Gulag",
        "22_Sweet_Tooth.png":               "Sweet Tooth",
        "23_Robot_Chicken_Gummy_Bear.png":  "Robot Chicken Gummy Bear",
        "24_Golden_Ticket.png":             "Golden Ticket",
        "25_Zombieland_Twinkie.png":        "Zombieland Twinkie",
        "26_Caroline_Ellison.png":          "Caroline Ellison",
        "28_opengotchi.png":                "Opengotchi",
        "Sweetardio_200 (30).png":          "Cookboy",
    },
    # 1/1 secret rares (standalone full-canvas artworks, never composited).
    SECRET_RAREZ: {
        "Secret_Milk_Dunk.png":         "Milk Dunk",
        "Secret_Churro_Cantina.png":    "Churro Cantina",
        "Secret_Cold_Served.png":       "Cold Served",
        "Secret_Off_The_Line.png":      "Off The Line",
        "Secret_High_Voltage.png":      "High Voltage",
        "Secret_Golden_Waffle.png":     "Golden Waffle",
        "Secret_Cookie_Bro.png":        "Cookie Bro",
        "Secret_Graveyard_Scoop.png":     "Graveyard Scoop",
        "Secret_Checkered_Oreo.png":      "Checkered Oreo",
        "Secret_Marshmallow_Blaze.png":   "Marshmallow Blaze",
        "Secret_Waffle_Loops.png":        "Waffle Loops",
        "Secret_Bubble_Gum_Rules.png":    "Bubble Gum Rules",
        "Secret_Smokey_Marshmallow.png":  "Smokey Marshmallow",
        "Secret_Liberty_Churro.png":      "Liberty Churro",
        "Secret_Frosted_Crate.png":       "Frosted Crate",
        "Secret_Jackpot_Waffle.png":      "Jackpot Waffle",
        "Secret_Stadium_Marshmallow.png": "Stadium Marshmallow",
        "Secret_Cosmic_Melt.png":         "Cosmic Melt",
        "Secret_Twinkie_Cash.png":        "Twinkie Cash",
        "Secret_Cabaret_Cone.png":        "Cabaret Cone",
        "Secret_Unicorn_Twinkie.png":     "Unicorn Twinkie",
        "Secret_Waffle_Nothing.png":      "Waffle Nothing",
        "Secret_Grinning_Oreo.png":       "Grinning Oreo",
    },
}


def _fallback_display_name(filename):
    """Derive a readable display name from a raw filename when no explicit
    mapping exists: strip layer- prefixes, extension, numeric index suffixes,
    and convert underscores to spaces."""
    import re as _re
    name = os.path.basename(filename)
    name = _re.sub(r'\.png$', '', name, flags=_re.IGNORECASE)
    name = _re.sub(r'^(layer-)+', '', name)
    name = _re.sub(r'\s*\(\d+\)\s*', ' ', name).strip()
    name = name.replace('_', ' ').strip()
    return name


def trait_name(category, key):
    """Return the human-readable display name for a trait.
    category: one of the BACKGROUNDZ / SKINZ / ... constants.
    key: filename (with .png) for most categories; the internal char_name
    for CHARACTERZ; the wat_base_name() result (or "Gorbhouse") for
    WHAT_ARE_THOSEZ."""
    return TRAIT_NAMES.get(category, {}).get(key) or _fallback_display_name(key)


def extract_metadata(layers, char_name):
    """Build an OpenSea-compatible metadata attributes list from the layer
    stack returned by generate_random_combination().

    Returns a list of {"trait_type": ..., "value": ...} dicts in the
    canonical display order:
      Character → Background → Skin → Eyes → Mouth → Footwear → Arms → Sticker
    Optional traits that were not selected are omitted (no "None" entries)."""

    # 1/1 secret rare: standalone artwork, no composited traits. Report it under
    # the "Secret Rarez" trait, numbered #1..#N, rather than the normal breakdown.
    if any(is_secret_rare(layer["path"]) for layer in layers):
        sr = next(layer for layer in layers if is_secret_rare(layer["path"]))
        fn = os.path.basename(sr["path"])
        name = trait_name(SECRET_RAREZ, fn)
        return [{"trait_type": "Secret Rarez",
                 "value": f"#{secret_rare_number(fn)} {name}"}]

    overlay_filenames = set(BG_OVERLAY_PAIRS.values())

    attrs = {}  # trait_type -> value, filled in order below

    # Character (always present)
    attrs["Character"] = trait_name(CHARACTERZ, char_name)

    sticker_prefix = os.path.normpath(os.path.join(TRAITS_DIR, STICKERZ))
    armz_prefix    = os.path.normpath(os.path.join(TRAITS_DIR, ARMZ))
    skinz_prefix   = os.path.normpath(os.path.join(TRAITS_DIR, SKINZ))
    eyez_prefix    = os.path.normpath(os.path.join(TRAITS_DIR, EYEZ))
    mouthz_prefix  = os.path.normpath(os.path.join(TRAITS_DIR, MOUTHZ))
    wat_prefix     = os.path.normpath(os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ))
    # backgroundz_originals is a valid fallback dir
    bg_prefixes    = (
        os.path.normpath(os.path.join(TRAITS_DIR, BACKGROUNDZ)),
        os.path.normpath(os.path.join(TRAITS_DIR, BACKGROUNDZ_FALLBACK)),
    )
    bg_categories  = (BACKGROUNDZ, BACKGROUNDZ)  # parallel to bg_prefixes

    import re as _re

    for layer in layers:
        p = os.path.normpath(layer["path"])
        fname = os.path.basename(p)

        # Background plate (not an overlay)
        if any(p.startswith(bp + os.sep) for bp in bg_prefixes):
            if fname not in overlay_filenames:
                bg_cat = next(
                    (c for bp, c in zip(bg_prefixes, bg_categories)
                     if p.startswith(bp + os.sep)),
                    BACKGROUNDZ,
                )
                attrs.setdefault("Background", trait_name(bg_cat, fname))

        # Skin ball
        elif p.startswith(skinz_prefix + os.sep):
            attrs.setdefault("Skin", trait_name(SKINZ, fname))

        # Eyes
        elif p.startswith(eyez_prefix + os.sep):
            attrs.setdefault("Eyes", trait_name(EYEZ, fname))

        # Mouth
        elif p.startswith(mouthz_prefix + os.sep):
            attrs.setdefault("Mouth", trait_name(MOUTHZ, fname))

        # Arms
        elif p.startswith(armz_prefix + os.sep):
            attrs.setdefault("Arms", trait_name(ARMZ, fname))

        # Sticker
        elif p.startswith(sticker_prefix + os.sep):
            attrs.setdefault("Sticker", trait_name(STICKERZ, fname))

        # Footwear (WAT base or gorbhouse overlay)
        elif p.startswith(wat_prefix + os.sep):
            if "gorbhouse" in fname.lower() and "overlay" in fname.lower():
                attrs.setdefault("Footwear", trait_name(WHAT_ARE_THOSEZ, "Gorbhouse"))
            else:
                m = _re.match(r"(.+?)_base(?:\s*\(\d+\))?\.png$", fname, _re.IGNORECASE)
                if m:
                    base = m.group(1)
                    attrs.setdefault("Footwear", trait_name(WHAT_ARE_THOSEZ, base))

    # Return in canonical order; omit absent optional traits
    order = ["Character", "Background", "Skin", "Eyes", "Mouth",
             "Footwear", "Arms", "Sticker"]
    return [{"trait_type": k, "value": attrs[k]}
            for k in order if k in attrs]


# ---- OpenSea token metadata ----
COLLECTION_NAME = "Sweetardio Collection"
COLLECTION_DESCRIPTION = (
    "Sweetardio Collection — 4,444 hand-crafted sweet degens. Every trait "
    "is composited and graded for the cleanest, most collectible look on-chain."
)


def token_metadata(attributes, token_id=None, image=None,
                   name=None, description=None):
    """Wrap an attributes list (from extract_metadata) into a complete,
    OpenSea-compatible token metadata object.

    token_id : int  -> default name becomes "Sweetardio Collection #<id>".
    image    : str  -> image URI/path (e.g. "ipfs://CID/123.png" or "123.png").
    Keys are ordered name, description, image, attributes for clean files."""
    meta = {}
    meta["name"] = name or (f"{COLLECTION_NAME} #{token_id}"
                            if token_id is not None else COLLECTION_NAME)
    meta["description"] = description or COLLECTION_DESCRIPTION
    if image is not None:
        meta["image"] = image
    meta["attributes"] = attributes
    return meta


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
    # bears are CHAR_SCALE-enlarged and aligned to the ice-cream cone line
    # (1290) via CHAR_Y_ADJUST; NO_OFFSET so the +150 footwear-less drop
    # never disturbs that placement
    "gummy_bear",
    # NOTE: smores used to live here (full +150 drop was too low) but bare it
    # then sat too HIGH. It is now offset-eligible with a SOFTENED footwear-less
    # drop via FOOTWEARLESS_DY["smores"], landing between the two extremes.
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

# Characters with no base / standing point (round cookies, the gummy worm,
# the round doughnuts, the ding dong ring) read better CENTERED than dropped to
# the ground: a round shape lowered to the floor looks like it is resting
# awkwardly, not standing. These skip the footwear-less drop AND any
# CHAR_Y_ADJUST trim, so they sit at their natural (asset-native) centred
# position. (ding_dong is a chocolate ring — geometrically a doughnut — so it
# belongs here with the other rings, not in the standing set.)
CENTERED_CHARS = [
    "chocolate_chip_cookie",
    "chocolate_sandwich_cookie",
    "oatmeal_cream_pie",
    "gummy_worm",
    "glazed_doughnut",
    "chocolate_doughnut",
    "sugar_doughnut",
    "ding_dong",
]

def is_centered(char_name):
    return any(k in char_name.lower() for k in CENTERED_CHARS)

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
    "gold_waffle": -18,        # measured separately from the plain waffle; the
                               # key must stay distinct or the "waffle" substring
                               # claims it and lifts it 20px too high
    "waffle": -38,
    "ding_dong": 34,
    "og_gummy_bear": 44,      # bears enlarged + aligned to the cone line (1290)
    "sugar_doughnut": -26,
    "zaffre_sherbert_ice_cream": -25,
    "brownie_bite": 22,
    "zebra_cake": -37,         # with-footwear case raised; the (perfect) bare
                               # stance is held put by FOOTWEARLESS_DY
    "cyan_gummy_bear": 58,     # enlarged + aligned to the cone line (1290)
    "chocolate_doughnut": -18,
    "glazed_doughnut": -18,
    "gummy_worm": 18,
    "purple_gummy_bear": 63,    # enlarged + aligned to the cone line (1290)
    "oatmeal_cream_pie": 14,
    "pink_gummy_bear": 68,     # enlarged + aligned to the cone line (1290)
}

def char_y_adjust(char_name):
    # Longest key wins: several characters contain a shorter character's name
    # ("gold_waffle" contains "waffle"), and a first-match lookup silently
    # hands them the wrong trim. Shared keys that are deliberately generic
    # ("poptart" for all three poptarts) are unaffected.
    name = char_name.lower()
    hits = [k for k in CHAR_Y_ADJUST if k in name]
    return CHAR_Y_ADJUST[max(hits, key=len)] if hits else 0

# Per-character vertical trim (px, +down) for CENTERED characters in their
# footwear-less CENTRED position (where the normal CHAR_Y_ADJUST is suppressed
# so the round/baseless body sits at its natural centre). A round body's native
# centre can still read slightly high in-frame (the face holes sit ~100px above
# canvas centre), so this nudges it down WITHOUT touching the character's
# footwear placement (CHAR_Y_ADJUST). Default 0; tuned by eye.
CENTERED_FOOTWEARLESS_DY = {
    "glazed_doughnut": 45,
    "chocolate_doughnut": 38,
    "sugar_doughnut": 38,
    "chocolate_sandwich_cookie": 35,
    "chocolate_chip_cookie": 32,
    "gummy_worm": 24,
    "oatmeal_cream_pie": 80,
    "ding_dong": 94,       # was the only CENTERED character with no entry, so
                           # it floated ~94px above its ring/disc peers when
                           # bare; 94 puts its bottom on their median (1016)
}

def centered_footwearless_dy(char_name):
    return next((dy for k, dy in CENTERED_FOOTWEARLESS_DY.items()
                 if k in char_name.lower()), 0)

# Extra vertical trim (px, +down) applied ONLY in the footwear-less drop case
# (apply_offset True: an offset-eligible character standing with no footwear).
# This lets a character's grounded/footwear placement (CHAR_Y_ADJUST) stay
# fixed while nudging only its footwear-less standing height — needed when a
# character looks right with shoes but too low/high standing bare. Default 0.
FOOTWEARLESS_DY = {
    "sugar_cube": -45,   # the +150 bare drop bottomed it out; raise the stance
    "smores": -75,       # softened bare drop (full +150 was too low; see below)
    "zebra_cake": 15,    # keep the (perfect) bare stance while CHAR_Y_ADJUST
                         # raises only the with-footwear case
    "brownie_bite": -65, # raise bare stance to match visual placement with others
}

def footwearless_dy(char_name):
    return next((dy for k, dy in FOOTWEARLESS_DY.items()
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
    "gummy_bear": 1.19,   # -> ~789px wide, matching the ice-cream family
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
    """ELIGIBILITY for the gorbhouse overlay (deterministic). Gorbhouse
    slippers are footwear, so the WAT exclusion wins over GORBHOUSE_CHARS
    membership (twinkie/poptarts are in both lists). The overlay is then
    APPLIED only on a GORBHOUSE_CHANCE roll, so eligible characters still get
    plenty of generations with no what-are-thosez trait at all."""
    return (any(gc.lower() in char_name.lower() for gc in GORBHOUSE_CHARS)
            and not is_wat_excluded(char_name))

# How often an eligible character actually wears the gorbhouse (rolled per
# generation) WHEN its footwear slot is active. < 1.0 so eligible characters
# still get regular slippers (and, via the tiers below, footwear-less runs).
GORBHOUSE_CHANCE = 0.4

# ---- minimal-traits-first selection (probability tiers) ----
# The mandatory core of every NFT is background + body + skin + eyes + mouth.
# Footwear (what_are_thosez / gorbhouse), arms and the corner sticker are
# OPTIONAL. To guarantee every character can be generated CLEAN (minimal
# traits) before extras are layered on, each generation first rolls HOW MANY of
# its available optional slots to fill, weighted toward FEWER. Keys are the
# optional-trait COUNT (0 = pure minimal: core only); values are relative
# weights. Counts above the number of slots a given character actually has are
# ignored, and the weights renormalise over what's left. Tune to taste:
# raising the 0/1 weights makes minimal/near-minimal renders more common.
OPTIONAL_TRAIT_COUNT_WEIGHTS = {0: 4, 1: 3, 2: 2, 3: 1}


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

# ---- character grounding shadow (cast ONTO the background) ----
# Soft shadow cast by the character's silhouette onto the background plate,
# composited ABOVE the plate and BELOW the character, so each character sits
# on top of its own shadow and reads as part of the scene instead of pasted
# on. This is the OPPOSITE of SKIN_SHADOW (which clips to the foreground): the
# grounding shadow is deliberately NOT clipped to the foreground, so it falls
# on the background behind/under the subject. The character is drawn on top
# afterwards, so the shadow can never show through or above the subject.
#
# Set to None to disable entirely. Tunables:
#   mode        "ground" = squashed contact pool seated at the silhouette's
#               lowest opaque row (for characters that stand on something);
#               "drop"   = the whole silhouette, offset + blurred (for
#               centred/portrait characters that float by design);
#               "auto"   = pick per character from geometry: a contact pool
#               when the silhouette reaches the ground band, else a soft drop.
#   blur        Gaussian blur radius in px (softness of the shadow edge).
#   opacity     peak shadow alpha, 0..1.
#   dx, dy      shadow offset in px (+dy = down). Light is assumed slightly
#               above, so a small +dy seats the shadow just below the feet.
#   squash      "ground" mode only: vertical compression of the silhouette
#               into a flat contact pool (smaller = flatter pool).
#   exclude_arms  derive the silhouette from the body+skin mass only, dropping
#               held weapons (e.g. a katana) so they don't throw a shadow
#               spike across the scene.
#   ground_line "auto" mode only: silhouette bottoms at/below this canvas row
#               are treated as grounded (contact pool); higher = drop shadow.
GROUND_SHADOW = {
    "mode": "auto",
    "blur": 26,
    "opacity": 0.40,
    "dx": 0,
    "dy": 6,
    "squash": 0.16,
    "exclude_arms": True,
    "ground_line": 1040,
}

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

# Deepest face-hole vertical extent across the after-skinz characters
# (measured: top 466 = brownie_bite, bottom 730 = rice_crispy_treat). A skin
# ball must reach from the top to the bottom or it shows a background gap
# through the hole — the short, low alien ball (center y 605, height 248) was
# the failure case on tall holes like brownie_bite's.
FACE_HOLE_TOP = 464
FACE_HOLE_BOTTOM = 732

# A few after-skinz bodies have a face hole that sits lower/deeper than the
# cast-wide FACE_HOLE_BOTTOM, so the standard skin ball stopped short of the
# hole's bottom edge and a sliver of background showed under the face. Override
# the hole bottom (px) for just those characters so their ball is enlarged
# enough to cover it, without growing every other character's face. Substring
# match on the character base-name.
FACE_HOLE_BOTTOM_OVERRIDE = {
    "gold_waffle": 750,   # hole bottom ~741; ball must reach below it
}

def face_hole_bottom(char_name):
    return next((v for k, v in FACE_HOLE_BOTTOM_OVERRIDE.items()
                 if k in char_name.lower()), FACE_HOLE_BOTTOM)

def ball_fit(skin_path, eye_path, hole_bottom=FACE_HOLE_BOTTOM,
             hole_top=FACE_HOLE_TOP):
    """Enlargement factor + pivot so the skin ball contains the eyes AND
    covers the deepest character face hole (no gap through after-skinz holes).
    hole_bottom/hole_top default to the cast-wide values; pass a per-character
    override for bodies whose hole sits deeper (see FACE_HOLE_BOTTOM_OVERRIDE)."""
    sx0, sy0, sx1, sy1 = _opaque_bbox(skin_path)
    ex0, _, ex1, _ = _opaque_bbox(eye_path)
    ball_w = max(sx1 - sx0, 1)
    ball_h = max(sy1 - sy0, 1)
    cy = (sy0 + sy1) / 2.0
    eye_w = max(ex1 - ex0, 1)
    # extra height needed so the ball reaches the hole top and bottom from its
    # own center (depends per skin: the alien ball sits low, so it needs more)
    need_h = 2.0 * max(cy - hole_top, hole_bottom - cy)
    factor = max(1.0, eye_w / (BALL_FIT_MARGIN * ball_w), need_h / ball_h)
    return factor, ((sx0 + sx1) / 2.0, cy)

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

def generate_random_combination(force_bg=None, force_arm="auto",
                                force_wat="auto", force_sticker="auto"):
    """force_bg = (bg_dir, bg_file) pins the background (e.g. a legendary
    plate from traits/backgroundz); it bypasses the random plate pick,
    the char<->bg compat filter and any paired overlay. Default = random.

    force_arm / force_wat / force_sticker drive the optional slots for the
    mint allocator (build_mint.py) so exact rarity counts can be hit:
      * "auto" (default) -> roll the slot normally (minimal-traits-first).
      * None             -> force the slot OFF (never drawn).
      * <value>          -> force the slot ON with that specific trait:
          force_arm     = an armz filename (e.g. "...-AK15.png")
          force_wat     = a footwear base name (wat_base_name), or "gorbhouse"
          force_sticker = a stickerz filename
    A forced slot bypasses the count roll; only the remaining "auto" slots
    take part in the minimal-traits-first weighting."""
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
    
    # Check if this character should be excluded from what_are_thosez. The
    # gorbhouse roll now happens INSIDE the footwear slot below, as part of the
    # minimal-traits-first optional-trait selection.
    should_exclude_wat = is_wat_excluded(char_name)

    # 2. Select Required Traits
    if force_bg is not None:
        bg_dir, bg = force_bg
    else:
        bg_dir = BACKGROUNDZ
        bg_files = get_files(bg_dir)
        if not bg_files:
            print(f"Warning: traits/{BACKGROUNDZ} is empty; falling back to "
                  f"the ungraded traits/{BACKGROUNDZ_FALLBACK}")
            bg_dir = BACKGROUNDZ_FALLBACK
            bg_files = get_files(bg_dir)
        # overlays pair with their parent plate; they are never a background
        bg_files = [f for f in bg_files if f not in BG_OVERLAY_PAIRS.values()]
        # Legendary_* plates are 1/1-style rares: they appear ONLY via the
        # mint allocator's fixed per-plate quota (force_bg), never in the
        # normal weighted random pick, so their hard caps stay exact.
        bg_files = [f for f in bg_files if not is_legendary_bg(f)]
        if not bg_files:
            raise ValueError("No background assets found")
        # character <-> background pairing. Hard rule: drop plates this
        # character would camouflage against (never stranding it). Soft rule:
        # bias the remaining pick toward the best-looking pairings (measured
        # weights), while keeping every non-camouflage plate possible so the
        # background variety / combinatorial space stays large.
        char_blocked = load_char_blocklist().get(char_name, [])
        allowed_bgs = [f for f in bg_files if f not in char_blocked] or bg_files
        cw = load_char_weights().get(char_name, {})
        bg = random.choices(allowed_bgs,
                            weights=[cw.get(f, 1.0) for f in allowed_bgs],
                            k=1)[0]
    
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
    
    # eye <-> background compatibility (measured): drop clashing eyes (hard
    # block), then bias the remaining pick toward the best-complementing eyes
    # (soft weights), mirroring the character<->background pairing rule.
    eyez_blocked = load_eyez_blocklist().get(bg, [])
    allowed_eyes = [f for f in eye_files if f not in eyez_blocked] or eye_files
    ew = load_eyez_weights().get(bg, {})
    eye = random.choices(allowed_eyes,
                         weights=[ew.get(f, 1.0) for f in allowed_eyes], k=1)[0]
    mouth = random.choice(mouth_files)
    
    # ---- optional traits: minimal-traits-first via probability tiers ----
    # The mandatory core (background + body + skin + eyes + mouth) is already
    # chosen above. Footwear, arms and the corner sticker are OPTIONAL. First
    # work out which optional slots are even available to THIS character, then
    # roll how many to fill (weighted toward fewer) and which ones, so every
    # character has a real chance of a clean minimal render.
    all_arm_files = get_files(ARMZ)
    sticker_files = get_files(STICKERZ)
    wat_files = get_files(WHAT_ARE_THOSEZ)

    # base files look like "layer-Bunny_Slippers_Base (1).png": match the
    # "_base" marker with an optional " (n)" suffix, case-insensitively
    import re as _re
    def wat_base_name(f):
        m = _re.match(r"(.+?)_base(?:\s*\(\d+\))?\.png$", f, _re.IGNORECASE)
        return m.group(1) if m else None

    # regular wearable footwear bases (gorbhouse is handled as its own roll)
    wat_bases = [wat_base_name(f) for f in wat_files]
    wat_bases = [b for b in wat_bases if b and "gorbhouse" not in b.lower()]

    # footwear is available only when the character isn't WAT-excluded and has
    # something to wear (regular slippers, or gorbhouse for eligible chars)
    footwear_available = (not should_exclude_wat
                          and (wat_bases or gets_gorbhouse_overlay(char_name)))

    # Only slots left on "auto" take part in the minimal-traits-first count
    # roll; any force-driven slot (mint allocator) is decided explicitly below.
    optional_slots = []
    if force_wat == "auto" and footwear_available:
        optional_slots.append("footwear")
    if force_arm == "auto" and all_arm_files:
        optional_slots.append("arms")
    if force_sticker == "auto" and sticker_files:
        optional_slots.append("sticker")

    # roll HOW MANY optional traits (weighted toward fewer), then WHICH slots
    counts = list(range(len(optional_slots) + 1))
    cw = [OPTIONAL_TRAIT_COUNT_WEIGHTS.get(k, 0) for k in counts]
    if sum(cw) == 0:                      # no configured weights -> uniform
        cw = [1] * len(counts)
    n_optional = random.choices(counts, weights=cw, k=1)[0]
    active = set(random.sample(optional_slots, n_optional)) if n_optional else set()

    # apply forced ON slots (a specific trait was requested by the allocator)
    if force_wat not in ("auto", None):
        active.add("footwear")
    if force_arm not in ("auto", None):
        active.add("arms")
    if force_sticker not in ("auto", None):
        active.add("sticker")

    # --- footwear slot: gorbhouse trash-cans (eligible chars) or regular WAT,
    # the latter biased by the measured footwear<->background compat table ---
    chosen_wat = None
    wat_overlays = []
    gets_gorbhouse = False
    if "footwear" in active:
        if force_wat not in ("auto", None):
            # explicit footwear from the allocator, but honor character
            # eligibility: if this char can't wear it, leave footwear OFF so
            # the allocator re-rolls onto an eligible character.
            if str(force_wat).lower() == "gorbhouse":
                if gets_gorbhouse_overlay(char_name):
                    gets_gorbhouse = True
            elif footwear_available:
                chosen_wat = force_wat
        elif gets_gorbhouse_overlay(char_name) and random.random() < GORBHOUSE_CHANCE:
            gets_gorbhouse = True
        elif wat_bases:
            wat_blocked = load_wat_blocklist().get(bg, [])
            allowed_wat = [b for b in wat_bases
                           if b not in wat_blocked] or wat_bases
            ww = load_wat_weights().get(bg, {})
            chosen_wat = random.choices(
                allowed_wat,
                weights=[ww.get(b, 1.0) for b in allowed_wat], k=1)[0]
        if chosen_wat:
            for f in wat_files:
                if f.lower().startswith(chosen_wat.lower()) and "overlay" in f.lower():
                    wat_overlays.append(os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f))

    # --- arms slot: any arm may be drawn (including katanas/knives); a
    # character with a locked weapon overrides the draw with its own ---
    arm = None
    if "arms" in active and all_arm_files:
        if force_arm not in ("auto", None):
            # explicit arm from the allocator; for a character-LOCKED weapon,
            # only draw it on a character allowed to hold it (otherwise leave
            # the slot empty so the allocator re-rolls onto a valid character).
            if armz_allowed(force_arm, char_name):
                arm = force_arm
        else:
            arm = random.choice(all_arm_files)
            locked_arms = [f for f in all_arm_files
                           if f in ARMZ_CHAR_LOCK and armz_allowed(f, char_name)]
            if locked_arms:
                arm = random.choice(locked_arms)

    # --- sticker slot: corner sticker ---
    if "sticker" in active:
        sticker = (force_sticker if force_sticker not in ("auto", None)
                   else random.choice(sticker_files))
    else:
        sticker = None
    
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
    # Baseless/round characters sit centred ONLY when they have nothing under
    # them to stand on: no footwear (apply_offset) and no gorbhouse. With a
    # shoe or trash-can they keep their normal grounded placement.
    if is_centered(char_name) and apply_offset and not gets_gorbhouse:
        # natural centre (suppress the standing CHAR_Y_ADJUST), plus an optional
        # small per-character centre trim so a round body isn't left too high
        apply_offset = False
        y_adjust = centered_footwearless_dy(char_name)
    elif apply_offset:
        # offset-eligible body standing with no footwear: a footwear-less-only
        # trim so its grounded (footwear) placement stays put
        y_adjust += footwearless_dy(char_name)
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
    bfit, bcenter = ball_fit(skin_path, os.path.join(TRAITS_DIR, EYEZ, eye),
                             hole_bottom=face_hole_bottom(char_name))
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

    # 9. Gorbhouse special overlay (a footwear-type trait) — placed BEFORE
    # arms, like the WAT overlay, so a held weapon reads on top of it.
    if gets_gorbhouse:
        gorbhouse_path = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, "Gorbhouse_overlay.png")
        if not os.path.exists(gorbhouse_path):
            gorbhouse_path = os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, "Gorbhouse_Overlay.png")
        if os.path.exists(gorbhouse_path):
            layers.append({"path": gorbhouse_path, "offset": apply_offset, "dy": y_adjust + bg_extra_y})

    # 10. Armz (after ALL footwear overlays — WAT and gorbhouse — so a held
    # katana/knife reads on top of the footwear; tracks the character's scale)
    if arm:
        layers.append({"path": os.path.join(TRAITS_DIR, ARMZ, arm), "offset": apply_offset, "dy": y_adjust + bg_extra_y, "cscale": cscale, "ccenter": CHAR_SCALE_PIVOT, "ascale": arm_scale(arm), "acenter": ARM_SCALE_PIVOT})

    # 11. Sticker
    if sticker:
        layers.append({"path": os.path.join(TRAITS_DIR, STICKERZ, sticker), "offset": False})

    # 12. Paired background overlay - always placed LAST, on top of everything
    if bg in BG_OVERLAY_PAIRS:
        ov_path = os.path.join(TRAITS_DIR, bg_dir, BG_OVERLAY_PAIRS[bg])
        if os.path.exists(ov_path):
            layers.append({"path": ov_path, "offset": False})

    return layers, char_name

def _render_layer(layer_info):
    """Load a layer and apply all of its geometric transforms (fscale, cscale,
    ascale, then the footwear-less offset + per-character dy). Returns a
    full-canvas RGBA image, or None if the file is missing. No shadow is
    applied here — shadows are handled by the compositor stages."""
    layer_path = layer_info["path"]
    if not os.path.exists(layer_path):
        print(f"Warning: Layer not found: {layer_path}")
        return None

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
    dy = (VERTICAL_OFFSET if layer_info["offset"] else 0) + layer_info.get("dy", 0)
    if dy:
        offset_img = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
        offset_img.paste(img, (0, dy))
        img = offset_img
    return img


def _ground_shadow(sil_alpha, cfg):
    """Build the character grounding shadow from a silhouette alpha (L-mode,
    full canvas). Returns a black RGBA layer to composite onto the background
    BELOW the character, or None when the silhouette is empty.

    The shadow is intentionally NOT clipped to the foreground: it falls on the
    background, and the character (drawn afterwards) covers any overlap, so it
    can never show through or above the subject."""
    from PIL import ImageFilter
    bbox = sil_alpha.getbbox()
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox

    mode = cfg.get("mode", "auto")
    if mode == "auto":
        # grounded characters reach the ground band; portrait/centred ones
        # float well above it and get a soft drop instead of a contact pool.
        mode = "ground" if y1 >= cfg.get("ground_line", 1040) else "drop"

    dx = int(cfg.get("dx", 0))
    dy = int(cfg.get("dy", 0))
    moved = Image.new("L", sil_alpha.size, 0)

    if mode == "ground":
        # squash the silhouette into a flat contact pool seated at its lowest
        # opaque row (the feet / footwear base / cone tip).
        squash = cfg.get("squash", 0.16)
        sub = sil_alpha.crop(bbox)
        pool_w = max(1, x1 - x0)
        pool_h = max(1, round((y1 - y0) * squash))
        pool = sub.resize((pool_w, pool_h), Image.Resampling.LANCZOS)
        moved.paste(pool, (x0 + dx, y1 - pool_h // 2 + dy))
    else:  # drop: the whole silhouette, offset and blurred
        moved.paste(sil_alpha.crop(bbox), (x0 + dx, y0 + dy))

    shadow_a = moved.filter(ImageFilter.GaussianBlur(cfg.get("blur", 24)))
    op = cfg.get("opacity", 0.4)
    shadow_a = shadow_a.point(lambda v: int(v * op))
    shadow = Image.new("RGBA", sil_alpha.size, (0, 0, 0, 255))
    shadow.putalpha(shadow_a)
    return shadow


def create_image(layers, output_name=None, metadata=None):
    """Composite all layers and write the PNG.
    If metadata is provided (a list of {"trait_type", "value"} dicts as
    returned by extract_metadata()), a matching .json sidecar is saved
    next to the PNG with OpenSea-compatible attributes."""
    if output_name is None:
        import time
        if not os.path.exists("output"):
            os.makedirs("output")
        output_name = f"output/gen_{int(time.time())}_{random.randint(1000, 9999)}.png"

    from PIL import ImageChops, ImageFilter
    canvas = (CANVAS_SIZE, CANVAS_SIZE)
    base_img = Image.new("RGBA", canvas, (0, 0, 0, 0))

    # Classify the layer stack. The first layer is always the background
    # plate. The corner sticker and the paired background overlay ride on TOP
    # of everything (and of the shadow); everything in between is
    # character-anchored and casts the grounding shadow.
    sticker_prefix = os.path.normpath(os.path.join(TRAITS_DIR, STICKERZ))
    armz_prefix = os.path.normpath(os.path.join(TRAITS_DIR, ARMZ))
    overlay_names = set(BG_OVERLAY_PAIRS.values())

    def _is_top(layer_info):
        p = os.path.normpath(layer_info["path"])
        return (p.startswith(sticker_prefix + os.sep)
                or os.path.basename(p) in overlay_names)

    def _is_arm(layer_info):
        return os.path.normpath(layer_info["path"]).startswith(
            armz_prefix + os.sep)

    bg_layer = layers[0] if layers else None
    char_layers = [li for li in layers[1:] if not _is_top(li)]
    top_layers = [li for li in layers[1:] if _is_top(li)]

    # 1. Background plate(s).
    if bg_layer is not None:
        bg_img = _render_layer(bg_layer)
        if bg_img is not None:
            base_img.alpha_composite(bg_img)

    # 2. Character composite on its own transparent canvas, with identical
    #    per-layer transforms. fg_mask tracks the foreground built so far so a
    #    per-layer SKIN_SHADOW still clips to the body (never the background).
    #    sil_alpha accumulates the grounding silhouette (body+skin mass,
    #    optionally excluding held-weapon arms).
    char_img = Image.new("RGBA", canvas, (0, 0, 0, 0))
    fg_mask = Image.new("L", canvas, 0)
    sil_alpha = Image.new("L", canvas, 0)
    exclude_arms = bool(GROUND_SHADOW and GROUND_SHADOW.get("exclude_arms"))

    for layer_info in char_layers:
        img = _render_layer(layer_info)
        if img is None:
            continue
        sh = layer_info.get("shadow")
        if sh:
            a = img.getchannel("A")
            blurred = a.filter(ImageFilter.GaussianBlur(sh["blur"]))
            moved = Image.new("L", a.size, 0)
            moved.paste(blurred, (sh.get("dx", 0), sh.get("dy", 0)))
            op = sh["opacity"]
            shadow_a = moved.point(lambda v: int(v * op))
            # clip to the foreground built so far (never the background)
            shadow_a = ImageChops.multiply(shadow_a, fg_mask)
            shadow = Image.new("RGBA", a.size, (0, 0, 0, 255))
            shadow.putalpha(shadow_a)
            char_img.alpha_composite(shadow)
        char_img.alpha_composite(img)
        alpha = img.getchannel("A")
        fg_mask = ImageChops.lighter(fg_mask, alpha)
        if not (exclude_arms and _is_arm(layer_info)):
            sil_alpha = ImageChops.lighter(sil_alpha, alpha)

    # 3. Grounding shadow derived from the silhouette, onto the background.
    if GROUND_SHADOW:
        shadow = _ground_shadow(sil_alpha, GROUND_SHADOW)
        if shadow is not None:
            base_img.alpha_composite(shadow)

    # 4. Character composite, on top of its own shadow.
    base_img.alpha_composite(char_img)

    # 5. Sticker + paired background overlay, on top of everything.
    for layer_info in top_layers:
        img = _render_layer(layer_info)
        if img is not None:
            base_img.alpha_composite(img)

    base_img.save(output_name)

    if metadata is not None:
        json_path = os.path.splitext(output_name)[0] + ".json"
        # Accept either a bare attributes list (legacy) or a full token object
        # (from token_metadata()). A bare list is wrapped into a complete
        # OpenSea token so the produced file is always drop-ready.
        if isinstance(metadata, dict):
            token = metadata
        else:
            token = token_metadata(metadata,
                                   image=os.path.basename(output_name))
        with open(json_path, "w") as _jf:
            json.dump(token, _jf, indent=2, ensure_ascii=False)

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
            meta = extract_metadata(layers, char_name)
            out = create_image(layers,
                               f"output/test_{i+1}_{char_name}_{status}.png",
                               metadata=meta)
            attrs_str = ", ".join(f"{a['trait_type']}: {a['value']}" for a in meta)
            print(f"  Metadata → {attrs_str}")
        except Exception as e:
            print(f"Error: {e}")
