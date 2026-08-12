#!/usr/bin/env python3
"""Render the game assets used by the Sweetarded-Games site.

The site's slot machine and coin pusher show characters from this collection,
but they are *pinned* renders, not mint output: the slot reel needs the same
nine faces every spin and the pusher's mascot has to stay Choppa Cone. This
tool renders those pinned combinations through generator.py's production
pipeline, so anything the collection gains — the relit skin balls, the
registered and glossed eyes, the eye / mouth / face-inset shadows, the
normalised face holes, the armed lift — reaches the games the next time it is
run, instead of the site drifting a year behind the art.

What it changes about the pipeline, and why:

- **No background plate.** A game symbol composites over the reel, so it is
  rendered onto transparency. `create_image()` always treats `layers[0]` as
  the plate, so it gets a fully transparent one rather than being special-cased.
- **No `GROUND_SHADOW`, no `SUBJECT_SEPARATION`.** Both exist to seat the
  character *into a plate*; with no plate they would bake a grey smudge into
  the cutout. Every shadow that lives on the figure itself — skin, eyes,
  mouth, face inset — is left alone, which is most of what the recent work
  added.
- **Traits are pinned, not rolled.** `generate_random_combination()` picks
  skin / eyes / mouth at random, so the pick is forced by narrowing what
  `get_files()` reports for those three categories. Everything downstream —
  `ball_fit`, the hole registration, `armed_lift`, placement — then runs
  exactly as it does for a mint token.

Symbols are cropped to their alpha and fitted into a fixed box so the reel
cells stay optically even; the mascot keeps the full 1393 canvas, because the
pusher positions it by percentage against the frame.

  python3 asset_assessment/export_game_assets.py --out /path/to/games/public
  python3 asset_assessment/export_game_assets.py --only cone --out ...
  python3 asset_assessment/export_game_assets.py --contact-sheet /tmp/sheet.png
"""

import argparse
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator  # noqa: E402

# A plate is picked before it is thrown away, and the pick is not inert: it
# drives BG_CHAR_EXTRA_Y. Pin one that carries no entry so placement is the
# character's own.
NEUTRAL_PLATE = "Sugar.png"

# Trait files, by the display names in generator.TRAIT_NAMES.
SKIN = {
    "Alien": "layer-Skin_Alien (2).png",
    "Black": "layer-Skin_Black (3).png",
    "White": "layer-layer-layer-Skin_White (2).png",
}
EYES = {
    "Blue": "Blue.png",
    "Cerise": "Cerise.png",
    "Alien": "layer-Sweetardio_nft (15).png",
    "Cyan": "layer-Eyes_Cyan (1).png",
    "Googly": "layer-Eyes_Googly (1).png",
    "Side Eye": "layer-Eyes_Side_Eye (1).png",
    "Beady": "layer-art_mattrick_011.png",
    "Cyborg": "layer-file_000000001e1c71fd9d410745ea63114e (1).png",
    "Clueless": "layer-file_0000000062b071f8b3d115704b04609c (1).png",
    "Smug": "layer-file_00000000a21871f894573a9d4ee67519 (2).png",
}
MOUTH = {
    "Awkward Smile": "Awkward_smile.png",
    "Diamond Grill": "layer-Mouth_Diamond_Grill (1).png",
    "Fang": "layer-Mouth_Fang (1).png",
    "Flat": "layer-Mouth_Flat (1).png",
    "Lollipop": "layer-Mouth_Lollipop (1).png",
    "Smirk": "layer-Mouth_Smirk (1).png",
    "Smoke": "layer-Mouth_Smoke (1).png",
    "Tasty": "layer-Mouth_Tasty-1.png",
    "Sad": "layer-layer-layer-Mouth_Sad (1).png",
}
ARM = {
    "Cash": "Arms_Cash.png",
    "Katana": "Armz_Katana.png",
    "Knives": "Armz_Knives.png",
    "Blue Saber": "Sweetardio_114 (4).png",
    "Pink Saber": "Sweetardio_114 (5).png",
    "Cyan Saber": "Sweetardio_114 (6).png",
    "Dual Uzis": "Sweetardio_115 (11).png",
    "AK15": "layer-layer-layer-layer-AK15.png",
    "AR47": "layer-layer-layer-layer-AR47.png",
    "Military Brat": "layer-layer-layer-layer-Military_Brat.png",
    "Nerf Blaster": "layer-layer-layer-layer-Nerf_Blaster.png",
}

