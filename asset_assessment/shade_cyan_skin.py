#!/usr/bin/env python3
"""Candidate fix: add proper shading to the Fluorescent Cyan skin ball.

The Cyan skin asset is a flat bright disc, while White/Black/Alien are
shaded spheres (top-left light, lower-edge falloff) - this is why cyan
faces look stickered-on. Measured (luma / in-ball median, outer limb along
the TL->BR diagonal):

    skin        TL-limb  BR-limb  BR/TL
    White        1.096    0.526   0.48
    Black        1.131    0.565   0.50
    Gold Foil    1.147    0.665   0.58
    Alien        1.054    0.680   0.65
    Cyan (src)   1.080    1.245   1.15  <- INVERTED: BR rim GLOWS

OWNER FEEDBACK ON v1 CANDIDATES (2026-06-11): "the shading on the bottom
right curve is missing". Root cause found in v1: the field was blurred
with the outside-ball region filled at 1.0, so the Gaussian erased the
dark limb values exactly at the rim. v2 fixes this two ways:

  1. Normalized convolution - blur(field*mask)/blur(mask) - so the limb
     darkness survives the 18px blur instead of bleeding into the 1.0
     surround.
  2. An explicit synthetic directional term: smoothstep ramp along the
     TL->BR diagonal (zero at ball center, full at the BR limb), depth k.

Candidates written to /tmp (target band for output BR/TL: 0.48-0.65):
  A  white field, k=0.12  - gentle extra BR shadow
  B  white field, k=0.30  - strong BR shadow (Black/White-like)
  C  black field, k=0.00  - direct transfer of the most directional skin

Also renders deterministic before/after proofs ON characters
(marshmallow / gummy_bear / waffle) plus a ball-only ladder with the
measured stats. Does NOT modify the trait asset. Before ever overwriting
traits/skinz/, back the original up to a NON-trait sibling folder
(traits/skinz_originals/ - never inside traits/skinz, the generator picks
every .png there).

Usage (from repo root): python3 asset_assessment/shade_cyan_skin.py
"""

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator import VERTICAL_OFFSET, ball_fit, create_image  # noqa: E402

WHITE = "traits/skinz/layer-layer-layer-Skin_White (2).png"
BLACK = "traits/skinz/layer-Skin_Black (3).png"
CYAN = "traits/skinz/layer-Skin_Fluorescent_Cyan (2).png"

BLUR = 18
CANDIDATES = [  # (tag, source skin for the field, synthetic BR depth k)
    ("A_white_k012", WHITE, 0.12),
    ("B_white_k030", WHITE, 0.30),
    ("C_black_k000", BLACK, 0.00),
]

# fixed, blocklist-checked proof combos: (character, background, eyes, mouth)
PROOF_COMBOS = [
    ("after_skinz_marshmallow.png", "Candy_Land.png",
     "Blue.png", "Awkward_smile.png"),
    ("before_skinz_gummy_bear.png", "Celestial.png",
     "layer-Eyes_Side_Eye (1).png", "layer-Mouth_Flat (1).png"),
    ("after_skinz_waffle.png", "Blue_Fur.png",
     "layer-Eyes_Lowkey (1).png", "layer-Mouth_Tasty-1.png"),
]


def bbox(a):
    m = a[..., 3] >= 128
    rs = np.where(m.any(1))[0]
    cs = np.where(m.any(0))[0]
    return cs.min(), rs.min(), cs.max() + 1, rs.max() + 1


def luma_of(a):
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def directional_stats(a):
    """(TL-limb, BR-limb, BR/TL) of luma/median along the TL->BR diagonal."""
    m = a[..., 3] >= 128
    field = luma_of(a) / np.median(luma_of(a)[m])
    rs, cs = np.where(m)
    cy, cx = rs.mean(), cs.mean()
    ry = (rs.max() - rs.min()) / 2
    rx = (cs.max() - cs.min()) / 2
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    d = ((xx - cx) / rx + (yy - cy) / ry) / np.sqrt(2)
    tl = field[m & (d < -0.75)].mean()
    br = field[m & (d > 0.75)].mean()
    return tl, br, br / tl


def lighting_field(src_path, out_w, out_h):
    """Macro lighting field of a shaded ball, limb-preserving blur."""
    a = np.asarray(Image.open(src_path).convert("RGBA"), float)
    x0, y0, x1, y1 = bbox(a)
    m = (a[..., 3] >= 128).astype(float)
    field = np.where(m > 0, luma_of(a) / np.median(luma_of(a)[m > 0]), 0.0)
    # normalized convolution: blur(field*mask)/blur(mask) keeps the dark
    # limb from bleeding into the surround (the v1 mistake). PIL blurs
    # uint8 only -> scale field by 150 (max ~1.5), 0.7% quantization.
    scale = 150.0
    fi = Image.fromarray(np.uint8(np.clip(field * m * scale, 0, 255)))
    mi = Image.fromarray(np.uint8(m * 255))
    fi = fi.crop((x0, y0, x1, y1)).resize((out_w, out_h), Image.Resampling.LANCZOS)
    mi = mi.crop((x0, y0, x1, y1)).resize((out_w, out_h), Image.Resampling.LANCZOS)
    fb = np.asarray(fi.filter(ImageFilter.GaussianBlur(BLUR)), float) / scale
    mb = np.asarray(mi.filter(ImageFilter.GaussianBlur(BLUR)), float) / 255.0
    return np.where(mb > 0.01, fb / np.maximum(mb, 1e-6), 1.0)


