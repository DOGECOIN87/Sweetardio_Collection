import json
import os
import random
import re
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

# Global per-asset rarity gains for the ALWAYS-PRESENT traits (eyes, mouths,
# backgrounds). An optional trait — arms, footwear, stickers — is either on a
# token or not, so build_mint.py can slot-allocate it to an EXACT count. An
# always-present trait cannot be allocated that way: it has to compose with the
# compat blocklists, so it is drawn by weight instead, and the weights are
# solved by asset_assessment/calibrate_rarity.py until the realised share
# matches the intended one. Missing file -> every gain 1.0, i.e. the previous
# behaviour exactly.
RARITY_PATH = os.path.join(TRAITS_DIR, "rarity_weights.json")
_rarity_cache = None


def load_rarity_gains(category):
    """{asset filename: draw multiplier} for a trait category. 1.0 default."""
    global _rarity_cache
    if _rarity_cache is None:
        try:
            with open(RARITY_PATH) as f:
                _rarity_cache = json.load(f)
        except (OSError, ValueError):
            _rarity_cache = {}
    return (_rarity_cache.get(category) or {}).get("gain", {})


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

# The ANIMATED plate. Its PNG in traits/backgroundz is frame 0 of a 12-frame
# loop that dynamic/starfield.py rebuilds from Nyan_Blank.gif; the loop is
# what animation_url points at, and build_mint.py --render --animation writes
# it for the tokens that drew the plate (there is no separate bake pass: this
# is the one animated tier whose PLATE moves, so its frames have to be
# re-composited rather than graded over a finished still).
#
# The PNG here is the dy=0 REFERENCE plate -- what the trait sheet and any
# ad-hoc render show, and what build_mint checks for before it will mint the
# tier. The minted tokens each get their own copy of it, because the rainbow
# trail is centred on the character it leaves (starfield.centre_layers).
STARFIELD_BG = "Starfield.png"

# Plates the ALLOCATOR places and the weighted draw never touches, so their
# hard caps stay exact. Legendary plates have always worked this way; the
# starfield joins them because an ultra-rare cap cannot survive a plate also
# being drawable at weight 1.0 alongside ~70 others -- that alone would mint
# it onto roughly 1 token in 70 rather than 10 in 4444.
ALLOCATOR_ONLY_BGS = {STARFIELD_BG}

def is_allocator_only_bg(filename):
    """True for a plate that may appear ONLY via force_bg from build_mint."""
    f = os.path.basename(filename)
    return is_legendary_bg(f) or f in ALLOCATOR_ONLY_BGS


# ---- Plate Tier: the plate's scarcity band, as a metadata attribute ----
#
# A plate's rarity was legible only by counting the mint, and the counts
# contradicted the one label a collector could see: at 50 each, every
# "Legendary" plate was MORE common than 17 ordinary ones -- Sweet Castle
# realised 19, Abduction 21, Goo Lagoon 26. Holding the rarest background in
# the collection looked exactly like holding the 40th rarest.
#
# The band is derived from the DESIGNED target in traits/rarity_weights.json
# rather than from a realised count, so it is a property of the collection and
# not of whichever seed was minted. The ladder is monotone by construction:
#
#   Ultra      Starfield, 10                    (allocator-only)
#   Legendary  4 plates x LEG_EACH              (allocator-only)
#   Scarce     pinned at the low target
#   Uncommon   pinned at the high target
#   Standard   unpinned -- shares whatever is left, so the most common
#
# Unpinned is Standard and NOT an error: 41 of 66 plates have no target and
# draw at gain 1.0 together. A plate added without a target lands here, which
# is the honest answer for it.
_PLATE_TIER_CACHE = None


def _plate_targets():
    """{plate filename -> designed share} from traits/rarity_weights.json.
    Missing file or key is not fatal -- every plate then reads Standard,
    which is what an uncalibrated collection actually is."""
    global _PLATE_TIER_CACHE
    if _PLATE_TIER_CACHE is None:
        try:
            import json as _json
            with open(os.path.join(TRAITS_DIR, "rarity_weights.json")) as fh:
                _PLATE_TIER_CACHE = (_json.load(fh)
                                     .get(BACKGROUNDZ, {}).get("target", {}))
        except Exception:
            _PLATE_TIER_CACHE = {}
    return _PLATE_TIER_CACHE


def plate_tier(filename):
    """The scarcity band of a background, for the Plate Tier attribute."""
    f = os.path.basename(filename)
    if f == STARFIELD_BG:
        return "Ultra"
    if is_legendary_bg(f):
        return "Legendary"
    tgt = _plate_targets().get(f)
    if tgt is None:
        return "Standard"
    # The band is the plate's RANK among the distinct targets in use, rarest
    # first -- not a comparison against any literal value. An earlier version
    # split on the midpoint of the target range, which silently collapsed
    # three pinned tiers into two the moment a third target was introduced:
    # every Scarce and Uncommon plate came back "Scarce" together.
    bands = sorted({v for v in _plate_targets().values()})
    names = ["Scarce", "Uncommon", "Standard"]
    i = bands.index(tgt)
    # More pinned tiers than names: the extra ones are all the common end.
    return names[i] if i < len(names) else names[-1]

# Characters the starfield may pair with. The plate is FLAT, so the usual
# camouflage test (build_char_compat.py, which scores a body against a
# plate's LOCAL colour) degenerates -- there is one colour to clash with, and
# what decides legibility is contrast against it.
#
# Measured as mean CIE76 dE between the composited character's pixels and the
# field (#002147), over all 27: the cast runs 38.1 (chocolate sandwich
# cookie) to 103.9 (Twinkie), and the natural break is at ~75 -- below it sit
# the dark chocolate bodies (mean L* 22-40), which read as silhouettes rather
# than as characters against deep space. The 14 above it are listed here.
#
# Nothing is illegible at any point on that range (0 % of any body's pixels
# fall within dE 25 of the field, bar 1.5 % of the gummy bear), so this is an
# APPEARANCE cut, not a legibility one -- re-render the cast sheet and move
# the line if the owner's eye disagrees with the number.
#
# THAT MEASUREMENT IS AGAINST THE FIELD ALONE, and the plate is no longer
# only field: the rainbow trail runs behind the left ~57 % of a body's width
# (the cut sits at canvas x 721, bodies span 458..922). It is a partial
# reading rather than a wrong one -- the excluded bodies are dark, and dark
# against a saturated trail is the pairing this cut was never scored on. Do
# not "fix" the list on that alone: changing it moves the allocation and
# costs a rarity re-solve, so re-measure against the composited plate first.
STARFIELD_CHARS = [
    "Twinkie", "gold_waffle", "og_poptart", "glazed_doughnut", "smores",
    "sugar_doughnut", "churro", "rice_crispy_treat", "waffle", "marshmallow",
    "cyan_sherbert_ice_cream", "vanilla_ice_cream", "zebra_cake",
    "pink_sherbert_ice_cream",
]

def starfield_allowed(char_name):
    """EXACT match, not substring: 'waffle' and 'gold_waffle' are both on the
    list and a substring test cannot tell one from the other -- the repo's
    recurring failure class (see char_base_name)."""
    return char_name in STARFIELD_CHARS
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

_secret_rare_keys_cache = None


def _secret_rare_keys():
    """Sorted secret-rare filenames, from the trait folder. Empty when the
    folder is absent, which is how the tier is retired wholesale."""
    global _secret_rare_keys_cache
    if _secret_rare_keys_cache is None:
        d = os.path.join(TRAITS_DIR, SECRET_RAREZ)
        try:
            _secret_rare_keys_cache = sorted(
                f for f in os.listdir(d)
                if f.lower().endswith(".png") and is_secret_rare(f))
        except OSError:
            _secret_rare_keys_cache = []
    return _secret_rare_keys_cache


def secret_rare_number(filename):
    """Stable 1-based index (#1..#N) of a secret rare within the set, ordered
    by filename so it never shifts run to run."""
    # Read the FOLDER, not TRAIT_NAMES: the names block was removed when the
    # tier was retired, and deriving the number from it would have silently
    # numbered every restored secret rare #0. Sorted filenames give the same
    # order the names table did, so restored tokens keep their old numbers.
    keys = _secret_rare_keys()
    base = os.path.basename(filename)
    return keys.index(base) + 1 if base in keys else 0

def secret_rare_token_name(filename):
    """Drop-ready token name, e.g. 'Secret Rarez #1 — Milk Dunk'."""
    return (f"Secret Rarez #{secret_rare_number(filename)} — "
            f"{trait_name(SECRET_RAREZ, os.path.basename(filename))}")


# Who actually drew a secret rare, for the pieces made by a GUEST artist, and
# where to find them. The piece's TITLE is its display name; the artist is a
# different string for one of the two and would otherwise appear nowhere a
# collector can see.
#
# It matters unevenly. "Radbro Webring" is both the piece and the artist, so
# that one carries the name by accident. Emily Cartoons appears in no metadata
# at all — her signature is painted into the Duhnut Candy Man art and vanishes
# at thumbnail size.
#
# This lives here rather than in build_mint.py because the credit is a property
# of the ARTWORK, not of one mint run: every path that builds a secret rare's
# metadata goes through extract_metadata() and so cannot drop it.
#
# An ABSENT entry is legitimate and must never be fatal — the 23 pieces parked
# in traits/secret_rarez_retired are in-house art with no guest to credit. Only
# a guest artist's piece belongs here.
#
# Minted with the permission of both artists (confirmed by the owner, 2026-08).
# The same two links are the collection site's own attribution, in the games
# repo at src/content/artistRares.ts.
SECRET_RARE_ARTISTS = {
    "Secret_Radbro_Webring.png":   ("Radbro Webring", "https://radbro.xyz"),
    "Secret_Duhnut_Candy_Man.png": ("Emily Cartoons", "https://emilycartoons.com"),
}


def secret_rare_artist(filename):
    """(artist, url) for a guest-artist secret rare, or None for in-house art."""
    return SECRET_RARE_ARTISTS.get(os.path.basename(filename))


def secret_rare_artist_url(filename):
    """The artist's own site, for the token's external_url. None when the piece
    has no guest artist."""
    credit = secret_rare_artist(filename)
    return credit[1] if credit else None

