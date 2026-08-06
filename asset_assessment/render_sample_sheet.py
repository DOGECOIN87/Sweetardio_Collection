#!/usr/bin/env python3
"""Render N random tokens and assemble them into a labeled inspection sheet.

Uses generator.py's full production pipeline (weights, compat blocklists,
footwear rules, ball_fit, character scale, shadows, overlays), so the sheet
shows exactly what the collection mints today.

Every cell is captioned with its index and character name, and the run prints
a manifest (one line per token, all traits) so anything that looks wrong on
the sheet can be traced back to the traits that produced it.

The seed is random unless you pass --seed, and is always printed / stamped on
the sheet, so any sheet can be re-rendered identically:

  python3 asset_assessment/render_sample_sheet.py                 # fresh 100
  python3 asset_assessment/render_sample_sheet.py --seed 4444     # reproduce
  python3 asset_assessment/render_sample_sheet.py --n 25 --cell 500 \
      --out /tmp/quick.png                                        # quick look

Default output is catalog/sample_batch_100.png (the committed reference
sheet). Individual token PNGs land in --token-dir (default output/sample_batch,
git-ignored) if you want to zoom on one at native 1393px.
"""

import argparse
import os
import random
import sys
import time

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator  # noqa: E402
from generator import (  # noqa: E402
    create_image,
    extract_metadata,
    generate_random_combination,
)

LABEL_H = 36  # caption band under each cell, in px
BG = (14, 14, 14)
FG = (235, 235, 235)


def font(size):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=100, help="tokens to render")
    ap.add_argument("--seed", type=int, default=None,
                    help="RNG seed (default: random, printed and stamped)")
    ap.add_argument("--cols", type=int, default=10, help="cells per row")
    ap.add_argument("--cell", type=int, default=700, help="px per cell")
    ap.add_argument("--out", default="catalog/sample_batch_100.png",
                    help="sheet path")
    ap.add_argument("--token-dir", default="output/sample_batch",
                    help="where the individual token PNGs are written")
    ap.add_argument("--backgrounds", default=None,
                    help="swap the background plate dir for A/B testing")
    return ap.parse_args()


def main():
    args = parse_args()
    if args.backgrounds:
        # os.path.join(TRAITS_DIR, <absolute path>) resolves to the absolute
        # path, so this reroutes every background lookup in generator.py
        generator.BACKGROUNDZ = os.path.abspath(args.backgrounds)
        print(f"backgrounds dir override: {generator.BACKGROUNDZ}")

    seed = args.seed if args.seed is not None else random.randrange(1, 10**9)
    random.seed(seed)
    print(f"seed {seed} — re-render this exact sheet with --seed {seed}")

    os.makedirs(args.token_dir, exist_ok=True)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)

    tokens = []  # (path, character display name, attributes)
    t0 = time.time()
    for i in range(args.n):
        layers, char_name = generate_random_combination()
        meta = extract_metadata(layers, char_name)
        path = os.path.join(args.token_dir, f"{i+1:03d}_{char_name}.png")
        create_image(layers, path)
        display = next((a["value"] for a in meta
                        if a["trait_type"] in ("Character", "Secret Rarez")),
                       char_name)
        tokens.append((path, display, meta))
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{args.n}  ({time.time()-t0:.0f}s)")
    print(f"all {args.n} renders done in {time.time()-t0:.0f}s")

    # ── manifest: what each cell is made of ──────────────────────────────
    print("\nmanifest")
    for i, (_, _, meta) in enumerate(tokens):
        traits = " · ".join(f"{a['trait_type']}: {a['value']}" for a in meta)
        print(f"  {i+1:03d}  {traits}")

    # ── contact sheet ────────────────────────────────────────────────────
    cols = args.cols
    rows = (args.n + cols - 1) // cols
    cell, row_h = args.cell, args.cell + LABEL_H
    # + one footer band for the seed stamp, so it can never collide with the
    # last cell's caption
    sheet = Image.new("RGB", (cols * cell, rows * row_h + LABEL_H), BG)
    draw = ImageDraw.Draw(sheet)
    caption = font(max(12, LABEL_H // 2))

    for i, (path, display, _) in enumerate(tokens):
        x, y = (i % cols) * cell, (i // cols) * row_h
        im = Image.open(path).convert("RGB").resize((cell, cell), Image.LANCZOS)
        sheet.paste(im, (x, y))
        draw.text((x + 8, y + cell + LABEL_H // 5),
                  f"{i+1:03d}  {display}", fill=FG, font=caption)

    stamp = f"seed {seed} · {args.n} random tokens"
    draw.text((sheet.width - 8, sheet.height - LABEL_H + LABEL_H // 5), stamp,
              fill=(140, 140, 140), font=caption, anchor="ra")

    sheet.save(args.out)
    print(f"\nwrote {args.out}  ({sheet.width}×{sheet.height}, "
          f"{os.path.getsize(args.out)/1e6:.1f} MB)")
    print(f"tokens in {args.token_dir}/")


if __name__ == "__main__":
    main()
