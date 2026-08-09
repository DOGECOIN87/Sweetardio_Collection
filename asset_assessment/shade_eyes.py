#!/usr/bin/env python3
"""Give the eye assets form so they sit ON the lit ball instead of on top of it.

Once the skin balls were relit as spheres (shade_skin_balls.py) the eyes became
the flat thing on the face: painted art with no relationship to the key light,
pasted across a surface that now has a visible light-to-shadow ramp.

This pass borrows the ball's own geometry. Each eye pixel is assigned the
sphere normal it would have at that point on the FACE BALL -- not on the eye's
own shape -- so the eyes pick up exactly the ramp the skin underneath them has,
and the two read as one surface:

  form    a mean-preserving Lambert gradient from the upper-left key, so the
          eye on the shadow side of the face is fractionally darker, matching
          the ball
  gloss   a wet Blinn-Phong highlight, kept OFF the pixels that are already
          painted highlights (they are near-white and would blow out) and off
          near-black line art (a brow is matte, not glass)

Both are deliberately gentle. These are stylised 2D assets with painted
catchlights of their own; the goal is to seat them on the ball, not to
re-render them as 3D objects. Rendered as a ladder before picking.

ALPHA IS PRESERVED BIT-FOR-BIT, only RGB is touched. ball_fit() sizes the skin
ball from the eye's opaque WIDTH, so any change to eye alpha would resize every
ball in the collection. The tool asserts on it.

Originals are backed up to traits/eyez_originals/ (a sibling of traits/eyez --
the generator mints every .png in a trait folder). Because the tool always
relights from the backup, re-running is idempotent rather than compounding.

Run register_eyes.py FIRST: this pass assumes the eyes are already centred on
the ball, since it reads the normal from the ball's geometry.

Usage (from repo root):
  python3 asset_assessment/shade_eyes.py --ladder out.png
  python3 asset_assessment/shade_eyes.py
  python3 asset_assessment/shade_eyes.py --restore
"""

import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator import EYEZ, TRAITS_DIR  # noqa: E402

EYE_DIR = os.path.join(TRAITS_DIR, EYEZ)
# NOT eyez_originals: that holds the PRE-registration art (and the retired
# assets). Relighting from there would silently undo register_eyes.py, since
# this tool always works from its backup to stay idempotent. This pass's
# input is the registered art, so it keeps its own copy of that.
BACKUP_DIR = os.path.join(TRAITS_DIR, "eyez_registered")

# The face ball, in canvas space. The eyes composite unscaled around it, so
# these are the numbers that make an eye pixel's normal agree with the skin
# pixel it is covering. Ball centre is CHAR_SCALE_PIVOT; the radius is the
# median rendered ball half-width.
BALL_CX, BALL_CY, BALL_R = 690.0, 601.0, 155.0
KEY = np.array([-0.52, -0.52, 0.68])     # same key as shade_skin_balls.py

