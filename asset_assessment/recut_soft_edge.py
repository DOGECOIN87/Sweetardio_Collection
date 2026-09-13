#!/usr/bin/env python3
"""Re-cut an asset whose alpha was lifted with a SOFT selection.

A soft lasso spreads the clear->opaque transition over 5-7px of
background-blended colour, and the alpha wobbles up and down inside it instead
of ramping once.  The result is a mushy, ragged edge carrying the colour of
whatever the piece was photographed against.  The Nerf Blaster is the worked
example: a vertical profile across its barrel reads

    alpha   0   1   7  32  75  48  35 123 244 255
    rgb              <-- pale lavender -->  <-- real blue

NO EXISTING AUDIT SEES THIS.  audit_edges.py finds no STEPPED pixel (the ramp
exists), no GHOST and no HALO.  audit_rim_line.py averages the rim against the
art and a pale feather cancels against a dark one.  Feather width does not
separate it either -- the blaster reads 1.77 mid-alpha px per px of boundary
against an arms median of 1.51.  What does separate it is the SHAPE: boundary
px displaced by a 2px smooth, 39.6 % against a class median of 13.0 %.  And
the colour is only visible by eye, on a light field, which is what CLAUDE.md
already says about this asset.

THREE STAGES, and the first is the one that matters:

1. COLOUR -- every non-trusted pixel takes the RGB of its NEAREST trusted
   pixel, found with a distance transform.
   **Do not use clean_alpha.bleed() here.**  Its radius is `max(8, size//24)`
   -- 58px on this canvas -- so it returns a far-field AVERAGE of everything
   around, which on a small, high-detail, multi-coloured asset is roughly the
   same muddy grey the soft cut already baked in.  Measured on the blaster it
   changed exactly ZERO pixels: the average of blue, orange, black and a white
   decal within 58px is (91, 93, 159), and the lavender it was asked to
   replace was (91, 93, 159).  Nearest-neighbour pulls the real blue from 3px
   away instead.  This stage alone is provably safe -- alpha is bit-identical.

2. SHAPE -- a median filter on alpha.  A median removes 1-2px protrusions and
   notches while preserving straight runs and genuine corners, which a
   gaussian does not.

3. RAMP -- a contrast curve on alpha, PINNED AT 128 so the `alpha >= 128`
   isoline is fixed.  That matters: generator._opaque_bbox() thresholds at 128
   and armed_lift() reads the arm's bottom edge off it.  (The median in stage 2
   can still move that box by a px, so the run reports it -- see --check.)

Stage 3 HARDENS the edge and so introduces STEPPED pixels, 732 on the blaster
where there were none.  soften_stepped_edges.py is therefore not optional
after a recut; --soften runs it inline and asserts the result is back to 0.

  python3 asset_assessment/recut_soft_edge.py --report armz
  python3 asset_assessment/recut_soft_edge.py armz "<file>.png" --colour-only
  python3 asset_assessment/recut_soft_edge.py armz "<file>.png" --soften
"""

import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generator as g  # noqa: E402
from soften_stepped_edges import soften, stepped  # noqa: E402

TRUST = 200        # only pixels this opaque are believed to be pure art
BAND = 2           # px of opaque edge that can also carry the baked blend
MEDIAN = 2         # radius; 5x5
CONTRAST = 3.0     # alpha slope about 128
PIN = 128.0        # generator._opaque_bbox()'s threshold -- do not change
BACKUP_SUFFIX = "_precut"


def roughness(alpha):
    """Boundary px displaced by a 2px smooth, as % of boundary length."""
    m = alpha >= PIN
    if m.sum() < 500:
        return float("nan")
    edge = m ^ ndi.binary_erosion(m, np.ones((3, 3)))
    n = int(edge.sum())
    if n < 100:
        return float("nan")
    sm = ndi.gaussian_filter(alpha.astype(float), 2.0) >= PIN
    return 100.0 * int((m ^ sm).sum()) / n


