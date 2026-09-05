#!/usr/bin/env python3
"""Lift the real Sweetardio wordmark out of the plate it lives on.

The collection already HAS a logo -- a pink neon script "Sweetardio" over a
teal "COLLECTION" pill -- but it exists only as part of the shop-window
photograph in traits/backgroundz_originals/Sweetardio.png. There is no
standalone asset. This cuts one, so the banner and anything else can set
the actual mark instead of approximating it with a typeface.

The key is by HUE, not brightness, and that is the whole trick. The sign
sits on a light grey mesh, so a plain luminance key keeps the background;
and a warm gold bokeh flare overlaps the sign's lower left, so a plain
chroma key keeps that too. Gating on the two colours the logo is actually
made of -- pink neon around 295-360 degrees and teal around 150-225 --
drops both, while a separate low-chroma highlight pass picks up the white
tube outlines the hue gate cannot see.

The pink haze that survives inside the sign is kept deliberately: it is the
neon's own glow on the mesh, and cutting it would make the mark look like
clip art rather than a lit sign.

    python3 dynamic/extract_logo.py            # writes the asset
    python3 dynamic/extract_logo.py --preview  # ...and a dark-card proof
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
TRAITS = os.path.join(HERE, "..", "traits", "backgroundz_originals")

# TWO signs exist, on two different plates, and they want different cuts.
#
#   red   Sweetardio (16).png -- a lit sign BOARD: red script on a silver
#         plaque with a dark green COLLECTION pill. Solid edges, high
#         contrast, and it holds up when scaled. This is the default.
#   neon  Sweetardio.png -- pink neon tubing in a shop window. Atmospheric,
#         but it is glass and glow, so it goes soft at size and needs a
#         dark backing to read at all.
VARIANTS = {
    "red": dict(src="Sweetardio (16).png", crop=(395, 60, 995, 292),
                dst="sweetardio_logo.png"),
    "neon": dict(src="Sweetardio.png", crop=(50, 10, 670, 300),
                 dst="sweetardio_logo_neon.png"),
}
GAMMA = 2.1


def _smoothstep(lo, hi, x):
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _hue_deg(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    c = np.maximum(mx - mn, 1e-6)
    h = np.zeros_like(mx)
    m = mx == r
    h[m] = ((g - b)[m] / c[m]) % 6.0
    m = mx == g
    h[m] = (b - r)[m] / c[m] + 2.0
    m = mx == b
    h[m] = (r - g)[m] / c[m] + 4.0
    return h * 60.0


def extract_red(v):
    """Cut the sign BOARD out of the tiled wall behind it.

    Two things make this awkward and both are handled here:

    The COLLECTION pill is dark green, so a brightness key drops it while
    keeping the plaque around it. But the plaque is a solid board, so
    filling each row between its own extremes recovers the pill (and the
    script's interior) without needing to key those colours at all.

    The wall is dark navy and nearly the pill's luminance, so the key runs
    first on brightness OR chroma, then keeps only the largest connected
    component -- which is the board -- before the row fill. Without that
    step the fill would run from a wall tile on one side to the board on
    the other and swallow the gap between them.
    """
    from scipy import ndimage

    im = Image.open(os.path.join(TRAITS, v["src"])).convert("RGB").crop(
        v["crop"])
    a = np.asarray(im, dtype=np.float32) / 255.0
    luma = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    chroma = a.max(-1) - a.min(-1)

    raw = np.maximum(_smoothstep(0.22, 0.36, luma),
                     _smoothstep(0.12, 0.24, chroma)) > 0.5
    raw = ndimage.binary_closing(raw, np.ones((7, 7)))

    def largest(mask):
        lab, n = ndimage.label(mask)
        if n == 0:
            return mask
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        return lab == int(np.argmax(sizes)) + 1

    keep = largest(raw)
    board = np.zeros_like(keep)
    for y in range(keep.shape[0]):
        xs = np.flatnonzero(keep[y])
        if xs.size > 40:
            board[y, xs[0]:xs[-1] + 1] = True
    board = largest(ndimage.binary_opening(board, np.ones((5, 5))))

    mask = Image.fromarray((board * 255).astype(np.uint8), "L").filter(
        ImageFilter.GaussianBlur(1.2))
    out = im.convert("RGBA")
    out.putalpha(mask)
    return out


def extract_neon(v):
    im = Image.open(os.path.join(TRAITS, v["src"])).convert("RGB").crop(
        v["crop"])
    a = np.asarray(im, dtype=np.float32) / 255.0
    chroma = a.max(-1) - a.min(-1)
    luma = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    h = _hue_deg(a)

    def band(lo, hi, feather):
        return np.minimum(_smoothstep(lo - feather, lo + feather, h),
                          1.0 - _smoothstep(hi - feather, hi + feather, h))

    pink = np.maximum(band(295, 360, 10), band(-5, 18, 10))
    teal = band(150, 225, 14)
    colour = _smoothstep(0.14, 0.30, chroma) * np.maximum(pink, teal)
    # white glass tubing: bright AND near-neutral, which the hue gate misses
    white = _smoothstep(0.78, 0.95, luma) * (
        1.0 - _smoothstep(0.05, 0.16, chroma))

    alpha = np.clip(np.maximum(colour, white), 0.0, 1.0)
    # Suppress the weak tail. The neon's glow on the mesh reads as authentic
    # bloom over a DARK panel but as a dirty rectangle over a bright one, and
    # the banner has both. A gamma on the alpha keeps the tubes and their
    # near glow at full strength while collapsing the wide haze -- the mark
    # then sits on any background instead of only on black.
    alpha = alpha ** GAMMA
    mask = Image.fromarray((alpha * 255).astype(np.uint8), "L").filter(
        ImageFilter.GaussianBlur(0.7))
    out = im.convert("RGBA")
    out.putalpha(mask)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="all",
                    choices=["all", "red", "neon"])
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()
    names = list(VARIANTS) if args.variant == "all" else [args.variant]
    for name in names:
        v = VARIANTS[name]
        src = os.path.join(TRAITS, v["src"])
        if not os.path.exists(src):
            sys.exit(f"missing source plate: {src}")
        logo = extract_red(v) if name == "red" else extract_neon(v)
        dst = os.path.join(HERE, "assets", v["dst"])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        logo.save(dst)
        _report(name, logo, dst, args.preview)


def _report(name, logo, dst, preview):
    DST = dst
    cover = (np.asarray(logo)[..., 3] > 127).mean() * 100
    print(f"  {name:<5} {DST}  {logo.size[0]}x{logo.size[1]}  "
          f"{os.path.getsize(DST) / 1024:.0f} KB  {cover:.0f}% opaque")
    if preview:
        card = Image.new("RGBA", logo.size, (14, 15, 20, 255))
        card.alpha_composite(logo)
        p = DST.replace(".png", "_preview.png")
        card.convert("RGB").save(p)
        print(p)


if __name__ == "__main__":
    main()