# ---- Human-readable display names for every trait asset ----
# Keys for CHARACTERZ: the internal char_name (prefix-stripped, no .png).
# Keys for WHAT_ARE_THOSEZ: the base-name returned by wat_base_name()
#   (e.g. "layer-Bunny_Slippers"). The gorbhouse trash-cans are an ordinary
#   footwear base, so they key off "Gorbhouse" like any other.
# Keys for all other categories: the bare filename (with .png).
TRAIT_NAMES = {
    CHARACTERZ: {
        "Twinkie":                          "Twinkie",
        "Nutty_Bar":                         "Nutty Bar",
        "brownie_bite":                     "Brownie Bite",
        "chocolate_chip_cookie":            "Chocolate Chip Cookie",
        "chocolate_doughnut":               "Chocolate Doughnut",
        "chocolate_frosted_poptart":        "Chocolate Frosted Pop Tart",
        "chocolate_sandwich_cookie":        "Chocolate Sandwich Cookie",
        "churro":                           "Churro",
        "cyan_frosted_poptart":             "Cyan Frosted Pop Tart",
        "cyan_sherbert_ice_cream":          "Cyan Sherbert Ice Cream",
        "ding_dong":                        "Ding Dong",
        "glazed_doughnut":                  "Glazed Doughnut",
        "gold_waffle":                      "Gold Waffle",
        "marshmallow":                      "Marshmallow",
        "neopolitan_ice_cream":             "Neapolitan Ice Cream",
        "oatmeal_cream_pie":                "Oatmeal Cream Pie",
        "og_gummy_bear":                    "OG Gummy Bear",
        "og_poptart":                       "OG Pop Tart",
        "pink_sherbert_ice_cream":          "Pink Sherbert Ice Cream",
        "rice_crispy_treat":                "Rice Crispy Treat",
        "chocolate_ice_cream":              "Chocolate Ice Cream",
        "smores":                           "S'mores",
        "sugar_cube":                       "Sugar Cube",
        "sugar_doughnut":                   "Sugar Doughnut",
        "vanilla_ice_cream":                "Vanilla Ice Cream",
        "waffle":                           "Waffle",
        "zebra_cake":                       "Zebra Cake",
    },
    BACKGROUNDZ: {
        "Ayotollah.png":                    "Ayatollah",
        "Baked.png":                        "Baked",
        "Bubble_Trouble.png":               "Bubble Trouble",
        "Cabaret_Alley.png":                "Cabaret Alley",
        "Candy_Tundra.png":                 "Candy Tundra",
        "Cereal_Killer.png":                "Cereal Killer",
        "Choco_Falls.png":                  "Choco Falls",
        "Coder_Chick.png":                  "Coder Chick",
        "Cookboy.png":                      "Cookboy",
        "Crumble_Trail.png":                "Crumble Trail",
        "Drained_The_Swamp.png":            "Drained The Swamp",
        "Druski.png":                       "Druski",
        "Flavor_Explosion.png":             "Flavor Explosion",
        "Goo_Lagoon.png":                   "Goo Lagoon",
        "He_Needs_Some_Milk.png":           "He Needs Some Milk",
        "Im_Not_Sorry.png":                 "I'm Not Sorry",
        "Legendary_Just_Aliens.png":        "Legendary Just Aliens",
        "Legendary_Opengotchi.png":         "Legendary Opengotchi",
        "Legendary_Simplex.png":            "Legendary Simplex",
        "Legendary_Tenders.png":            "Legendary Tenders",
        "Midnight_Snack (1).png":           "Midnight Snack",
        "Nabisco.png":                      "Nabisco",
        "Tampa_Bay_Pete.png":               "Tampa Bay Pete",
        "Pink_Abyss.png":                   "Pink Abyss",
        "Psychedelics.png":                 "Psychedelics",
        "RIP_Gorbagana.png":                "RIP Gorbagana",
        "Smuckers_Blue.png":                "Smuckers Blue",
        "Snack_Pack.png":                   "Snack Pack",
        # GENERATED, not photographed: dynamic/starfield.py rebuilds it from
        # Nyan_Blank.gif. It is the one ANIMATED plate -- this PNG is frame 0
        # of a 12-frame loop, and the loop is what animation_url points at.
        "Starfield.png":                    "Starfield",
        "Straight_of_America (1).png":      "Straight of America",
        "Sugar.png":                        "Sugar",
        "Sweet_Castle_2.png":               "Sweet Castle",
        "Sweet_Shop.png":                   "Sweet Shop",
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
        "Cookie_Dough.png":                 "Cookie Dough",
        "art_mattrick_001-15-2 (1).png":    "In Cook We Trust",
        "soft_serve.png":                   "Soft Serve",
        "Abduction.png":                    "Abduction",
        "Bored_Apes.png":                   "Bored Apes",
        "Tooth_Decay.png":                  "Tooth Decay",
        "Empty_Fridge.png":                 "Empty Fridge",
        "Graham.png":                       "Graham",
        "Hurshey.png":                      "Hurshey",
        "The_2023_Las_Vegas_Incident.png":  "The 2023 Las Vegas Incident",
        "The_Miami_Mall_Incident.png":      "The Miami Mall Incident",
        "Cookboy_Chocolate.png":            "Cookboy Chocolate",
        "Starburst.png":                    "Starburst",
        "Emblem.png":                       "Emblem",
        "Store.png":                        "Store",
        "Swolex.png":                       "Swolex",
        "Clouds.png":                       "Clouds",
        "Room.png":                         "Room",
        "The_Board.png":                    "The Board",
    },
    SKINZ: {
        "layer-Skin_Alien (2).png":                 "Alien",
        "layer-Skin_Black (3).png":                 "Black",
        "layer-layer-layer-Skin_White (2).png":     "White",
    },
    EYEZ: {
        "Blue.png":                                             "Blue",
        "Cerise.png":                                           "Cerise",
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
        "Armz_Katana.png":                              "Katana",
        "Armz_Knives.png":                              "Knives",
        "Sweetardio_114 (4).png":                       "Blue Saber",
        "Sweetardio_114 (5).png":                       "Pink Saber",
        "Sweetardio_114 (6).png":                       "Cyan Saber",
        "Sweetardio_115 (11).png":                      "Dual Uzis",
        "layer-layer-layer-layer-AK15.png":             "AK15",
        "layer-layer-layer-layer-AR47.png":             "AR47",
        "layer-layer-layer-layer-Military_Brat.png":    "Military Brat",
        "layer-layer-layer-layer-Nerf_Blaster.png":     "Nerf Blaster",
    },
    # Keyed by wat_base_name() result -- the trash-cans included.
    WHAT_ARE_THOSEZ: {
        # Every one of these is a novelty SLIPPER, the gorbhouse included (it
        # is a pair of trash-can slippers), so every value says so. "Monster"
        # was a truncation of Cookie Monster that read as a creature rather
        # than footwear, and bare "Pepe" / "Shiba" / "Bunny" did the same.
        "Cookie_Monster_Slippers":  "Cookie Monster Slippers",
        "Gorbhouse":                "Gorbhouse Slippers",
        "layer-Bunny_Slippers":     "Bunny Slippers",
        "layer-Pepe":               "Pepe Slippers",
        "layer-Shiba":              "Shiba Slippers",
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
    # SECRET_RAREZ has no names block ON PURPOSE, and the live tier depends on
    # it: secret_rare_number() reads the folder rather than this table, and
    # display names fall back from the filenames, where _fallback_display_name
    # strips the Secret_ tier marker. "Secret_Duhnut_Candy_Man.png" therefore
    # gives "Duhnut Candy Man" with nothing to keep in sync here.
    #
    # That fallback is now load-bearing rather than a retired-tier leftover:
    # the two guest-artist 1/1s in traits/secret_rarez are named through it.
    # Adding a block here would take the strip path out of service again,
    # which is exactly how it stayed broken until 33dbdff -- every secret rare
    # had an explicit name until there were none at all.
}


def _fallback_display_name(filename):
    """Derive a readable display name from a raw filename when no explicit
    mapping exists: strip the structural prefixes, extension, numeric index
    suffixes, and convert underscores to spaces.

    `Secret_` is stripped for the same reason `layer-` is: it is a TIER
    MARKER that is_secret_rare() matches on, not part of the artwork's name.
    Leaving it in produced "Secret Rarez #1 - Secret Milk Dunk" against the
    "Secret Rarez #1 - Milk Dunk" that secret_rare_token_name's own docstring
    specifies. It only became reachable when the tier was retired and
    TRAIT_NAMES[SECRET_RAREZ] went with it, which is why nothing caught it:
    every secret rare had an explicit name until there were none at all."""
    import re as _re
    name = os.path.basename(filename)
    name = _re.sub(r'\.png$', '', name, flags=_re.IGNORECASE)
    name = _re.sub(r'^(layer-)+', '', name)
    name = _re.sub(r'^' + _re.escape(SECRET_RARE_PREFIX), '', name)
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
        attrs = [{"trait_type": "Secret Rarez",
                  "value": f"#{secret_rare_number(fn)} {name}"}]
        # Guest artists are credited on the piece itself. Only the guest-drawn
        # 1/1s carry this, which makes Artist a rarity signal as well as a
        # credit: a marketplace shows it as a trait held by 2 of 4444.
        credit = secret_rare_artist(fn)
        if credit:
            attrs.append({"trait_type": "Artist", "value": credit[0]})
        return attrs

    overlay_filenames = set(BG_OVERLAY_PAIRS.values())

    attrs = {}  # trait_type -> value, filled in order below
    bg_file = None  # the plate's filename, for its Plate Tier band

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
                if "Background" not in attrs:
                    attrs["Background"] = trait_name(bg_cat, fname)
                    bg_file = fname

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

        # Footwear. The gorbhouse ships a base like every other slipper, so
        # the regex below names it too; the overlay branch is the fallback for
        # a stack that somehow carries only the front piece.
        elif p.startswith(wat_prefix + os.sep):
            if "gorbhouse" in fname.lower() and "overlay" in fname.lower():
                attrs.setdefault("Footwear",
                                 trait_name(WHAT_ARE_THOSEZ, GORBHOUSE_BASE))
            else:
                m = _re.match(r"(.+?)_base(?:\s*\(\d+\))?\.png$", fname, _re.IGNORECASE)
                if m:
                    base = m.group(1)
                    attrs.setdefault("Footwear", trait_name(WHAT_ARE_THOSEZ, base))

    # Plate Tier rides directly after Background, so the band reads next to
    # the plate it describes rather than at the end of the attribute list.
    if "Background" in attrs and bg_file:
        attrs["Plate Tier"] = plate_tier(bg_file)

    # Return in canonical order; omit absent optional traits
    order = ["Character", "Background", "Plate Tier", "Skin", "Eyes", "Mouth",
             "Footwear", "Arms", "Sticker"]
    return [{"trait_type": k, "value": attrs[k]}
            for k in order if k in attrs]


# ---- OpenSea token metadata ----
COLLECTION_NAME = "Sweetardio Collection"
COLLECTION_DESCRIPTION = (
    "Sweetardio Collection — 4,444 hand-crafted sweet degens. Every trait "
    "is composited and graded for the cleanest, most collectible look on-chain."
)


# Mime types for the file extensions this collection actually emits. Used
# to type properties.files[] -- a marketplace that reads the file list
# rather than the bare `image` / `animation_url` fields needs the type to
# know what it is being handed.
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".webp": "image/webp", ".gif": "image/gif", ".mp4": "video/mp4",
         ".webm": "video/webm", ".html": "text/html", ".glb": "model/gltf-binary"}


