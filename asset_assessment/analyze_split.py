#!/usr/bin/env python3
"""Vertical-split (top half vs bottom half) analysis of character bodies.

Follow-up to ASSESSMENT.md: verifies the observation that ice-cream
characters have a warm lower half (cone) and a cool, brand-palette upper
half (scoop). For every characterz asset: find the opaque bounding box,
split it at its vertical midpoint, and measure each half separately
(opaque pixels only): mean L, mean S, temp (R-B), saturation-weighted hue
histogram, share of pixels within RGB distance 60 of each brand colour.

Writes asset_assessment/split_metrics.json and prints a summary table.
Read-only. Usage: python3 asset_assessment/analyze_split.py
"""

import json
import os

import numpy as np
from PIL import Image

CHAR_DIR = "traits/characterz"
OUT = "asset_assessment/split_metrics.json"
ALPHA_OPAQUE = 128

BRAND = {
    "oxford": (0x07, 0x0F, 0x34),
    "zaffre": (0x03, 0x13, 0xA6),
    "violet": (0x92, 0x01, 0xCB),
    "cerise": (0xF7, 0x15, 0xAB),
    "cyan": (0x34, 0xED, 0xF3),
}
BANDS = ["R", "O", "Y", "YG", "G", "GC", "C", "CB", "B", "V", "M", "P"]

ICE_HINTS = ("ice_cream", "churro", "twinkie")  # cone/stick-style bodies


def half_stats(px: np.ndarray) -> dict:
    if len(px) == 0:
        return {}
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    mx, mn = px.max(axis=1), px.min(axis=1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0.0)
    # hue (degrees) for saturation-weighted histogram
    c = np.maximum(mx - mn, 1e-9)
    h = np.zeros(len(px))
    m = mx == r
    h[m] = ((g - b)[m] / c[m]) % 6.0
    m = mx == g
    h[m] = (b - r)[m] / c[m] + 2.0
    m = mx == b
    h[m] = (r - g)[m] / c[m] + 4.0
    h *= 60.0
    hist, _ = np.histogram(h, bins=12, range=(0, 360), weights=sat)
    hist = hist / max(hist.sum(), 1e-9)
    brand = {}
    for name, (br, bg_, bb) in BRAND.items():
        d = np.sqrt((r - br) ** 2 + (g - bg_) ** 2 + (b - bb) ** 2)
        brand[name] = float((d < 60.0).mean())
    return {
        "L": round(float(y.mean()), 1),
        "S": round(float(sat.mean()), 3),
        "temp": round(float((r - b).mean()), 1),
        "hue_hist": [round(float(x), 4) for x in hist],
        "brand": {k: round(v, 4) for k, v in brand.items()},
        "n_px": int(len(px)),
    }


def main():
    out = []
    for fn in sorted(os.listdir(CHAR_DIR)):
        if not fn.endswith(".png"):
            continue
        rgba = np.asarray(Image.open(os.path.join(CHAR_DIR, fn))
                          .convert("RGBA"), dtype=np.float64)
        opq = rgba[..., 3] >= ALPHA_OPAQUE
        if not opq.any():
            continue
        rows = np.where(opq.any(axis=1))[0]
        top_row, bot_row = rows.min(), rows.max()
        mid = (top_row + bot_row + 1) // 2
        top_px = rgba[..., :3][np.where(opq[:mid])[0] + 0, :][...] \
            if False else rgba[:mid][opq[:mid]][:, :3]
        bot_px = rgba[mid:][opq[mid:]][:, :3]
        rec = {
            "file": fn,
            "is_cone_style": any(h in fn.lower() for h in ICE_HINTS),
            "bbox_rows": [int(top_row), int(bot_row)],
            "top": half_stats(top_px),
            "bottom": half_stats(bot_px),
        }
        out.append(rec)

    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)

    def fmt_half(h):
        hh = np.array(h["hue_hist"])
        topbands = ",".join(f"{BANDS[i]}{100*hh[i]:.0f}" for i in
                            np.argsort(-hh)[:2])
        bb = max(h["brand"], key=h["brand"].get)
        bv = h["brand"][bb]
        brand_s = f"{bb}{100*bv:.0f}%" if bv > 0.10 else "-"
        return (f"L{h['L']:6.1f} S{h['S']:.2f} t{h['temp']:+6.1f} "
                f"[{topbands:<12}] {brand_s:<10}")

    print(f"{'character':<46} {'half':<7} stats  "
          f"[top hue bands %]  brand>10%")
    for r in out:
        tag = " *ICE*" if r["is_cone_style"] else ""
        print(f"{r['file'][:45]:<46} TOP    {fmt_half(r['top'])}{tag}")
        print(f"{'':<46} BOTTOM {fmt_half(r['bottom'])}")

    # aggregates
    def agg(recs, key):
        n = sum(r[key]["n_px"] for r in recs)
        L = sum(r[key]["L"] * r[key]["n_px"] for r in recs) / n
        S = sum(r[key]["S"] * r[key]["n_px"] for r in recs) / n
        T = sum(r[key]["temp"] * r[key]["n_px"] for r in recs) / n
        hh = np.sum([np.array(r[key]["hue_hist"]) * r[key]["n_px"]
                     for r in recs], axis=0)
        hh = hh / hh.sum()
        return L, S, T, hh

    for label, group in (("CONE-STYLE (ice cream/churro/twinkie)",
                          [r for r in out if r["is_cone_style"]]),
                         ("ALL OTHER BODIES",
                          [r for r in out if not r["is_cone_style"]])):
        print(f"\n=== {label}: {len(group)} files ===")
        for key in ("top", "bottom"):
            L, S, T, hh = agg(group, key)
            bands = " ".join(f"{BANDS[i]}:{100*v:.0f}%"
                             for i, v in enumerate(hh) if v > 0.05)
            print(f"  {key.upper():<7} L={L:6.1f} S={S:.2f} temp={T:+6.1f}  "
                  f"{bands}")


if __name__ == "__main__":
    main()
