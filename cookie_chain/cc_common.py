"""Shared wiring for the Cookie Chain Edition build.

The edition is composited by the main collection's compositor
(`generator.py`) over the main collection's figure art (`traits/characterz`,
`skinz`, `eyez`, `mouthz`, `what_are_thosez`, `armz`), so every fix made to
that art and to its placement rules carries over. What is the edition's own
lives under `assets/`:

    backgroundz/   the 19 Cookie Chain plates + 5 one-of-one Legendary plates
    stickerz/      the 22 Cookie Chain stickers (built by prepare_assets.py)
    what_are_thosez/  the five footwear sets, outlines re-cut (prepare_footwear.py)
    armz/          the two Cookie Chain held items: Cookboy Handheld, Printer
    branding/      the Cookie Chain Edition plaque (off since 2026-10-25: PLAQUE_ON)

The same scripts run from two layouts:

    Sweetardio_Collection/            sweetardio-cookie-chain-edition/
      generator.py, traits/             compositor/generator.py, traits/  (vendored)
      cookie_chain/                     scripts/   <- these files
        <these files>, assets/,         assets/, plan.json
        plan.json

`setup()` points the compositor at the edition's folders. It never writes into
`traits/`, so nothing here can leak into the main mint.
"""

import os
import sys
from pathlib import Path

from PIL import Image

CC_ROOT = Path(__file__).resolve().parent
if (CC_ROOT / "assets").is_dir():           # Sweetardio_Collection/cookie_chain/
    EDITION_ROOT = CC_ROOT
    REPO_ROOT = CC_ROOT.parent
else:                                       # sweetardio-cookie-chain-edition/scripts/
    EDITION_ROOT = CC_ROOT.parent
    REPO_ROOT = Path(os.environ.get("SWEETARDIO_COMPOSITOR",
                                    EDITION_ROOT / "compositor")).resolve()
# REPO_ROOT is the COMPOSITOR root: generator.py and its traits/ live there.
ASSETS = EDITION_ROOT / "assets"
PLAN = EDITION_ROOT / "plan.json"
WORK = EDITION_ROOT / "work"                # scratch: candidate thumbs, pool, sheet
BACKGROUNDS = ASSETS / "backgroundz"
STICKERS = ASSETS / "stickerz"
CC_ARMS = ASSETS / "armz"
FOOTWEAR = ASSETS / "what_are_thosez"
PLAQUE = ASSETS / "branding" / "cookie_chain_edition.png"

EDITION = "Cookie Chain Edition"
SUPPLY = 444

# ---- figure scale -----------------------------------------------------------
# The main collection fills its frame: a shod gold waffle runs y 132..1147, a
# bare one 28% of the canvas. On this edition the bottom corners are spoken
# for -- the sticker on the left, the edition plaque on the right -- and at
# full size the figure crowded both and sat with almost no headroom.
#
# So the WHOLE figure (body, skin ball, eyes, mouth, footwear, arm) is scaled
# as one piece about a point on the ground line. One piece, because the face
# hole, the ball and the eyes are registered against each other at native
# size and any part scaled on its own would break that registration. On the
# ground line, so a standing figure keeps its feet where they were and the
# contact shadow stays under it.
#
# FIGURE_SCALE is the cast-wide factor; 0.88 was chosen off a rendered ladder
# at 1.0 / 0.90 / 0.84 / 0.78 -- below ~0.84 the ice creams start to read
# small.
#
# BIG_BODY_SCALE trims, on top of that, the bodies whose rendered area (body +
# ball, bare, at 1.0) sits above the cast median of 23.3% of the canvas:
# trim = (23.3 / area) ** 0.35, floored at 0.92. Measured, the bare cast ran
# 18.6% (ice creams) to 28.3% (gold waffle), a 1.52x spread in which every
# blocky body -- the waffles, sugar cube, rice crispy, brownie, s'mores,
# zebra cake, marshmallow, the poptarts -- outweighed the rest of the cast.
# With the trims it is 14.4%..19.1% (1.33x). The trim is deliberately
# partial: it scales the face along with the body, so it is held to <= 7% to
# keep every face in the edition within a few percent of the same size --
# the main collection's "one face, one size" rule, kept as nearly as a
# whole-figure scale allows.
FIGURE_SCALE = 0.88
FIGURE_PIVOT = (690, 1100)
BIG_BODY_SCALE = {
    "gold_waffle": 0.934, "sugar_cube": 0.935, "rice_crispy_treat": 0.936,
    "brownie_bite": 0.937, "smores": 0.938, "zebra_cake": 0.94,
    "marshmallow": 0.95, "chocolate_frosted_poptart": 0.954,
    "og_poptart": 0.955, "cyan_frosted_poptart": 0.955, "churro": 0.96,
    "waffle": 0.978,
}

# ---- the two Cookie Chain held items ---------------------------------------
GAME_DEVICE = "Cookboy_Handheld.png"
PRINTER = "Printer.png"
# The Printer is lifted 18px on every holder (owner-approved alignment in the
# previous release) and never goes on a gummy bear, whose own arm lobes it
# sits across.
CC_ARM_DY = {PRINTER: -18}
CC_ARM_EXCLUDE = {PRINTER: ("gummy_bear",)}