def _mime(uri):
    return _MIME.get(os.path.splitext(str(uri).split("?")[0])[1].lower(),
                     "application/octet-stream")


def token_metadata(attributes, token_id=None, image=None,
                   name=None, description=None, animation_url=None,
                   symbol=None, seller_fee_basis_points=None,
                   creators=None, external_url=None):
    """Wrap an attributes list (from extract_metadata) into a complete,
    OpenSea-compatible token metadata object.

    token_id : int  -> default name becomes "Sweetardio Collection #<id>".
    image    : str  -> image URI/path (e.g. "ipfs://CID/123.png" or "123.png").

    animation_url, if given, ALSO builds the Metaplex `properties` block --
    `files[]` typed by extension and `category: "video"` -- because on
    Solana the bare field is not enough on its own. Marketplaces and
    wallets differ in which they read, and a token that carries one without
    the other plays on some surfaces and not others.

    `image` MUST stay a still even when an animation is attached. Every
    grid, thumbnail, search result and push notification uses it; animation
    only ever plays in a detail view, often only on hover or click.

    symbol, seller_fee_basis_points and creators are Metaplex fields with
    no sensible default -- royalties and payout addresses are the owner's
    decision, not this function's -- so they are emitted only when passed.

    Keys are ordered name, symbol, description, image, animation_url,
    external_url, attributes, properties for clean files."""
    meta = {}
    meta["name"] = name or (f"{COLLECTION_NAME} #{token_id}"
                            if token_id is not None else COLLECTION_NAME)
    if symbol is not None:
        meta["symbol"] = symbol
    meta["description"] = description or COLLECTION_DESCRIPTION
    if seller_fee_basis_points is not None:
        meta["seller_fee_basis_points"] = seller_fee_basis_points
    if image is not None:
        meta["image"] = image
    if animation_url is not None:
        meta["animation_url"] = animation_url
    if external_url is not None:
        meta["external_url"] = external_url
    meta["attributes"] = attributes

    files = []
    if image is not None:
        files.append({"uri": image, "type": _mime(image)})
    if animation_url is not None:
        files.append({"uri": animation_url, "type": _mime(animation_url)})
    props = {}
    if files:
        props["files"] = files
    if animation_url is not None:
        # Not a typed field of the Metaplex standard -- it rides the
        # JsonMetadata type's open index signature -- but it is what makes
        # a surface treat the token as playable rather than as a still with
        # an extra URL hanging off it. Convention, and load-bearing.
        props["category"] = "video"
    if creators is not None:
        props["creators"] = creators
    # Only attach `properties` when there is something in it, so a plain
    # static mint keeps emitting byte-identical metadata to before.
    if props and (animation_url is not None or creators is not None):
        meta["properties"] = props
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
# churro, twinkie, poptarts, all ice creams, and the zebra cake.
#
# The zebra cake is a flat hexagonal wafer whose bottom edge is a straight
# horizontal line, with no legs and nothing to put a shoe on. Rendered against
# all four footwear options the slippers simply park under it with a gap and
# the body hovers above them -- it reads as shoes left beside a floating
# biscuit rather than worn. The gorbhouse is no better: a can under a flat
# hexagon has the same problem, which is why this is a WHOLE-footwear
# exclusion and not a slippers-only one.
#
# It stays listed in GORBHOUSE_CHARS above even though this list wins, which
# is the convention twinkie and the poptarts already follow -- membership
# there records eligibility, and this list is what actually decides.
EXCLUDE_WAT_CHARS = [
    "cyan_sherbert_ice_cream",
    "neopolitan_ice_cream",
    "vanilla_ice_cream",
    "chocolate_ice_cream",
    "pink_sherbert_ice_cream",
    "gummy_bear",
    "twinkie",
    "nutty_bar",
    "churro",
    "poptart",
    "zebra_cake",
]

