#!/usr/bin/env python3
"""Render specific characters (real generator pipeline) into a labelled
comparison strip with placement gridlines — a focused alternative to the
random 100-render batch for eyeballing scale/placement/arm changes.

Characters are produced by running generator.generate_random_combination()
under a fixed seed and keeping the first combination whose character name
contains each requested substring, so runs are reproducible. The background
plate is dropped and each figure is composited on a neutral canvas so only
the character geometry is compared; reference lines are drawn for the ball
center and the ground targets used by audit_placement.py.

Usage (from repo root):
  python3 asset_assessment/render_chars.py [name_substr ...]
Default set compares the gummy bears against the ice-cream / churro family.
Writes /tmp/char_compare.png
"""

import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g
from generator import create_image, generate_random_combination

SEED = 42
CANVAS = g.CANVAS_SIZE
CELL = 460
LINES = {          # y (canvas px) -> label, colour
    601: ("ball 601", (90, 200, 255)),
    957: ("stand 957", (120, 120, 120)),
    1107: ("ground 1107", (80, 220, 120)),
    1111: ("churro 1111", (230, 200, 80)),
    1290: ("cone 1290", (230, 120, 200)),
}
DEFAULT = ["og_gummy_bear", "cyan_gummy_bear", "pink_gummy_bear",
           "purple_gummy_bear", "vanilla_ice_cream", "churro", "twinkie"]


def font(size):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def collect(names, max_draws=4000):
    """seed -> first combination whose char name contains each substring."""
    random.seed(SEED)
    want = list(names)
    found = {}
    for _ in range(max_draws):
        layers, char = generate_random_combination()
        for w in want:
            if w in char.lower() and w not in found:
                found[w] = (layers, char)
        if len(found) == len(want):
            break
    return found


def render_one(layers):
    """Composite character-only (drop the background plate) on transparent."""
    tmp = "/tmp/_char_only.png"
    create_image(layers[1:], tmp)            # layers[0] is the bg plate
    return Image.open(tmp).convert("RGBA")


def main():
    names = sys.argv[1:] or DEFAULT
    found = collect(names)
    f18, f22 = font(18), font(22)
    cells = []
    for w in names:
        if w not in found:
            print(f"  (no draw produced {w})")
            continue
        layers, char = found[w]
        fig = render_one(layers)
        bg = Image.new("RGBA", (CANVAS, CANVAS), (28, 28, 32, 255))
        dr = ImageDraw.Draw(bg)
        for y, (lbl, col) in LINES.items():
            dr.line([(0, y), (CANVAS, y)], fill=col, width=2)
            dr.text((6, y + 2), lbl, fill=col, font=f18)
        bg.alpha_composite(fig)
        cell = bg.convert("RGB").resize((CELL, CELL), Image.LANCZOS)
        strip = Image.new("RGB", (CELL, CELL + 26), (14, 14, 14))
        strip.paste(cell, (0, 0))
        ImageDraw.Draw(strip).text((6, CELL + 3), f"{char[:24]} x{g.char_scale(char):.2f}",
                                   fill=(235, 235, 235), font=f22)
        cells.append(strip)

    if not cells:
        print("nothing rendered")
        return
    W = sum(c.width for c in cells)
    sheet = Image.new("RGB", (W, cells[0].height), (14, 14, 14))
    x = 0
    for c in cells:
        sheet.paste(c, (x, 0))
        x += c.width
    out = "/tmp/char_compare.png"
    sheet.save(out)
    print("wrote", out, sheet.size)


if __name__ == "__main__":
    main()
