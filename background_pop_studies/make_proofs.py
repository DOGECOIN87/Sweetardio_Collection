#!/usr/bin/env python3
"""Proof images for the Sweetardio background grade.

Builds Original-vs-Graded side-by-sides with REAL composited characters
(layer order copied from generator.py: character -> skinz -> eyez -> mouthz
-> armz, +150 px vertical offset for non-ice-cream characters without
footwear), plus colour chips: the 5 brand palette colours and the measured
dominant colours of the composited character. Also builds a 3x3 cohesion
grid of graded plates.

Usage (from repo root):
  python3 background_pop_studies/make_proofs.py --phase1   # 4 sample pairs
  python3 background_pop_studies/make_proofs.py --final    # pairs + 3x3 grid
"""

import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC = "traits/backgroundz_originals"
DST = "traits/backgroundz"
OUT = "background_pop_studies/samples"
CANVAS = 1393
OFFSET = 150

BRAND = [("Oxford", "#070F34"), ("Zaffre", "#0313A6"),
         ("Violet", "#9201CB"), ("Cerise", "#F715AB"), ("Cyan", "#34EDF3")]

# deterministic trait picks for proof characters (generator.py layer order)
SKIN = "traits/skinz/layer-layer-layer-Skin_White (2).png"
EYES = "traits/eyez/Blue.png"
MOUTH = "traits/mouthz/Awkward_smile.png"
ARMS = "traits/armz/layer-layer-layer-layer-Shy-1.png"

# plate -> (character, needs_offset, eyes) ; hard cases on purpose:
# dark-on-dark, bright-on-bright, busy+mid, warm-on-warm, plus the two
# palette-collision cases from the vertical split study: cyan scoop on the
# bluest plate, cerise scoop on the magenta plate. Ice creams get no
# vertical offset (generator.py EXCLUDE_WAT_CHARS rule).
PHASE1 = [
    ("Cookboy", "after_skinz_brownie_bite", True, None),
    ("Celestial", "after_skinz_marshmallow", True, None),
    ("Why_So_Cereal", "after_skinz_glazed_doughnut", True, None),
    ("Sweetardio", "after_skinz_chocolate_chip_cookie", True, None),
    ("Sweet_Castle_2", "before_skinz_cyan_sherbert_ice_cream", False,
     "traits/eyez/Cerise.png"),
    ("Bubble_Trouble", "before_skinz_pink_sherbert_ice_cream", False, None),
]

# single-tone worst cases (cast is NOT all dual-tone): gummy worm lives in
# the stage's own blue corridor; cyan poptart is uniformly cool; chocolate
# doughnut is uniformly dark-warm on the darkest navy plate.
VERIFY = [
    ("Smuckers_Blue", "layer-after_skinz_gummy_worm (1)", True,
     "traits/eyez/Cerise.png"),
    ("Blue_Fur", "before_skinz_cyan_frosted_poptart", True,
     "traits/eyez/Cerise.png"),
    ("Tootsie_Blue", "after_skinz_chocolate_doughnut", True, None),
]


def font(sz):
    try:
        return ImageFont.load_default(size=sz)
    except TypeError:
        return ImageFont.load_default()


def load_layer(path):
    im = Image.open(path).convert("RGBA")
    if im.size != (CANVAS, CANVAS):
        im = im.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS)
    return im


def build_character(char_file, offset=True, eyes=None):
    """Composite a character cutout exactly like generator.py (no plate)."""
    import sys
    sys.path.insert(0, ".")
    from generator import is_skin_under, face_fit, scale_about
    cut = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    eye_path = eyes or EYES
    char_path = f"traits/characterz/{char_file}.png"
    body = [SKIN, char_path] if is_skin_under(f"{char_file}.png") \
        else [char_path, SKIN]
    fit, ctr = face_fit(SKIN, eye_path)
    for p in body + [eye_path, MOUTH, ARMS]:
        im = load_layer(p)
        if p in (eye_path, MOUTH):
            im = scale_about(im, fit, ctr)
        if offset:
            shifted = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
            shifted.paste(im, (0, OFFSET))
            im = shifted
        cut.alpha_composite(im)
    return cut


def dominant_of(char_file):
    recs = json.load(open("asset_assessment/metrics.json"))
    for r in recs:
        if r.get("folder") == "characterz" and char_file in r["file"]:
            return [d["hex"] for d in r["dominant"][:3]]
    return []


def panel(plate_path, char, label, chips, width=660):
    plate = load_layer(plate_path)
    comp = plate.copy()
    comp.alpha_composite(char)
    comp = comp.convert("RGB").resize((width, width), Image.Resampling.LANCZOS)
    strip_h = 64
    out = Image.new("RGB", (width, width + 30 + strip_h), (16, 16, 16))
    d = ImageDraw.Draw(out)
    d.text((10, 6), label, fill=(240, 240, 240), font=font(20))
    out.paste(comp, (0, 30))
    x = 10
    for name, hexc in chips:
        d.rectangle([x, width + 36, x + 52, width + 36 + 40],
                    fill=hexc, outline=(255, 255, 255))
        d.text((x, width + 36 + 42), name[:7], fill=(200, 200, 200),
               font=font(11))
        x += 60
    return out


def side_by_side(stem, char_file, offset, out_path, eyes=None):
    char = build_character(char_file, offset, eyes)
    chips = BRAND + [(f"body{i+1}", h)
                     for i, h in enumerate(dominant_of(char_file))]
    src = None
    for ext in (".png", ".jpg"):
        p = os.path.join(SRC, stem + ext)
        if os.path.exists(p):
            src = p
            break
    dst = os.path.join(DST, stem + ".png")
    a = panel(src, char, f"ORIGINAL  {stem}", chips)
    b = panel(dst, char, "GRADED (cool / desat / mid-key stage)", chips)
    sheet = Image.new("RGB", (a.width * 2 + 12, a.height), (16, 16, 16))
    sheet.paste(a, (0, 0))
    sheet.paste(b, (a.width + 12, 0))
    sheet.save(out_path)
    print("wrote", out_path)


def cohesion_grid(out_path, n=9, cell=420):
    files = sorted(f for f in os.listdir(DST) if f.endswith(".png"))
    if len(files) < n:
        print(f"grid skipped ({len(files)} graded plates < {n})")
        return
    # spread picks evenly across the (sorted) set
    idx = np.linspace(0, len(files) - 1, n).round().astype(int)
    grid = Image.new("RGB", (cell * 3, cell * 3), (10, 10, 10))
    for k, i in enumerate(idx):
        im = Image.open(os.path.join(DST, files[i])).convert("RGB")
        im = im.resize((cell, cell), Image.Resampling.LANCZOS)
        grid.paste(im, ((k % 3) * cell, (k // 3) * cell))
    grid.save(out_path)
    print("wrote", out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", action="store_true")
    ap.add_argument("--verify", action="store_true",
                    help="single-tone worst-case pairs only")
    ap.add_argument("--final", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    prefix = "verify" if args.verify else ("phase1" if args.phase1
                                           else "final")
    pairs = VERIFY if args.verify else PHASE1
    for stem, char_file, off, eyes in pairs:
        safe = stem.replace(" ", "_").replace("(", "").replace(")", "")[:40]
        side_by_side(stem, char_file, off,
                     os.path.join(OUT, f"{prefix}_{safe}.png"), eyes)
    if args.final:
        cohesion_grid(os.path.join(OUT, "final_cohesion_3x3.png"))


if __name__ == "__main__":
    main()
