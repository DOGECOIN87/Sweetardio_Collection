#!/usr/bin/env python3
"""Rank a trait class by the baked dark line on its OUTER silhouette.

The defect is a 1px ragged dark rim left behind when a piece was cut from its
background -- invisible on a dark plate, unmistakable on a light one. It is
the same thing fix_matte_line.py repairs on the arms, measured on the boundary
nothing else looks at.

MEASURE IT LOCALLY. The obvious reading -- fringe luma minus the luma of the
art it borders, averaged over the whole edge -- is dominated by genuine
material changes at the silhouette rather than by the defect: a poptart's
crust is darker than its sprinkled top, so it scores -49 with a perfectly
clean edge, while og_gummy_bear, the worst asset in the cast, scored a
mid-pack -33.7 and was nearly missed. Comparing every rim pixel with the art
DEEP px directly behind it cancels anything that follows the form, and only a
line that is dark everywhere survives.

The clean reference is the five ice creams at -0.7 to -9.7; anything past
about -20 is worth rendering over flat grey and looking at.

Repair with, per asset and only where it measurably improves:

    python3 asset_assessment/fix_matte_line.py --outer-only --threshold 0 \\
        <class> "<file>.png"

NOT on eyez or mouthz: they read worst of all (Awkward_smile -160) because a
cartoon mouth is DRAWN with a black outline. See CLAUDE.md.

  python3 asset_assessment/audit_rim_line.py                 # characterz
  python3 asset_assessment/audit_rim_line.py what_are_thosez
"""

import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g  # noqa: E402

DEEP = 4        # px inside the silhouette: past any baked line, still local
SOLID = 200
FLAG = -20.0


def rim_deficit(arr):
    """(mean, 25th pct, n) of rim luma minus the art DEEP px behind it."""
    al = arr[:, :, 3].astype(float)
    rgb = arr[:, :, :3].astype(float)
    L = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    solid = al > SOLID

    # only the OUTER edge: interior holes are fix_hole_matte_line.py's job
    lab, n = ndi.label(~solid)
    if n == 0:
        return None
    border = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    border.discard(0)
    outside = np.isin(lab, list(border))

    rim = solid & ndi.binary_dilation(outside, np.ones((3, 3)))
    inner = ndi.binary_erosion(solid, np.ones((3, 3)), iterations=DEEP)
    if rim.sum() < 100 or inner.sum() < 100:
        return None
    idx = ndi.distance_transform_edt(~inner, return_distances=False,
                                     return_indices=True)
    d = L[rim] - L[idx[0][rim], idx[1][rim]]
    return float(d.mean()), float(np.percentile(d, 25)), int(rim.sum())


def main():
    cls = sys.argv[1] if len(sys.argv) > 1 else g.CHARACTERZ
    d = os.path.join(g.TRAITS_DIR, cls)
    if not os.path.isdir(d):
        sys.exit(f"no such trait class: {d}")
    rows = []
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith(".png"):
            continue
        r = rim_deficit(np.asarray(Image.open(os.path.join(d, fn))
                                   .convert("RGBA")))
        if r:
            rows.append((r[0], r[1], fn, r[2]))
    if not rows:
        sys.exit(f"nothing measurable in {cls}")
    rows.sort()
    print(f"## {cls}   rim luma - art {DEEP}px behind it   "
          f"(flag past {FLAG:.0f})")
    print(f"{'mean':>8} {'p25':>8}  asset")
    for m, q, fn, n in rows:
        print(f"{m:+8.1f} {q:+8.1f}  {fn:52s} {n:6d}px"
              f"{'  <-- BAKED LINE' if m < FLAG else ''}")
    print(f"\n  median {np.median([r[0] for r in rows]):+.1f}   n={len(rows)}")


if __name__ == "__main__":
    main()
