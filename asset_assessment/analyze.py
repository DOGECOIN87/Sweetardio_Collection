#!/usr/bin/env python3
"""Phase 1 asset assessment for the Sweetardio collection.

Measures, for every image in traits/ (opaque pixels only for RGBA layers):
  - mean luminance (Rec.709, 0-255), luminance std (busyness)
  - mean HSV saturation (0-1)
  - temperature  = mean(R - B)            (>0 warm, <0 cool)
  - pink bias    = mean((R + B)/2 - G)    (>0 pink/magenta, <0 green)
  - edge density = mean |gradient| of luma on a 512px copy (supplementary
    busyness measure, separates "detailed" from merely "high contrast")
  - 5-colour k-means dominant colours (deterministic, seeded)
  - fraction of opaque pixels within RGB distance 60 of each brand colour
  - saturation-weighted hue histogram (12 x 30-degree bins)

Writes asset_assessment/metrics.csv + metrics.json and prints a per-folder
summary. Purely read-only: never modifies any asset.

Usage: python3 asset_assessment/analyze.py   (from the repo root)
"""

import json
import os
import sys

import numpy as np
from PIL import Image

TRAITS_DIR = "traits"
OUT_DIR = "asset_assessment"
ALPHA_OPAQUE = 128          # pixels with alpha >= this count as opaque
KMEANS_K = 5
KMEANS_SAMPLES = 60_000
SEED = 42

BRAND = {
    "oxford_blue_070F34": (0x07, 0x0F, 0x34),
    "zaffre_0313A6": (0x03, 0x13, 0xA6),
    "dark_violet_9201CB": (0x92, 0x01, 0xCB),
    "hollywood_cerise_F715AB": (0xF7, 0x15, 0xAB),
    "fluor_cyan_34EDF3": (0x34, 0xED, 0xF3),
}
BRAND_DIST = 60.0  # RGB euclidean radius counted as "this brand colour"


def kmeans(pixels: np.ndarray, k: int, rng: np.random.Generator, iters: int = 25):
    """Tiny deterministic k-means (k-means++ init) on float RGB pixels."""
    n = len(pixels)
    if n == 0:
        return np.zeros((0, 3)), np.zeros(0)
    if n > KMEANS_SAMPLES:
        pixels = pixels[rng.choice(n, KMEANS_SAMPLES, replace=False)]
        n = len(pixels)
    k = min(k, n)
    # k-means++ init
    centers = [pixels[rng.integers(n)]]
    for _ in range(k - 1):
        d2 = np.min([np.sum((pixels - c) ** 2, axis=1) for c in centers], axis=0)
        probs = d2 / max(d2.sum(), 1e-9)
        centers.append(pixels[rng.choice(n, p=probs)])
    centers = np.array(centers, dtype=np.float64)
    for _ in range(iters):
        d = np.linalg.norm(pixels[:, None, :] - centers[None, :, :], axis=2)
        lab = d.argmin(axis=1)
        new = np.array([
            pixels[lab == i].mean(axis=0) if np.any(lab == i) else centers[i]
            for i in range(k)
        ])
        if np.allclose(new, centers, atol=0.5):
            centers = new
            break
        centers = new
    d = np.linalg.norm(pixels[:, None, :] - centers[None, :, :], axis=2)
    lab = d.argmin(axis=1)
    weights = np.bincount(lab, minlength=k) / n
    order = np.argsort(-weights)
    return centers[order], weights[order]


