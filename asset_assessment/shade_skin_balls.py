#!/usr/bin/env python3
"""Relight the skin balls as lit, satin spheres instead of flat discs.

The three skin assets (White / Black / Alien) ship as near-uniform matte discs
with a faint darkening at the very rim and nothing in between: measured across
the ball, the luma gradient lives almost entirely in the outer ~8 % of the
radius. That is why a face reads as a sticker rather than a head — the eye gets
no form information anywhere the eyes and mouth actually sit.

This pass rebuilds the lighting from the collection's key (CLAUDE.md: upper
left, ~45 deg, cooler dimmer fill from the lower right) on a fitted sphere:

  form      mean-preserving multiplicative Lambert gradient, so the ball gains
            a real light-to-shadow ramp across its whole face without its
            average colour (its identity as White / Black / Alien) moving
  sheen     Blinn-Phong specular, a BROAD lobe for the satin body plus a small
            tight one for the glossy hotspot, both up-left of centre
  fill      cool bounce on the lower-right limb, so the shadow side does not
            go dead — this is the "rim light picking that edge back out"
  occl      ambient occlusion at the extreme limb, deepest lower-right

ALPHA IS PRESERVED BIT-FOR-BIT. Only RGB is touched. That is deliberate and
load-bearing: ball_fit() sizes every ball from the widest eye and the face
hole is registered against the ball's footprint, so any change to the alpha
would move the whole cast's face geometry. Because alpha is untouched,
verify_face_coverage.py and audit_face_holes.py cannot regress.

Originals are backed up to traits/skinz_originals/ before anything is written.
That folder is a sibling of traits/skinz, never inside it — the generator picks
up every .png in a trait folder, so a backup living there would mint as a skin.

Usage (from repo root):
  python3 asset_assessment/shade_skin_balls.py --ladder   # candidates, no write
  python3 asset_assessment/shade_skin_balls.py            # apply the picked set
  python3 asset_assessment/shade_skin_balls.py --restore  # put the originals back
"""

import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image

SKIN_DIR = "traits/skinz"
BACKUP_DIR = "traits/skinz_originals"
OPAQUE = 128

# Key light, in image space: +x right, +y DOWN, +z toward the viewer.
# Upper-left at ~45 deg, tilted out of the plane so the terminator lands on
# the lower-right limb rather than cutting the ball in half.
KEY = np.array([-0.52, -0.52, 0.68])
# The fill sits opposite the key and below, and is cool (CLAUDE.md).
FILL = np.array([0.46, 0.44, -0.77])
FILL_TINT = np.array([0.62, 0.72, 1.00])     # cool bounce
SPEC_TINT = np.array([1.00, 0.98, 0.94])     # near-white, faintly warm

# Picked from the ladder (see --ladder). Tuned so the ball gains real form
# while its measured BR/TL limb ratio stays inside the band the cast already
# established in shade_cyan_skin.py (White 0.48, Black 0.50, Alien 0.65).
PRESET = {
    "form": 0.62,        # depth of the Lambert ramp
    "form_gamma": 0.85,  # <1 opens the shadows so the ramp is not a hard edge
    "spec_broad": 0.20,  # satin lobe strength
    "spec_broad_n": 12,  # ...and its exponent (low = broad)
    "spec_tight": 0.13,  # glossy hotspot strength
    "spec_tight_n": 90,
    "fill": 0.15,        # cool bounce on the shadow limb
    "occl": 0.26,        # rim ambient occlusion
    "occl_width": 0.34,  # how far in from the limb the occlusion reaches
    # Cheek blush. Positions are in ball-normalised coordinates (0 = centre,
    # 1 = limb), so they ride the ball and stay put whatever ball_fit does.
    # Applied as a per-channel REDDENING of the skin's own colour rather than
    # a pink overlay, so it reads on the dark skin too instead of going
    # chalky. Set "blush" to 0 to switch it off.
    "blush": 0.0,        # off by default -- see --blush
    "blush_x": 0.52,     # cheek centre, left/right of the ball centre
    "blush_y": 0.26,     # ...and below it
    "blush_r": 0.30,     # cheek radius
    "blush_gain": np.array([0.34, -0.07, 0.01]),   # reddening per channel
}


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def sphere_normals(alpha):
    """Fit the opaque disc and return (nx, ny, nz, inside, rim).

    rim is 0 at the ball's centre and 1 at its silhouette edge, i.e. 1 - nz,
    which is what the occlusion term rides on."""
    inside = alpha >= OPAQUE
    ys, xs = np.nonzero(inside)
    if len(xs) == 0:
        raise ValueError("skin ball has no opaque pixels")
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    rx, ry = max((x1 - x0) / 2.0, 1.0), max((y1 - y0) / 2.0, 1.0)

    h, w = alpha.shape
    yy, xx = np.mgrid[0:h, 0:w]
    nx = (xx - cx) / rx
    ny = (yy - cy) / ry
    r2 = nx * nx + ny * ny
    nz = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0))
    return nx, ny, nz, inside, np.sqrt(np.clip(r2, 0.0, 1.0))