def recut(arr, colour_only=False, median=MEDIAN, contrast=CONTRAST):
    a = arr.copy()
    al0 = a[:, :, 3]
    solid = al0 > TRUST
    trusted = ndi.binary_erosion(solid, iterations=BAND)
    if trusted.sum() < 200:
        return None

    rgb = a[:, :, :3].copy()
    idx = ndi.distance_transform_edt(~trusted, return_distances=False,
                                     return_indices=True)
    fill = ~trusted
    for c in range(3):
        ch = rgb[:, :, c]
        ch[fill] = ch[idx[0][fill], idx[1][fill]]
        rgb[:, :, c] = ch

    if colour_only:
        return np.dstack([rgb, al0])

    al = al0.astype(np.float64)
    if median:
        al = ndi.median_filter(al, size=2 * median + 1).astype(np.float64)
    al = np.clip(PIN + (al - PIN) * contrast, 0, 255)
    return np.dstack([rgb, al.astype(np.uint8)])


def bbox128(alpha):
    m = alpha >= PIN
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trait_class")
    ap.add_argument("files", nargs="*", help="default: every file in the class")
    ap.add_argument("--colour-only", action="store_true",
                    help="stage 1 only: alpha comes back bit-identical")
    ap.add_argument("--soften", action="store_true",
                    help="run soften_stepped_edges inline afterwards (required "
                         "unless --colour-only)")
    ap.add_argument("--report", action="store_true",
                    help="rank the class by boundary roughness, write nothing")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    d = os.path.join(g.TRAITS_DIR, args.trait_class)
    if not os.path.isdir(d):
        sys.exit(f"no such trait class: {d}")
    files = args.files or sorted(f for f in os.listdir(d)
                                 if f.lower().endswith(".png"))

    if args.report:
        rows = []
        for f in files:
            a = np.asarray(Image.open(os.path.join(d, f)).convert("RGBA"))
            rows.append((roughness(a[:, :, 3]), f))
        rows = [r for r in rows if r[0] == r[0]]
        rows.sort(reverse=True)
        med = np.median([r[0] for r in rows])
        print(f"## {args.trait_class}   boundary roughness "
              f"(median {med:.1f}%)")
        for v, f in rows:
            print(f"  {v:6.1f}%  {f}")
        print("\nA high reading is NOT proof of a soft cut -- fur, a lightsaber"
              "\nglow and a ridged churro all read high legitimately. Render the"
              "\nasset over flat grey and look at it.")
        return

    if not (args.colour_only or args.soften or args.dry_run):
        sys.exit("a full recut hardens the edge; pass --soften (or --colour-only)")

    done = 0
    for f in files:
        p = os.path.join(d, f)
        a0 = np.asarray(Image.open(p).convert("RGBA"))
        out = recut(a0, colour_only=args.colour_only)
        if out is None:
            continue
        n_step = 0
        if not args.colour_only and args.soften:
            out, _, _, n_step = soften(out)
        else:
            n_step = int(stepped(out[:, :, 3]).sum())

        assert (out[:, :, 3] > TRUST).sum() > 0
        if args.colour_only:
            assert (out[:, :, 3] == a0[:, :, 3]).all(), f"{f}: alpha moved"
        assert n_step == 0, f"{f}: {n_step} stepped px left; --soften needed"

        b0, b1 = bbox128(a0[:, :, 3]), bbox128(out[:, :, 3])
        print(f"  {f:46.46s} rough {roughness(a0[:, :, 3]):5.1f}% -> "
              f"{roughness(out[:, :, 3]):5.1f}%   bbox {b0} -> {b1}"
              f"{'   (dry run)' if args.dry_run else ''}")
        if b0 != b1:
            print("      NOTE: the alpha>=128 box moved. generator.armed_lift()"
                  " reads the arm's bottom edge off it -- re-run"
                  " verify_generator_rules.py.")
        if not args.dry_run:
            bd = os.path.join(g.TRAITS_DIR, args.trait_class + BACKUP_SUFFIX)
            os.makedirs(bd, exist_ok=True)
            bak = os.path.join(bd, f)
            if not os.path.exists(bak):
                shutil.copy2(p, bak)
            Image.fromarray(out).save(p)
        done += 1
    print(f"\n{done} asset(s) {'would be ' if args.dry_run else ''}re-cut")


if __name__ == "__main__":
    main()
