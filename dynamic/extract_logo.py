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
SRC = os.path.join(HERE, "..", "traits", "backgroundz_originals",
                   "Sweetardio.png")
DST = os.path.join(HERE, "assets", "sweetardio_logo.png")

# The sign's box on the 1393 plate, measured by eye and then tightened.
CROP = (50, 10, 670, 300)
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


def extract():
    im = Image.open(SRC).convert("RGB").crop(CROP)
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
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()
    if not os.path.exists(SRC):
        sys.exit(f"missing source plate: {SRC}")
    logo = extract()
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    logo.save(DST)
    cover = (np.asarray(logo)[..., 3] > 127).mean() * 100
    print(f"{DST}  {logo.size[0]}x{logo.size[1]}  "
          f"{os.path.getsize(DST) / 1024:.0f} KB  {cover:.0f}% opaque")
    if args.preview:
        card = Image.new("RGBA", logo.size, (14, 15, 20, 255))
        card.alpha_composite(logo)
        p = os.path.join(HERE, "assets", "sweetardio_logo_preview.png")
        card.convert("RGB").save(p)
        print(p)


if __name__ == "__main__":
    main()
