#!/usr/bin/env python3
"""Render a catalog contact sheet for one trait class (catalog/traitsheet_*.png).

Full background plates are drawn whole, edge to edge; transparent traits are
cropped to their content and matted on neutral gray. Every tile is labeled
with its display name from generator.py.

  python3 asset_assessment/render_traitsheet.py backgroundz_legendary
  python3 asset_assessment/render_traitsheet.py stickerz --cols 8 --tile 260

Sheet keys map to (trait dir, title, filename filter); see SHEETS below.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g

# measured from the committed sheets so regenerated ones stay consistent
PAGE_BG = (14, 14, 16)
HEADER_BG = (28, 28, 32)
HEADER_H = 52
TITLE_RGB = (230, 210, 80)
LABEL_RGB = (238, 238, 240)
MATTE = (128, 128, 128)
LABEL_BAND = 46          # strip under each tile that carries the label
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

SHEETS = {
    "backgroundz":           (g.BACKGROUNDZ, "Backgrounds",
                              lambda f: not g.is_legendary_bg(f)),
    "backgroundz_all":       (g.BACKGROUNDZ, "Backgrounds — All", None),
    "backgroundz_legendary": (g.BACKGROUNDZ, "Backgrounds — Legendary",
                              g.is_legendary_bg),
    "characterz":            (g.CHARACTERZ, "Characters", None),
    "skinz":                 (g.SKINZ, "Skins", None),
    "eyez":                  (g.EYEZ, "Eyes", None),
    "mouthz":                (g.MOUTHZ, "Mouths", None),
    "armz":                  (g.ARMZ, "Arms", None),
    "what_are_thosez":       (g.WHAT_ARE_THOSEZ, "Footwear", None),
    "stickerz":              (g.STICKERZ, "Stickers", None),
    "secret_rarez":          (g.SECRET_RAREZ, "Secret Rares", None),
}


def tile_image(path, size, matte):
    """Whole plate for opaque art; content-cropped + matted for transparent."""
    im = Image.open(path).convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    transparent = bbox is not None and bbox != (0, 0, *im.size)
    if transparent:
        im = im.crop(bbox)
    w, h = im.size
    scale = min(size / w, size / h) if transparent else max(size / w, size / h)
    im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                   Image.LANCZOS)
    tile = Image.new("RGB", (size, size), matte if transparent else PAGE_BG)
    tile.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
    return tile


def _fit(draw, text, font, max_px):
    """Ellipsize a label so it never runs into the next tile's caption."""
    if draw.textlength(text, font=font) <= max_px:
        return text
    while text and draw.textlength(text + "…", font=font) > max_px:
        text = text[:-1]
    return text.rstrip() + "…"


def render(sheet_key, cols, tile_px, out_path):
    trait_dir, title, keep = SHEETS[sheet_key]
    files = g.get_files(trait_dir)
    if keep:
        files = [f for f in files if keep(f)]
    if not files:
        sys.exit(f"no assets for sheet '{sheet_key}'")

    cols = min(cols, len(files))
    rows = (len(files) + cols - 1) // cols
    row_pitch = tile_px + LABEL_BAND
    W, H = cols * tile_px, HEADER_H + rows * row_pitch

    sheet = Image.new("RGB", (W, H), PAGE_BG)
    sheet.paste(Image.new("RGB", (W, HEADER_H), HEADER_BG), (0, 0))
    dr = ImageDraw.Draw(sheet)
    title_font = ImageFont.truetype(FONT_BOLD, 26)
    label_font = ImageFont.truetype(FONT_BOLD, 15)

    dr.text((8, HEADER_H // 2), title, font=title_font, fill=TITLE_RGB,
            anchor="lm")
    dr.text((W - 8, HEADER_H // 2), f"{len(files)} traits", font=title_font,
            fill=LABEL_RGB, anchor="rm")

    matte = None if trait_dir == g.BACKGROUNDZ else MATTE
    for i, f in enumerate(files):
        x = (i % cols) * tile_px
        y = HEADER_H + (i // cols) * row_pitch
        sheet.paste(tile_image(os.path.join(g.TRAITS_DIR, trait_dir, f),
                               tile_px, matte or MATTE), (x, y))
        dr.text((x + 2, y + tile_px + LABEL_BAND // 2),
                _fit(dr, g.trait_name(trait_dir, f), label_font, tile_px - 8),
                font=label_font, fill=LABEL_RGB, anchor="lm")

    sheet.save(out_path)
    print(f"{out_path}  {W}x{H}  {len(files)} traits")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet", choices=sorted(SHEETS))
    ap.add_argument("--cols", type=int, default=7)
    ap.add_argument("--tile", type=int, default=340)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    render(a.sheet, a.cols, a.tile,
           a.out or f"catalog/traitsheet_{a.sheet}.png")
