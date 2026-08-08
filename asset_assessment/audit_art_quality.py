#!/usr/bin/env python3
"""Audit the art itself: sharpness, alpha edges, lighting direction, hygiene.

ASSESSMENT.md measures colour and composition for grading decisions. This asks
a different question — is any individual asset technically substandard, and
does it obey the collection's conventions?

Four checks, all objective:

  SHARPNESS      mean gradient magnitude across the opaque mass, normalised by
                 contrast. A soft asset is one that was upscaled from smaller
                 art or over-blurred; it reads mushy next to its peers even
                 though the canvas says 1393x1393.

  ALPHA EDGE     width of the semi-transparent band around the silhouette, and
                 whether transparent pixels still carry colour. A wide band
                 means a soft/feathered cut; colour under full transparency
                 means the asset was flattened against a background at some
                 point and will fringe when composited.

  LIGHTING       luma of the upper-left limb vs the lower-right limb of the
                 form. The collection's key light is TOP LEFT (see CLAUDE.md),
                 so the upper-left limb must read brighter. A ratio at or below
                 1.0 means that asset is lit from somewhere else and will not
                 sit with the rest of the cast.

  HYGIENE        canvas size, colour mode, and stray disconnected specks that
                 will composite as floating debris.

Usage:
  python3 asset_assessment/audit_art_quality.py            # every class
  python3 asset_assessment/audit_art_quality.py characterz armz
"""

import math
import os
import statistics
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")
import generator as g  # noqa: E402

CANVAS = 1393
CLASSES = ["characterz", "skinz", "eyez", "mouthz", "armz",
           "what_are_thosez", "stickerz", "backgroundz", "secret_rarez"]


def load(path):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im).astype(np.float32)
    rgb, alpha = a[:, :, :3], a[:, :, 3]
    luma = 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]
    return im, rgb, alpha, luma


def sharpness(luma, mask):
    """Mean |gradient| over the opaque mass, normalised by that region's
    contrast so a dark asset is not penalised for being dark."""
    if mask.sum() < 500:
        return float("nan")
    gy, gx = np.gradient(luma)
    grad = np.hypot(gx, gy)[mask]
    spread = luma[mask].std()
    return float(grad.mean() / spread) if spread > 1 else float("nan")


def alpha_edge(alpha):
    """(fringe band width in px, share of transparent pixels carrying colour)."""
    soft = ((alpha > 8) & (alpha < 248))
    solid = alpha >= 248
    # a clean anti-aliased cut is a 1-2px ring around a large solid mass
    width = soft.sum() / max(1, perimeter_estimate(solid))
    return float(width), soft.sum()


def perimeter_estimate(solid):
    if solid.sum() == 0:
        return 1
    # 4-neighbour boundary count
    p = np.zeros_like(solid)
    p[:-1, :] |= solid[:-1, :] & ~solid[1:, :]
    p[1:, :] |= solid[1:, :] & ~solid[:-1, :]
    p[:, :-1] |= solid[:, :-1] & ~solid[:, 1:]
    p[:, 1:] |= solid[:, 1:] & ~solid[:, :-1]
    return max(1, int(p.sum()))


def ghost_colour(rgb, alpha):
    """Mean luma of fully transparent pixels. Non-zero means the asset was
    flattened onto something and carries that colour under the transparency."""
    t = alpha <= 4
    if t.sum() == 0:
        return 0.0
    return float(rgb[t].mean())


def albedo_uniform(rgb, mask, thresh=26):
    """True when the asset is close to one colour, so a luma comparison reads
    SHADING rather than paint. Multi-coloured art (a dark scoop on a light
    cone) fails a limb-luma test on albedo alone, which makes the lighting
    check meaningless there — those are reported n/a rather than flagged."""
    if mask.sum() < 2000:
        return False
    px = rgb[mask]
    return bool(px.std(axis=0).mean() < thresh)


def lighting_ratio(luma, mask):
    """Upper-left limb luma / lower-right limb luma.

    Samples the 60-95% radius band in the two opposing 45-degree sectors, so
    it reads the form's terminator rather than any single highlight. Only
    meaningful on uniform-albedo assets — see albedo_uniform().
    """
    ys, xs = np.nonzero(mask)
    if len(ys) < 2000:
        return float("nan")
    cy, cx = ys.mean(), xs.mean()
    r = np.hypot(ys - cy, xs - cx)
    rmax = np.percentile(r, 99)
    limb = (r > 0.60 * rmax) & (r <= 0.95 * rmax)
    ang = np.arctan2(-(ys - cy), xs - cx)      # screen y is down
    ul = limb & (ang > math.radians(100)) & (ang < math.radians(170))
    lr = limb & (ang > math.radians(-80)) & (ang < math.radians(-10))
    v = luma[ys, xs]
    if ul.sum() < 200 or lr.sum() < 200:
        return float("nan")
    lo = v[lr].mean()
    return float(v[ul].mean() / lo) if lo > 1 else float("nan")


