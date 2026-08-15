#!/usr/bin/env python3
"""Render catalog/highlights_25.png -- 25 curated tokens, not 25 random ones.

Every other sheet in catalog/ answers "what does the collection mint?".
This one answers "what does it look like when it goes right", so the picks are
by eye and the file records them.

How the 25 were chosen: 200 tokens were rendered off the production pipeline
at POOL_SEED, scored to prune the muddy and the flat -- colourfulness, the
luma gap between the body and the ring of plate around it, distance from the
family's mid-key target, and how loud the plate is right behind the head --
and the top of that ranking was then looked at and picked over. The score only
prunes. It cannot tell a striking token from a merely high-contrast one, and
left to itself it returns eight marshmallows on dark plates: pale body, busy
frame, top of the list. The final set spans 23 of the 27 characters.

PICKS are indices into that seeded run, so the sheet is exactly reproducible
as long as the collection's assets do not change. It is NOT reproducible
across an asset change -- adding or retiring any trait re-randomises every
draw after it, and the indices then point at different tokens. Re-curate
rather than trusting a stale index list; the sheet is a curated artefact, not
a measurement.

  python3 asset_assessment/render_highlights.py
  python3 asset_assessment/render_highlights.py --cell 700 --out /tmp/big.png
"""
import argparse
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g  # noqa: E402
from generator import (  # noqa: E402
    create_image, extract_metadata, generate_random_combination,
)

POOL_SEED = 8215
POOL_N = 200
PICKS = [122, 76, 125, 82, 18, 94, 124, 163, 153, 101, 10, 49, 102, 111, 128,
         38, 180, 176, 47, 152, 154, 24, 169, 59, 78]

COLS = 5
LABEL_H = 46
BG = (16, 16, 20)
FG = (238, 238, 238)
DIM = (150, 170, 200)


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def fit(draw, text, fnt, width):
    while text and draw.textlength(text, font=fnt) > width:
        text = text[:-1]
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", type=int, default=560)
    ap.add_argument("--out", default="catalog/highlights_25.png")
    ap.add_argument("--token-dir", default="output/highlights")
    a = ap.parse_args()

    os.makedirs(a.token_dir, exist_ok=True)
    wanted = set(PICKS)
    tokens = {}

    # Replay the seeded pool and keep only the picks. The draws have to run in
    # order: each one advances the shared RNG, so skipping ahead changes them.
    random.seed(POOL_SEED)
    for i in range(POOL_N):
        layers, char = generate_random_combination()
        if i not in wanted:
            continue
        path = os.path.join(a.token_dir, f"{i:03d}.png")
        create_image(layers, path)
        attrs = {d["trait_type"]: d["value"]
                 for d in extract_metadata(layers, char)}
        tokens[i] = (path, attrs)
        print(f"  {i:>3}  {attrs.get('Character','?'):<26} "
              f"{attrs.get('Background','?')}")

    missing = wanted - set(tokens)
    if missing:
        sys.exit(f"picks not produced by the seeded run: {sorted(missing)} — "
                 f"the assets have changed since curation, so re-curate")

    rows = (len(PICKS) + COLS - 1) // COLS
    cell = a.cell
    sheet = Image.new("RGB", (COLS * cell, rows * (cell + LABEL_H)), BG)
    dr = ImageDraw.Draw(sheet)
    f_name, f_sub = font(19), font(15)

    for k, idx in enumerate(PICKS):
        path, attrs = tokens[idx]
        x, y = (k % COLS) * cell, (k // COLS) * (cell + LABEL_H)
        sheet.paste(Image.open(path).convert("RGB")
                    .resize((cell, cell), Image.LANCZOS), (x, y))
        dr.text((x + 10, y + cell + 15),
                fit(dr, attrs.get("Character", "?"), f_name, cell - 20),
                font=f_name, fill=FG, anchor="lm")
        dr.text((x + 10, y + cell + 34),
                fit(dr, attrs.get("Background", "?"), f_sub, cell - 20),
                font=f_sub, fill=DIM, anchor="lm")

    dr.text((sheet.width - 10, sheet.height - 8),
            f"seed {POOL_SEED} · curated from {POOL_N}", font=f_sub,
            fill=(110, 110, 120), anchor="rb")
    sheet.save(a.out)
    print(f"\n{a.out}  {sheet.width}x{sheet.height}  {len(PICKS)} tokens")


if __name__ == "__main__":
    main()
