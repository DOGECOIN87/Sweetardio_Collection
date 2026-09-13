#!/usr/bin/env python3
"""Anti-alias the hard, un-anti-aliased edges audit_edges.py flags as STEPPED.

A STEPPED edge is a fully-opaque pixel touching a fully-clear one: the alpha
was cut with no ramp at all, so the boundary is a staircase. It is the most
visible edge defect there is, because every other edge in the collection
carries a 1-2px ramp and a stepped one reads as a jagged cut beside them.

THE REPAIR ADDS, IT NEVER ERODES. The obvious fix -- blur the alpha at the
boundary -- pulls opaque pixels down below 255 and so moves the `alpha > 200`
silhouette. That box is load-bearing twice over: WAT_SCALE_PIVOT was solved
against the footwear sole line measured at that threshold (see CLAUDE.md), and
clean_trait_art.py already refuses to touch a footwear asset whose solid bbox
would move. So instead a single ramp ring is painted just OUTSIDE the hard
edge, in pixels that are currently fully clear:

    hard  = opaque(>=248) touching clear(<=8)
    ring  = the clear pixels adjacent to `hard`
    ring alpha -> RING_ALPHA, ring RGB -> nearest opaque neighbour

Every previously-opaque pixel keeps its exact alpha AND its exact RGB, and
RING_ALPHA is far below 200, so the `alpha > 200` bbox provably cannot move in
either direction. The run asserts both.

RGB comes from the nearest already-opaque pixel rather than from black or
white, for the reason clean_alpha.py documents: colour that does not match the
art bleeds into the fringe the moment the layer is resampled.

  python3 asset_assessment/soften_stepped_edges.py --report
  python3 asset_assessment/soften_stepped_edges.py armz --dry-run
  python3 asset_assessment/soften_stepped_edges.py               # every class
"""

import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g  # noqa: E402

# Half coverage. High enough that the ramp actually reads as anti-aliasing,
# low enough that it can never enter the alpha>200 silhouette.
RING_ALPHA = 110
OPAQUE = 248
CLEAR = 8
SOLID = 200          # the threshold the footwear geometry is measured at

CLASSES = [g.CHARACTERZ, g.EYEZ, g.MOUTHZ, g.ARMZ, g.WHAT_ARE_THOSEZ,
           g.STICKERZ, g.SKINZ]
BACKUP_SUFFIX = "_prestep"


def stepped(alpha):
    """Fully-opaque pixels touching fully-clear ones."""
    op = alpha >= OPAQUE
    cl = alpha <= CLEAR
    return ndi.binary_dilation(cl, np.ones((3, 3))) & op


def soften(rgba):
    """Return (new_rgba, n_ring, n_step_before, n_step_after)."""
    a = rgba.copy()
    rgb, al = a[:, :, :3], a[:, :, 3]
    before = stepped(al)
    n_before = int(before.sum())
    if n_before == 0:
        return a, 0, 0, 0

    ring = ndi.binary_dilation(before, np.ones((3, 3))) & (al <= CLEAR)
    if not ring.any():
        return a, 0, n_before, n_before

    src = al >= OPAQUE
    idx = ndi.distance_transform_edt(~src, return_distances=False,
                                     return_indices=True)
    for c in range(3):
        ch = rgb[:, :, c]
        ch[ring] = ch[idx[0][ring], idx[1][ring]]
        rgb[:, :, c] = ch
    al[ring] = RING_ALPHA
    return a, int(ring.sum()), n_before, int(stepped(al).sum())


def backup_dir(cls):
    return os.path.join(g.TRAITS_DIR, f"{cls}{BACKUP_SUFFIX}")


def run(classes, apply_it, report_only):
    total_assets = total_ring = 0
    for cls in classes:
        d = os.path.join(g.TRAITS_DIR, cls)
        if not os.path.isdir(d):
            continue
        rows = []
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith(".png"):
                continue
            path = os.path.join(d, fn)
            arr = np.array(Image.open(path).convert("RGBA"))
            out, n_ring, n0, n1 = soften(arr)
            if n0 == 0:
                continue
            rows.append((fn, n0, n1, n_ring))
            if report_only:
                continue

            # provable safety: the solid silhouette and every opaque pixel
            # must be byte-identical to what went in.
            assert ((arr[:, :, 3] > SOLID) == (out[:, :, 3] > SOLID)).all(), \
                f"{fn}: alpha>{SOLID} silhouette moved"
            keep = arr[:, :, 3] > CLEAR
            assert (out[:, :, 3][keep] == arr[:, :, 3][keep]).all(), \
                f"{fn}: alpha changed on a visible pixel"
            assert (out[:, :, :3][keep] == arr[:, :, :3][keep]).all(), \
                f"{fn}: rgb changed on a visible pixel"

            if apply_it:
                bd = backup_dir(cls)
                os.makedirs(bd, exist_ok=True)
                bak = os.path.join(bd, fn)
                if not os.path.exists(bak):
                    shutil.copy2(path, bak)
                Image.fromarray(out).save(path)
            total_ring += n_ring
        if rows:
            print(f"## {cls}")
            for fn, n0, n1, n_ring in rows:
                tag = "" if apply_it else "   (dry run)"
                print(f"  {fn:48s} stepped {n0:5d} -> {n1:<5d} "
                      f"ramp {n_ring:5d}px{tag}")
            total_assets += len(rows)
    verb = "softened" if apply_it else "would be softened"
    print(f"\n{total_assets} asset(s) {verb}"
          + ("" if report_only else
             f"; {total_ring} ramp px added, solid silhouette verified unchanged"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("classes", nargs="*", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", action="store_true",
                    help="list stepped assets, compute nothing else")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()

    classes = args.classes or CLASSES
    if args.restore:
        for cls in classes:
            bd, live = backup_dir(cls), os.path.join(g.TRAITS_DIR, cls)
            if not os.path.isdir(bd):
                continue
            for fn in sorted(os.listdir(bd)):
                shutil.copy2(os.path.join(bd, fn), os.path.join(live, fn))
                print(f"  restored {cls}/{fn}")
        return
    run(classes, apply_it=not (args.dry_run or args.report),
        report_only=args.report)


if __name__ == "__main__":
    main()
