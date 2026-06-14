#!/usr/bin/env python3
"""Before/after comparison for the character grounding shadow (GROUND_SHADOW).

Renders a diverse set of characters twice through the real generator.py
compositing path — shadow OFF (GROUND_SHADOW=None) vs ON — and stacks the two
side by side per character so the owner can approve the effect. Also prints,
per character, the silhouette's lowest opaque row and the mode the "auto"
rule picked (ground contact pool vs soft drop).

Usage (from repo root): python3 asset_assessment/render_ground_shadow.py
Writes: /tmp/ground_shadow_before_after.png
"""

import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as gen  # noqa: E402

# A diverse spread: grounded ice cream + bear, a footwear wearer, a gorbhouse
# doughnut, centred floaters (cookie, gummy worm, footwear-less doughnut),
# plus a churro. We seed-search generate_random_combination for one combo of
# each so every render goes through the production pipeline untouched.
WANT = [
    ("ice cream", lambda n: "ice_cream" in n),
    ("gummy bear", lambda n: "gummy_bear" in n),
    ("cookie (centred)", lambda n: "cookie" in n),
    ("gummy worm (centred)", lambda n: "gummy_worm" in n),
    ("churro", lambda n: "churro" in n),
    ("twinkie", lambda n: n == "twinkie"),
    ("doughnut", lambda n: "doughnut" in n),
    ("marshmallow", lambda n: "marshmallow" in n),
]

CELL = 460
PAD = 10
HEAD = 56


def font(size):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def find_combo(pred, has_footwear=None):
    """Seeded search for a combination whose character matches pred. When
    has_footwear is set, also require (or forbid) a what_are_thosez layer."""
    wat_dir = os.path.normpath(os.path.join(gen.TRAITS_DIR, gen.WHAT_ARE_THOSEZ))
    for s in range(5000):
        random.seed(s)
        layers, name = gen.generate_random_combination()
        if not pred(name):
            continue
        if has_footwear is not None:
            wat = any(os.path.normpath(l["path"]).startswith(wat_dir + os.sep)
                      for l in layers)
            if wat != has_footwear:
                continue
        return layers, name
    return None, None


def silhouette_info(layers):
    """Replay the compositor's silhouette build to report the auto decision."""
    sticker_prefix = os.path.normpath(os.path.join(gen.TRAITS_DIR, gen.STICKERZ))
    armz_prefix = os.path.normpath(os.path.join(gen.TRAITS_DIR, gen.ARMZ))
    overlay_names = set(gen.BG_OVERLAY_PAIRS.values())
    sil = Image.new("L", (gen.CANVAS_SIZE, gen.CANVAS_SIZE), 0)
    for li in layers[1:]:
        p = os.path.normpath(li["path"])
        if p.startswith(sticker_prefix + os.sep) or \
                os.path.basename(p) in overlay_names:
            continue
        if p.startswith(armz_prefix + os.sep):  # exclude_arms default
            continue
        img = gen._render_layer(li)
        if img is not None:
            sil = ImageChops.lighter(sil, img.getchannel("A"))
    bbox = sil.getbbox()
    bottom = bbox[3] if bbox else None
    gl = (gen.GROUND_SHADOW or {}).get("ground_line", 1040)
    mode = "ground" if (bottom is not None and bottom >= gl) else "drop"
    return bottom, mode


def main():
    saved = gen.GROUND_SHADOW
    f24, f18 = font(24), font(18)
    cols = len(WANT)
    sheet = Image.new("RGB", (cols * (CELL + PAD) + PAD, 2 * CELL + HEAD + PAD),
                      (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    dr.text((PAD, 8), "top: shadow OFF      bottom: shadow ON",
            fill=(255, 255, 64), font=f24)

    for ci, (label, pred) in enumerate(WANT):
        layers, name = find_combo(pred)
        x = PAD + ci * (CELL + PAD)
        if layers is None:
            dr.text((x, HEAD), f"{label}\n(not found)", fill=(255, 80, 80),
                    font=f18)
            continue
        bottom, mode = silhouette_info(layers)

        gen.GROUND_SHADOW = None
        off = gen.create_image(layers, f"/tmp/gs_off_{ci}.png")
        gen.GROUND_SHADOW = saved
        on = gen.create_image(layers, f"/tmp/gs_on_{ci}.png")

        for ri, p in enumerate((off, on)):
            im = Image.open(p).convert("RGB").resize(
                (CELL, CELL), Image.Resampling.LANCZOS)
            sheet.paste(im, (x, HEAD + ri * (CELL + PAD)))
        dr.text((x + 2, HEAD + 2),
                f"{name[:20]}\nbottom={bottom} mode={mode}",
                fill=(235, 235, 235), font=f18)

    out = "/tmp/ground_shadow_before_after.png"
    sheet.save(out)
    print("wrote", out)
    gen.GROUND_SHADOW = saved


if __name__ == "__main__":
    main()