def relight(img, p):
    """Return a new RGBA image, relit. Alpha is copied through untouched."""
    rgba = np.asarray(img.convert("RGBA"), dtype=np.float64) / 255.0
    rgb = rgba[..., :3].copy()
    alpha8 = np.asarray(img.convert("RGBA"))[..., 3]

    nx, ny, nz, inside, rim = sphere_normals(alpha8)
    n = np.stack([nx, ny, nz], axis=-1)

    key = KEY / np.linalg.norm(KEY)
    fill = FILL / np.linalg.norm(FILL)
    lam = np.clip((n * key).sum(axis=-1), 0.0, 1.0) ** p["form_gamma"]

    # ---- form: multiplicative and MEAN-PRESERVING over the ball, so the
    # skin's identity (its average colour) does not drift lighter or darker.
    if inside.any():
        lam_mean = float(lam[inside].mean())
    else:
        lam_mean = 0.5
    gain = 1.0 + p["form"] * (lam - lam_mean)

    # ---- occlusion: only at the limb, and deeper on the shadow side
    shadow_side = np.clip(-(n * key).sum(axis=-1), 0.0, 1.0)
    occ = sstep(1.0 - p["occl_width"], 1.0, rim) * (0.45 + 0.55 * shadow_side)
    gain *= 1.0 - p["occl"] * occ

    rgb *= gain[..., None]

    # ---- sheen: broad satin lobe + tight hotspot, both from the key
    view = np.array([0.0, 0.0, 1.0])
    half = key + view
    half /= np.linalg.norm(half)
    ndh = np.clip((n * half).sum(axis=-1), 0.0, 1.0)
    spec = (p["spec_broad"] * ndh ** p["spec_broad_n"]
            + p["spec_tight"] * ndh ** p["spec_tight_n"])
    # a specular highlight does not survive past the silhouette edge
    spec *= 1.0 - sstep(0.90, 1.0, rim)
    rgb += SPEC_TINT * spec[..., None]

    # ---- cool bounce on the lower-right limb
    bounce = np.clip((n * fill).sum(axis=-1), 0.0, 1.0) ** 2.0
    bounce *= sstep(0.45, 1.0, rim)
    rgb += FILL_TINT * (p["fill"] * bounce)[..., None]

    # ---- cheek blush ----
    if p.get("blush", 0.0) > 0.001:
        bx, by, br = p["blush_x"], p["blush_y"], p["blush_r"]
        cheeks = np.zeros_like(nx)
        for sx in (-1.0, 1.0):
            d = np.sqrt(((nx - sx * bx) / br) ** 2 + ((ny - by) / br) ** 2)
            cheeks = np.maximum(cheeks, 1.0 - sstep(0.0, 1.0, d))
        # keep it on the ball and off the limb
        cheeks *= 1.0 - sstep(0.72, 0.98, rim)
        rgb *= 1.0 + p["blush"] * cheeks[..., None] * p["blush_gain"]

    # filmic shoulder so the hotspot rolls off instead of clipping flat
    s = 0.90
    over = rgb > s
    rgb[over] = s + (1 - s) * np.tanh((rgb[over] - s) / (1 - s))
    rgb = np.clip(rgb, 0.0, 1.0)

    # outside the ball, leave the source pixels alone entirely
    keep = ~inside
    rgb[keep] = rgba[..., :3][keep]

    out = np.dstack([rgb * 255.0 + 0.5, alpha8[..., None].astype(np.float64)])
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def limb_ratio(img):
    """BR-limb / TL-limb luma, normalised by the in-ball median — the metric
    shade_cyan_skin.py established for 'is this ball lit from the top left'.
    The cast band is 0.48 (White) to 0.65 (Alien)."""
    a = np.asarray(img.convert("RGBA"), dtype=np.float64)
    alpha = a[..., 3]
    y = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    nx, ny, nz, inside, rim = sphere_normals(alpha)
    if not inside.any():
        return float("nan")
    med = np.median(y[inside])
    band = inside & (rim > 0.80)
    diag = (nx + ny) / np.sqrt(2.0)          # TL negative, BR positive
    tl = band & (diag < -0.55)
    br = band & (diag > 0.55)
    if not tl.any() or not br.any():
        return float("nan")
    return float((y[br].mean() / med) / (y[tl].mean() / med))