def synth_br_term(w, h, k):
    """1.0 at/above ball center, falling to 1-k at the bottom-right limb."""
    yy, xx = np.mgrid[0:h, 0:w]
    u = (xx - (w - 1) / 2) / (w / 2)
    v = (yy - (h - 1) / 2) / (h / 2)
    d = np.clip((u + v) / np.sqrt(2), 0, 1)  # 0 until center, 1 at BR limb
    t = d * d * (3 - 2 * d)  # smoothstep
    return 1.0 - k * t


def make_candidate(cyan, field_src, k, out_path):
    c = cyan.copy()
    cx0, cy0, cx1, cy1 = bbox(c)
    w, h = cx1 - cx0, cy1 - cy0
    f = lighting_field(field_src, w, h) * synth_br_term(w, h, k)
    sub = c[cy0:cy1, cx0:cx1, :3]
    am = c[cy0:cy1, cx0:cx1, 3:4] / 255.0
    shaded = np.clip(sub * f[..., None], 0, 255)
    c[cy0:cy1, cx0:cx1, :3] = sub * (1 - am) + shaded * am
    Image.fromarray(np.uint8(c + 0.5), "RGBA").save(out_path)
    return c


def font(size):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def render_character(skin_path, char_f, bg_f, eye_f, mouth_f, out_path):
    eye_path = os.path.join("traits/eyez", eye_f)
    fscale, fcenter = ball_fit(skin_path, eye_path)
    layers = [
        {"path": os.path.join("traits/backgroundz", bg_f), "offset": False},
        {"path": os.path.join("traits/characterz", char_f), "offset": True},
        {"path": skin_path, "offset": True,
         "fscale": fscale, "fcenter": fcenter},
        {"path": eye_path, "offset": True},
        {"path": os.path.join("traits/mouthz", mouth_f), "offset": True},
    ]
    create_image(layers, out_path)
    # face crop box: scaled ball bbox + vertical offset + 18% margin
    a = np.asarray(Image.open(skin_path).convert("RGBA"), float)
    x0, y0, x1, y1 = bbox(a)
    cx, cy = fcenter
    hw, hh = fscale * (x1 - x0) / 2, fscale * (y1 - y0) / 2
    mg = 0.18 * 2 * max(hw, hh)
    return (int(cx - hw - mg), int(cy - hh - mg + VERTICAL_OFFSET),
            int(cx + hw + mg), int(cy + hh + mg + VERTICAL_OFFSET))


def main():
    cyan = np.asarray(Image.open(CYAN).convert("RGBA"), float)
    tl, br, ratio = directional_stats(cyan)
    print(f"{'original':14s} TL={tl:.3f} BR={br:.3f} BR/TL={ratio:.3f}")

    cand_paths = {}
    for tag, src, k in CANDIDATES:
        out = f"/tmp/cyan_v2_{tag}.png"
        shaded = make_candidate(cyan, src, k, out)
        tl, br, ratio = directional_stats(shaded)
        cand_paths[tag] = (out, ratio)
        print(f"{tag:14s} TL={tl:.3f} BR={br:.3f} BR/TL={ratio:.3f}  -> {out}")

    # ---- ball-only ladder on neutral gray ----
    cols = [("original", CYAN, None)] + [
        (tag, cand_paths[tag][0], cand_paths[tag][1])
        for tag, _, _ in CANDIDATES]
    cw, pad, head = 340, 12, 46
    sheet = Image.new("RGB", (len(cols) * (cw + pad) + pad, cw + head + pad),
                      (128, 128, 128))
    dr = ImageDraw.Draw(sheet)
    f24 = font(24)
    for i, (tag, path, ratio) in enumerate(cols):
        im = Image.open(path).convert("RGBA")
        x0, y0, x1, y1 = bbox(np.asarray(im, float))
        m = int(0.12 * (x1 - x0))
        im = im.crop((x0 - m, y0 - m, x1 + m, y1 + m)).resize(
            (cw, cw), Image.Resampling.LANCZOS)
        cell = Image.new("RGBA", (cw, cw), (128, 128, 128, 255))
        cell.alpha_composite(im)
        x = pad + i * (cw + pad)
        sheet.paste(cell.convert("RGB"), (x, head))
        label = tag if ratio is None else f"{tag}  BR/TL={ratio:.2f}"
        dr.text((x + 6, 10), label, fill=(255, 255, 64), font=f24)
    sheet.save("/tmp/cyan_v2_ladder.png")
    print("wrote /tmp/cyan_v2_ladder.png")

    # ---- before/after proofs on characters ----
    crop_w = 380
    grid = Image.new("RGB", (len(cols) * (crop_w + pad) + pad,
                             len(PROOF_COMBOS) * (crop_w + pad) + head),
                     (24, 24, 24))
    dr = ImageDraw.Draw(grid)
    for ci, (tag, skin_path, _) in enumerate(cols):
        dr.text((pad + ci * (crop_w + pad) + 6, 10), tag,
                fill=(255, 255, 64), font=f24)
        for ri, (char_f, bg_f, eye_f, mouth_f) in enumerate(PROOF_COMBOS):
            out = f"/tmp/cyan_v2_full_{ri}_{tag}.png"
            box = render_character(skin_path, char_f, bg_f, eye_f, mouth_f, out)
            face = Image.open(out).convert("RGB").crop(box).resize(
                (crop_w, crop_w), Image.Resampling.LANCZOS)
            grid.paste(face, (pad + ci * (crop_w + pad),
                              head + ri * (crop_w + pad)))
    grid.save("/tmp/cyan_v2_proof_faces.png")
    print("wrote /tmp/cyan_v2_proof_faces.png "
          "(full renders: /tmp/cyan_v2_full_<row>_<tag>.png)")


if __name__ == "__main__":
    main()