# Character-specific armz: each file here may ONLY appear on characters
# whose name contains one of the listed substrings (individuals or groups,
# e.g. "ice_cream" covers every *_ice_cream character; "gummy_bear" covers
# all bear color variants). Armz files NOT in this map are generic and can
# pair with any character.
#
# EMPTY BY DESIGN. There used to be seven locked weapons — five files all
# named "Katana" in the metadata and two named "Knives" — because each
# character family was a different size and needed its own copy at its own
# scale. CHAR_SCALE has since brought the whole cast to one size, so one
# katana and one pair of knives fit everyone and the duplicates were retired
# to traits/armz_originals/. The mechanism stays for a genuinely
# character-specific weapon later; the arm draw below respects it.
ARMZ_CHAR_LOCK = {}

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
    "vanilla_ice_cream",
    "chocolate_ice_cream",
    "pink_sherbert_ice_cream",
    "twinkie",
    "nutty_bar",
    "churro",
    # bears are CHAR_SCALE-adjusted and aligned to the ice-cream family's
    # ground line (1111) via CHAR_Y_ADJUST; NO_OFFSET so the +150
    # footwear-less drop never disturbs that placement
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
# to the churro line (1111), and ice-cream cone tips / gummy-bear feet to
# that same 1111 line now that CHAR_SCALE brings both down to cast size.
# poptart/twinkie keep their owner-tuned overshoot values (2026-06).
CHAR_Y_ADJUST = {
    "poptart": -65,
    "twinkie": 45,
    # The five regenerated ice creams (vanilla, neopolitan, chocolate, cyan
    # and pink sherbert) all measure the same body, so they take the same trim
    # onto the shared 1111 cone-tip line. The three still on the old art keep
    # their own values below. "rocky road" named the third of these until the
    # ice cream names were corrected against their art; it is not a character.
    "vanilla_ice_cream": -18,
    "neopolitan_ice_cream": -21,
    # -18 follows the CHOCOLATE body. It was mis-named pink_sherbert until the
    # ice cream names were corrected against their art; the value was measured
    # from the art, so it moved with it.
    "chocolate_ice_cream": -18,
    "cyan_sherbert_ice_cream": -21,
    "pink_sherbert_ice_cream": -21,
    # Centred characters use CHAR_Y_ADJUST only when they WEAR FOOTWEAR (bare,
    # CENTERED_FOOTWEARLESS_DY places them instead), so this value is purely
    # the shod position. At 50 the cookie sat 52px below its six siblings,
    # which land in a 953-959 band, and its body sank into the slippers
    # instead of resting on them. -6 puts it at 955, with the group.
    "chocolate_sandwich_cookie": -6,
    "sugar_cube": 42,
    "gold_waffle": -18,        # measured separately from the plain waffle; the
                               # key must stay distinct or the "waffle" substring
                               # claims it and lifts it 20px too high
    "waffle": -38,
    "ding_dong": 34,
    "og_gummy_bear": 32,      # rescaled; feet on the shared ground line (1111)
    "sugar_doughnut": -26,
    "brownie_bite": 22,
    "zebra_cake": -20,         # footwear-excluded now, so only the BARE path
                               # runs: -20 here plus FOOTWEARLESS_DY -2 gives
                               # the same -22 the bare case always had. Kept as
                               # a pair rather than collapsed to -22, so the
                               # shod value is still correct if it ever wears
                               # footwear again. Originally: the bare
                               # stance is held put by FOOTWEARLESS_DY
    "chocolate_doughnut": -18,
    "glazed_doughnut": -18,
    "oatmeal_cream_pie": 14,
    "churro": 21,              # joins Twinkie and Nutty Bar on the 1132 bar
                               # line; it was the odd one out at 1111
    "nutty_bar": -20,          # bar body, stands with the Twinkie at 1132;
                               # re-derived after the art was squashed to
                               # aspect 1.98 (was -118 at aspect 2.33)
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
# footwear-less position, where the normal CHAR_Y_ADJUST and the +150 drop are
# both suppressed and this value places the body outright.
#
# Align these by BOTTOM, on the same 1096 line the standing-bare characters
# use. They were previously aligned by BODY CENTRE onto the canvas centre
# (y=696), on the reasoning that a round body floats and a shared bottom
# pushes the biggest bodies high. Centre-alignment has the mirror-image flaw,
# and it is the worse one: it makes the float depend on body height, so the
# SHORTEST bodies hang highest. This group spans 639-759px tall, so their
# bottoms spread 1017-1076 — the ding_dong (shortest at 639) ended up 79px
# above where the bare standing cast plants, the cookie 65px, while the sugar
# doughnut sat only 20px off. It also straddled GROUND_SHADOW's 1053
# ground_line, so half the group cast a floating drop shadow and half a
# grounded contact pool.
#
# A shared bottom makes every bare character in the collection sit in one
# 1084-1109 band and gives them all the same contact shadow. The tops now
# vary by body height instead, which is what resting on a floor looks like.
# Each value is the character's own CHAR_Y_ADJUST plus a SHARED DROP, so the
# group keeps one tight bare-bottom band and the drop is a single number to
# tune. The drop is 70.
#
# It was 139, which grounded these bodies onto the same 1084-1109 band the
# STANDING characters use -- and that is what made them read as sitting too
# low. The drop carries the face with it, so at 139 a bare chocolate chip
# cookie put its eyes at y 735 against y 598 for the same cookie in slippers,
# and the shorter the body the worse it got: ding dong +139 onto the shortest
# body in the cast (635px) left it pinned to the floor with a third of the
# frame empty above its head.
#
# Grounding them also contradicted the reason CENTERED_CHARS exists, which is
# that "a round shape lowered to the floor looks like it is resting awkwardly,
# not standing". A round body has no feet to put on a floor; 70 lets it sit
# centred, which is the whole point of the list.
#
# THE GROUP IS DELIBERATELY HIGHER THAN THE STANDING CAST after this: bare
# bottoms land 1023-1027 against 1082-1110 for the standing characters. That
# is the feature working, not a regression -- these bodies float, the standing
# ones stand. Chosen off a rendered ladder at 139 / 100 / 70 / 40; past ~40
# they start to read as floating rather than centred.
_CENTERED_DROP = 70
CENTERED_FOOTWEARLESS_DY = {
    "glazed_doughnut": -18 + _CENTERED_DROP,
    "chocolate_doughnut": -18 + _CENTERED_DROP,
    "sugar_doughnut": -26 + _CENTERED_DROP,
    "chocolate_sandwich_cookie": -6 + _CENTERED_DROP,  # two-part asset: the
                                      # bbox bottom is the BACK wafer, which
                                      # is the lowest thing it rests on, so
                                      # measuring by bbox is right here even
                                      # though the front disc sits higher.
    "chocolate_chip_cookie": -2 + _CENTERED_DROP,
    "oatmeal_cream_pie": 14 + _CENTERED_DROP,
    "ding_dong": 34 + _CENTERED_DROP,
}

def centered_footwearless_dy(char_name):
    return next((dy for k, dy in CENTERED_FOOTWEARLESS_DY.items()
                 if k in char_name.lower()), 0)

# Extra vertical trim (px, +down) applied ONLY in the footwear-less drop case
# (apply_offset True: an offset-eligible character standing with no footwear).
# This lets a character's grounded/footwear placement (CHAR_Y_ADJUST) stay
# fixed while nudging only its footwear-less standing height — needed when a
# character looks right with shoes but too low/high standing bare. Default 0.
# These three were raised because the full +150 drop bottomed them out, but
# the lift overshot and left them floating 34-58px above the ground band while
# every other standing character sat on it (measured by verify_placement.py).
# They now land on the band's TOP edge (1084): still the highest stance the
# approved band allows, which is what the original tuning was reaching for,
# but inside it rather than above it.
FOOTWEARLESS_DY = {
    "sugar_cube": -23,   # bare bottom -> 1084 (was -45, floating at 1062)
    "smores": -29,       # bare bottom -> 1084 (was -75, floating at 1038)
    "zebra_cake": -2,    # keep the (perfect) bare stance while CHAR_Y_ADJUST
                         # raises only the with-footwear case.
                         # CHAR_Y_ADJUST -37 overshot: it put the shod bottom
                         # at 940 against a cast band of 953-961, so the body
                         # rode ~16px further out of the slipper than every
                         # other wearer and read as too tall. -20 measures
                         # back at 957, mid-band; this -2 holds the bare
                         # bottom at 1105, exactly where it was.
    "brownie_bite": -23, # bare bottom -> 1084 (was -65, floating at 1042)
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
    # The ice creams were 43% taller than the rest of the cast (1067px vs a
    # 743px median) and their cone tips sat ~180px BELOW the ground band every
    # other character stands on, so they read oversized and broke the floor.
    # 0.74 brings the body to cast height and the cone tip onto the band.
    "ice_cream": 0.74,
    # The bears had been scaled UP to 1.19 to match the old, oversized
    # ice-cream family, so they inherited the same problem. 0.881 puts their
    # feet on the same line as the rescaled cone tips and their width (581px)
    # alongside the rescaled ice creams (582px), keeping the two a family.
    "gummy_bear": 0.881,
    # The regenerated bar came in at 1139 tall against a cast median of 771 —
    # a plank. 0.93 was chosen to fit it on the canvas, but a UNIFORM scale
    # cannot fix a proportion: every value that brought its height into line
    # left it a narrower plank with a smaller face. The art has since been
    # squashed vertically to aspect 1.98 (asset_assessment/squash_character.py),
    # which matches the Twinkie, the cast's other standing bar. 0.93 is kept
    # because it is what its CHAR_Y_ADJUST and the bar line are tuned to.
    "nutty_bar": 0.93,
}

def char_scale(char_name):
    return next((s for k, s in CHAR_SCALE.items()
                 if k in char_name.lower()), 1.0)

def char_base_name(fname):
    """A characterz filename -> the internal character base-name.

    Strips the authoring prefixes and a trailing " (n)" duplicate marker.
    The longest prefix must go first: "layer-after_skinz_" before
    "after_skinz_", otherwise "layer-after_skinz_churro" becomes
    "layer-churro" and never matches its own file again. A bare "layer-" is
    deliberately NOT stripped — some assets carry it as part of their name.

    This is the ONE definition of a character's name. It builds the cast list
    AND resolves a name back to its art, so the two cannot disagree; keeping
    them separate is what let 'waffle' resolve to gold_waffle's file (see the
    body-file lookup in generate_random_combination)."""
    name = (fname.replace("layer-after_skinz_", "")
                 .replace("before_skinz_", "")
                 .replace("after_skinz_", "")
                 .replace(".png", ""))
    return re.sub(r"\s*\(\d+\)", "", name).strip()

def body_after_skin(char_name, fname):
    """Always True: the BODY draws AFTER (on top of) the skin ball, for every
    character. The ball is composited first and the visible face is whatever
    shows through the body's face hole — no skin is ever painted over a
    character.

    This used to switch on the `after_skinz_` / `before_skinz_` filename
    marker, with two per-character exception lists on top of it
    (SKIN_ON_TOP_CHARS for the churro, BODY_OVER_SKIN_CHARS for the gummy
    bears and the nutty bar). All three are gone: the filename prefixes now
    record only how the art was authored, not how it is composited.

    The consequence to keep in mind is that flipping a character to
    body-over-skin SHRINKS its visible face from the whole ball to the hole,
    and the ball must then reach the hole's rim for every skin x eye pair —
    see FACE_HOLE_BOTTOM_OVERRIDE and asset_assessment/verify_face_coverage.py.
    The signature keeps `fname` so the call sites read the same and a future
    per-file rule has somewhere to go.
    """
    return True

# ---- per-arm intrinsic scale (about the hand line) ----
# Some arm art was exported larger than the character family. ARM_SCALE
# shrinks a specific arm file about ARM_SCALE_PIVOT (the held-weapon hand
# line) so the fists stay attached to the body while the weapon scales down.
# It composes on top of any character CHAR_SCALE, so a scaled character still
# gets a proportionally adjusted arm.
ARM_SCALE_PIVOT = (694, 1040)

# Arms composite at a FIXED canvas row and are NOT repositioned RELATIVE TO
# THE BODY. (The whole figure does rise when armed -- see ARMED_LIFT above --
# but that moves body and arm together and changes nothing between them.)
# Tried and reverted (2026-08): shifting the arm to follow each body -- by a
# fraction of body height, by a fixed distance above the body's base, and by
# how far the body's base differs from the cast median. All three fixed the
# short characters whose weapon hung past their bottom edge and all three broke
# something worse, because the FACE is pinned at a fixed canvas position while
# bodies are not: on the squat bodies (sugar cube, ding dong, marshmallow) every
# variant rode the weapon up over the eyes, ~13,000 px of gun across the face.
#
# A FOURTH attempt, also reverted, got closest and is the most instructive. It
# was a one-sided CLAMP: lift an arm only by however far it hung past the
# body's base, never push one down, and allow 55px of overhang so the weapon
# still reads as touching the ground. That removed the overhang everywhere
# (+117px worst case -> +55) and left 9 of 27 characters untouched. It still
# lost, for a reason no formula over a bbox can dodge: the clamp measures the
# WEAPON'S bbox, and some weapons are drawn long on purpose. The three sabers
# span 122..1302 with the blade past the feet, so clamping them hauled the
# blade up across the eyes on 8 pairings; exempting tall art then left the Dual
# Uzis doing the same thing to the sugar cube (844px of gun over its eyes).
#
# The owner's call, after seeing all four rendered: no clamp. A weapon hanging
# below a short body looks better than any of the corrections that move it.
#
# What DID work was the owner's own suggestion: stop trying to move the arm and
# raise the whole figure instead (ARMED_LIFT). It solves what the four attempts
# were chasing -- the figure no longer looks sunk through its own shadow --
# without touching a single relationship inside the figure, which is precisely
# why it cannot reproduce any of their failures.
#
# Worth knowing if this is ever revisited: ARM_SCALE_PIVOT (694, 1040) is a
# SCALING pivot, not a hand line -- y=1040 is outside most of the arm art
# entirely (Cash spans 625..908, the sabers 122..1302), so it is not a usable
# anchor. Every approach here failed the same way, by inferring where the hands
# are from a bounding box. A real fix needs a per-arm HAND MARKER authored into
# the art, or per-character arm offsets authored by eye -- not a formula.
# ---- armed figures ride slightly higher ----
# A held weapon is drawn to hang below the fists, so on the short bodies the
# gun reached past the character's own feet -- up to 117px, and 109px below the
# CONTACT SHADOW, which excludes arms and so reads as the floor. The figure
# looked like it had sunk through the ground it was standing on.
#
# This lifts the WHOLE figure -- body, face, arm, footwear, and therefore the
# shadow derived from them -- by a flat amount whenever a weapon is held, so
# the arm's pose on the body is untouched. That is the difference from the four
# attempts that were reverted: every one of those moved the arm RELATIVE to the
# body, and all four either rode the gun up over the eyes on the squat
# characters or destroyed the sabers' blade-down pose. Moving both together
# cannot do either, because it changes no relationship inside the figure.
#
# Only characters whose weapon actually overhangs are lifted; a character whose
# arm already sits inside its own footprint (the ice creams, churro, the Nutty
# Bar, Twinkie) is left exactly where it was.
ARMED_LIFT = 70


def armed_lift(char_file, arm_file, cscale):
    """Px to raise a whole figure that is holding a weapon. 0 when the weapon
    does not reach past the body's base."""
    if not ARMED_LIFT or not char_file or not arm_file:
        return 0
    try:
        _, _, _, by = _opaque_bbox(os.path.join(TRAITS_DIR, CHARACTERZ,
                                                char_file))
        _, _, _, ay = _opaque_bbox(os.path.join(TRAITS_DIR, ARMZ, arm_file))
    except (OSError, ValueError):
        return 0
    piv = CHAR_SCALE_PIVOT[1]
    overhang = ay - (piv + (by - piv) * cscale)
    return ARMED_LIFT if overhang > 0 else 0


# ---- per-character arm offset ----
# Authored BY EYE, per character, which is the only thing that works here: four
# attempts at a formula over the body bbox were reverted (see below), because a
# bounding box cannot tell where a character's hands should be.
#
# Negative raises the arm on that body. Applied to the arm layer ONLY, so it
# does move the weapon relative to the body -- the difference from the reverted
# formulas is that each value is checked against that specific character's face
# instead of being derived for all 27 at once.
#
# ding_dong: its arm centre sat at 92.2 % of body height against a cast band of
# 67-88 %, second lowest of the 27, because it is a short round body (636px)
# and the arm composites at a fixed canvas row.
ARM_CHAR_DY = {
    "ding_dong": -40,   # 92.2 % -> 85.9 %, in line with the doughnuts (86.1 %)
}

# Per-(character, arm) overrides, which WIN over the per-character value above.
# Needed because arms differ in pose, so one number per character cannot fit
# them all on a short body:
#   Dual Uzis are held lowest of any weapon -- still at 95.6 % of the ding
#     dong's body height even after -40 -- so they take -55.
#   Cash is the opposite: the fists hold the notes fanned UPWARD at chest
#     height, so it was never sitting low, and -40 put the notes across the
#     eyes (0 px of overlap at 0, 489 px at -40). It opts out at 0.
#
# THE GUMMY BEAR AND THE THREE SABERS take +100, the only positive entry: it
# pushes an arm DOWN rather than lifting it.
#
# The bear is the one character whose body art carries its own arms -- two
# ~6,700px lobes at x 396..451 and x 922..977, y 751..911, tips at (429,839)
# and (944,839). Every armz asset lays gloved hands over that, and the
# pairing reads right only when the added glove lands ON the bear's own arm.
# Measured, right glove vs that right-arm tip:
#
#     Knives          dx  +3  dy  -18     its hand
#     Military Brat   dx  -1  dy  -55     its hand
#     Cash            dx +57  dy  +16     its hand
#     Dual Uzis       dx +128 dy  -86     in front of the torso
#     AK15            dx +244 dy  +22     in front of the torso
#     the 3 sabers    dx -59  dy +263     a hand floating above an orphaned arm
#
# The saber is the only asymmetric pose in the set -- it holds its hands
# 187px apart vertically where every other two-handed arm keeps them within
# 0-93px -- so its LEFT glove lands on the bear's left arm (dx +5, dy +75)
# and reads fine while the right rides up by the head, stranding the right
# arm below it.
#
# +100 is as far down as the pose can go and stay in frame: the blade spans
# y 84..1263 at rest and 184..1363 at +100, against a 1393 canvas. It takes
# the glove's coverage of the bear's own arms from 32 % to 64 %, which
# closes most of the gap but NOT all of it -- the arm tip still shows past
# the hilt. Chosen off a rendered ladder (0/+40/+70/+100/+130/+160); +130
# and beyond clip the blade. Removing the artefact outright needs a bear
# body authored without its own arms for the armed case, which is art that
# does not exist yet.
ARM_CHAR_ARM_DY = {
    ("ding_dong", "Sweetardio_115 (11).png"): -55,   # Dual Uzis
    ("ding_dong", "Arms_Cash.png"): 0,
    ("og_gummy_bear", "Sweetardio_114 (4).png"): 100,   # Blue Saber
    ("og_gummy_bear", "Sweetardio_114 (5).png"): 100,   # Pink Saber
    ("og_gummy_bear", "Sweetardio_114 (6).png"): 100,   # Cyan Saber
}


def arm_char_dy(char_name, arm_file):
    """Vertical offset for THIS character holding THIS arm, authored by eye."""
    if (char_name, arm_file) in ARM_CHAR_ARM_DY:
        return ARM_CHAR_ARM_DY[(char_name, arm_file)]
    return ARM_CHAR_DY.get(char_name, 0)


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

# The gorbhouse's footwear BASE NAME, i.e. what wat_base_name() returns for
# Gorbhouse_base.png. It is the key that carries the trash-cans through the
# ordinary footwear path -- the base/overlay layer pair, extract_metadata's
# Footwear attribute and trait_name() all key off it -- so it must keep
# matching the filename exactly.
GORBHOUSE_BASE = "Gorbhouse"

# ---- per-footwear geometry ----
#
# WAT_CHAR_LIFT: px to raise the CHARACTER (body, face, arms — never the
# footwear) when it wears this base. Default 0, and four of the five need it.
#
# It exists because a slipper's SILHOUETTE decides how buried the body looks,
# not its height. Measured per-column tops: the bunny/pepe/shiba/monster
# taper — only ears, eyes and ankle stubs reach the asset's top, and 90 % of
# their width starts at y 972–1006. The gorbhouse is a flat-topped cylinder:
# its 90th percentile column top is y 895. So at one shared body line the
# cans cover 37.2 % of their own mass against 28–30 % for every other
# slipper, and the body sits 63px BELOW the point where the can's bulk
# begins where every other slipper puts it 17–49px ABOVE. Rendered as a
# ladder (0 / -40 / -70 / -95 / -120), -70 is where the black ankle stubs
# authored into the can art read as short legs and the body still rests on
# the lids; -95 and beyond floats it.
#
# NOT a per-character value: it is a property of the SLIPPER, so it applies
# to all six gorbhouse wearers identically and needs no per-character tuning.
WAT_CHAR_LIFT = {
    "Gorbhouse": 70,
}

def wat_char_lift(wat_base):
    return WAT_CHAR_LIFT.get(wat_base, 0) if wat_base else 0

# WAT_SCALE / WAT_SCALE_PIVOT: intrinsic scale for a footwear asset, about a
# pivot in the art's own space. Same mechanism as the arms' ARM_SCALE.
#
# The Cookie Monster was authored oversized against the rest of the set.
# Measured on the SOLID art (alpha > 200 — the soft drop shadow baked into
# four of the five assets makes any lower threshold read as extra sole):
#
#     slipper          one foot w   sole      height
#     Cookie Monster          327   1168         345
#     Pepe                    287   1147         329
#     Shiba                   286   1142         309
#     Gorbhouse               282   1144         323
#     Bunny                   256   1147         321
#
# So it is ~14 % wider than the cast mean and its sole sits 23px below a
# 1142-1147 band the other four agree on — meaning a character wearing it
# stood on a lower floor than everyone else, contact shadow and all.
#
# 0.88 puts one foot at 287 wide: EXACTLY Pepe's, the largest of the other
# four, rather than smaller than them — which is what "slightly oversized"
# asks for. The pivot is solved against the real render path, not by algebra
# on the bbox: scale_about resamples, so the threshold that defines "sole"
# moves under it. y 985 is the value that measures back as sole 1145, dead
# centre of the band; x 716 is the pair's own centre, so it does not drift.
# Re-solve both if the scale changes.
WAT_SCALE = {
    "Cookie_Monster_Slippers": 0.88,
}
WAT_SCALE_PIVOT = {
    "Cookie_Monster_Slippers": (716, 985),
}

def wat_scale(wat_base):
    """(scale, pivot) for a footwear base; (1.0, None) when it is native."""
    if not wat_base:
        return 1.0, None
    return WAT_SCALE.get(wat_base, 1.0), WAT_SCALE_PIVOT.get(wat_base)

def _wat_layer(path, wscale, wpivot):
    """One footwear layer. offset=False ALWAYS: a slipper is composited at the
    position it was authored at, and the character is moved to meet it (that
    is what CHAR_Y_ADJUST and WAT_CHAR_LIFT are for). Every file of a pair —
    base and overlay(s) — must take the same scale and pivot, or the front
    piece slides off the back one."""
    layer = {"path": path, "offset": False}
    if wpivot is not None and abs(wscale - 1.0) > 0.001:
        layer["fscale"] = wscale
        layer["fcenter"] = wpivot
    return layer

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
# ---- optional-trait rates (arms, footwear, sticker) ----
# DERIVED, never declared. The exact mint counts in the "optional" block of
# traits/rarity_weights.json are the single source of truth: build_mint.py
# slot-allocates them, and these rates are computed from the same numbers, so
# a one-off render is a real sample of the mint rather than a different
# collection that happens to share the art.
#
# They used to be declared twice — exact counts in build_mint, independent
# rates here — and they silently disagreed. Sheets showed arms at 34.7 %
# against a mint of 15.9 %, so every sample sheet overstated how armed the
# collection was by more than double, and it was invisible because nothing
# compared the two. verify_generator_rules.py now fails if they drift.
#
# Each slot rolls INDEPENDENTLY. The previous scheme rolled "how many optional
# traits" and then picked that many slots uniformly, which meant a slot could
# not be common while its pool-mates were rare (that is what pinned stickers
# at ~18 %), and the per-slot rate moved with how many slots the character
# happened to have available.
#
# Footwear is the one that is not a straight division: it is only offered to
# characters that can wear it, so the roll has to be scaled up by the share of
# tokens where the slot exists at all. That share is MEASURED, not assumed —
# 12 of 27 are wat-excluded, but the pinned character counts skew the mix, so
# the uniform 15/27 = 0.556 is wrong.
def _optional_rates():
    try:
        with open(RARITY_PATH) as f:
            o = json.load(f).get("optional") or {}
        n = float(o.get("supply") or 0) or None
        if not n:
            raise ValueError("no supply")
        avail = float(o.get("footwear_availability") or 1.0)
        return (sum(o["arms"].values()) / n,
                min(1.0, (sum(o["footwear"].values()) / n) / max(avail, 1e-6)),
                o["sticker_total"] / n)
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError):
        # missing/broken file -> the pre-rarity behaviour, not a crash
        return 0.33, 0.33, 0.95