def contrast_span(img):
    """5th-95th percentile luma span inside the ball, as a share of its
    median — how much form the ball actually carries."""
    a = np.asarray(img.convert("RGBA"), dtype=np.float64)
    y = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    inside = a[..., 3] >= OPAQUE
    if not inside.any():
        return float("nan")
    lo, hi = np.percentile(y[inside], [5, 95])
    return float((hi - lo) / max(np.median(y[inside]), 1e-6))


def skin_files():
    return sorted(f for f in os.listdir(SKIN_DIR) if f.lower().endswith(".png"))


def crop_ball(img, size=300, bg=(38, 38, 46)):
    bb = img.getbbox()
    c = img.crop(bb).resize((size, size), Image.Resampling.LANCZOS)
    plate = Image.new("RGBA", (size, size), bg + (255,))
    plate.alpha_composite(c)
    return plate.convert("RGB")


def render_ladder(out_path):
    from PIL import ImageDraw, ImageFont
    variants = [("original", None)]
    for name, scale in [("soft", 0.6), ("PICKED", 1.0), ("strong", 1.45)]:
        p = dict(PRESET)
        for k in ("form", "spec_broad", "spec_tight", "fill", "occl"):
            p[k] = PRESET[k] * scale
        variants.append((name, p))

    files = skin_files()
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    CS, LH = 300, 42
    sheet = Image.new("RGB", (len(variants) * CS, len(files) * (CS + LH)),
                      (16, 16, 16))
    d = ImageDraw.Draw(sheet)
    for r, fn in enumerate(files):
        src = Image.open(os.path.join(SKIN_DIR, fn)).convert("RGBA")
        for c, (name, p) in enumerate(variants):
            im = src if p is None else relight(src, p)
            x, y = c * CS, r * (CS + LH)
            sheet.paste(crop_ball(im, CS), (x, y))
            d.text((x + 5, y + CS + 3),
                   f"{name}  {fn[:24]}", font=font, fill=(235, 235, 235))
            d.text((x + 5, y + CS + 21),
                   f"BR/TL {limb_ratio(im):.2f}   span {contrast_span(im):.2f}",
                   font=font, fill=(150, 200, 150))
    sheet.save(out_path)
    print(f"ladder -> {out_path}")


def apply():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for fn in skin_files():
        src = os.path.join(SKIN_DIR, fn)
        bak = os.path.join(BACKUP_DIR, fn)
        if not os.path.exists(bak):
            shutil.copy2(src, bak)
            print(f"backed up {fn}")
        # always relight from the ORIGINAL, so re-running is idempotent
        # rather than compounding the shading pass on itself
        img = Image.open(bak).convert("RGBA")
        out = relight(img, PRESET)
        before_a = np.asarray(img)[..., 3]
        after_a = np.asarray(out)[..., 3]
        assert np.array_equal(before_a, after_a), f"{fn}: alpha changed"
        out.save(src)
        print(f"  {fn}: BR/TL {limb_ratio(img):.2f} -> {limb_ratio(out):.2f}   "
              f"span {contrast_span(img):.2f} -> {contrast_span(out):.2f}")


def restore():
    if not os.path.isdir(BACKUP_DIR):
        sys.exit(f"no backup at {BACKUP_DIR}")
    for fn in sorted(os.listdir(BACKUP_DIR)):
        if fn.lower().endswith(".png"):
            shutil.copy2(os.path.join(BACKUP_DIR, fn),
                         os.path.join(SKIN_DIR, fn))
            print(f"restored {fn}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ladder", metavar="OUT", nargs="?",
                    const="/tmp/skin_ladder.png", default=None,
                    help="render candidates and exit without writing")
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
