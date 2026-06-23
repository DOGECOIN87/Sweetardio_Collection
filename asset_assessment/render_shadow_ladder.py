#!/usr/bin/env python3
"""Render a contact-shadow strength ladder for the skin ball.

Uses the real generator.py compositing path so the shadow clips correctly
to the foreground (never falls on the background plate). Renders five
columns: off + four candidate settings, across two character scenes.

Usage (from repo root): python3 asset_assessment/render_shadow_ladder.py
Writes: /tmp/shadow_ladder_faces.png  /tmp/shadow_ladder_fullbody.png
"""

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as gen  # noqa: E402

# ── shadow candidates ─────────────────────────────────────────────────────────
CANDIDATES = [
    ("off",          None),
    ("soft",         {"blur": 20, "opacity": 0.35, "dx": 0, "dy": 8}),
    ("medium",       {"blur": 14, "opacity": 0.55, "dx": 0, "dy": 10}),
    ("strong",       {"blur": 11, "opacity": 0.72, "dx": 2, "dy": 12}),
    ("hard-offset",  {"blur":  8, "opacity": 0.80, "dx": 4, "dy": 14}),
]

# fixed scenes: (before_/after_, char_file, bg, eye, mouth)
# chose varied body tones: marshmallow (pale/warm), ding_dong (dark), waffle (gold)
COMBOS = [
    ("after_skinz_marshmallow.png",  "Candy_Land.png",
     "Blue.png", "Awkward_smile.png"),
    ("after_skinz_ding_dong.png",    "Cookboy.png",
     "layer-Eyes_Lowkey (1).png", "layer-Mouth_Flat (1).png"),
    ("after_skinz_waffle.png",       "Blue_Fur.png",
     "layer-Eyes_Side_Eye (1).png", "layer-Mouth_Tasty-1.png"),
]

SKIN = "traits/skinz/layer-layer-layer-Skin_White (2).png"

PAD = 12
HEAD = 50
CROP = 380


def font(size):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def ball_bbox_on_canvas(skin_path, eye_path):
    fscale, fcenter = gen.ball_fit(skin_path, eye_path)
    a = np.asarray(Image.open(skin_path).convert("RGBA"), float)
    op = a[..., 3] >= 128
    rs, cs = np.where(op)
    y0, y1 = rs.min(), rs.max()
    x0, x1 = cs.min(), cs.max()
    hw = fscale * (x1 - x0) / 2
    hh = fscale * (y1 - y0) / 2
    cx, cy = fcenter
    mg = 0.20 * 2 * max(hw, hh)
    return (int(cx - hw - mg),
            int(cy - hh - mg + gen.VERTICAL_OFFSET),
            int(cx + hw + mg),
            int(cy + hh + mg + gen.VERTICAL_OFFSET))


def render(skin_path, shadow_cfg, char_f, bg_f, eye_f, mouth_f, out_path):
    eye_path = os.path.join("traits/eyez", eye_f)
    fscale, fcenter = gen.ball_fit(skin_path, eye_path)
    skin_layer = {"path": skin_path, "offset": True,
                  "fscale": fscale, "fcenter": fcenter}
    if shadow_cfg:
        skin_layer["shadow"] = dict(shadow_cfg)
    layers = [
        {"path": os.path.join("traits/backgroundz", bg_f), "offset": False},
        {"path": os.path.join("traits/characterz", char_f), "offset": True},
        skin_layer,
        {"path": eye_path, "offset": True},
        {"path": os.path.join("traits/mouthz", mouth_f), "offset": True},
    ]
    gen.create_image(layers, out_path)


def main():
    f24 = font(24)
    ncols = len(CANDIDATES)
    nrows = len(COMBOS)

    # ── face-crop grid ─────────────────────────────────────────────────────
    grid = Image.new("RGB",
                     (ncols * (CROP + PAD) + PAD,
                      nrows * (CROP + PAD) + HEAD),
                     (24, 24, 24))
    dr = ImageDraw.Draw(grid)

    for ci, (tag, shadow_cfg) in enumerate(CANDIDATES):
        dr.text((PAD + ci * (CROP + PAD) + 4, 10), tag,
                fill=(255, 255, 64), font=f24)
        for ri, (char_f, bg_f, eye_f, mouth_f) in enumerate(COMBOS):
            out = f"/tmp/shadow_{tag}_row{ri}.png"
            render(SKIN, shadow_cfg, char_f, bg_f, eye_f, mouth_f, out)
            box = ball_bbox_on_canvas(
                SKIN, os.path.join("traits/eyez", eye_f))
            face = Image.open(out).convert("RGB").crop(box).resize(
                (CROP, CROP), Image.Resampling.LANCZOS)
            grid.paste(face, (PAD + ci * (CROP + PAD),
                               HEAD + ri * (CROP + PAD)))
            print(f"  {tag} row{ri} done")

    grid.save("/tmp/shadow_ladder_faces.png")
    print("wrote /tmp/shadow_ladder_faces.png")

    # ── full-body strip (middle row only) ──────────────────────────────────
    ri = 1
    char_f, bg_f, eye_f, mouth_f = COMBOS[ri]
    W = 400
    strip = Image.new("RGB",
                      (ncols * (W + PAD) + PAD, W + HEAD + PAD),
                      (24, 24, 24))
    dr2 = ImageDraw.Draw(strip)
    for ci, (tag, _) in enumerate(CANDIDATES):
        im = Image.open(f"/tmp/shadow_{tag}_row{ri}.png") \
                  .convert("RGB").resize((W, W), Image.Resampling.LANCZOS)
        strip.paste(im, (PAD + ci * (W + PAD), HEAD))
        dr2.text((PAD + ci * (W + PAD) + 4, 10), tag,
                 fill=(255, 255, 64), font=f24)
    strip.save("/tmp/shadow_ladder_fullbody.png")
    print("wrote /tmp/shadow_ladder_fullbody.png")


if __name__ == "__main__":
    main()