ARM_RATE, FOOTWEAR_RATE, STICKER_RATE = _optional_rates()


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

# ---- mouth shadow (cast onto the SKIN BALL) ----
# Two strengths, because the mouths are two different kinds of object.
#
# MOUTH_PROP_SHADOW is for the two that are three-dimensional props genuinely
# standing off the face: the lit joint and the lollipop.
#
# MOUTH_SHADOW is for the other seven, the line-art mouths. They were given
# nothing at first, on the reasoning that a shadow embosses art painted into a
# face. Rendered three ways once the eyes had shadows, that turned out to be
# half right: at the eyes' strength the thin line mouths DO emboss, but with
# no shadow at all they float, and they float conspicuously next to eyes that
# no longer do. A lighter shadow seats them without the embossing. So the
# distinction is strength, not presence.
#
# It rides the generic per-layer shadow in create_image(), which clips to the
# foreground built so far, so the shadow lands on the skin ball and the body
# and can never spill onto the background plate. Offset DOWN AND RIGHT — the
# key light is upper-left (CLAUDE.md), same as every other cast shadow here.
# Set to None to disable.
MOUTH_PROP_SHADOW = {"blur": 7, "opacity": 0.42, "dx": 9, "dy": 11}
MOUTH_SHADOW = {"blur": 5, "opacity": 0.26, "dx": 5, "dy": 7}

# ---- eye shadow (cast onto the SKIN BALL) ----
# The eyes are the last thing on the face still standing off the ball with
# nothing under them. Everything else that sits proud of a surface now drops a
# shadow -- the mouth props onto the skin, the hole rim onto the ball, the
# character onto the plate -- and at a face zoom the eyes read as stickers
# because of it, most obviously the brow-style assets, which are floating
# black shapes on a lit sphere.
#
# Unlike the mouths this applies to EVERY eye, because every eye asset is a
# thing lying on the face rather than a marking painted into it: a sclera, a
# lens, a moulded brow. It rides the generic per-layer shadow, which clips to
# the foreground built so far, so it lands on the ball and the body and can
# never reach the plate. Offset down and right for the top-left key.
# Set to None to disable.
EYE_SHADOW = {"blur": 6, "opacity": 0.36, "dx": 7, "dy": 9}
MOUTH_PROP_FILES = {
    "layer-Mouth_Smoke (1).png",
    "layer-Mouth_Lollipop (1).png",
}

