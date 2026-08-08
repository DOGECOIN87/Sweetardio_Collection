#!/usr/bin/env python3
"""Strip render debris — small disconnected fragments — from an asset's alpha.

These are not visible as dots. Every speck found in this collection peaks at
alpha 1-11, well under 5% opacity, so a straight composite barely changes.

They matter because `Image.getbbox()` counts ANY non-zero alpha. The OG gummy
bear carried a column of them off its right side, which read the bear as
1014 x 1293 against a true 663 x 888 — so every fit-to-bbox render drew it 35%
small, and the grounding silhouette fed to its drop shadow was equally wrong.
An earlier pass at that bear labelled components on `alpha > 8` and left an
alpha 1-8 ghost of the same debris standing, which getbbox() still saw.

Two guards keep real art safe: a fragment must be smaller than SPECK_MAX, and
its peak opacity must be under PEAK_MAX. A separate design element — a sticker's
lettering, the second slipper of a pair — fails one or both.

  python3 asset_assessment/strip_specks.py characterz --dry-run
  python3 asset_assessment/strip_specks.py            # every class
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

CLASSES = ["characterz", "skinz", "eyez", "mouthz", "armz",
           "what_are_thosez", "stickerz", "secret_rarez"]
SPECK_MAX = 400      # px; bigger disconnected pieces are design, not debris
PEAK_MAX = 40        # alpha; anything that actually reads on screen is kept


def strip(path):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im).copy()
    al = a[..., 3]
    lab, n = ndimage.label(al > 0)
    if n < 2:
        return None, 0, 0, None
    sz = ndimage.sum(al > 0, lab, range(1, n + 1))
    main = int(np.argmax(sz)) + 1
    kill = np.zeros(al.shape, bool)
    count = 0
    for i in range(1, n + 1):
        if i == main or sz[i - 1] >= SPECK_MAX:
            continue
        piece = lab == i
        if al[piece].max() > PEAK_MAX:
            continue
        kill |= piece
        count += 1
    if not count:
        return None, 0, 0, None
    before = im.getbbox()
    a[kill] = 0
    out = Image.fromarray(a, "RGBA")
    return out, count, int(kill.sum()), (before, out.getbbox())


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("classes", nargs="*", default=CLASSES)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total = 0
    for c in args.classes:
        d = os.path.join(g.TRAITS_DIR, c)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith(".png"):
                continue
            p = os.path.join(d, f)
            out, count, px, bboxes = strip(p)
            if out is None:
                continue
            moved = "" if bboxes[0] == bboxes[1] else \
                f"   bbox {bboxes[0]} -> {bboxes[1]}"
            print(f"  {c}/{f:<46.46s} {count:4d} specks, {px:5d} px{moved}")
            if not args.dry_run:
                out.save(p)
            total += 1
    print(f"\n{total} asset(s) {'would be ' if args.dry_run else ''}cleaned")


if __name__ == "__main__":
    main()
