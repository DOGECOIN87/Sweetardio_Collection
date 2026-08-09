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
  gloss   a broad face-wide sheen, also from the ball's normal

That seats them, but it does not make them look WET, and a single specular
taken from the ball's normal never will: it lays one soft sheen across the
whole face. A wet eye carries its own catchlight, because each eyeball is a
separate convex lens. So there is a third term:

  lens    every connected blob in the asset is fitted as its own lens and
          given a catchlight on its upper-left from the same key -- a broad
          bead plus a tighter speck -- with its own rim darkened slightly so
          the blob reads as rounded rather than as a flat cutout

The lens term deliberately does NOT skip dark pixels. An earlier version
guarded gloss away from near-black art to keep brows matte, and that also
killed it on every pupil and iris, i.e. on exactly the surfaces meant to look
wet: a glossy eye is mostly dark with a bright speck on it. What IS guarded is
the near-white end, so the assets carrying a painted catchlight of their own
keep its shape instead of blooming into a patch.

Strength was picked off a ladder judged on rendered FACES, not on the isolated
assets. At 1.5x the picked value the beads start washing the colour out of an
iris and the brow assets turn into a white streak.

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
    "gloss": 0.10,       # face-wide sheen, from the BALL normal
    "gloss_n": 34,
    "hi_guard": 0.80,    # roll gloss off above this luma, so the assets that
                         # already carry a painted catchlight do not blow out
    # ---- per-eyeball lens gloss ----
    # This is what actually reads as "glossy". A single specular taken from
    # the ball's normal puts one soft sheen across the whole face; a wet eye
    # instead carries its OWN catchlight, because each eyeball is a separate
    # convex lens. So every connected blob in the asset is fitted as its own
    # lens and gets a highlight on its upper-left, from the same key.
    #
    # Note this deliberately does NOT skip dark pixels. The first version
    # guarded gloss off near-black art to keep brows matte, which also killed
    # it on every pupil and iris -- i.e. on exactly the surfaces that are
    # meant to look wet. A glossy eye is mostly dark with a bright speck.
    "lens": 0.62,        # catchlight strength
    "lens_n": 26,        # exponent: lower = broader, softer bead
    "lens_tight": 0.40,  # a second, tighter speck on top
    "lens_tight_n": 150,
    "lens_min_px": 300,  # ignore blobs smaller than this (stray marks)
    "lens_rim": 0.20,    # darken each lens's own rim, so it reads rounded
}

# Per-asset multiplier on the lens terms. One global strength was wrong: the
# assets differ in what they ALREADY are, so the same bead that rescues a flat
# cartoon eye doubles a highlight that was painted in, or puts a wet streak on
# a brow that is not an eyeball at all.
#
# An attempt to decide this by measurement failed and is worth recording: the
# obvious signal, "fraction of near-white pixels", ranks Googly / Side Eye /
# Clueless highest at ~0.47-0.49 -- but that is their white SCLERA, not a
# catchlight, and those three are precisely the flat ones that need the gloss
# most. A catchlight is small and compact; a sclera is most of the asset. The
# numbers said the exact opposite of the renders, so these are set by eye.
#
#   1.0   flat cartoon eyes, nothing painted in -- the gloss is the whole point
#   0.45  anime eyes that already carry a painted triangle catchlight; a full
#         bead gives them a competing second highlight
#   0.35  brows, which are line art rather than eyeballs
#   0.0   art that is already rendered as a glossy 3D object, where the bead
#         only adds glare on top of a specular that is already there
LENS_SCALE = {
    "layer-Sweetardio_nft (15).png": 0.0,                        # Alien
    "layer-file_000000001e1c71fd9d410745ea63114e (1).png": 0.0,   # Cyborg
    "layer-art_mattrick_011.png": 0.35,                          # Beady
    "layer-file_00000000a21871f894573a9d4ee67519 (2).png": 0.35,  # Smug
    "Blue.png": 0.45,
    "Cerise.png": 0.45,
    "layer-Eyes_Cyan (1).png": 0.45,                             # Cyan
    # Googly, Side Eye and Clueless default to 1.0
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


def preset_for(filename, base=None):
    """PRESET with this asset's LENS_SCALE applied to the lens terms."""
    p = dict(base or PRESET)
    s = LENS_SCALE.get(filename, 1.0)
    if s != 1.0:
        for k in ("lens", "lens_tight", "lens_rim"):
            p[k] = p[k] * s
    return p


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

    view = np.array([0.0, 0.0, 1.0])
    half = key + view
    half /= np.linalg.norm(half)

    def guard_of(img_rgb):
        """Roll the highlight off where the art is already near-white, so a
        painted catchlight keeps its shape instead of blooming into a patch."""
        yy = (0.2126 * img_rgb[..., 0] + 0.7152 * img_rgb[..., 1]
              + 0.0722 * img_rgb[..., 2])
        return 1.0 - sstep(p["hi_guard"], p["hi_guard"] + 0.16, yy)

    # ---- face-wide sheen, from the ball's normal ----
    ndh = np.clip((n * half).sum(axis=-1), 0.0, 1.0)
    spec = p["gloss"] * ndh ** p["gloss_n"]
    spec = spec * guard_of(rgb) * (1.0 - sstep(0.92, 1.0, rim))
    rgb += spec[..., None]

    # ---- per-eyeball lens gloss ----
    if p.get("lens", 0.0) > 0.001:
        from scipy import ndimage
        lab, ncomp = ndimage.label(on)
        h, w = on.shape
        yy, xx = np.mgrid[0:h, 0:w]
        for c in range(1, ncomp + 1):
            m = lab == c
            if m.sum() < p["lens_min_px"]:
                continue
            ys, xs = np.nonzero(m)
            cx, cy = (xs.min() + xs.max()) / 2.0, (ys.min() + ys.max()) / 2.0
            rx = max((xs.max() - xs.min()) / 2.0, 1.0)
            ry = max((ys.max() - ys.min()) / 2.0, 1.0)
            lx = (xx[m] - cx) / rx
            ly = (yy[m] - cy) / ry
            lr2 = lx * lx + ly * ly
            lz = np.sqrt(np.clip(1.0 - lr2, 0.0, 1.0))
            ln = np.stack([lx, ly, lz], axis=-1)
            ldh = np.clip((ln * half).sum(axis=-1), 0.0, 1.0)
            bead = (p["lens"] * ldh ** p["lens_n"]
                    + p["lens_tight"] * ldh ** p["lens_tight_n"])
            # a highlight dies at the silhouette, and the lens's own rim
            # darkens so the blob reads as a bead rather than a flat cutout
            edge = sstep(0.72, 1.0, np.sqrt(np.clip(lr2, 0.0, 1.0)))
            bead *= 1.0 - edge
            sub = rgb[m]
            sub *= 1.0 - p["lens_rim"] * edge[..., None]
            sub += (bead * guard_of(sub))[..., None]
            rgb[m] = sub

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
        for k in ("form", "gloss", "lens", "lens_tight", "lens_rim"):
            p[k] = PRESET[k] * s
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
            im = src if p is None else relight(src, preset_for(fn, p))
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
        out = relight(img, preset_for(fn))
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