# ---- public names -----------------------------------------------------------
BACKGROUND_NAMES = {
    "Black_Cookie_Emboss.png": "Cookboy Black Enamel",
    "Chocolate_Cookie_Emboss.png": "Cookboy Chocolate",
    "Gold_Cookie_Emboss.png": "Cookboy Gold",
    "Silver_Cookie_Emboss.png": "Cookboy Silver",
    "Cookboy_Paisley.png": "Sarv Legendary",
    "Cookie_Vault.png": "M Power Legendary",
    "Cookie_Dough.png": "Cookie Dough",
    "Digital_Future_Mural.png": "NFTs Aren't Dead",
    "Emyr_Gallery.png": "Emyr Legendary",
    "Fairdevs_Night.png": "Fairdevs Legendary",
    "Marsel_Blue.png": "Morsel Legendary",
    "Short_The_Banks_Vault.png": "Short The Banks Legendary",
    "Simplex_Arcade.png": "Cookboy Legendary",
    "Welders_Equipment.png": "GorWeld Legendary",
    "Gorbhouse_Treasures.png": "Gorbhouse Treasures",
    "Liberty_Cookie_Dime.png": "Liberty Cookie Dime",
    "Moon_Surface.png": "Moon Surface",
    "Picnic_Stage.png": "Picnic Stage",
    "Yatrah_Arcade.png": "Yatrah Arcade",
    "Legendary_Nightly.png": "Nightly Legendary",
    "Legendary_Mattrick.png": "Mattrick Legendary",
    "Legendary_Shubbi.png": "Shubbi Legendary",
    "Legendary_Tenders.png": "Tenders Legendary",
    "Legendary_Opengotchi.png": "Opengotchi Legendary",
}
# Every legendary plate mints exactly once. Mattrick is the alien plate (the
# main collection carries the same art as Legendary_Just_Aliens); Opengotchi
# is the main collection's own Legendary_Opengotchi, added for this edition.
# The main collection's other two legendaries are already here under this
# edition's names -- Legendary_Simplex is Simplex_Arcade ("Cookboy
# Legendary") and Legendary_Tenders is the same Tenders art -- so they are not
# added twice.
ONE_OF_ONE_BACKGROUNDS = ("Legendary_Nightly.png", "Legendary_Mattrick.png",
                          "Legendary_Shubbi.png", "Legendary_Tenders.png",
                          "Legendary_Opengotchi.png")
ALL_ONE_OF_ONE_BACKGROUNDS = ONE_OF_ONE_BACKGROUNDS   # the pool draws all five,
                                                       # whichever the board keeps

# ---- whole-token 1/1s -------------------------------------------------------
# A secret rare is finished artwork that IS the token: no plate, figure or
# sticker is composited over it. Cookboy Blue Raspberry is the main
# collection's animated 1/1 -- the Cookboy flown across the moving starfield --
# built by dynamic/cookboy.py; the still is traits/secret_rarez/<file> and the
# loop is re-composited per plate frame at render time.
SECRET_RARES = {"Secret_Cookboy_Blue_Raspberry.png": "Cookboy Blue Raspberry"}
ANIMATED_SECRET_RARES = {"Secret_Cookboy_Blue_Raspberry.png"}
LOOP_SIZE, LOOP_MS = 640, 70          # build_mint.py's --anim-size / --anim-ms

STICKER_NAMES = {
    "Anime_Detective.png": "L",
    "Armed_Hero.png": "Real as a Doughnut",
    "Baked_Bazaar.png": "Baked Bazaar",
    "Candy_Shop.png": "Candy Shop",
    "Chibi_Monster.png": "Chibi Monster",
    "CookBook.png": "CookBook",
    "CookOven.png": "CookOven",
    "CookieScan.png": "CookieScan",
    "CookieSwap.png": "CookieSwap",
    "Cookie_Chat.png": "Cookie Chat",
    "Cookie_Lock.png": "Cookie Lock",
    "Cookie_MCP.png": "Cookie MCP",
    "Cookie_Quads.png": "Cookie Quads",
    "Cookiebox.png": "Cookiebox",
    "Emyr.png": "Emyr",
    "GORBOY.png": "Cookboy",
    "MomoSwap.png": "MomoSwap",
    "Morsel.png": "Morsel",
    "Nightly_Wallet.png": "Nightly Wallet",
    "Out_Of_Order.png": "Out of Order",
    "Poptart_Cat.png": "Nyancat",
    "Shorts_Doggo.png": "Shorts Doggo",
}

ARM_NAMES = {
    GAME_DEVICE: "Cookboy Handheld",
    PRINTER: "Printer",
    "layer-layer-layer-layer-AK15.png": "AK-15",
    "layer-layer-layer-layer-AR47.png": "AR-47",
}


_STAGED_ARMS = None


