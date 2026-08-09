#!/usr/bin/env python3
"""Remove the dark matte line baked into a character's face-hole rim.

Some character art was cut with a black outline left in the pixels bordering
the face hole. Composited over the skin ball -- which is much lighter than the
line -- it shows as a hard dark hairline tracing the face, and it is stepped
rather than smooth because it follows the cut rather than the art. Rendered
over flat green it is unmistakable.

Measured as the luma of successive 1px rings outward from the hole against the
body 9-14px in, the affected characters are obvious:

    churro           ring+1  21.7   body 136.8    (-59.5 at ring+3)
    sugar_cube      ring+1 113.9   body 183.4    (-69.5)
    gold_waffle      ring+1  95.1   body 155.0    (-59.9)
    og_gummy_bear    ring+1  49.6   body 107.3    (-57.7)

...while most of the cast sits within ~10 of its own body, i.e. no line. It is
a defect in four assets, not the collection's house style.

The fix replaces the RGB of the rim pixels with the colour of the nearest
healthy body pixel, so the character's own texture is extended out to the
edge instead of a black line sitting there.

ALPHA IS NEVER TOUCHED. That is what makes this safe: the face hole is
registered geometry (audit_face_holes.py checks it renders at
FACE_HOLE_WIDTH, verify_face_coverage.py checks the ball still covers it),
and feathering or eroding alpha would move it. Only colour changes, so both
checks are unaffected by construction. The tool asserts on it.

Originals are backed up to characterz_originals/ before anything is written.

Usage (from repo root):
  python3 asset_assessment/fix_hole_matte_line.py --report
  python3 asset_assessment/fix_hole_matte_line.py churro
  python3 asset_assessment/fix_hole_matte_line.py churro --width 3
  python3 asset_assessment/fix_hole_matte_line.py --restore churro
"""

import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator import CHARACTERZ, TRAITS_DIR, char_base_name  # noqa: E402

CHAR_DIR = os.path.join(TRAITS_DIR, CHARACTERZ)
BACKUP_DIR = "characterz_originals"
OPAQUE = 128
MIN_HOLE_PX = 2000


def find_hole(alpha):
    """The largest fully-enclosed transparent region: the face hole."""
    clear = alpha < OPAQUE
    lab, n = ndimage.label(clear)
    if n == 0:
        return None
    border = (set(lab[0, :]) | set(lab[-1, :])
              | set(lab[:, 0]) | set(lab[:, -1]))
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    cands = [i + 1 for i in range(n)
             if (i + 1) not in border and sizes[i] > MIN_HOLE_PX]
    if not cands:
        return None
    return lab == max(cands, key=lambda i: sizes[i - 1])


def ring_profile(path):
    """(ring+1, ring+3, body) mean luma around the hole, or None."""
    arr = np.asarray(Image.open(path).convert("RGBA")).astype(float)
    hole = find_hole(arr[..., 3])
    if hole is None:
        return None
    y = (0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2])

    def band(a, b):
        m = (ndimage.binary_dilation(hole, iterations=b)
             & ~ndimage.binary_dilation(hole, iterations=a))
        return y[m].mean() if m.any() else float("nan")

    return band(0, 1), band(2, 3), band(9, 14)


def fix(path, width):
    """Extend the body colour over the rim band. Returns (before, after)."""
    img = Image.open(path).convert("RGBA")
    arr = np.asarray(img).astype(np.uint8).copy()
    alpha = arr[..., 3]
    hole = find_hole(alpha)
    if hole is None:
        raise ValueError(f"{path}: no enclosed face hole found")

    # The band to repaint straddles the boundary. It has to: the partially
    # transparent pixels INSIDE the hole still carry the dark line in their
    # RGB, and leaving them behind leaves a dotted fringe where the solid one
    # was. Anything with any coverage at all within `width` of the hole is
    # repainted; only fully transparent pixels are skipped, since their RGB
    # never reaches the composite.
    near = (ndimage.binary_dilation(hole, iterations=width) & (alpha > 0))
    healthy = (~near) & (~hole) & (alpha >= OPAQUE)

    # nearest healthy pixel for every pixel, then copy its colour into the band
    _, (iy, ix) = ndimage.distance_transform_edt(~healthy, return_indices=True)
    for c in range(3):
        ch = arr[..., c]
        ch[near] = ch[iy[near], ix[near]]
        arr[..., c] = ch

    out = Image.fromarray(arr, "RGBA")
    assert np.array_equal(np.asarray(out)[..., 3], alpha), "alpha changed"
    return out


def resolve(name):
    for f in sorted(os.listdir(CHAR_DIR)):
        if f.lower().endswith(".png") and char_base_name(f) == name:
            return os.path.join(CHAR_DIR, f)
    sys.exit(f"no character art with base name {name!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="character base names")
    ap.add_argument("--width", type=int, default=3,
                    help="rim band to repaint, in px (default 3)")
    ap.add_argument("--report", action="store_true",
                    help="rank the whole cast by hole-rim darkening and exit")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    if args.report:
        rows = []
        for f in sorted(os.listdir(CHAR_DIR)):
            if not f.lower().endswith(".png"):
                continue
            p = ring_profile(os.path.join(CHAR_DIR, f))
            if p:
                rows.append((p[1] - p[2], char_base_name(f), p))
        rows.sort()
        print(f"{'character':<32}{'ring+1':>9}{'ring+3':>9}"
              f"{'body':>9}{'drop':>9}")
        for d, name, (r1, r3, body) in rows:
            flag = "  <-- matte line" if d < -40 else ""
            print(f"{name:<32}{r1:9.1f}{r3:9.1f}{body:9.1f}{d:9.1f}{flag}")
        return

    if not args.names:
        sys.exit("give one or more character base names, or --report")

    os.makedirs(BACKUP_DIR, exist_ok=True)
    for name in args.names:
        path = resolve(name)
        bak = os.path.join(BACKUP_DIR, os.path.basename(path))
        if args.restore:
            if not os.path.exists(bak):
                sys.exit(f"no backup for {name}")
            shutil.copy2(bak, path)
            print(f"restored {name}")
            continue
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
            print(f"backed up {name} -> {bak}")
        before = ring_profile(bak)
        fix(bak, args.width).save(path)          # always from the backup
        after = ring_profile(path)
        print(f"{name}: ring+1 {before[0]:.1f} -> {after[0]:.1f}   "
              f"ring+3 {before[1]:.1f} -> {after[1]:.1f}   "
              f"body {after[2]:.1f}")


if __name__ == "__main__":
    main()