# ---- face-inset shadow (the hole's rim, cast ONTO the skin ball) ----
# The ball sits BEHIND the body and shows through the face hole, so the hole
# is a recess and its rim occludes it. Without this the ball is lit as a free
# sphere floating in a hole, which is why a face can still read as pasted
# behind the body rather than set into it: there is no contact anywhere the
# two meet.
#
# Two terms, both confined to the hole (body transparent AND ball opaque), so
# nothing here can touch the body, the plate or the silhouette:
#   cast   the rim's own shadow, the body alpha pushed DOWN AND RIGHT by the
#          top-left key (CLAUDE.md) and blurred, so the shadow hugs the
#          hole's upper-left interior and falls away across the face
#   ao     contact occlusion all the way round the rim, unoffset and tighter,
#          so the ball darkens slightly wherever it meets the hole edge
#
# Applied after the body and BEFORE the eyes and mouth, so the face features
# sit on top of the shading rather than under it.
#
# Owner-picked off a rendered ladder (2026-08, "deep looks better"): the
# deepest of the four candidates, roughly 1.4x the mid setting. Set to None
# to disable.
FACE_INSET_SHADOW = {
    "cast_blur": 26,
    "cast_opacity": 0.55,
    "cast_dx": 15,
    "cast_dy": 17,
    "ao_blur": 9,
    "ao_opacity": 0.40,
}

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
#   dx, dy      shadow offset in px (+dx = right, +dy = down). Used by the
#               contact pool, which sits under its caster regardless of the
#               key light, so dx stays 0 and a small +dy seats it just below
#               the feet.
#   drop_dx,    same, for "drop" mode only. The collection's key light comes
#   drop_dy     from the TOP LEFT (see CLAUDE.md), so a floating body casts
#               down AND to the right. Falls back to dx/dy when unset.
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
    "drop_dx": 16,   # top-left key -> a floating body casts down AND right;
    "drop_dy": 16,   # equal offsets put the cast at 45 deg to match the key
    "squash": 0.16,
    "exclude_arms": True,
    # Sits in the middle of the empty band between the two populations it has
    # to separate: centred/floating bodies bottom out at 1023, grounded ones
    # start at 1084. 1040 gave only 17px of clearance on the floating side and
    # put smores (1038) and brownie_bite (1042) on opposite sides of the flip
    # while standing in the same pose; 1053 clears both by ~30px.
    "ground_line": 1053,
}