def _stage_arms(g):
    """One arm folder holding the main collection's arms and the two Cookie
    Chain items, as symlinks under the build's scratch dir. The compositor
    reads every arm from one folder and keys ARM_SCALE / ARM_CHAR_ARM_DY on
    the filename, so the main arms keep their own names (and their tuning)."""
    global _STAGED_ARMS
    if _STAGED_ARMS:
        return _STAGED_ARMS
    stage = Path(os.environ.get("CC_STAGE", "/tmp/cookie_chain_stage")) / "armz"
    stage.mkdir(parents=True, exist_ok=True)
    for old in stage.iterdir():
        old.unlink()
    for src in list((REPO_ROOT / "traits" / "armz").glob("*.png")) + \
            list(CC_ARMS.glob("*.png")):
        (stage / src.name).symlink_to(src.resolve())
    _STAGED_ARMS = stage
    return stage


def setup():
    """Import the compositor and point it at the Cookie Chain assets."""
    os.chdir(REPO_ROOT)                     # generator.py resolves traits/ relatively
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import generator as g
    if getattr(g, "_cookie_chain_ready", False):
        return g

    # generator.scale_about() pastes a layer with ITSELF as the mask, which
    # blends the alpha band too: an edge pixel at alpha 128 comes out at 64
    # with its colour halved toward black. Every layer this edition scales
    # (the whole figure, via FIGURE_SCALE) would carry that thinned, darkened
    # fringe, so it composites instead. Main-collection renders are unchanged.
    def scale_about(img, factor, center):
        if abs(factor - 1.0) < 0.001:
            return img
        w, h = img.size
        scaled = img.resize((max(1, round(w * factor)), max(1, round(h * factor))),
                            Image.Resampling.LANCZOS)
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cx, cy = center
        x, y = round(cx * (1 - factor)), round(cy * (1 - factor))
        # crop what falls off the canvas so alpha_composite gets a valid box
        sx, sy = max(0, -x), max(0, -y)
        scaled = scaled.crop((sx, sy, min(scaled.width, w - x), min(scaled.height, h - y)))
        out.alpha_composite(scaled, (x + sx, y + sy))
        return out
    g.scale_about = scale_about

    g.BACKGROUNDZ = str(BACKGROUNDS)        # os.path.join(traits, <abs>) -> <abs>
    if FOOTWEAR.is_dir():                   # the re-cut outlines (prepare_footwear.py)
        g.WHAT_ARE_THOSEZ = str(FOOTWEAR)
    g.STICKERZ = str(STICKERS)
    g.ARMZ = str(_stage_arms(g))

    # The main collection's compat tables are keyed to ITS plates. None of
    # these filenames collide with them, but make that a guarantee rather than
    # an accident: this edition curates by eye and by score instead.
    g.load_char_blocklist = lambda: {}
    g.load_char_weights = lambda: {}
    g.load_eyez_blocklist = lambda: {}
    g.load_eyez_weights = lambda: {}
    g.load_wat_blocklist = lambda: {}
    g.load_wat_weights = lambda: {}

    _armz_allowed = g.armz_allowed

    def armz_allowed(arm_file, char_name):
        if any(k in char_name.lower() for k in CC_ARM_EXCLUDE.get(arm_file, ())):
            return False
        return _armz_allowed(arm_file, char_name)
    g.armz_allowed = armz_allowed

    _arm_char_dy = g.arm_char_dy

    def arm_char_dy(char_name, arm_file):
        return _arm_char_dy(char_name, arm_file) + CC_ARM_DY.get(arm_file, 0)
    g.arm_char_dy = arm_char_dy

    _render = g._render_layer

    def render_layer(layer_info):
        img = _render(layer_info)
        s = layer_info.get("gscale", 1.0)
        if img is not None and abs(s - 1.0) > 1e-4:
            img = g.scale_about(img, s, layer_info["gcenter"])
        return img
    g._render_layer = render_layer

    g._cookie_chain_ready = True
    return g


def figure_scale(char_name):
    return FIGURE_SCALE * BIG_BODY_SCALE.get(char_name, 1.0)


def apply_figure_scale(g, layers, char_name):
    """Tag every figure layer (everything but the plate and the sticker) with
    the edition's figure scale. Returns the same list."""
    s = figure_scale(char_name)
    sticker_root = os.path.normpath(str(STICKERS))
    for li in layers[1:]:
        if os.path.normpath(li["path"]).startswith(sticker_root + os.sep):
            continue
        li["gscale"] = s
        li["gcenter"] = FIGURE_PIVOT
    return layers


# The owner took the edition plaque off every token (2026-10-25). The art
# stays in assets/branding, so putting it back is this one flag.
PLAQUE_ON = False


def add_plaque(path):
    """Composite the Cookie Chain Edition plaque over a finished token (when
    PLAQUE_ON), and flatten it to RGB either way."""
    token = Image.open(path).convert("RGBA")
    if PLAQUE_ON:
        token.alpha_composite(Image.open(PLAQUE).convert("RGBA"))
    token = token.convert("RGB")
    if str(path).endswith(".png"):
        token.save(path, compress_level=6)
    else:
        token.save(path)
