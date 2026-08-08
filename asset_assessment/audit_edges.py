#!/usr/bin/env python3
"""Audit every asset for the defects the Nutty Bar rebuild turned up.

audit_art_quality.py asks whether an asset is soft or the wrong size. This asks
a narrower, more mechanical question: **is the alpha channel clean?** Those are
the defects that survive every other check, because they only show at the
boundary and only against certain backgrounds.

Six measurements, each one a defect that was actually found in this collection:

  HALO      Semi-transparent fringe brighter than the art beside it. Means the
            asset was flattened onto a light background before keying and the
            blend is baked into RGB. Compared against the art it touches, not
            against the whole asset, so a genuinely bright rim does not flag.
  STEPPED   Fully-opaque pixels touching fully-clear ones: no anti-aliasing at
            all, a staircase edge.
  BINARY    Fewer than ~32 distinct alpha levels — the alpha was thresholded,
            so every edge in the asset is stepped.
  GHOST     Colour hiding under alpha 0 that does NOT match the art it sits
            beside. Invisible in a straight composite, but it bleeds into the
            fringe the moment the layer is resampled. Measured as a difference
            from the neighbouring art, not as a raw level: an asset whose
            transparent pixels carry the edge colour on purpose (what
            clean_alpha.py and fix_matte_line.py both produce) is CORRECT, and
            a raw mean cannot tell that apart from junk.
  SPECKS    Disconnected fragments away from the main shape. Render debris.
            Counted at ANY opacity: an alpha 1-8 ghost is invisible but still
            inflates getbbox(), which is what silently shrank the OG bear.
  WOBBLE    For assets with a face hole, how far its outline strays from the
            ellipse fitted to it. The hole's rim is the line the skin ball is
            seen through, so raggedness there reads as bad art.

  python3 asset_assessment/audit_edges.py                 # every class
  python3 asset_assessment/audit_edges.py characterz skinz
  python3 asset_assessment/audit_edges.py --verbose       # all rows, not just flags
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

# Thresholds. HALO is the loose one on purpose: the cast sits at -40 to -88, so
# anything at or above zero is carrying background, and the Nutty Bar was +42.
HALO = 0.0
STEPPED = 20
LEVELS = 32
GHOST = 30.0     # px of luma difference from the art the transparency borders
SPECKS = 0
WOBBLE = 2.0
SPECK_MAX = 400      # px; bigger disconnected pieces are design, not debris


def measure(path):
    a = np.asarray(Image.open(path).convert("RGBA"))
    al = a[..., 3].astype(np.int16)
    rgb = a[..., :3].astype(np.int16)
    m = al > 8
    if not m.any():
        return None
    out = {"levels": len(np.unique(al)),
           "has_edge": bool((al == 0).any()),
           "ghost": 0.0}

    solid = al > 250
    clear = al < 5
    fringe = (al >= 5) & (al <= 250)
    out["stepped"] = int((ndimage.binary_dilation(solid) & clear).sum())

    # Specks: SMALL disconnected fragments, at ANY opacity. Counting every
    # component over-flags — a sticker legitimately has separate letters and a
    # pair of slippers is two blobs — so only fragments under SPECK_MAX count,
    # and the distance to the main blob is reported so real design elements
    # sitting against the art can be told from debris thrown clear of it.
    lab, n = ndimage.label(al > 0)
    out["specks"] = out["speck_px"] = 0
    out["speck_far"] = 0
    if n > 1:
        sz = ndimage.sum(al > 0, lab, range(1, n + 1))
        main = int(np.argmax(sz)) + 1
        my, mx = np.where(lab == main)
        bb = (mx.min(), my.min(), mx.max(), my.max())
        far = 0
        small = 0
        px = 0
        for i in range(1, n + 1):
            if i == main or sz[i - 1] >= SPECK_MAX:
                continue
            small += 1
            px += int(sz[i - 1])
            yy, xx = np.where(lab == i)
            d = max(bb[0] - xx.max(), xx.min() - bb[2],
                    bb[1] - yy.max(), yy.min() - bb[3], 0)
            far = max(far, int(d))
        out["specks"], out["speck_px"], out["speck_far"] = small, px, far

    # ghost: under-colour near the shape vs the art it borders
    # strictly alpha == 0: pixels at alpha 1-8 still contribute to a composite,
    # so clean_alpha.py deliberately preserves their colour and it is not ghost
    near_clear = ndimage.binary_dilation(m, iterations=10) & (al == 0)
    near_art = ndimage.binary_dilation(near_clear, iterations=3) & solid
    if near_clear.sum() > 200 and near_art.any():
        out["ghost"] = float(abs(rgb[near_clear].mean() - rgb[near_art].mean()))

    # halo: fringe vs the art it actually touches
    if fringe.any():
        near = ndimage.binary_dilation(fringe, iterations=3) & solid
        out["halo"] = (float(rgb[fringe].mean() - rgb[near].mean())
                       if near.any() else float("nan"))
    else:
        out["halo"] = float("nan")

    # wobble: face-hole outline vs the ellipse fitted to it
    out["hole_w"] = 0
    out["wobble"] = float("nan")
    hole = ndimage.binary_fill_holes(m) & ~m
    lb, nn = ndimage.label(hole)
    if nn:
        hsz = ndimage.sum(hole, lb, range(1, nn + 1))
        if hsz.max() > 5000:
            hh = lb == int(np.argmax(hsz)) + 1
            ys, xs = np.where(hh)
            cy, cx = ys.mean(), xs.mean()
            ry = (ys.max() - ys.min() + 1) / 2
            rx = (xs.max() - xs.min() + 1) / 2
            bnd = ndimage.binary_dilation(hh) & ~hh
            by, bx = np.where(bnd)
            r = np.sqrt(((bx - cx) / rx) ** 2 + ((by - cy) / ry) ** 2)
            out["hole_w"] = int(xs.max() - xs.min() + 1)
            out["wobble"] = float(r.std() * (rx + ry) / 2)
    return out


def flags(v):
    f = []
    if not np.isnan(v["halo"]) and v["halo"] > HALO:
        f.append("HALO")
    if v["stepped"] > STEPPED:
        f.append("STEPPED")
    # A fully opaque plate (the 1/1s) has one alpha level by design, and no
    # edge to anti-alias. Only flag thresholded alpha where there IS an edge.
    if v["levels"] < LEVELS and v["has_edge"]:
        f.append("BINARY")
    if v["ghost"] > GHOST:
        f.append("GHOST")
    if v["specks"] > SPECKS:
        f.append("SPECKS")
    if not np.isnan(v["wobble"]) and v["wobble"] > WOBBLE:
        f.append("WOBBLE")
    return f


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("classes", nargs="*", default=CLASSES)
    ap.add_argument("--verbose", action="store_true",
                    help="print every asset, not just the flagged ones")
    args = ap.parse_args()

    rows = []
    for c in args.classes:
        d = os.path.join(g.TRAITS_DIR, c)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith(".png"):
                continue
            v = measure(os.path.join(d, f))
            if v:
                v["cls"], v["name"] = c, f
                rows.append(v)

    hdr = (f"{'asset':<48s}{'halo':>7s}{'step':>6s}{'lvls':>6s}"
           f"{'ghost':>7s}{'specks':>7s}{'wobble':>8s}  flags")
    print(hdr)
    print("-" * len(hdr))
    bad = [r for r in rows if flags(r)]
    show = rows if args.verbose else bad
    for r in sorted(show, key=lambda r: -len(flags(r))):
        w = "  n/a " if np.isnan(r["wobble"]) else f"{r['wobble']:6.1f}"
        h = "  n/a " if np.isnan(r["halo"]) else f"{r['halo']:6.1f}"
        print(f"{r['cls'] + '/' + r['name']:<48.48s}{h:>7s}{r['stepped']:>6d}"
              f"{r['levels']:>6d}{r['ghost']:>7.1f}{r['specks']:>7d}"
              f"{w:>8s}  {','.join(flags(r))}")

    print(f"\n{len(bad)} of {len(rows)} assets flagged")
    counts = {}
    for r in bad:
        for f in flags(r):
            counts[f] = counts.get(f, 0) + 1
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<9s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