# Subject separation ("stage pocket"). Grading the plates as a family
# (background_pop_studies/grade.py) can only push the WHOLE plate back; it
# cannot know where the character will land, so a plate that is quiet in the
# corners and busy dead-centre still fights the body it is standing in front
# of. This pass runs at composite time, where the silhouette IS known, and
# opens a pocket in the plate around the character:
#
#   wide    an atmospheric-recession field, the silhouette blurred out to
#           `wide_blur` px, gained so it is already at full strength on the
#           silhouette's edge and falls to nothing by the frame. Inside it the
#           plate is defocused, desaturated and dimmed, so detail and colour
#           recede exactly where the eye compares them against the body.
#   tight   a short-range occlusion band hugging the silhouette, which is what
#           actually crisps the edge. Offset DOWN AND RIGHT because the
#           collection's key light comes from the top left (see CLAUDE.md), so
#           it reads as the body's own occlusion rather than a sticker glow.
#
# Both fields are derived from the same silhouette the grounding shadow uses,
# so they follow footwear, arms and per-character placement for free. The
# background overlays (BG_OVERLAY_PAIRS) are composited after the character
# and are deliberately NOT touched — they are foreground, not stage.
# Set to None to disable the pass entirely.
# How hard the pass works is NOT fixed: it scales with how much the plate
# actually competes, measured on the ring of plate the character does not
# cover. A fixed amplitude is wrong in both directions — rendered as a ladder,
# a busy plate (Toasted) still lost to its own marshmallows at the setting
# that already smudged a quiet one (Celestial) into a grey cloud.
#
# The competition metric is a BAND-PASS, |blur(8) - blur(40)|, not a plain
# high-pass: the first metric tried was gradient energy at 4px, which ranked
# Celestial the 7th busiest plate in the set because it read the plate's film
# grain. Grain is not what the eye compares a doughnut against; mid-scale
# structure is. Band-passed, Celestial drops to 2.6 (second quietest) and
# Toasted rises to 17.4, which is what the renders show.
# (Celestial was retired in 2026-08 and is in traits/backgroundz_retired. The
# measurement stands as the reason this metric is a band-pass; it just cannot
# be re-run against that plate without restoring it.)
SUBJECT_SEPARATION = {
    "wide_blur": 170,     # px; radius of the recession field
    "wide_gain": 2.3,     # saturates the field at the silhouette edge
    "defocus": 6.0,       # px of extra blur at full strength
    "sat": 0.70,          # chroma multiplier at full strength
    "dim": 0.86,          # luma multiplier at full strength
    "tight_blur": 26,     # px; radius of the occlusion band
    "tight_gain": 1.5,
    "tight_dx": 11,       # top-left key -> occlusion falls down and right
    "tight_dy": 11,
    "tight_opacity": 0.34,
    # the occlusion band never reads as a cloud, so it keeps a floor even on
    # a plate that needs no recession at all
    "tight_floor": 0.35,
    "band_lo": 8,         # band-pass radii, in px
    "band_hi": 40,
    "busy0": 2.5,         # band-pass mean at/below which the pass is OFF
    "busy1": 14.0,        # ...and at/above which it runs at full strength
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

# The one face-hole width, in RENDERED pixels, that every character's art is
# registered to. The face assembly (ball, eyes, mouth) is the same size for
# the whole cast, so the hole has to be too, or the face reads a different
# size on different characters — the cast used to run 179-260px, a 1.45x
# spread. Because the BODY still carries CHAR_SCALE, a character's hole in
# FILE space must be FACE_HOLE_WIDTH / char_scale (338 for a 0.74 ice cream,
# 250 for an unscaled body). asset_assessment/normalize_face_hole.py warps
# art onto this, and audit_face_holes.py checks it.
FACE_HOLE_WIDTH = 250

# A body whose face hole sits lower/deeper than the cast-wide
# FACE_HOLE_BOTTOM leaves the standard skin ball stopping short of the hole's
# bottom edge, and a sliver of background shows under the face. An entry here
# raises the hole bottom (px) for that character alone, so ball_fit's need_h
# enlarges its ball enough to cover it. Substring match on the base-name; the
# value is in PRE-CHAR_SCALE file space.
#
# EMPTY, and it should stay that way. Both entries this once held died when
# their holes were registered rather than worked around: nutty_bar (765) when
# the art was squashed from a 246x293 tall ellipse to a round one, and
# gold_waffle (750) when normalize_face_hole.py put every hole on the same
# circle. Growing the ball is the wrong lever — it is the fallback for art
# that cannot be re-registered, and it costs face size wherever it applies.
FACE_HOLE_BOTTOM_OVERRIDE = {}

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
                                force_wat="auto", force_sticker="auto",
                                force_char=None, exclude_chars=None):
    """force_bg = (bg_dir, bg_file) pins the background (e.g. a legendary
    plate from traits/backgroundz); it bypasses the random plate pick,
    the char<->bg compat filter and any paired overlay. Default = random.

    force_char pins the character (a base character name as returned by
    build_char_compat.base_name, e.g. "sugar_cube"); it bypasses the uniform
    character pick so the mint allocator can hit exact per-character counts.
    Everything downstream — compat filtering, placement, skin/eye/mouth —
    behaves exactly as it would had the pick landed there naturally.

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
    
    base_names = {char_base_name(f) for f in char_files}

    if not base_names:
        raise ValueError("No valid character names found")
    
    # sorted: set iteration order varies per process (hash randomization),
    # which silently breaks seeded reproducibility
    if force_char is not None:
        if force_char not in base_names:
            raise ValueError(f"force_char {force_char!r} is not a character "
                             f"in traits/{CHARACTERZ}")
        char_name = force_char
    else:
        # exclude_chars is how the mint allocator makes a pinned character
        # count EXACT. Pinning alone only sets a floor: the pinned slots force
        # the character, and then every unpinned slot draws it again at random
        # on top, which put a 60-target character at 157. Unpinned slots draw
        # from the complement instead.
        pool = sorted(base_names - set(exclude_chars or ()))
        char_name = random.choice(pool or sorted(base_names))
    
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
        # Legendary_* plates and the starfield are capped rares: they appear
        # ONLY via the mint allocator's fixed per-plate quota (force_bg),
        # never in the normal weighted random pick, so their caps stay exact.
        bg_files = [f for f in bg_files if not is_allocator_only_bg(f)]
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
        bgg = load_rarity_gains(BACKGROUNDZ)
        bg = random.choices(
            allowed_bgs,
            weights=[cw.get(f, 1.0) * bgg.get(f, 1.0) for f in allowed_bgs],
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
    # The per-plate soft weight is multiplied by the asset's GLOBAL rarity
    # gain, so the two do different jobs: the soft weight decides which eye
    # suits this plate, the gain decides how often that eye appears across the
    # whole mint. Without the gain the eye distribution is whatever the hard
    # blocklist happens to leave behind — which made Blue the rarest eye in the
    # set at 3.9% purely because it is barred from 42% of plates.
    ew = load_eyez_weights().get(bg, {})
    eg = load_rarity_gains(EYEZ)
    eye = random.choices(
        allowed_eyes,
        weights=[ew.get(f, 1.0) * eg.get(f, 1.0) for f in allowed_eyes],
        k=1)[0]
    mg = load_rarity_gains(MOUTHZ)
    mouth = random.choices(mouth_files,
                           weights=[mg.get(f, 1.0) for f in mouth_files],
                           k=1)[0]
    
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

    # Each optional slot rolls on its own, at its own rate, so one can be
    # common while another stays rare and neither moves when the other is
    # unavailable for this character. See ARM_RATE / FOOTWEAR_RATE /
    # STICKER_RATE. Slots driven by the mint allocator are decided below.
    active = set()
    if (force_wat == "auto" and footwear_available
            and random.random() < FOOTWEAR_RATE):
        active.add("footwear")
    if (force_arm == "auto" and all_arm_files
            and random.random() < ARM_RATE):
        active.add("arms")
    if (force_sticker == "auto" and sticker_files
            and random.random() < STICKER_RATE):
        active.add("sticker")

    # apply forced ON slots (a specific trait was requested by the allocator)
    if force_wat not in ("auto", None):
        active.add("footwear")
    if force_arm not in ("auto", None):
        active.add("arms")
    if force_sticker not in ("auto", None):
        active.add("sticker")

    # --- footwear slot: gorbhouse trash-cans (eligible chars) or regular WAT,
    # the latter biased by the measured footwear<->background compat table ---
    #
    # The gorbhouse has its own DRAW (eligibility + GORBHOUSE_CHANCE, not the
    # bg-weighted pick), but from here on it is an ordinary footwear base:
    # chosen_wat carries it, so it lands on exactly the same code path as the
    # bunny/pepe/shiba/monster slippers. It used to be a separate flag with a
    # layer of its own, and that is what sank the character into the cans --
    # see the note at the placement branch below.
    chosen_wat = None
    wat_overlays = []
    if "footwear" in active:
        if force_wat not in ("auto", None):
            # explicit footwear from the allocator, but honor character
            # eligibility: if this char can't wear it, leave footwear OFF so
            # the allocator re-rolls onto an eligible character.
            if str(force_wat).lower() == "gorbhouse":
                if gets_gorbhouse_overlay(char_name):
                    chosen_wat = GORBHOUSE_BASE
            elif footwear_available:
                chosen_wat = force_wat
        elif gets_gorbhouse_overlay(char_name) and random.random() < GORBHOUSE_CHANCE:
            chosen_wat = GORBHOUSE_BASE
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

    # --- arms slot: draw from the arms this character is ALLOWED to hold; a
    # character with a locked weapon of its own gets that instead ---
    arm = None
    if "arms" in active and all_arm_files:
        if force_arm not in ("auto", None):
            # explicit arm from the allocator; for a character-LOCKED weapon,
            # only draw it on a character allowed to hold it (otherwise leave
            # the slot empty so the allocator re-rolls onto a valid character).
            if armz_allowed(force_arm, char_name):
                arm = force_arm
        else:
            # The draw MUST be filtered by armz_allowed. It used to be
            # `random.choice(all_arm_files)` over every arm, with the locked
            # override applied only when the character had a lock of its own —
            # so a character with no signature weapon could pick up someone
            # else's (a glazed doughnut holding the gummy bear's knives), at
            # 56 hits per 600 combos.
            allowed = [f for f in all_arm_files if armz_allowed(f, char_name)]
            if allowed:
                arm = random.choice(allowed)
            locked_arms = [f for f in allowed if f in ARMZ_CHAR_LOCK]
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
        wscale, wpivot = wat_scale(chosen_wat)
        for f in wat_files:
            base = wat_base_name(f)
            if base and base.lower() == chosen_wat.lower():
                layers.append(_wat_layer(
                    os.path.join(TRAITS_DIR, WHAT_ARE_THOSEZ, f),
                    wscale, wpivot))
                break
    
    # Determine if we should apply offset
    # Rule: If no footwear AND (not ice cream, not twinkie, not churro)
    no_offset_char = any(ex.lower() in char_name.lower()
                         for ex in NO_OFFSET_CHARS)
    apply_offset = not chosen_wat and not no_offset_char
    y_adjust = char_y_adjust(char_name)
    cscale = char_scale(char_name)
    # Baseless/round characters sit centred ONLY when they have nothing under
    # them to stand on -- i.e. no footwear at all, which apply_offset already
    # says (the gorbhouse is footwear, so it clears apply_offset like any
    # other base). With a shoe or a trash-can they keep their normal grounded
    # placement.
    if is_centered(char_name) and apply_offset:
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
    # Every body now sits ABOVE the ball (body_after_skin is unconditionally
    # True): the skin is composited first and the face is what shows through
    # the body's face hole, so no skin is ever drawn over a character. The
    # before_skinz_ / after_skinz_ filename prefixes are historical and say
    # only how the art was authored. before_char_layers is kept because the
    # split is the shape of the compositor, not because anything uses it today.
    #
    # A character's art is whatever file(s) share its base name EXACTLY. This
    # used to be a cascade of prefix patterns with a SUBSTRING fallback
    # (`char_name in f and "after_skinz" in f`), and a substring match cannot
    # tell a name from a name that contains it: "waffle" matched
    # after_skinz_gold_waffle.png, so the waffle rendered the gold waffle's
    # body — with the waffle's own CHAR_SCALE / CHAR_Y_ADJUST /
    # face_hole_bottom applied to it, which is what leaked a 132x31 hole
    # through its face — and after_skinz_waffle.png was never drawn at all.
    # Base-name equality also removes the need for the fallback: char_base_name
    # builds base_names above, so every name resolves by construction.
    before_char_layers = []
    after_char_layers = []

    body_files = [f for f in char_files if char_base_name(f) == char_name]
    if not body_files:
        raise ValueError(f"No art in traits/{CHARACTERZ} for character "
                         f"{char_name!r}")

    # Raise the whole figure when it holds a weapon (ARMED_LIFT) or when its
    # footwear needs the body above its own bulk (WAT_CHAR_LIFT). Applied to
    # y_adjust BEFORE any layer is built, so the body, skin ball, eyes, mouth
    # and the arm all take it together and nothing inside the figure shifts
    # relative to anything else. The grounding shadow is derived from those
    # layers plus the footwear, so it stays on the sole.
    #
    # The two are ALTERNATIVES, never cumulative. Both say "this figure must
    # ride N px higher for clearance", so the figure takes the larger N.
    # Summed, an armed gorbhouse went up 140px and floated clear of the cans
    # on two long black ankles — rendered, and plainly wrong.
    lift = max(armed_lift(body_files[0], arm, cscale) if arm else 0,
               wat_char_lift(chosen_wat))
    if lift:
        y_adjust -= lift
    for f in body_files:
        layer = {"path": os.path.join(TRAITS_DIR, CHARACTERZ, f), "offset": apply_offset, "dy": y_adjust + bg_extra_y, "cscale": cscale, "ccenter": CHAR_SCALE_PIVOT}
        if body_after_skin(char_name, f):
            after_char_layers.append(layer)
        else:
            before_char_layers.append(layer)

    # 3. Before-skinz body layers (below skin ball)
    layers.extend(before_char_layers)

    # 5/6/7. The FACE ASSEMBLY: skin ball, eyes and mouth.
    #
    # These deliberately do NOT carry the character's CHAR_SCALE. The face is
    # one fixed-size assembly pinned at CHAR_SCALE_PIVOT for every character
    # in the cast; only the BODY varies in size. That is what makes every
    # character's face the same size — the thing CHAR_SCALE otherwise
    # prevents, because it scales the ball and the hole together and so a
    # 0.74 ice cream got a 0.74 face (a 217px ball against everyone else's
    # 293px, and a 190px hole against their 250px).
    #
    # The old comment here warned that native eyes overflow a scaled-down
    # ball. That was true of eyes native WITH the ball still scaled; with the
    # whole assembly native the eye-in-ball relationship ball_fit establishes
    # holds for everyone, identically, at any CHAR_SCALE.
    #
    # The other half of the rule lives in the ART: each body's face hole is
    # authored so that hole x CHAR_SCALE == FACE_HOLE_WIDTH, which is what
    # asset_assessment/normalize_face_hole.py enforces. A body whose hole is
    # not registered that way will show a ring of skin ball (hole too small)
    # or leak the plate (hole too big) — verify_face_coverage.py catches the
    # second, audit_face_holes.py the first.
    skin_path = os.path.join(TRAITS_DIR, SKINZ, skin)
    bfit, bcenter = ball_fit(skin_path, os.path.join(TRAITS_DIR, EYEZ, eye),
                             hole_bottom=face_hole_bottom(char_name))
    skin_layer = {"path": skin_path, "offset": apply_offset,
                  "dy": y_adjust + bg_extra_y,
                  "fscale": bfit, "fcenter": bcenter}
    if SKIN_SHADOW:
        skin_layer["shadow"] = dict(SKIN_SHADOW)
    layers.append(skin_layer)

    # 4. After-skinz body layers (above skin ball — face hole reveals skin)
    layers.extend(after_char_layers)

    eye_layer = {"path": os.path.join(TRAITS_DIR, EYEZ, eye),
                 "offset": apply_offset, "dy": y_adjust + bg_extra_y}
    if EYE_SHADOW:
        eye_layer["shadow"] = dict(EYE_SHADOW)
    layers.append(eye_layer)

    mouth_layer = {"path": os.path.join(TRAITS_DIR, MOUTHZ, mouth),
                   "offset": apply_offset, "dy": y_adjust + bg_extra_y}
    # a 3D prop mouth (joint, lollipop) drops a full shadow; a line-art mouth
    # drops a lighter one — see MOUTH_PROP_SHADOW / MOUTH_SHADOW
    if mouth in MOUTH_PROP_FILES:
        if MOUTH_PROP_SHADOW:
            mouth_layer["shadow"] = dict(MOUTH_PROP_SHADOW)
    elif MOUTH_SHADOW:
        mouth_layer["shadow"] = dict(MOUTH_SHADOW)
    layers.append(mouth_layer)

    # 8. What Are Thosez OVERLAY (footwear front piece) — placed BEFORE arms
    # so a held weapon (katana/knives) reads on top of the slippers instead
    # of being hidden behind them.
    wscale, wpivot = wat_scale(chosen_wat)
    for overlay_path in wat_overlays:
        layers.append(_wat_layer(overlay_path, wscale, wpivot))

    # (The gorbhouse used to be appended here, as a ninth step of its own,
    # anchored to the CHARACTER -- offset=apply_offset, dy=y_adjust. It is
    # drawn by the WAT base/overlay pair above now, at offset=False like every
    # other slipper, because the art says so: Gorbhouse_base.png occupies
    # y 820..1146, the same authored band as Bunny (825..1148) and Cookie
    # Monster (821..1276). Riding the character meant riding the +150
    # footwear-LESS drop -- on a character that is, by definition, wearing
    # footwear -- so cans and body went down 130-190px together and the body
    # bottom landed 156px BELOW the can rims instead of 138px above their
    # floor. The character sat in the cans up to its middle.)

    # 9. Armz (after the footwear overlay, so a held katana/knife reads on
    # top of the footwear; tracks the character's scale)
    if arm:
        # Arms deliberately do NOT take cscale. A weapon is a rarity trait, and
        # a Blue Saber should read as the same object whoever holds it — when
        # arms inherited the character scale, the sabers on the ice creams and
        # gummy bears (0.74 / 0.881) came out visibly smaller than the same
        # saber on everyone else. Native size keeps the trait consistent across
        # the mint; the slightly oversized fists on a small character read as
        # cartoon, not as an error.
        layers.append({"path": os.path.join(TRAITS_DIR, ARMZ, arm),
                       "offset": apply_offset,
                       "dy": (y_adjust + bg_extra_y
                              + arm_char_dy(char_name, arm)),
                       "ascale": arm_scale(arm), "acenter": ARM_SCALE_PIVOT})

    # 10. Sticker
    if sticker:
        layers.append({"path": os.path.join(TRAITS_DIR, STICKERZ, sticker), "offset": False})

    # 11. Paired background overlay - always placed LAST, on top of everything
    if bg in BG_OVERLAY_PAIRS:
        ov_path = os.path.join(TRAITS_DIR, bg_dir, BG_OVERLAY_PAIRS[bg])
        if os.path.exists(ov_path):
            layers.append({"path": ov_path, "offset": False})

    return layers, char_name

def _render_layer(layer_info):
    """Load a layer and apply all of its geometric transforms (fscale, ascale,
    cscale, then the footwear-less offset + per-character dy). Returns a
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
    # Per-arm intrinsic scale about the hand line, BEFORE cscale. ARM_SCALE_PIVOT
    # is the hand line in the art's NATIVE space, and cscale moves it (a 0.74
    # character puts its hands at y=926, not 1040). Scaling about the stale pivot
    # afterwards left the weapon off the hands by (1-ascale) x the displacement:
    # 17px on the old 1.19 bears, 23px on a 0.74 ice cream. Applying it first
    # keeps the pivot valid, and cscale then carries the result with the body.
    # Only affects arms with an ARM_SCALE entry (today: the dual Uzis).
    if abs(layer_info.get("ascale", 1.0) - 1.0) > 0.001:
        img = scale_about(img, layer_info["ascale"], layer_info["acenter"])
    # per-character scale about the ball center (body + arms + ball + face)
    if abs(layer_info.get("cscale", 1.0) - 1.0) > 0.001:
        img = scale_about(img, layer_info["cscale"], layer_info["ccenter"])

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
    if mode == "drop":
        # The collection's key light comes from the TOP LEFT, so a floating
        # body casts down AND to the right. A contact pool does not: it sits
        # under its caster whatever the key is doing, which is why the offset
        # is per-mode rather than shared.
        dx = int(cfg.get("drop_dx", dx))
        dy = int(cfg.get("drop_dy", dy))
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