# Calibration. Measured on the relit White ball at the two eye centres
# (x 620 and 760, y 572), the SKIN under the right eye is 34.9 % darker than
# under the left. form 0.26 gives the eyes 11.5 % -- deliberately about a
# third of the surface they sit on, not a match.
#
# Matching it fully would be physically consistent and look wrong: an eye
# white is wet and picks up light from everywhere, so it stays bright where
# matte skin falls off, and a sclera taken down 35 % reads as dirty rather
# than shaded. Same partial-strength reasoning as MIDKEY_STRENGTH in
# background_pop_studies/grade.py. Judged on rendered faces, not on the
# isolated assets, where the effect is nearly invisible either way.
PRESET = {
    "form": 0.26,        # depth of the Lambert ramp (skins use 0.62)
    "gloss": 0.16,       # wet highlight strength
    "gloss_n": 34,       # ...and its exponent
    "hi_guard": 0.72,    # skip gloss above this luma (painted catchlights)
    "lo_guard": 0.10,    # skip gloss below this luma (matte black line art)
}


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ball_normals(shape):
    """Sphere normals of the FACE BALL, sampled at every canvas pixel."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w]
    nx = (xx - BALL_CX) / BALL_R
    ny = (yy - BALL_CY) / BALL_R
    r2 = nx * nx + ny * ny
    nz = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0))
    return np.stack([nx, ny, nz], axis=-1), np.sqrt(np.clip(r2, 0.0, 1.0))


def relight(img, p):
    rgba = np.asarray(img.convert("RGBA"), dtype=np.float64) / 255.0
    rgb = rgba[..., :3].copy()
    alpha8 = np.asarray(img.convert("RGBA"))[..., 3]
    on = alpha8 >= 128
    if not on.any():
        return img.copy()

    n, rim = ball_normals(rgb.shape[:2])
    key = KEY / np.linalg.norm(KEY)
    lam = np.clip((n * key).sum(axis=-1), 0.0, 1.0)

    # ---- form: mean-preserving over the eye's own pixels ----
    lam_mean = float(lam[on].mean())
    rgb *= (1.0 + p["form"] * (lam - lam_mean))[..., None]

    # ---- gloss: skip painted catchlights and matte line art ----
    view = np.array([0.0, 0.0, 1.0])
    half = key + view
    half /= np.linalg.norm(half)
    ndh = np.clip((n * half).sum(axis=-1), 0.0, 1.0)
    spec = p["gloss"] * ndh ** p["gloss_n"]
    y = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    guard = (1.0 - sstep(p["hi_guard"], p["hi_guard"] + 0.18, y)) \
        * sstep(p["lo_guard"] - 0.06, p["lo_guard"] + 0.06, y)
    spec = spec * guard * (1.0 - sstep(0.92, 1.0, rim))
    rgb += spec[..., None]

    rgb = np.clip(rgb, 0.0, 1.0)
    # never touch a pixel the eye does not cover
    keep = ~on
    rgb[keep] = rgba[..., :3][keep]

    out = np.dstack([rgb * 255.0 + 0.5, alpha8[..., None].astype(np.float64)])
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def eye_files(d=None):
    d = d or EYE_DIR
    return sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))


def render_ladder(out_path):
    from PIL import ImageDraw, ImageFont
    variants = [("original", None)]
    for name, s in [("soft", 0.55), ("PICKED", 1.0), ("strong", 1.7)]:
        p = dict(PRESET)
        p["form"], p["gloss"] = PRESET["form"] * s, PRESET["gloss"] * s
        variants.append((name, p))
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
    files = eye_files()
    CS, LH = 260, 26
    sheet = Image.new("RGB", (len(variants) * CS, len(files) * (CS + LH)),
                      (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    for r, fn in enumerate(files):
        src = Image.open(os.path.join(EYE_DIR, fn)).convert("RGBA")
        for c, (name, p) in enumerate(variants):
            im = src if p is None else relight(src, p)
            crop = im.crop((BALL_CX - 160, BALL_CY - 150,
                            BALL_CX + 160, BALL_CY + 90))
            plate = Image.new("RGBA", crop.size, (196, 166, 132, 255))
            plate.alpha_composite(crop)
            x, y = c * CS, r * (CS + LH)
            sheet.paste(plate.convert("RGB").resize((CS, CS), Image.LANCZOS),
                        (x, y))
            d.text((x + 4, y + CS + 5), f"{name}  {fn[:22]}",
                   font=font, fill=(232, 232, 232))
    sheet.save(out_path)
    print(f"ladder -> {out_path}")


def apply():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for fn in eye_files():
        src = os.path.join(EYE_DIR, fn)
        bak = os.path.join(BACKUP_DIR, fn)
        if not os.path.exists(bak):
            shutil.copy2(src, bak)
        img = Image.open(bak).convert("RGBA")
        out = relight(img, PRESET)
        assert np.array_equal(np.asarray(img)[..., 3],
                              np.asarray(out)[..., 3]), f"{fn}: alpha changed"
        out.save(src)
        print(f"shaded {fn}")


def restore():
    for fn in eye_files(BACKUP_DIR):
        dst = os.path.join(EYE_DIR, fn)
        if os.path.exists(dst):
            shutil.copy2(os.path.join(BACKUP_DIR, fn), dst)
            print(f"restored {fn}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ladder", metavar="OUT", nargs="?",
                    const="/tmp/eye_ladder.png", default=None)
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    if args.restore:
        restore()
    elif args.ladder:
        render_ladder(args.ladder)
    else:
        apply()


if __name__ == "__main__":
    main()
