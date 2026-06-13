#!/usr/bin/env python3
"""Restyle the lightsaber armz traits into glowing neon blades.

Owner reference (2026-06): blade should read like a lit neon tube — a hot
white core down the blade axis, color deepening toward the edges, plus an
outer bloom. The original art is a flat colored blade with a white stripe.

Pipeline (always starts from the pristine art in traits/armz_originals):
  1. blade region = saturated colored pixels (eroded 2px to drop the thin
     keylines around the gloves), morphologically closed to swallow the
     white core stripe inside the blade
  2. distance transform to the blade edge (iterative 1px erosion), then a
     radial color ramp: edge = palette color darkened, mid = palette color,
     axis = white-hot core
  3. multi-radius gaussian bloom tinted with the palette color at full
     luminance, composited UNDER the art; faint hot-spill pass on top

Palette anchors: Zaffre #0313A6, Hollywood Cerise #F715AB,
Fluorescent Cyan #34EDF3.

Usage:
  python3 asset_assessment/glow_lightsabers.py            # /tmp previews
  python3 asset_assessment/glow_lightsabers.py --apply M  # write traits/armz
"""

import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageFilter

ARMZ = "traits/armz"
BACKUP = "traits/armz_originals"
SABERS = {
    "Sweetardio_114 (4).png": (0x03, 0x13, 0xA6),   # Zaffre
    "Sweetardio_114 (5).png": (0xF7, 0x15, 0xAB),   # Hollywood Cerise
    "Sweetardio_114 (6).png": (0x34, 0xED, 0xF3),   # Fluorescent Cyan
}

# (radius_px, opacity) bloom stack + top-spill opacity, per strength preset
GLOW_PRESETS = {
    "S": {"stack": [(6, 0.50), (18, 0.30), (44, 0.16)], "spill": 0.10},
    "M": {"stack": [(6, 0.70), (18, 0.45), (44, 0.26)], "spill": 0.16},
    "L": {"stack": [(6, 0.90), (20, 0.60), (52, 0.36)], "spill": 0.22},
}

# radial ramp stops as fractions of the blade half-width (0=edge, 1=axis)
CORE_START = 0.74   # white core occupies the central ~26% of the blade
EDGE_END = 0.50     # darkened rim fades into full palette color by here
EDGE_DARKEN = 0.50  # edge color = palette * EDGE_DARKEN
# Measured blade anatomy (cross-section): cyan keyline 3px | navy 4px |
# cerise 18px | white stripe 18px (off-center) | cerise 16px | navy | cyan.
# The closed colored mask misses the outer ~10px (navy+cyan keylines), so
# the repaint footprint dilates that far to swallow them.
PAINT_DILATE = 21   # MaxFilter size: repaint reaches ~10px past the mask


def blade_colored_mask(arr):
    """Eroded mask of the saturated blade pixels (keylines removed)."""
    alpha = arr[:, :, 3].astype(np.float32)
    rgb = arr[:, :, :3].astype(np.float32)
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    colored = (alpha > 128) & (sat > 0.35) & (mx > 60)
    mask = Image.fromarray((colored * 255).astype(np.uint8), "L")
    return mask.filter(ImageFilter.MinFilter(5))


def blade_region(im):
    """Blade footprint seed: colored mask closed over the white stripe."""
    arr = np.array(im)
    colored = blade_colored_mask(arr)
    # closing (dilate then erode, r=12) bridges the 18px white stripe so
    # the two cerise bands merge into one footprint (a smaller kernel
    # leaves the stripe unbridged in places -> doubled white cores)
    closed = colored.filter(ImageFilter.MaxFilter(25)) \
                    .filter(ImageFilter.MinFilter(25))
    region = np.array(closed) > 128
    region &= arr[:, :, 3] > 128
    return region


def edge_distance(region):
    """Per-pixel distance (px) to the blade edge via iterative erosion.

    The region is edge-replicate padded first: blades run off-canvas, and
    without padding the canvas border never erodes, which inflated the
    distance there and painted a white wedge at the blade tip.
    """
    pad = 48
    padded = np.pad(region, pad, mode="edge")
    dist = np.zeros(padded.shape, dtype=np.float32)
    cur = Image.fromarray((padded * 255).astype(np.uint8), "L")
    for _ in range(60):  # full blade is ~70px wide; 60 rings is plenty
        a = np.array(cur) > 128
        if not a.any():
            break
        dist += a
        cur = cur.filter(ImageFilter.MinFilter(3))
    return dist[pad:-pad, pad:-pad]


