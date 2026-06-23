#!/usr/bin/env python3
"""Audit the 5 skin shades against the brand palette and the measured
collection (read-only; answers "are the skin shades the best possible for
the collection's colors?").

Per skin (opaque pixels, alpha >= 128):
  - identity color = per-channel MEDIAN RGB (robust to shading/highlights),
    plus Rec.709 L, HSV S, saturation-weighted dominant hue (same
    conventions as ASSESSMENT.md / verify_separation.py)
  - CIE76 delta-E (Lab, D65) to each of the 5 brand palette colors
  - pairwise delta-E between skins (redundancy check)
  - at-risk pairings against every graded plate in traits/backgroundz,
    using the exact at_risk() rule from verify_separation.py

Usage (from repo root): python3 asset_assessment/audit_skin_palette.py
"""

import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, "asset_assessment")
from verify_separation import at_risk, plate_stats  # noqa: E402

BRAND = {
    "Oxford_Blue": (0x07, 0x0F, 0x34),
    "Zaffre": (0x03, 0x13, 0xA6),
    "Dark_Violet": (0x92, 0x01, 0xCB),
    "Hollywood_Cerise": (0xF7, 0x15, 0xAB),
    "Fluorescent_Cyan": (0x34, 0xED, 0xF3),
}

SKIN_DIR = "traits/skinz"


def srgb_to_lab(rgb):
    c = np.asarray(rgb, float) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = M @ c
    xyz /= np.array([0.95047, 1.0, 1.08883])  # D65
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz),
                 xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.array([116 * f[1] - 16,
                     500 * (f[0] - f[1]),
                     200 * (f[1] - f[2])])


def de76(rgb_a, rgb_b):
    return float(np.linalg.norm(srgb_to_lab(rgb_a) - srgb_to_lab(rgb_b)))


def skin_stats(path):
    a = np.asarray(Image.open(path).convert("RGBA"), float)
    op = a[..., 3] >= 128
    px = a[..., :3][op]
    med = np.median(px, axis=0)
    L = float((0.2126 * px[:, 0] + 0.7152 * px[:, 1]
               + 0.0722 * px[:, 2]).mean())
    mx, mn = px.max(1), px.min(1)
    S = float(np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0).mean())
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
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0.0)
    hist, _ = np.histogram(h, bins=24, range=(0, 360), weights=sat)
    hue = float((np.argmax(hist) + 0.5) * 15.0)
    return med, L, S, hue


def main():
    skins = {}
    for f in sorted(os.listdir(SKIN_DIR)):
        if f.endswith(".png"):
            name = f.split("Skin_")[1].split(" (")[0].replace(".png", "")
            skins[name] = skin_stats(os.path.join(SKIN_DIR, f))

    print("== skin identity (median RGB / L / S / dominant hue) ==")
    for n, (med, L, S, hue) in skins.items():
        print(f"{n:18s} rgb=({med[0]:3.0f},{med[1]:3.0f},{med[2]:3.0f}) "
              f"#{int(med[0]):02X}{int(med[1]):02X}{int(med[2]):02X}  "
              f"L={L:5.1f} S={S:.2f} hue={hue:5.1f}")

    print("\n== delta-E (CIE76) skin median vs brand palette ==")
    hdr = "".join(f"{b[:12]:>14}" for b in BRAND)
    print(f"{'':18s}{hdr}")
    for n, (med, *_rest) in skins.items():
        row = "".join(f"{de76(med, c):14.1f}" for c in BRAND.values())
        print(f"{n:18s}{row}")

    print("\n== pairwise skin delta-E (redundancy check) ==")
    names = list(skins)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            print(f"{a:18s} vs {b:18s} dE={de76(skins[a][0], skins[b][0]):6.1f}")

    print("\n== at-risk pairings vs graded plates (verify_separation rule) ==")
    plates = [(f, plate_stats(os.path.join("traits/backgroundz", f)))
              for f in sorted(os.listdir("traits/backgroundz"))
              if f.endswith(".png")]
    for n, (_med, L, S, hue) in skins.items():
        risky = [f for f, p in plates if at_risk(L, S, hue, p)]
        names_short = ", ".join(os.path.splitext(r)[0][:24] for r in risky[:4])
        more = f" (+{len(risky) - 4} more)" if len(risky) > 4 else ""
        print(f"{n:18s} {len(risky):2d}/{len(plates)}  {names_short}{more}")

    # the ball always sits ON TOP of the body, so face-vs-body contrast
    # matters more than face-vs-plate: reuse the same rule with each body
    # treated as the "plate" behind the ball
    print("\n== at-risk pairings vs character bodies (ball sits ON body) ==")
    import json
    bodies = []
    for r in json.load(open("asset_assessment/metrics.json")):
        if r.get("folder") != "characterz" or r.get("empty"):
            continue
        hue = (int(np.argmax(r["hue_hist"])) + 0.5) * 30.0
        bodies.append((os.path.basename(r["file"]),
                       {"L": r["L_mean"], "S": r["S_mean"], "hue": hue}))
    for n, (_med, L, S, hue) in skins.items():
        risky = [f for f, p in bodies if at_risk(L, S, hue, p)]
        names_short = ", ".join(
            r.replace("before_skinz_", "").replace("after_skinz_", "")
            .replace("layer-", "").replace(".png", "")[:22]
            for r in risky[:4])
        more = f" (+{len(risky) - 4} more)" if len(risky) > 4 else ""
        print(f"{n:18s} {len(risky):2d}/{len(bodies)}  {names_short}{more}")


if __name__ == "__main__":
    main()