def stray_specks(alpha, min_px=64):
    """Disconnected opaque blobs far smaller than the main mass."""
    from scipy import ndimage                      # noqa
    return None


def speck_count(alpha, min_px=64):
    solid = (alpha >= 128)
    if solid.sum() == 0:
        return 0, 0
    # cheap connected components via label propagation on a downsample
    small = solid[::2, ::2]
    lbl = np.zeros(small.shape, np.int32)
    cur = 0
    sizes = []
    stack = []
    H, W = small.shape
    for sy in range(H):
        for sx in range(W):
            if not small[sy, sx] or lbl[sy, sx]:
                continue
            cur += 1
            stack.append((sy, sx))
            lbl[sy, sx] = cur
            n = 0
            while stack:
                y, x = stack.pop()
                n += 1
                for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
                    if 0 <= ny < H and 0 <= nx < W and small[ny, nx] \
                            and not lbl[ny, nx]:
                        lbl[ny, nx] = cur
                        stack.append((ny, nx))
            sizes.append(n * 4)
    if not sizes:
        return 0, 0
    biggest = max(sizes)
    strays = [s for s in sizes if s != biggest and s >= min_px]
    return len(strays), biggest


def main():
    want = sys.argv[1:] or CLASSES
    print("Sweetardio — art quality audit\n" + "=" * 76)
    findings = []

    for cls in want:
        d = os.path.join(g.TRAITS_DIR, cls)
        if not os.path.isdir(d):
            continue
        files = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
        if not files:
            continue
        rows = []
        for f in files:
            path = os.path.join(d, f)
            im, rgb, alpha, luma = load(path)
            mask = alpha >= 128
            rows.append({
                "file": f, "size": im.size,
                "sharp": sharpness(luma, mask),
                "fringe": alpha_edge(alpha)[0],
                "ghost": ghost_colour(rgb, alpha),
                "light": (lighting_ratio(luma, mask)
                          if albedo_uniform(rgb, mask) else float("nan")),
                "flat": cls in ("eyez", "mouthz"),
                "opaque": float(mask.mean() * 100),
            })

        sh = [r["sharp"] for r in rows if not math.isnan(r["sharp"])]
        med_sh = statistics.median(sh) if sh else float("nan")
        print(f"\n## {cls}  ({len(rows)} assets, median sharpness {med_sh:.3f})")
        print(f"{'asset':46s} {'size':>10s} {'sharp':>6s} {'fringe':>7s} "
              f"{'ghost':>6s} {'UL/LR':>6s}")
        for r in sorted(rows, key=lambda r: r["sharp"]):
            flags = []
            if not math.isnan(r["sharp"]) and med_sh and r["sharp"] < med_sh * 0.55:
                flags.append("SOFT")
            if r["fringe"] > 4.0:
                flags.append("WIDE-EDGE")
            if r["ghost"] > 8:
                flags.append("GHOST-COLOUR")
            # flat graphic classes have stylised catchlights, not rendered
            # form lighting, so the convention does not apply to them
            if (not r["flat"] and not math.isnan(r["light"])
                    and r["light"] < 1.0):
                flags.append("LIT-WRONG")
            if r["size"] != (CANVAS, CANVAS):
                flags.append(f"SIZE{r['size'][0]}x{r['size'][1]}")
            if flags:
                findings.append((cls, r["file"], flags, r))
            print(f"{r['file'][:46]:46s} {str(r['size']):>10s} "
                  f"{r['sharp']:6.3f} {r['fringe']:7.2f} {r['ghost']:6.1f} "
                  f"{r['light']:6.2f}  {' '.join(flags)}")

    print("\n" + "=" * 76)
    print(f"FINDINGS: {len(findings)} assets flagged")
    by = {}
    for cls, f, flags, r in findings:
        for fl in flags:
            by.setdefault(fl.split("SIZE")[0] or "SIZE", []).append(f"{cls}/{f}")
    for k, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"\n  {k}  ({len(v)})")
        for n in v[:12]:
            print(f"    {n}")
        if len(v) > 12:
            print(f"    ... and {len(v)-12} more")


if __name__ == "__main__":
    main()
