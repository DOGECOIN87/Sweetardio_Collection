#!/usr/bin/env python3
"""Render the skin-reference sheet handed to an image generator (catalog/skin_reference_sheet.png).

Unlike catalog/traitsheet_skinz.png, which scales every ball to fill its tile,
this sheet draws each ball at its NATIVE pixel size on a common grid. Relative
scale and aspect ratio survive, so the generator can see that the balls differ
in size and that none of them is a perfect circle — the two things it is most
likely to "fix" on its own and the two things the compositor cannot tolerate.

Sizing is deliberate: image models downsample an input to roughly 1024px on the
long side, so a bigger sheet does not mean more detail — it means each ball
arrives SMALLER in model-space. The default keeps the long side near 1024 with
the balls at 1:1, which is the most detail that can actually reach the model.
Use --scale for a larger, more legible copy to read yourself.

  python3 asset_assessment/render_skin_ref_sheet.py
  python3 asset_assessment/render_skin_ref_sheet.py --scale 2 --out /tmp/big.png

See SKIN_ENHANCE_PROMPTS.md for the prompts this sheet accompanies.
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g  # noqa: E402

PAGE_BG = (18, 18, 20)
MATTE = (115, 115, 115)      # neutral: separates both the pale and dark balls
HEADER_BG = (28, 28, 32)
TITLE_RGB = (230, 210, 80)
LABEL_RGB = (240, 240, 242)
DIM_RGB = (170, 170, 174)
HEADER_H = 44
LABEL_BAND = 46
MARGIN = 26                  # gray around the widest ball in its cell
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_PLAIN = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def parse_args():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cols", type=int, default=3, help="cells per row")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="supersample the finished sheet (1 = model-optimal)")
    ap.add_argument("--out", default="catalog/skin_reference_sheet.png")
    return ap.parse_args()


def main():
    args = parse_args()
    skins = g.get_files(g.SKINZ)
    if not skins:
        sys.exit("no skins found in traits/skinz")

    # measure every ball first: the grid is sized by the widest/tallest one so
    # each is drawn 1:1 and the size differences stay visible
    balls = []
    for fname in skins:
        path = os.path.join(g.TRAITS_DIR, g.SKINZ, fname)
        x0, y0, x1, y1 = g._opaque_bbox(path)
        im = Image.open(path).convert("RGBA").crop((x0, y0, x1, y1))
        balls.append({
            "file": fname,
            "name": g.trait_name(g.SKINZ, fname),
            "img": im,
            "w": x1 - x0,
            "h": y1 - y0,
            "cx": (x0 + x1) // 2,
            "cy": (y0 + y1) // 2,
        })
    balls.sort(key=lambda b: b["name"])

    cell_w = max(b["w"] for b in balls) + 2 * MARGIN
    cell_h = max(b["h"] for b in balls) + 2 * MARGIN
    cols = args.cols
    rows = (len(balls) + cols - 1) // cols
    sheet_w = cols * cell_w
    sheet_h = HEADER_H + rows * (cell_h + LABEL_BAND)

    sheet = Image.new("RGB", (sheet_w, sheet_h), PAGE_BG)
    draw = ImageDraw.Draw(sheet)

    draw.rectangle((0, 0, sheet_w, HEADER_H), fill=HEADER_BG)
    f_title = font(FONT_BOLD, 22)
    f_sub = font(FONT_PLAIN, 14)
    draw.text((14, HEADER_H // 2), "Sweetardio — Skin Traits", fill=TITLE_RGB,
              font=f_title, anchor="lm")
    draw.text((sheet_w - 14, HEADER_H // 2),
              "shown 1:1 — sizes and proportions are exact",
              fill=DIM_RGB, font=f_sub, anchor="rm")

    f_name = font(FONT_BOLD, 16)
    f_meta = font(FONT_PLAIN, 12)
    for i, b in enumerate(balls):
        cx0 = (i % cols) * cell_w
        cy0 = HEADER_H + (i // cols) * (cell_h + LABEL_BAND)
        draw.rectangle((cx0, cy0, cx0 + cell_w - 1, cy0 + cell_h - 1),
                       fill=MATTE)
        # native size, centred in the cell
        sheet.paste(b["img"],
                    (cx0 + (cell_w - b["w"]) // 2,
                     cy0 + (cell_h - b["h"]) // 2),
                    b["img"])
        ty = cy0 + cell_h
        draw.text((cx0 + 10, ty + 8), f'{i+1}. {b["name"]}',
                  fill=LABEL_RGB, font=f_name)
        draw.text((cx0 + 10, ty + 28),
                  f'{b["w"]}x{b["h"]} px  ·  centre ({b["cx"]}, {b["cy"]})',
                  fill=DIM_RGB, font=f_meta)

    # unused cells stay page-coloured, not gray, so they read as empty
    if args.scale != 1.0:
        sheet = sheet.resize((round(sheet_w * args.scale),
                              round(sheet_h * args.scale)), Image.LANCZOS)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    sheet.save(args.out)
    print(f"wrote {args.out}  ({sheet.width}x{sheet.height}, "
          f"{os.path.getsize(args.out)/1e6:.2f} MB)")
    print(f"{len(balls)} skins, {cell_w}x{cell_h} cells, balls at 1:1")
    for i, b in enumerate(balls):
        print(f"  {i+1}. {b['name']:18s} {b['w']}x{b['h']}   {b['file']}")


if __name__ == "__main__":
    main()