# The slot reel, in payout order. SkillGame.tsx pays by INDEX — index 0 is the
# 25x jackpot, index 8 the 0.2x — so the order of this list is the paytable.
# Renaming a symbol here means renaming it in SYMBOL_IMAGES too.
#
# `box` is the square each symbol is fitted into. It is deliberately smaller
# for the wide, squat bodies (the cookie, the waffles) than for the tall ones,
# so nine symbols of very different aspect read as the same visual weight in a
# reel cell rather than the widest one dominating.
SYMBOLS = [
    dict(file="cone.png",          char="neopolitan_ice_cream",
         skin="Black", eyes="Smug",     mouth="Flat",          arm="AK15"),
    dict(file="og-gummy-bear.png", char="og_gummy_bear",
         skin="Alien", eyes="Alien",    mouth="Smoke",         arm=None),
    dict(file="smores.png",        char="smores",
         skin="White", eyes="Googly",   mouth="Awkward Smile", arm=None),
    dict(file="churro.png",        char="churro",
         skin="Black", eyes="Beady",    mouth="Smirk",         arm=None),
    dict(file="cookie.png",        char="chocolate_chip_cookie",
         skin="White", eyes="Cyan",     mouth="Tasty",         arm=None),
    dict(file="waffle-gold.png",   char="gold_waffle",
         skin="Black", eyes="Cyborg",   mouth="Diamond Grill", arm="Cash"),
    dict(file="waffle.png",        char="waffle",
         skin="Alien", eyes="Cyan",     mouth="Flat",          arm=None),
    dict(file="sugar-cube.png",    char="sugar_cube",
         skin="White", eyes="Clueless", mouth="Sad",           arm=None),
    dict(file="twinkie.png",       char="Twinkie",
         skin="Black", eyes="Side Eye", mouth="Fang",          arm=None),
]

SYMBOL_BOX = 320       # px, the square a symbol is fitted into
SYMBOL_MARGIN = 12     # px of clear alpha kept inside that square

# Choppa Cone: the site mascot, and the figure the coin pusher raises from
# below. Kept at the full canvas because JunkPusherGame.tsx places it by
# percentage of the frame — cropping it would move it.
#
# The traits are the ones the site's existing mascot already wears, AR47's
# black rifle included, so this re-render reads as the SAME character with
# better lighting rather than as a new one. The reel's jackpot symbol is the
# same figure but carries the gold AK15 instead: it is the 25x cell and the
# gold says so at a glance.
#
# `bbox` is the footprint the shipped mascot.png already occupies inside the
# canvas. The site positions this file by percentage — MascotGuide.tsx in the
# corner, JunkPusherGame.tsx rising from below the pusher — so the figure's
# place *within* the 1393 square is layout, not art. A straight re-render is
# 606x809 against the old 814x1069 (the face assembly no longer scales with
# the 0.74 ice-cream body), which would silently shrink the mascot on every
# page that shows it. Refitting to the old footprint keeps both callers put.
MASCOT = dict(file="mascot.png", char="neopolitan_ice_cream",
              skin="Black", eyes="Smug", mouth="Flat", arm="AR47",
              bbox=(286, 222, 1100, 1291))


def pin_traits(skin_file, eye_file, mouth_file):
    """Narrow get_files() for the face categories so the random pick lands on
    the pinned trait. Returns the replacement; the caller restores the
    original. Every other category is passed through untouched, so arms,
    footwear and the character list behave normally."""
    real = generator.get_files
    pinned = {
        generator.SKINZ: [skin_file],
        generator.EYEZ: [eye_file],
        generator.MOUTHZ: [mouth_file],
    }

    def get_files(category):
        if category in pinned:
            files = real(category)
            for want in pinned[category]:
                if want not in files:
                    raise SystemExit(
                        f"traits/{category}/{want} is gone — the export "
                        f"tables in this script need updating")
            return list(pinned[category])
        return real(category)

    return get_files


def render(spec, out_path, box=None, margin=SYMBOL_MARGIN, bbox=None):
    """Render one pinned combination onto transparency."""
    real_get_files = generator.get_files
    real_ground = generator.GROUND_SHADOW
    real_sep = generator.SUBJECT_SEPARATION
    try:
        generator.get_files = pin_traits(SKIN[spec["skin"]], EYES[spec["eyes"]],
                                         MOUTH[spec["mouth"]])
        # No plate to seat the figure into, so the two plate-side effects are
        # off. Every on-figure shadow stays.
        generator.GROUND_SHADOW = None
        generator.SUBJECT_SEPARATION = None

        layers, char_name = generator.generate_random_combination(
            force_bg=(generator.BACKGROUNDZ, NEUTRAL_PLATE),
            force_char=spec["char"],
            force_arm=ARM[spec["arm"]] if spec["arm"] else None,
            force_wat=None,
            force_sticker=None,
        )
        if spec["arm"] and not any("armz" in os.path.normpath(l["path"]).split(os.sep)
                                   for l in layers):
            raise SystemExit(
                f"{spec['file']}: {char_name} is not allowed to hold "
                f"{spec['arm']} (see armz_allowed); pick another arm")

        layers[0] = {"path": transparent_plate(), "offset": False}
        generator.create_image(layers, output_name=out_path)
    finally:
        generator.get_files = real_get_files
        generator.GROUND_SHADOW = real_ground
        generator.SUBJECT_SEPARATION = real_sep

    if box:
        fit_to_box(out_path, box, margin)
    if bbox:
        fit_to_bbox(out_path, bbox)
    return out_path


