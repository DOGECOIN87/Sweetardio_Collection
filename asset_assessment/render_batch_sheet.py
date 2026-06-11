#!/usr/bin/env python3
"""Generate 100 random combinations and assemble them into a contact sheet.

Uses generator.py's full random pipeline (weights, blocklist, footwear rules,
ball_fit, VERTICAL_OFFSET, Whitehouse_Lawn overlay, gorbhouse, etc.) exactly
as production would. Outputs:
  /tmp/batch100_sheet.png     - 10x10 grid at 350px/cell, good for overview
  /tmp/batch100_strip_*.png   - 4 strips of 25 at 500px, easier to zoom

Usage (from repo root): python3 asset_assessment/render_batch_sheet.py
"""

import os
import random
import sys
import time

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator import create_image, generate_random_combination  # noqa

SEED = 42   # deterministic run; change or remove for a different 100
N = 100
CELL = 350  # px per thumbnail in the 10x10 overview grid
STRIP_CELL = 500  # px per cell in the 4×25 zoomed strips
OUT_DIR = "/tmp/batch100"


def font(size):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def main():
    random.seed(SEED)
    os.makedirs(OUT_DIR, exist_ok=True)

    paths = []
    char_names = []
    t0 = time.time()
    for i in range(N):
        layers, char_name = generate_random_combination()
        out = os.path.join(OUT_DIR, f"{i+1:03d}_{char_name}.png")
        create_image(layers, out)
        paths.append(out)
        char_names.append(char_name)
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{N}  ({time.time()-t0:.0f}s)")

    print(f"all {N} renders done in {time.time()-t0:.0f}s")

    # ── 10x10 overview sheet ─────────────────────────────────────────────
    cols, rows = 10, 10
    sheet = Image.new("RGB", (cols * CELL, rows * CELL), (14, 14, 14))
    for i, p in enumerate(paths):
        im = Image.open(p).convert("RGB").resize((CELL, CELL), Image.LANCZOS)
        sheet.paste(im, ((i % cols) * CELL, (i // cols) * CELL))
    overview = "/tmp/batch100_sheet.png"
    sheet.save(overview)
    print("wrote", overview)

    # ── 4 strips of 25 at higher res ─────────────────────────────────────
    f18 = font(18)
    strip_size = 25
    for s in range(4):
        chunk = paths[s * strip_size:(s + 1) * strip_size]
        names = char_names[s * strip_size:(s + 1) * strip_size]
        strip = Image.new("RGB",
                          (strip_size * STRIP_CELL, STRIP_CELL + 24),
                          (14, 14, 14))
        dr = ImageDraw.Draw(strip)
        for j, (p, n) in enumerate(zip(chunk, names)):
            im = Image.open(p).convert("RGB").resize(
                (STRIP_CELL, STRIP_CELL), Image.LANCZOS)
            strip.paste(im, (j * STRIP_CELL, 0))
            label = f"{s*25+j+1:03d} {n[:16]}"
            dr.text((j * STRIP_CELL + 4, STRIP_CELL + 4), label,
                    fill=(235, 235, 235), font=f18)
        out_strip = f"/tmp/batch100_strip_{s+1}.png"
        strip.save(out_strip)
        print("wrote", out_strip)

    print("done.")


if __name__ == "__main__":
    main()
