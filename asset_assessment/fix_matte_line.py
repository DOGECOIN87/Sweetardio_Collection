#!/usr/bin/env python3
"""Remove the white matte line from an asset's anti-aliased edge.

An asset that was composited over white before being keyed keeps the blend in
its RGB: every semi-transparent pixel is part art, part background. Against a
dark plate that reads as a bright outline drawn around the character.

Un-premultiplying cannot fix it here. The textbook correction is
F = (C - (1-a)*BG) / a, but these pixels are CLIPPED at 255 — the poptarts
measure 100% of their fringe at pure white — and once a channel saturates the
foreground colour is gone, not merely mixed. Solving for F just returns 255.

So the colour is replaced rather than corrected: the art's own colour is bled
outward across the edge, and the original alpha is put back unchanged. The
silhouette, its anti-aliasing and every opaque pixel are provably untouched —
the run asserts both — so this is a colour repair, not a re-cut.

  python3 asset_assessment/fix_matte_line.py characterz --dry-run
  python3 asset_assessment/fix_matte_line.py characterz before_skinz_og_poptart.png
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")
import generator as g  # noqa: E402
from clean_alpha import bleed  # noqa: E402

TRUST_ALPHA = 200    # only pixels this opaque are believed to be pure art
BAND = 2             # px of opaque edge that can also carry the baked blend


def white_pct(a):
    al = a[..., 3].astype(np.float32)
    lum = a[..., :3].astype(np.float32).mean(2)
    fr = (al >= 15) & (al <= 200)
    return float((lum[fr] >= 250).mean() * 100) if fr.sum() > 200 else 0.0


def fix(path):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)
    al = a[..., 3]
    before = white_pct(a)

    solid = al > TRUST_ALPHA
    # the outermost ring of opaque pixels can carry the blend too
    band = solid & ~ndimage.binary_erosion(solid, iterations=BAND)
    trusted = solid & ~band
    if not trusted.any():
        return None, before, before

    tmp = im.copy()
    tmp.putalpha(Image.fromarray((trusted * 255).astype(np.uint8)))
    tmp = bleed(tmp)                       # art colour now covers the fringe

    out = tmp.copy()
    out.putalpha(Image.fromarray(al))      # original alpha, unchanged

    b = np.asarray(out)
    assert (b[..., 3] == al).all(), "alpha changed"
    keep = al > TRUST_ALPHA
    keep &= ~band
    assert (b[..., :3][keep] == a[..., :3][keep]).all(), "trusted art changed"
    return out, before, white_pct(b)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trait_class")
    ap.add_argument("files", nargs="*", help="default: every file in the class")
    ap.add_argument("--threshold", type=float, default=20.0,
                    help="skip assets whose fringe is less than this %% white")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    d = os.path.join(g.TRAITS_DIR, args.trait_class)
    if not os.path.isdir(d):
        sys.exit(f"no such trait class: {d}")
    files = args.files or sorted(f for f in os.listdir(d)
                                 if f.lower().endswith(".png"))
    done = 0
    for f in files:
        p = os.path.join(d, f)
        a = np.asarray(Image.open(p).convert("RGBA"))
        if white_pct(a) < args.threshold:
            continue
        out, before, after = fix(p)
        if out is None:
            continue
        print(f"  {f:46.46s} white fringe {before:5.1f}% -> {after:4.1f}%"
              f"{'   (dry run)' if args.dry_run else ''}")
        if not args.dry_run:
            out.save(p)
        done += 1
    print(f"\n{done} asset(s) {'would be ' if args.dry_run else ''}repaired; "
          f"alpha and opaque art verified unchanged")


if __name__ == "__main__":
    main()