_PLATE_CACHE = []


def transparent_plate():
    """A fully transparent canvas standing in for the background plate."""
    if not _PLATE_CACHE:
        path = os.path.join("output", "_transparent_plate.png")
        os.makedirs("output", exist_ok=True)
        Image.new("RGBA", (generator.CANVAS_SIZE, generator.CANVAS_SIZE),
                  (0, 0, 0, 0)).save(path)
        _PLATE_CACHE.append(path)
    return _PLATE_CACHE[0]


def fit_to_box(path, box, margin):
    """Crop to the figure and centre it in a `box`-square canvas.

    Fitting the LONGER side means a tall figure and a wide one end up the same
    height-or-width rather than the same area, which is what keeps a reel of
    mixed silhouettes looking evenly weighted.
    """
    img = Image.open(path).convert("RGBA")
    bbox = img.getchannel("A").getbbox()
    if bbox is None:
        raise SystemExit(f"{path} rendered empty")
    img = img.crop(bbox)
    inner = box - 2 * margin
    scale = inner / max(img.size)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    img = img.resize(size, Image.LANCZOS)
    out = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    out.paste(img, ((box - size[0]) // 2, (box - size[1]) // 2))
    out.save(path)


def fit_to_bbox(path, target):
    """Rescale the figure onto a target footprint inside the same canvas.

    Anchored bottom-centre, because that is the edge the callers reason about:
    the pusher slides the mascot up from below the frame and the corner guide
    stands it on the page's baseline. Scaling by the smaller of the two ratios
    keeps the aspect the art was rendered at — the target box is a footprint to
    sit inside, not a shape to distort to.
    """
    tx0, ty0, tx1, ty1 = target
    img = Image.open(path).convert("RGBA")
    bbox = img.getchannel("A").getbbox()
    if bbox is None:
        raise SystemExit(f"{path} rendered empty")
    fig = img.crop(bbox)
    scale = min((tx1 - tx0) / fig.width, (ty1 - ty0) / fig.height)
    size = (max(1, round(fig.width * scale)), max(1, round(fig.height * scale)))
    fig = fig.resize(size, Image.LANCZOS)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(fig, ((tx0 + tx1) // 2 - size[0] // 2, ty1 - size[1]))
    out.save(path)


def contact_sheet(paths, out_path, cols=5, cell=320):
    """Lay the rendered symbols out on one sheet, captioned, for eyeballing."""
    label = 30
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label)), (18, 18, 18))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for i, path in enumerate(paths):
        img = Image.open(path).convert("RGBA")
        img.thumbnail((cell, cell), Image.LANCZOS)
        x, y = (i % cols) * cell, (i // cols) * (cell + label)
        # over a mid grey, so both the dark and the pale bodies are legible
        tile = Image.new("RGBA", (cell, cell), (110, 110, 110, 255))
        tile.alpha_composite(img, ((cell - img.width) // 2,
                                   (cell - img.height) // 2))
        sheet.paste(tile.convert("RGB"), (x, y))
        draw.text((x + 6, y + cell + 6), f"{i}  {os.path.basename(path)}",
                  fill=(235, 235, 235), font=font)
    sheet.save(out_path)
    return out_path


def parse_args():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="output/game_assets",
                    help="the games repo's public/ directory (symbols land in "
                         "<out>/symbols, the mascot at <out>/mascot.png)")
    ap.add_argument("--only", default=None,
                    help="render one asset by file name, e.g. cone.png")
    ap.add_argument("--contact-sheet", default=None,
                    help="also write a captioned sheet of the symbols here")
    ap.add_argument("--seed", type=int, default=7,
                    help="RNG seed; every trait that matters is pinned, so "
                         "this only settles ties in untouched slots")
    return ap.parse_args()


def main():
    args = parse_args()
    random.seed(args.seed)

    sym_dir = os.path.join(args.out, "symbols")
    os.makedirs(sym_dir, exist_ok=True)

    wanted = args.only
    rendered = []
    for spec in SYMBOLS:
        if wanted and spec["file"] != wanted:
            continue
        path = os.path.join(sym_dir, spec["file"])
        render(spec, path, box=SYMBOL_BOX)
        print(f"  symbols/{spec['file']:20} {spec['char']}"
              f"  [{spec['skin']} / {spec['eyes']} / {spec['mouth']}"
              f"{' / ' + spec['arm'] if spec['arm'] else ''}]")
        rendered.append(path)

    if not wanted or wanted == MASCOT["file"]:
        path = os.path.join(args.out, MASCOT["file"])
        render(MASCOT, path, bbox=MASCOT["bbox"])
        print(f"  {MASCOT['file']:28} {MASCOT['char']} (full canvas)")

    if args.contact_sheet and rendered:
        print(f"  sheet -> {contact_sheet(rendered, args.contact_sheet)}")


if __name__ == "__main__":
    main()
