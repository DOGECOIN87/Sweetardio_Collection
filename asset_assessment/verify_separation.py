#!/usr/bin/env python3
"""Cast-wide figure-ground separation check, before vs after grading.

The cast is NOT all dual-tone, so this checks every body shape against the
graded sample plates: all 29 whole characters PLUS the top and bottom halves
of the 10 cone-style characters as separate entries (49 cast entries).

A (character, plate) pairing is counted AT RISK when all three contrast
channels are weak simultaneously:
  |L_char - L_plate| < 35   (luminance)
  S_char - S_plate  < 0.18  (saturation margin: char should be more saturated)
  circular hue distance of dominant hues < 40 deg (only when the plate is
  saturated enough for hue to matter, S_plate >= 0.15)

Usage: python3 asset_assessment/verify_separation.py [graded_dir]
Compares traits/backgroundz_originals vs graded_dir (default traits/backgroundz)
for every plate present in graded_dir.
"""

import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, "background_pop_studies")
from grade import measure  # same metric definitions as the engine

SRC = "traits/backgroundz_originals"


def plate_stats(path):
    img = Image.open(path).convert("RGBA")
    a = np.asarray(img, dtype=np.float64) / 255.0
    m = measure(a[..., :3], a[..., 3])
    # saturation-weighted dominant hue
    rgb = a[..., :3] * 255.0
    op = a[..., 3] >= 0.5
    px = rgb[op]
    mx, mn = px.max(axis=1), px.min(axis=1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0.0)
    c = np.maximum(mx - mn, 1e-9)
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    h = np.zeros(len(px))
    k = mx == r
    h[k] = ((g - b)[k] / c[k]) % 6.0
    k = mx == g
    h[k] = (b - r)[k] / c[k] + 2.0
    k = mx == b
    h[k] = (r - g)[k] / c[k] + 4.0
    h *= 60.0
    hist, _ = np.histogram(h, bins=24, range=(0, 360), weights=sat)
    m["hue"] = float((np.argmax(hist) + 0.5) * 15.0)
    return m


def cast_entries():
    out = []
    for r in json.load(open("asset_assessment/metrics.json")):
        if r.get("folder") != "characterz" or r.get("empty"):
            continue
        hue = (int(np.argmax(r["hue_hist"])) + 0.5) * 30.0
        out.append((os.path.basename(r["file"]), r["L_mean"], r["S_mean"],
                    hue))
    for r in json.load(open("asset_assessment/split_metrics.json")):
        if not r["is_cone_style"]:
            continue
        for half in ("top", "bottom"):
            h = r[half]
            hue = (int(np.argmax(h["hue_hist"])) + 0.5) * 30.0
            out.append((f"{r['file']}::{half}", h["L"], h["S"], hue))
    return out


def hue_dist(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def at_risk(cL, cS, cH, p):
    weak_L = abs(cL - p["L"]) < 35.0
    weak_S = (cS - p["S"]) < 0.18
    weak_H = p["S"] < 0.15 or hue_dist(cH, p["hue"]) < 40.0
    # when the plate is near-neutral, hue can't rescue a weak L+S pairing
    return weak_L and weak_S and weak_H


def main():
    graded_dir = sys.argv[1] if len(sys.argv) > 1 else "traits/backgroundz"
    cast = cast_entries()
    print(f"cast entries: {len(cast)} (29 whole bodies + cone-style halves)")
    print(f"{'plate':<44}{'at-risk before':>15}{'after':>7}  worst remaining")
    tot_b = tot_a = 0
    for fn in sorted(os.listdir(graded_dir)):
        if not fn.endswith(".png"):
            continue
        stem = os.path.splitext(fn)[0]
        src = next((os.path.join(SRC, stem + e) for e in (".png", ".jpg")
                    if os.path.exists(os.path.join(SRC, stem + e))), None)
        if src is None:
            continue
        pb = plate_stats(src)
        pa = plate_stats(os.path.join(graded_dir, fn))
        rb = [c for c in cast if at_risk(c[1], c[2], c[3], pb)]
        ra = [c for c in cast if at_risk(c[1], c[2], c[3], pa)]
        tot_b += len(rb)
        tot_a += len(ra)
        worst = ", ".join(c[0].replace("before_skinz_", "")
                          .replace("after_skinz_", "")[:28] for c in ra[:2])
        print(f"{stem[:43]:<44}{len(rb):>15}{len(ra):>7}  {worst}")
    print(f"\nTOTAL at-risk pairings: {tot_b} -> {tot_a}")


if __name__ == "__main__":
    main()
