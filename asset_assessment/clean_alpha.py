#!/usr/bin/env python3
"""Clean the colour hiding under an asset's fully transparent pixels.

Some assets carry arbitrary RGB where alpha is 0 — usually a render that was
flattened or a glow pass that wrote colour outside its own alpha. Under a
straight alpha composite that is invisible: alpha 0 contributes nothing. It
becomes real the moment the layer is RESAMPLED, because PIL resizes colour
channels independently of alpha, so colour from transparent pixels mixes into
the semi-transparent fringe of whatever is nearby.

That now happens on every ice cream and gummy bear, whose arms are scaled by
cscale (0.74 / 0.881).

The fix is NOT to zero those pixels. Black under transparency is the worst
case — resampling would then pull black into the fringe and ring the art with
a dark halo. Instead the visible colour is bled outward (premultiplied
push-pull), so anything mixed in from outside is the colour the edge already
is, and the fringe stays neutral at any scale.

Only pixels with alpha == 0 are touched, so a direct composite is provably
unchanged — the run asserts it.

  python3 asset_assessment/clean_alpha.py armz                  # whole class
  python3 asset_assessment/clean_alpha.py armz "Sweetardio_114 (4).png"
  python3 asset_assessment/clean_alpha.py armz --dry-run
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageMath

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")
import generator as g  # noqa: E402


def ghost_level(rgb, alpha):
    t = alpha <= 4
    return float(rgb[t].mean()) if t.any() else 0.0


def bleed(im, radius=None):
    """Fill transparent pixels with the average colour of nearby visible art."""
    rgb = im.convert("RGB")
    alpha = im.getchannel("A")
    # Two different masks, deliberately. `known` is the bleed SOURCE and skips
    # near-invisible pixels so their near-arbitrary colour is not what gets
    # spread. `visible` is what gets restored afterwards, and must cover every
    # pixel with ANY opacity — a pixel at alpha 3 still contributes to a
    # composite, so overwriting its colour would change the image.
    known = alpha.point(lambda a: 255 if a > 8 else 0)
    visible = alpha.point(lambda a: 255 if a > 0 else 0)
    if known.getbbox() is None:
        return im

    r = radius or max(8, max(im.size) // 24)
    mb = known.filter(ImageFilter.BoxBlur(r))
    bands = []
    for band in rgb.split():
        pm = ImageChops.multiply(band, known)
        pmb = pm.filter(ImageFilter.BoxBlur(r))
        # average of the known neighbours; image operand first for ImageMath
        bands.append(ImageMath.lambda_eval(
            lambda a: a["convert"](
                a["min"](a["p"] * 255 / a["max"](a["m"], 1), 255), "L"),
            p=pmb, m=mb))
    filled = Image.merge("RGB", bands)
    filled.paste(rgb, (0, 0), visible)    # never disturb a pixel with any opacity

    out = filled.convert("RGBA")
    out.putalpha(alpha)
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trait_class")
    ap.add_argument("files", nargs="*", help="default: every file in the class")
    ap.add_argument("--threshold", type=float, default=2.0,
                    help="skip assets whose ghost level is already below this")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    d = os.path.join(g.TRAITS_DIR, args.trait_class)
    if not os.path.isdir(d):
        sys.exit(f"no such trait class: {d}")
    files = args.files or sorted(f for f in os.listdir(d)
                                 if f.lower().endswith(".png"))

    cleaned = 0
    for f in files:
        p = os.path.join(d, f)
        im = Image.open(p).convert("RGBA")
        a = np.asarray(im).astype(np.float32)
        before = ghost_level(a[:, :, :3], a[:, :, 3])
        if before < args.threshold:
            continue

        out = bleed(im)
        ao = np.asarray(out).astype(np.float32)
        after = ghost_level(ao[:, :, :3], ao[:, :, 3])

        # the visible image must be untouched: alpha identical, and every
        # pixel with any opacity keeps its exact colour
        assert (ao[:, :, 3] == a[:, :, 3]).all(), f"{f}: alpha changed"
        vis = a[:, :, 3] > 0
        assert (ao[:, :, :3][vis] == a[:, :, :3][vis]).all(), \
            f"{f}: visible colour changed"

        print(f"  {f:34s} ghost {before:6.2f} -> {after:6.2f}"
              f"{'   (dry run)' if args.dry_run else ''}")
        if not args.dry_run:
            out.save(p)
        cleaned += 1

    print(f"\n{cleaned} asset(s) {'would be ' if args.dry_run else ''}cleaned; "
          f"visible pixels verified unchanged")


if __name__ == "__main__":
    main()
