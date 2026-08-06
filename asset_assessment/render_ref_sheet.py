#!/usr/bin/env python3
"""Render the 1:1 reference sheet handed to an image generator (catalog/<class>_reference_sheet.png).

Unlike catalog/traitsheet_*.png, which scales every asset to fill its tile,
this sheet draws each asset at its NATIVE pixel size on a common grid. Relative
scale and aspect ratio survive, so the generator can see that the assets differ
in size and proportion — the things it is most likely to "fix" on its own and
the things the compositor cannot tolerate, because eyes and mouths land at
fixed canvas coordinates and the skin ball is sized to fit the widest eyes.

Sizing targets what actually reaches the model: image models downsample an
input to roughly 1024px on the long side, so a bigger sheet does not mean more
detail. Sheets that come out under that budget are scaled up to fill it, which
gives small assets (a 48x7 flat mouth) far more pixels in model-space; sheets
already at or over it are left at 1:1. Labels always state true native size.

  python3 asset_assessment/render_ref_sheet.py skinz
  python3 asset_assessment/render_ref_sheet.py eyez
  python3 asset_assessment/render_ref_sheet.py mouthz --cols 4
  python3 asset_assessment/render_ref_sheet.py mouthz --scale 3 --out /tmp/big.png

See SKIN_ENHANCE_PROMPTS.md / EYEZ_ENHANCE_PROMPTS.md / MOUTHZ_ENHANCE_PROMPTS.md
for the prompts these sheets accompany.
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g  # noqa: E402

PAGE_BG = (18, 18, 20)
MATTE = (115, 115, 115)      # neutral: separates both pale and dark assets
HEADER_BG = (28, 28, 32)
TITLE_RGB = (230, 210, 80)
LABEL_RGB = (240, 240, 242)
DIM_RGB = (170, 170, 174)
HEADER_H = 44
LABEL_BAND = 46
MARGIN = 26                  # gray around the widest asset in its cell
TARGET_SIDE = 1024           # what an image model actually sees
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_PLAIN = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

CLASSES = {
    "skinz": (g.SKINZ, "Skin Traits"),
    "eyez": (g.EYEZ, "Eye Traits"),
    "mouthz": (g.MOUTHZ, "Mouth Traits"),
}


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def parse_args():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trait_class", choices=sorted(CLASSES),
                    help="which trait class to sheet")
    ap.add_argument("--cols", type=int, default=3, help="cells per row")
    ap.add_argument("--scale", type=float, default=None,
                    help="force a supersample factor (default: fill 1024px)")
    ap.add_argument("--target-side", type=int, default=TARGET_SIDE,
                    help="long-side budget the sheet is scaled up to fill")
    ap.add_argument("--out", default=None,
                    help="default catalog/<class>_reference_sheet.png")
    return ap.parse_args()


def main():
    args = parse_args()
    trait_dir, title = CLASSES[args.trait_class]
    files = g.get_files(trait_dir)
    if not files:
        sys.exit(f"no assets found in traits/{trait_dir}")

    # measure everything first: the grid is sized by the largest asset so each
    # is drawn 1:1 and the size differences between them stay visible
    items = []
    for fname in files:
        path = os.path.join(g.TRAITS_DIR, trait_dir, fname)
        x0, y0, x1, y1 = g._opaque_bbox(path)
        items.append({
            "file": fname,
            "name": g.trait_name(trait_dir, fname),
            "img": Image.open(path).convert("RGBA").crop((x0, y0, x1, y1)),
            "w": x1 - x0,
            "h": y1 - y0,
            "cx": (x0 + x1) // 2,
            "cy": (y0 + y1) // 2,
        })
    items.sort(key=lambda it: it["name"])

    cell_w = max(it["w"] for it in items) + 2 * MARGIN
    cell_h = max(it["h"] for it in items) + 2 * MARGIN
    cols = min(args.cols, len(items))
    rows = (len(items) + cols - 1) // cols
    sheet_w = cols * cell_w
    sheet_h = HEADER_H + rows * (cell_h + LABEL_BAND)

    # scale up only if the 1:1 sheet is under the model's downsample budget:
    # more pixels on a small asset is free, fewer is not recoverable
    if args.scale is not None:
        scale = args.scale
    else:
        scale = max(1.0, args.target_side / max(sheet_w, sheet_h))
    shown = f"shown 1:1" if scale == 1.0 else f"shown at {scale:.2f}x"

    sheet = Image.new("RGB", (sheet_w, sheet_h), PAGE_BG)
    draw = ImageDraw.Draw(sheet)

    draw.rectangle((0, 0, sheet_w, HEADER_H), fill=HEADER_BG)
    draw.text((14, HEADER_H // 2), f"Sweetardio — {title}", fill=TITLE_RGB,
              font=font(FONT_BOLD, 22), anchor="lm")
    draw.text((sheet_w - 14, HEADER_H // 2),
              f"{shown} — proportions are exact",
              fill=DIM_RGB, font=font(FONT_PLAIN, 14), anchor="rm")

    f_name = font(FONT_BOLD, 16)
    f_meta = font(FONT_PLAIN, 12)
    for i, it in enumerate(items):
        cx0 = (i % cols) * cell_w
        cy0 = HEADER_H + (i // cols) * (cell_h + LABEL_BAND)
        draw.rectangle((cx0, cy0, cx0 + cell_w - 1, cy0 + cell_h - 1),
                       fill=MATTE)
        sheet.paste(it["img"],
                    (cx0 + (cell_w - it["w"]) // 2,
                     cy0 + (cell_h - it["h"]) // 2),
                    it["img"])
        ty = cy0 + cell_h
        draw.text((cx0 + 10, ty + 8), f'{i+1}. {it["name"]}',
                  fill=LABEL_RGB, font=f_name)
        draw.text((cx0 + 10, ty + 28),
                  f'{it["w"]}x{it["h"]} px  ·  centre ({it["cx"]}, {it["cy"]})',
                  fill=DIM_RGB, font=f_meta)

    # unused cells stay page-coloured, not gray, so they read as empty
    if scale != 1.0:
        sheet = sheet.resize((round(sheet_w * scale), round(sheet_h * scale)),
                             Image.LANCZOS)

    out = args.out or os.path.join(
        "catalog", f"{args.trait_class}_reference_sheet.png")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out)
    print(f"wrote {out}  ({sheet.width}x{sheet.height}, "
          f"{os.path.getsize(out)/1e6:.2f} MB)")
    print(f"{len(items)} {args.trait_class}, {cell_w}x{cell_h} cells, {shown}")
    for i, it in enumerate(items):
        print(f"  {i+1:2d}. {it['name']:18s} {it['w']}x{it['h']}   {it['file']}")


if __name__ == "__main__":
    main()
