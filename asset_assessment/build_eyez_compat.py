#!/usr/bin/env python3
"""Build a measured eye <-> background compatibility map for generator.py.

Colored eyes (Blue/zaffre, Cerise, Cyan, tech-glow cyan) are the brand
accents; neutral black/white expression eyes are never restricted. For every
background plate we measure how much saturated mass sits within HUE_TOL
degrees of each colored eye's dominant hue. Two rules are supported:

  anti-clash (default): BLOCK an eye on plates that prominently wear the
      eye's own colour (plate would camouflage the accent)
  match: ALLOW a colored eye ONLY on plates that wear a related colour
      (thematic echo); neutral eyes stay unrestricted

Beyond the hard block, a SOFT curation weight is emitted for every colored eye
on every non-blocked plate, so the generator biases toward the best-looking
pairings (the same gentle, variety-preserving philosophy as char_compat's
weights). A colored accent looks best when the plate is toward its complement
AND isn't already wearing that colour, so:
    harmony = 0.5 * (complementary hue separation) + 0.5 * (1 - in-band share)
    weight  = max(harmony, 0.05) ** strength
Neutral (black/white) eyes are omitted -> the generator treats them as uniform.

Writes traits/eyez_compat.json:
  {"mode": ..., "src": ..., "strength": ...,
   "blocked": {bg_file: [eye_file, ...]},
   "weights": {bg_file: {eye_file: w, ...}}}
generator.py treats a missing file or empty entry as "everything allowed".

Usage:
  python3 asset_assessment/build_eyez_compat.py [--src traits/backgroundz]
          [--mode anti-clash|match] [--strength 0.8] [--dry-run]
"""

import argparse
import json
import os

import numpy as np
from PIL import Image

EYE_DIR = "traits/eyez"
OUT = "traits/eyez_compat.json"
HUE_TOL = 35.0        # deg: plate colour counted as "the eye's colour"
PLATE_SAT_MIN = 0.25  # plate must be at least this saturated to clash
SHARE_CLASH = 0.30    # >=30 % of plate's saturated mass in-band -> clash
SHARE_MATCH = 0.10    # >=10 % in-band counts as a thematic match
EYE_SAT_MIN = 0.35    # eyes with less saturated mass than this are neutral
EYE_SAT_SHARE = 0.10  # ...measured as share of opaque pixels


def hue_sat(rgb):  # rgb float 0..255 (N,3) -> hue deg, sat 0..1
    mx, mn = rgb.max(axis=1), rgb.min(axis=1)
    c = np.maximum(mx - mn, 1e-9)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0.0)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    h = np.zeros(len(rgb))
    k = mx == r
    h[k] = ((g - b)[k] / c[k]) % 6.0
    k = mx == g
    h[k] = (b - r)[k] / c[k] + 2.0
    k = mx == b
    h[k] = (r - g)[k] / c[k] + 4.0
    return h * 60.0, sat


def opaque_px(path):
    a = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float64)
    m = a[..., 3] >= 128
    return a[..., :3][m]


def eye_profile(path):
    px = opaque_px(path)
    h, s = hue_sat(px)
    colored = s >= EYE_SAT_MIN
    if colored.mean() < EYE_SAT_SHARE:
        return None  # neutral eye, unrestricted
    w = s[colored]
    hh = h[colored]
    # circular weighted mean hue
    ang = np.deg2rad(hh)
    mean = np.rad2deg(np.arctan2((w * np.sin(ang)).sum(),
                                 (w * np.cos(ang)).sum())) % 360.0
    return {"hue": float(mean), "sat_share": float(colored.mean())}


def plate_band_share(px, hue0):
    h, s = hue_sat(px)
    if s.sum() < 1e-6:
        return 0.0, 0.0
    d = np.abs((h - hue0 + 180.0) % 360.0 - 180.0)
    share = float((s * (d <= HUE_TOL)).sum() / s.sum())
    return share, float(s.mean())


def plate_dominant_hue(px):
    """Saturation-weighted dominant hue of a plate's opaque pixels (deg)."""
    h, s = hue_sat(px)
    if s.sum() < 1e-6:
        return 0.0
    hist, _ = np.histogram(h, bins=24, range=(0, 360), weights=s)
    return float((np.argmax(hist) + 0.5) * 15.0)


def hue_dist(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="traits/backgroundz")  # graded set
    ap.add_argument("--mode", choices=["anti-clash", "match"],
                    default="anti-clash")
    ap.add_argument("--strength", type=float, default=0.8,
                    help="how hard to favour the best eye pairings (0 = "
                         "uniform, 1 = linear in harmony). Gentle by default "
                         "so every non-blocked eye stays well represented.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    eyes = {}
    for f in sorted(os.listdir(EYE_DIR)):
        if f.endswith(".png"):
            eyes[f] = eye_profile(os.path.join(EYE_DIR, f))
    colored = {f: p for f, p in eyes.items() if p}
    print("colored eyes:",
          {f: f"hue {p['hue']:.0f}" for f, p in colored.items()})
    print("neutral (never restricted):",
          [f for f, p in eyes.items() if not p])

    blocked, weights = {}, {}
    plates = sorted(f for f in os.listdir(args.src)
                    if f.lower().endswith((".png", ".jpg")))
    print(f"\n{'plate':<46}" + "".join(f"{f.split('.')[0][:12]:>14}"
                                       for f in colored))
    for bg in plates:
        px = opaque_px(os.path.join(args.src, bg))
        dom = plate_dominant_hue(px)
        row, marks, wrow = [], [], {}
        for f, p in colored.items():
            share, msat = plate_band_share(px, p["hue"])
            if args.mode == "anti-clash":
                bad = share >= SHARE_CLASH and msat >= PLATE_SAT_MIN
            else:  # match: block colored eye when plate does NOT echo it
                bad = share < SHARE_MATCH
            if bad:
                row.append(f)
            else:
                # soft pairing preference: complementary + not self-coloured
                harmony = 0.5 * (hue_dist(p["hue"], dom) / 180.0) \
                    + 0.5 * (1.0 - min(share, 1.0))
                wrow[f] = round(max(harmony, 0.05) ** args.strength, 3)
            marks.append("BLOCK" if bad else ".")
        if row:
            blocked[bg] = row
        if wrow:
            weights[bg] = wrow
        print(f"{bg[:45]:<46}" + "".join(f"{m:>14}" for m in marks))

    n_pairs = sum(len(v) for v in blocked.values())
    print(f"\nmode={args.mode}: {n_pairs} blocked (eye,plate) pairs "
          f"across {len(blocked)} plates")
    print(f"pairing weights: strength={args.strength} over "
          f"{sum(len(v) for v in weights.values())} (eye,plate) pairs")
    if not args.dry_run:
        with open(OUT, "w") as f:
            json.dump({"mode": args.mode, "src": args.src,
                       "strength": args.strength,
                       "blocked": blocked, "weights": weights}, f, indent=1)
        print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
