#!/usr/bin/env python3
"""Land a generated character body on the collection canvas.

register_trait.py registers skins, eyes and mouths, which are placed by their
own footprint. A CHARACTER is placed by its FACE HOLE: the skin ball, eyes and
mouth all land at fixed coordinates around (690, 601) and nothing moves to
follow a body that drifted, so the hole is what has to be pinned.

It also keys out a preview checkerboard, because that is how generated bodies
tend to arrive — as an image of the preview rather than the PNG, with the
transparency already flattened onto a grey/white checker and often JPEG'd on
top. The checker is achromatic and two-valued (255 / 231), which is keyable,
but a near-white vanilla scoop is too — so the key is made CONNECTED: only
checker-coloured regions reachable from the border count as outside, and the
face hole is recovered as the one large enclosed checker component. An image
that already has real alpha is better; ask for it before falling back to this.

  python3 asset_assessment/register_character.py \
      vanilla.jpg=after_skinz_vanilla_ice_cream.png --dry-run
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")
import generator as g  # noqa: E402

BALL = (690, 601)


def key(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    chroma = a.max(2) - a.min(2)
    lum = a.mean(2)
    checker = (chroma <= 10) & (
        (np.abs(lum - 255) <= 14) | (np.abs(lum - 231) <= 14))

    lab, n = ndimage.label(checker)
    border = set(lab[0].tolist()) | set(lab[-1].tolist()) \
        | set(lab[:, 0].tolist()) | set(lab[:, -1].tolist())
    border.discard(0)
    outside = np.isin(lab, list(border))

    # the art is one blob; anything else the key left standing is JPEG noise
    solid = ndimage.binary_fill_holes(~outside)
    slab, sn = ndimage.label(solid)
    ssz = ndimage.sum(solid, slab, range(1, sn + 1))
    solid = slab == (int(np.argmax(ssz)) + 1)

    # the face hole: the largest enclosed checker component inside the body
    inner = checker & solid
    ilab, inn = ndimage.label(inner)
    isz = ndimage.sum(inner, ilab, range(1, inn + 1))
    hole = np.zeros_like(solid)
    if inn and isz.max() > 5000:
        hole = ilab == (int(np.argmax(isz)) + 1)

    alpha = ((solid & ~hole) * 255).astype(np.uint8)
    al = Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(0.9))
    out = im.convert("RGBA")
    out.putalpha(al)
    return out, hole


def despill(im):
    """Pull the checker's neutral grey out of the anti-aliased fringe.

    A pixel keyed at partial alpha still carries (1-a) of the background it was
    composited over. Un-premultiplying against the checker's mean level
    recovers the foreground colour instead of leaving a pale halo.
    """
    a = np.asarray(im).astype(np.float32)
    rgb, al = a[..., :3], a[..., 3:4] / 255.0
    bg = 243.0                      # mean of the 255/231 checker
    edge = (al > 0.02) & (al < 0.98)
    fg = np.where(edge, np.clip((rgb - (1 - al) * bg) / np.maximum(al, 0.02),
                                0, 255), rgb)
    out = np.concatenate([fg, a[..., 3:4]], axis=2).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def register(im, hole):
    """Scale 1408 -> 1393 and translate so the hole centre lands on the ball."""
    s = g.CANVAS_SIZE / im.size[0]
    im = im.resize((g.CANVAS_SIZE, g.CANVAS_SIZE), Image.LANCZOS)
    hy, hx = np.where(hole)
    cx, cy = hx.mean() * s, hy.mean() * s
    dx, dy = round(BALL[0] - cx), round(BALL[1] - cy)
    canvas = Image.new("RGBA", (g.CANVAS_SIZE, g.CANVAS_SIZE), (0, 0, 0, 0))
    canvas.paste(im, (dx, dy))
    return canvas, (dx, dy)


def report(im, label):
    a = np.asarray(im)
    al = a[..., 3]
    ys, xs = np.where(al > 8)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
    inside = ndimage.binary_fill_holes(al > 8)
    h = inside & (al <= 8)
    hy, hx = np.where(h)
    hcx, hcy = hx.mean(), hy.mean()
    hw = hx.max() - hx.min() + 1
    print(f"  {label:34s} body {x1-x0+1:4d}x{y1-y0+1:4d}  "
          f"hole ({hcx:.0f},{hcy:.0f}) w{hw:3d}  "
          f"face-frac {(hcy-y0)/(y1-y0+1):.3f}  below-face {y1-hcy:.0f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pairs", nargs="+", metavar="SRC=DEST.png",
                    help="source image = destination filename in characterz")
    ap.add_argument("--out", default=os.path.join(g.TRAITS_DIR, g.CHARACTERZ))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for pair in args.pairs:
        src, _, dst = pair.partition("=")
        if not dst:
            sys.exit(f"expected SRC=DEST.png, got {pair!r}")
        im, hole = key(src)
        im = despill(im)
        im, _ = register(im, hole)
        report(im, dst)
        if not args.dry_run:
            im.save(os.path.join(args.out, dst))