def recolor_blade(im, palette_rgb):
    """Repaint the blade as a neon gradient: white axis -> palette edge.

    The distance field comes from the true blade footprint, but the PAINT
    reaches a few px further (PAINT_DILATE) so the art's dark navy + cyan
    keylines along the blade are swallowed by the rim color instead of
    cutting a hard outline through the glow.
    """
    arr = np.array(im).astype(np.float32)
    region = blade_region(np.array(im))
    # full footprint = seed dilated over the navy/cyan keylines, clipped to
    # the art's alpha; the distance field runs over THIS so the ramp stays
    # smooth out to the true blade edge (no flat band where the paint
    # extends past the colored mask)
    region_img = Image.fromarray((region * 255).astype(np.uint8), "L")
    paint_np = np.array(region_img.filter(
        ImageFilter.MaxFilter(PAINT_DILATE))) > 128
    paint_np &= arr[:, :, 3] > 4
    dist = edge_distance(paint_np)
    half_w = np.percentile(dist[paint_np], 97)  # robust blade half-width
    t = np.clip(dist / max(half_w, 1.0), 0.0, 1.0)

    pal = np.array(palette_rgb, dtype=np.float32)
    edge = pal * EDGE_DARKEN
    white = np.array([255.0, 255.0, 255.0])

    # snappy saturation rise from the rim, narrow white-hot core
    lo = np.sqrt(np.clip(t / EDGE_END, 0, 1))[..., None]   # edge -> palette
    hi = np.clip((t - CORE_START) / (1 - CORE_START), 0, 1)[..., None]
    ramp = edge + (pal - edge) * lo
    ramp = ramp + (white - ramp) * hi                      # palette -> core

    # keylines sit near dist 0 -> rim color; soften 1px so the repaint
    # anti-aliases like the original art
    m = Image.fromarray((paint_np * 255).astype(np.uint8), "L") \
             .filter(ImageFilter.GaussianBlur(1.0))
    w = (np.array(m, dtype=np.float32) / 255.0)[..., None]

    out = arr.copy()
    out[:, :, :3] = arr[:, :, :3] * (1 - w) + ramp * w
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def build_glow(im, palette_rgb, preset):
    """Outer bloom + hot spill around the (already recolored) blade."""
    mask = blade_colored_mask(np.array(im))
    color = np.array(palette_rgb, dtype=np.float32)
    color = color / color.max() * 255.0  # full-luminance bloom tint

    bloom_a = np.zeros(mask.size[::-1], dtype=np.float32)
    for radius, op in preset["stack"]:
        b = np.array(mask.filter(ImageFilter.GaussianBlur(radius)),
                     dtype=np.float32) * op
        bloom_a = np.maximum(bloom_a, b)
    glow = Image.new("RGBA", im.size,
                     (int(color[0]), int(color[1]), int(color[2]), 0))
    glow.putalpha(Image.fromarray(
        np.clip(bloom_a, 0, 255).astype(np.uint8), "L"))

    out = glow.copy()
    out.alpha_composite(im)

    spill_a = np.array(mask.filter(ImageFilter.GaussianBlur(9)),
                       dtype=np.float32) * preset["spill"]
    spill_a = np.minimum(spill_a, np.array(im.getchannel("A"),
                                           dtype=np.float32))
    spill = Image.new("RGBA", im.size,
                      (int(color[0]), int(color[1]), int(color[2]), 0))
    spill.putalpha(Image.fromarray(spill_a.astype(np.uint8), "L"))
    out.alpha_composite(spill)
    return out


def restyle(im, palette_rgb, preset):
    return build_glow(recolor_blade(im, palette_rgb), palette_rgb, preset)


def source_image(fname):
    """Pristine art: prefer the backup so the pipeline never re-processes
    an already-glowed file."""
    bak = os.path.join(BACKUP, fname)
    src = bak if os.path.exists(bak) else os.path.join(ARMZ, fname)
    return Image.open(src).convert("RGBA")


def main():
    apply_mode = "--apply" in sys.argv
    preset_key = sys.argv[sys.argv.index("--apply") + 1] if apply_mode else None

    if apply_mode:
        preset = GLOW_PRESETS[preset_key]
        os.makedirs(BACKUP, exist_ok=True)
        for f, prgb in SABERS.items():
            src = os.path.join(ARMZ, f)
            bak = os.path.join(BACKUP, f)
            if not os.path.exists(bak):
                shutil.copy2(src, bak)
            restyle(source_image(f), prgb, preset).save(src)
            print(f"applied neon restyle ({preset_key}) -> {src}")
        return

    # preview: original vs restyle at each strength, dark + light plates
    plates = [("dark", (24, 22, 30)), ("light", (224, 218, 205))]
    cell = 420
    rows = len(SABERS)
    cols = 1 + len(GLOW_PRESETS)
    for pname, prgb in plates:
        sheet = Image.new("RGB", (cols * cell, rows * cell), prgb)
        for r, (f, srgb) in enumerate(SABERS.items()):
            im = source_image(f)
            variants = [im] + [restyle(im, srgb, GLOW_PRESETS[k])
                               for k in GLOW_PRESETS]
            for c, v in enumerate(variants):
                bgp = Image.new("RGBA", im.size, prgb + (255,))
                bgp.alpha_composite(v)
                crop = bgp.crop((700, 0, 1393, 693)).resize((cell, cell))
                sheet.paste(crop.convert("RGB"), (c * cell, r * cell))
        out = f"/tmp/saber_neon_{pname}.png"
        sheet.save(out)
        print("wrote", out, "(cols: original, S, M, L)")


if __name__ == "__main__":
    main()