def analyze_image(path: str) -> dict:
    img = Image.open(path)
    mode = img.mode
    w, h = img.size
    rgba = np.asarray(img.convert("RGBA"), dtype=np.float64)
    rgb = rgba[..., :3]
    alpha = rgba[..., 3]
    opaque = alpha >= ALPHA_OPAQUE
    opaque_frac = float(opaque.mean())
    px = rgb[opaque]  # (N, 3) opaque pixels only
    if len(px) == 0:
        return {"file": path, "mode": mode, "w": w, "h": h,
                "opaque_frac": 0.0, "empty": True}

    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    luma_px = 0.2126 * r + 0.7152 * g + 0.0722 * b
    mx = px.max(axis=1)
    mn = px.min(axis=1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0.0)

    # edge density on a 512px luma copy (opaque-masked)
    small = img.convert("RGBA").resize((512, 512), Image.Resampling.BILINEAR)
    srgba = np.asarray(small, dtype=np.float64)
    sluma = 0.2126 * srgba[..., 0] + 0.7152 * srgba[..., 1] + 0.0722 * srgba[..., 2]
    smask = srgba[..., 3] >= ALPHA_OPAQUE
    gy, gx = np.gradient(sluma)
    gmag = np.hypot(gx, gy)
    edge = float(gmag[smask].mean()) if smask.any() else 0.0

    # saturation-weighted hue histogram, 12 bins of 30 degrees
    hsv = np.asarray(img.convert("RGBA").convert("RGB").convert("HSV"),
                     dtype=np.float64)
    hue = hsv[..., 0][opaque] * 360.0 / 255.0
    wgt = sat  # weight hue by saturation so greys don't vote
    hist, _ = np.histogram(hue, bins=12, range=(0, 360), weights=wgt)
    hist = hist / max(hist.sum(), 1e-9)

    rng = np.random.default_rng(SEED)
    centers, weights = kmeans(px, KMEANS_K, rng)

    brand_fracs = {}
    for name, (br, bg_, bb) in BRAND.items():
        d = np.sqrt((r - br) ** 2 + (g - bg_) ** 2 + (b - bb) ** 2)
        brand_fracs[name] = float((d < BRAND_DIST).mean())

    return {
        "file": path,
        "mode": mode,
        "w": w,
        "h": h,
        "opaque_frac": round(opaque_frac, 4),
        "L_mean": round(float(luma_px.mean()), 2),
        "L_std": round(float(luma_px.std()), 2),
        "S_mean": round(float(sat.mean()), 4),
        "temp_RmB": round(float((r - b).mean()), 2),
        "pink_bias": round(float(((r + b) / 2 - g).mean()), 2),
        "edge_density": round(edge, 2),
        "dominant": [
            {"rgb": [int(round(c)) for c in centers[i]],
             "hex": "#%02X%02X%02X" % tuple(int(round(c)) for c in centers[i]),
             "w": round(float(weights[i]), 4)}
            for i in range(len(centers))
        ],
        "brand_fracs": {k: round(v, 4) for k, v in brand_fracs.items()},
        "hue_hist": [round(float(x), 4) for x in hist],
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    records = []
    for folder in sorted(os.listdir(TRAITS_DIR)):
        fpath = os.path.join(TRAITS_DIR, folder)
        if not os.path.isdir(fpath):
            continue
        for fn in sorted(os.listdir(fpath)):
            if not fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue
            p = os.path.join(fpath, fn)
            try:
                rec = analyze_image(p)
                rec["folder"] = folder
                records.append(rec)
                print(f"  analyzed {p}", file=sys.stderr)
            except Exception as e:
                print(f"  ERROR {p}: {e}", file=sys.stderr)

    with open(os.path.join(OUT_DIR, "metrics.json"), "w") as f:
        json.dump(records, f, indent=1)

    # CSV
    cols = ["folder", "file", "mode", "w", "h", "opaque_frac", "L_mean",
            "L_std", "S_mean", "temp_RmB", "pink_bias", "edge_density"]
    with open(os.path.join(OUT_DIR, "metrics.csv"), "w") as f:
        f.write(",".join(cols + list(BRAND) + ["dom1", "dom2", "dom3"]) + "\n")
        for rec in records:
            if rec.get("empty"):
                continue
            row = [str(rec.get(c, "")) for c in cols]
            row += [str(rec["brand_fracs"][k]) for k in BRAND]
            row += [rec["dominant"][i]["hex"] if i < len(rec["dominant"]) else ""
                    for i in range(3)]
            f.write(",".join(row) + "\n")

    # ---- per-folder summary ----
    print("\n================ PER-FOLDER SUMMARY ================")
    hdr = (f"{'folder':<18}{'n':>4}{'opaque%':>9}{'L':>8}{'Lstd':>8}"
           f"{'S':>8}{'temp':>8}{'pink':>8}{'edge':>7}")
    print(hdr)
    by_folder = {}
    for rec in records:
        if rec.get("empty"):
            continue
        by_folder.setdefault(rec["folder"], []).append(rec)
    for folder, recs in sorted(by_folder.items()):
        n = len(recs)
        m = lambda k: np.mean([r[k] for r in recs])
        print(f"{folder:<18}{n:>4}{100*m('opaque_frac'):>8.1f}%"
              f"{m('L_mean'):>8.1f}{m('L_std'):>8.1f}{m('S_mean'):>8.3f}"
              f"{m('temp_RmB'):>8.1f}{m('pink_bias'):>8.1f}"
              f"{m('edge_density'):>7.1f}")

    # aggregate brand fractions for the foreground vs background groups
    print("\n=== brand-colour pixel share (mean over folder) ===")
    for folder, recs in sorted(by_folder.items()):
        fr = {k: np.mean([r["brand_fracs"][k] for r in recs]) for k in BRAND}
        tops = "  ".join(f"{k.split('_')[0]}:{100*v:.1f}%" for k, v in fr.items())
        print(f"{folder:<18}{tops}")

    # aggregate hue histograms
    print("\n=== saturation-weighted hue share by 30-degree bin ===")
    bins = ["0-30 R", "30-60 O", "60-90 Y", "90-120 YG", "120-150 G",
            "150-180 GC", "180-210 C", "210-240 CB", "240-270 B",
            "270-300 V", "300-330 M", "330-360 P"]
    print(f"{'folder':<18}" + "".join(f"{b.split()[1]:>6}" for b in bins))
    for folder, recs in sorted(by_folder.items()):
        hh = np.mean([r["hue_hist"] for r in recs], axis=0)
        print(f"{folder:<18}" + "".join(f"{100*v:>5.1f}%" for v in hh))


if __name__ == "__main__":
    main()
