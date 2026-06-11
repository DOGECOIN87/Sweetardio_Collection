#!/usr/bin/env python3
"""Candidate fix: add proper shading to the Fluorescent Cyan skin ball.

The Cyan skin asset is a flat bright disc, while White/Black/Alien are
shaded spheres (top-left light, lower-edge falloff) - this is why cyan
faces look stickered-on. This script transfers the White ball's macro
lighting field (luma / in-ball median, blurred 18px so surface grain stays
behind) onto the cyan ball, preserving its bubbles and glassy rim.

OWNER FEEDBACK ON v1 CANDIDATES (2026-06-11): "the shading on the bottom
right curve is missing" - the transferred field needs a stronger
directional bottom-right limb shadow (the White source shades bottom-center
and the blur softens direction). Next iteration: add a synthetic
directional term (radial falloff centered top-left, bottom-right limb to
~0.5-0.65x) or sample the Black ball's field, then re-render candidates.

Writes candidates to /tmp only - does NOT modify the trait asset. Before
ever overwriting traits/skinz/, back the original up to a NON-trait sibling
folder (e.g. traits/skinz_originals/ - never inside traits/skinz, the
generator picks every .png there).

Usage: python3 asset_assessment/shade_cyan_skin.py
"""

import numpy as np
from PIL import Image, ImageFilter

WHITE = "traits/skinz/layer-layer-layer-Skin_White (2).png"
CYAN = "traits/skinz/layer-Skin_Fluorescent_Cyan (2).png"


def bbox(a):
    m = a[..., 3] >= 128
    rs = np.where(m.any(1))[0]
    cs = np.where(m.any(0))[0]
    return cs.min(), rs.min(), cs.max() + 1, rs.max() + 1


def main():
    w = np.asarray(Image.open(WHITE).convert("RGBA"), float)
    c = np.asarray(Image.open(CYAN).convert("RGBA"), float)
    wx0, wy0, wx1, wy1 = bbox(w)
    cx0, cy0, cx1, cy1 = bbox(c)

    luma = 0.2126 * w[..., 0] + 0.7152 * w[..., 1] + 0.0722 * w[..., 2]
    mask = w[..., 3] >= 128
    med = np.median(luma[mask])
    field = np.where(mask, luma / med, 1.0)
    f_img = Image.fromarray(np.uint8(np.clip(field * 127.0, 0, 255)))
    f_img = f_img.crop((wx0, wy0, wx1, wy1))
    f_img = f_img.resize((cx1 - cx0, cy1 - cy0), Image.Resampling.LANCZOS)
    f_img = f_img.filter(ImageFilter.GaussianBlur(18))
    f = np.asarray(f_img, float) / 127.0

    def shade(strength, out_path):
        out = c.copy()
        sub = out[cy0:cy1, cx0:cx1, :3]
        am = out[cy0:cy1, cx0:cx1, 3:4] / 255.0
        mod = (1.0 - strength) + strength * f[..., None]
        shaded = np.clip(sub * mod, 0, 255)
        out[cy0:cy1, cx0:cx1, :3] = sub * (1 - am) + shaded * am
        Image.fromarray(np.uint8(out + 0.5), "RGBA").save(out_path)
        print("wrote", out_path)

    shade(0.7, "/tmp/cyan_shaded_soft.png")
    shade(1.0, "/tmp/cyan_shaded_full.png")
    print(f"shading field range: {f.min():.2f}..{f.max():.2f}")


if __name__ == "__main__":
    main()