def _face_inset_shadow(char_img, ball_alpha, body_alpha, cfg):
    """Shade the skin ball where the face hole's rim occludes it.

    Composites in place onto char_img. Everything is masked to the HOLE --
    the region where the body is transparent and the ball is opaque -- so the
    result is identical to having drawn it under the body, and it can never
    reach the body, the plate or the silhouette. See FACE_INSET_SHADOW."""
    from PIL import ImageChops, ImageFilter
    # the hole: ball present, body absent
    hole = ImageChops.multiply(ball_alpha, ImageChops.invert(body_alpha))
    if hole.getbbox() is None:
        return

    shade = Image.new("L", char_img.size, 0)

    # ---- the rim's cast shadow, pushed down-right by the top-left key ----
    op = cfg.get("cast_opacity", 0.0)
    if op > 0.005:
        moved = Image.new("L", char_img.size, 0)
        moved.paste(body_alpha, (int(cfg.get("cast_dx", 0)),
                                 int(cfg.get("cast_dy", 0))))
        cast = moved.filter(ImageFilter.GaussianBlur(cfg.get("cast_blur", 26)))
        shade = ImageChops.lighter(shade, cast.point(lambda v: int(v * op)))

    # ---- contact occlusion all round the rim ----
    op = cfg.get("ao_opacity", 0.0)
    if op > 0.005:
        ao = body_alpha.filter(ImageFilter.GaussianBlur(cfg.get("ao_blur", 9)))
        shade = ImageChops.lighter(shade, ao.point(lambda v: int(v * op)))

    shade = ImageChops.multiply(shade, hole)
    layer = Image.new("RGBA", char_img.size, (0, 0, 0, 255))
    layer.putalpha(shade)
    char_img.alpha_composite(layer)


def _subject_separation(bg_img, sil_alpha, cfg):
    """Open a stage pocket in the background plate around the character.

    Takes the composited background (full-canvas RGBA) and the character
    silhouette, and returns a NEW background with the plate defocused,
    desaturated and dimmed behind the subject, plus a short-range occlusion
    band hugging its edge. See SUBJECT_SEPARATION for what each knob does.

    Runs before the grounding shadow and the character, so the pocket is
    under both; nothing here can ever draw over the foreground."""
    from PIL import ImageChops, ImageEnhance, ImageFilter, ImageStat
    if sil_alpha.getbbox() is None:
        return bg_img

    def _field(radius, gain, dx=0, dy=0):
        """Silhouette -> a 0..255 falloff field. The gain is what puts full
        strength ON the silhouette edge: a plain blur is only ~50% there,
        which spends the whole effect inside the body, where it is hidden."""
        src = sil_alpha
        if dx or dy:
            src = Image.new("L", sil_alpha.size, 0)
            src.paste(sil_alpha, (dx, dy))
        f = src.filter(ImageFilter.GaussianBlur(radius))
        if abs(gain - 1.0) > 0.001:
            f = f.point(lambda v: min(255, int(v * gain)))
        return f

    out = bg_img
    alpha = out.getchannel("A")
    wide = _field(cfg["wide_blur"], cfg.get("wide_gain", 1.0))

    # ---- how much does this plate actually compete? ----
    # Measured on the annulus (the lit field minus the silhouette), i.e. only
    # the plate the character does NOT cover — the pixels the eye compares it
    # against. Everything below scales with the result.
    annulus = ImageChops.subtract(wide, sil_alpha)
    if annulus.getbbox() is None:
        return bg_img
    grey = out.convert("L")
    band = ImageChops.difference(
        grey.filter(ImageFilter.GaussianBlur(cfg.get("band_lo", 8))),
        grey.filter(ImageFilter.GaussianBlur(cfg.get("band_hi", 40))))
    busy = ImageStat.Stat(band, annulus).mean[0]
    b0, b1 = cfg.get("busy0", 2.5), cfg.get("busy1", 14.0)
    t = min(1.0, max(0.0, (busy - b0) / max(b1 - b0, 1e-6)))
    amount = t * t * (3.0 - 2.0 * t)          # smoothstep

    # ---- wide: atmospheric recession (defocus + desaturate + dim) ----
    defocus = cfg.get("defocus", 0.0) * amount
    sat = 1.0 - (1.0 - cfg.get("sat", 1.0)) * amount
    dim = 1.0 - (1.0 - cfg.get("dim", 1.0)) * amount
    recessed = out
    if defocus > 0.05:
        recessed = recessed.filter(ImageFilter.GaussianBlur(defocus))
    if abs(sat - 1.0) > 0.001:
        recessed = ImageEnhance.Color(recessed).enhance(sat)
    if abs(dim - 1.0) > 0.001:
        recessed = ImageEnhance.Brightness(recessed).enhance(dim)
    if recessed is not out:
        # GaussianBlur/Enhance drop the plate's own alpha into the blur; put
        # the original back so a transparent plate stays transparent.
        recessed.putalpha(alpha)
        out = Image.composite(recessed, out, wide)

    # ---- tight: occlusion band, offset for the top-left key ----
    floor = cfg.get("tight_floor", 0.0)
    op = cfg.get("tight_opacity", 0.0) * (floor + (1.0 - floor) * amount)
    if op > 0.005:
        band = _field(cfg["tight_blur"], cfg.get("tight_gain", 1.0),
                      int(cfg.get("tight_dx", 0)), int(cfg.get("tight_dy", 0)))
        band = band.point(lambda v: int(v * op))
        # never darken past the plate's own coverage (overlay plates are
        # mostly transparent and must not gain a black cloud)
        band = ImageChops.multiply(band, alpha)
        occl = Image.new("RGBA", bg_img.size, (0, 0, 0, 255))
        occl.putalpha(band)
        out = out.copy()
        out.alpha_composite(occl)

    return out


def create_image(layers, output_name=None, metadata=None, mask_path=None,
                 float_mask_path=None):
    """Composite all layers and write the PNG.
    If metadata is provided (a list of {"trait_type", "value"} dicts as
    returned by extract_metadata()), a matching .json sidecar is saved
    next to the PNG with OpenSea-compatible attributes.

    mask_path, if given, additionally writes the PROTECT MASK for the
    dynamic sky pass (dynamic/sky.py) -- see the note where it is saved.

    float_mask_path, if given, writes the FLOAT MASK: the corner sticker
    alone, for the flood to rest on its surface rather than drown -- see the
    note where that is saved."""
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

    def _is_sticker(layer_info):
        return os.path.normpath(layer_info["path"]).startswith(
            sticker_prefix + os.sep)

    # The float mask is the sticker ALONE, not the union _is_top() composites:
    # a paired background overlay is part of the plate's own scene and must
    # keep drowning with it, so the two cannot share a mask.
    float_mask = Image.new("L", canvas, 0)

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

    skin_prefix = os.path.normpath(os.path.join(TRAITS_DIR, SKINZ))
    char_prefix = os.path.normpath(os.path.join(TRAITS_DIR, CHARACTERZ))
    ball_alpha = Image.new("L", canvas, 0)
    body_alpha = Image.new("L", canvas, 0)
    inset_done = False

    for layer_info in char_layers:
        img = _render_layer(layer_info)
        if img is None:
            continue
        # The inset shadow needs the ball and the body, and must land under
        # the eyes and mouth -- so it goes in the moment we leave the body
        # and reach the first face feature.
        p = os.path.normpath(layer_info["path"])
        is_skin = p.startswith(skin_prefix + os.sep)
        is_body = p.startswith(char_prefix + os.sep)
        if (FACE_INSET_SHADOW and not inset_done and not is_skin
                and not is_body and ball_alpha.getbbox() is not None):
            _face_inset_shadow(char_img, ball_alpha, body_alpha,
                               FACE_INSET_SHADOW)
            inset_done = True
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
        if is_skin:
            ball_alpha = ImageChops.lighter(ball_alpha, alpha)
        elif is_body:
            body_alpha = ImageChops.lighter(body_alpha, alpha)
        fg_mask = ImageChops.lighter(fg_mask, alpha)
        if not (exclude_arms and _is_arm(layer_info)):
            sil_alpha = ImageChops.lighter(sil_alpha, alpha)

    # 3a. Subject separation: push the plate back around the silhouette. Must
    #     run before the grounding shadow, so the shadow lands on the pocket
    #     rather than being defocused and dimmed by it.
    if SUBJECT_SEPARATION:
        base_img = _subject_separation(base_img, sil_alpha, SUBJECT_SEPARATION)

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
            a = img.getchannel("A")
            fg_mask = ImageChops.lighter(fg_mask, a)
            if _is_sticker(layer_info):
                float_mask = ImageChops.lighter(float_mask, a)

    base_img.save(output_name)

    # Protect mask for the dynamic sky pass (dynamic/sky.py): the union of
    # every layer EXCEPT the background plate -- i.e. exactly the pixels a
    # time-of-day or weather grade must never touch. fg_mask has already
    # accumulated the character stack (body, skin, eyes, mouth, arms,
    # footwear); the loop above adds the stickers and the paired background
    # overlays, which are foreground figures riding on their plate rather
    # than part of the stage.
    #
    # It is written HERE, at composite time, because this is the only place
    # the silhouette is known for free. Recovering it from the finished PNG
    # would mean segmenting the art; recovering it by re-running the
    # pipeline costs a full ~2s composite and all 441MB of traits/. Written
    # once at mint-build time, it makes the dynamic render a two-input op on
    # two PNGs.
    #
    # Anti-aliased edges are preserved as intermediate values, so the sky
    # blend feathers across the silhouette instead of stair-stepping it.
    if mask_path is not None:
        fg_mask.save(mask_path)

    # Float mask: the corner sticker on its own. `flooded` is the one state
    # that reaches past the protect mask, and every sticker in the collection
    # is authored at y 1114..1338 against a waterline at y 836 -- so all 23
    # are fully under water, and the flood tints the piece toward its deep
    # colour until the art is unreadable. With this the sticker rides ON the
    # surface instead, and the water gets a contact shadow, a meniscus and a
    # reflection around it so it reads as floating rather than pasted on.
    #
    # A SECOND FILE rather than a second channel of the protect mask: every
    # existing consumer opens that one with .convert("L"), which on a
    # multi-channel image returns a luma MIX of the channels and would
    # silently corrupt the protect mask itself. Optional everywhere, and a
    # token with no sticker simply writes an empty one.
    if float_mask_path is not None:
        float_mask.save(float_mask_path)

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
