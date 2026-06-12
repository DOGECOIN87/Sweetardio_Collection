#!/usr/bin/env python3
"""Add light bloom to the lightsaber armz traits so the blades read as glowing.

The three Sweetardio_114 saber files have flat colored blades with white
cores but no emitted light. This script builds a classic multi-radius bloom
from the blade pixels only:

  1. blade mask = saturated colored pixels (sat>0.35), eroded 2px so the
     thin colored keylines around the gloves don't halo the hands
  2. bloom = sum of gaussian blurs at three radii (tight/mid/wide), tinted
     with the blade's own color normalized to full brightness
  3. composite: bloom UNDER the original art (hands/hilt occlude it
     naturally), then a faint small-radius "hot spill" pass on top so the
     light licks the glove edges and the core reads white-hot

Strength is tunable via GLOW_PRESETS. Writes either /tmp previews
(default) or, with --apply, backs up originals to traits/armz_originals/
and overwrites traits/armz/ in place.

Usage:
  python3 asset_assessment/glow_lightsabers.py            # /tmp previews
  python3 asset_assessment/glow_lightsabers.py --apply M  # apply preset
"""

import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageFilter

ARMZ = "traits/armz"
BACKUP = "traits/armz_originals"
# saber file -> brand palette hex its blade matches (glow is anchored to
# the palette, not the measured blade average):
#   Zaffre #0313A6, Hollywood Cerise #F715AB, Fluorescent Cyan #34EDF3
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


def blade_mask(arr):
    """Eroded mask of the saturated blade pixels."""
    alpha = arr[:, :, 3].astype(np.float32)
    rgb = arr[:, :, :3].astype(np.float32)
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    colored = (alpha > 128) & (sat > 0.35) & (mx > 60)
    mask = Image.fromarray((colored * 255).astype(np.uint8), "L")
    # 2px erosion kills the 1-2px colored keyline around the gloves while
    # leaving the ~25px-wide blades intact
    mask = mask.filter(ImageFilter.MinFilter(5))
    return mask


def build_glow(im, palette_rgb, preset):
    arr = np.array(im)
    mask = blade_mask(arr)
    # palette hue at full luminance so the bloom reads as emitted light
    # (Zaffre is dark; lifting value keeps hue/sat identity but glows)
    color = np.array(palette_rgb, dtype=np.float32)
    color = color / color.max() * 255.0

    # multi-radius bloom alpha (lighter-combine of the blur stack)
    bloom_a = np.zeros(mask.size[::-1], dtype=np.float32)
    for radius, op in preset["stack"]:
        b = np.array(mask.filter(ImageFilter.GaussianBlur(radius)),
                     dtype=np.float32) * op
        bloom_a = np.maximum(bloom_a, b)
    bloom_a = np.clip(bloom_a, 0, 255).astype(np.uint8)

    glow = Image.new("RGBA", im.size,
                     (int(color[0]), int(color[1]), int(color[2]), 0))
    glow.putalpha(Image.fromarray(bloom_a, "L"))

    # bloom under the art, original on top (hands/hilt occlude the halo)
    out = glow.copy()
    out.alpha_composite(im)

    # faint hot spill ON TOP, clipped to the art's own alpha: lights the
    # glove edges next to the blade and pushes the core toward white-hot
    spill_a = np.array(mask.filter(ImageFilter.GaussianBlur(9)),
                       dtype=np.float32) * preset["spill"]
    spill_a = np.minimum(spill_a, np.array(im.getchannel("A"),
                                           dtype=np.float32))
    spill = Image.new("RGBA", im.size,
                      (int(color[0]), int(color[1]), int(color[2]), 0))
    spill.putalpha(Image.fromarray(spill_a.astype(np.uint8), "L"))
    out.alpha_composite(spill)
    return out


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
            im = Image.open(src).convert("RGBA")
            build_glow(im, prgb, preset).save(src)
            print(f"applied {preset_key} glow -> {src} (original in {bak})")
        return

    # preview: each saber at each strength over dark + light plates
    plates = [("dark", (24, 22, 30)), ("light", (224, 218, 205))]
    cell = 420
    rows = len(SABERS)
    cols = 1 + len(GLOW_PRESETS)  # original + presets
    for pname, prgb in plates:
        sheet = Image.new("RGB", (cols * cell, rows * cell), prgb)
        for r, (f, srgb) in enumerate(SABERS.items()):
            im = Image.open(os.path.join(ARMZ, f)).convert("RGBA")
            variants = [im] + [build_glow(im, srgb, GLOW_PRESETS[k])
                               for k in GLOW_PRESETS]
            for c, v in enumerate(variants):
                bgp = Image.new("RGBA", im.size, prgb + (255,))
                bgp.alpha_composite(v)
                # crop to the right-hand saber for a closer look
                crop = bgp.crop((700, 0, 1393, 693)).resize((cell, cell))
                sheet.paste(crop.convert("RGB"), (c * cell, r * cell))
        out = f"/tmp/saber_glow_{pname}.png"
        sheet.save(out)
        print("wrote", out, "(cols: original, S, M, L)")


if __name__ == "__main__":
    main()
