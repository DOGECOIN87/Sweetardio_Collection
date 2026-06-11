#!/usr/bin/env python3
"""Adaptive per-plate background grading engine for Sweetardio.

Direction (derived from asset_assessment/ASSESSMENT.md): the character bodies
measure WARM (temp R-B = +62.3), saturated (S = 0.629) and mid-bright
(L 54..206), with 80 % of their saturated mass in the 0-60 degree hue band.
The stage therefore goes COOL / DESATURATED / MID-KEY, and stays out of the
bodies' red-orange band.

Every operation is a deterministic, parameter-logged tone/colour transform of
the existing plate - no generation, no repainting. Originals are never
modified; output goes to traits/backgroundz_pop/. Alpha is preserved bit-for-
bit. All parameters are continuous functions of each plate's measured
L / S / busyness / temperature:

  1. mid-key power curve toward L* = 130  (midpoint of darkest body 54 and
     brightest body 206), partial strength, luma-ratio applied (hue-safe)
  2. gentle smoothstep S-curve, reduced on busy / already-contrasty plates
  3. desaturation toward mean S 0.30 (~half of body 0.63) with a floor,
     plus an extra squeeze inside the bodies' 0-60 degree hue band
  4. cool split-tone (shadows -> slate-navy, highlights -> pale cyan),
     amount = smoothstep of plate temperature: warm plates get the most
  5. depth blur + local-contrast reduction, gated to busy plates only
  6. cool-navy tinted vignette + slight bloom (skipped, like all spatial
     ops, for the one overlay asset that lives in the plates folder)

Usage (from repo root):
  python3 background_pop_studies/grade.py                 # full batch
  python3 background_pop_studies/grade.py --only 11317 "114 (10)"
  python3 background_pop_studies/grade.py --src traits/backgroundz \
          --dst traits/backgroundz_pop
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

# ---------------------------------------------------------------- constants
SRC_DEFAULT = "traits/backgroundz"
DST_DEFAULT = "traits/backgroundz_pop"
LOG_PATH = "background_pop_studies/ULTIMATE_GRADE_LOG.md"
ALPHA_OPAQUE = 128

# ---- targets derived from Phase 1 measurements (see ASSESSMENT.md) ----
L_TARGET = 130.0 / 255.0   # midpoint(darkest body 54.2, brightest body 206.4)
S_TARGET = 0.30            # ~half of measured body mean S 0.629
MIDKEY_STRENGTH = 0.55     # partial normalization (log-space lerp toward 1)
P_CLAMP = (0.55, 1.30)     # power-curve exponent clamp (no plate flattened)
SCURVE_BASE = 0.32         # base smoothstep blend
SAT_FLOOR = 0.45           # never desaturate below 45 % of original chroma
BODYBAND_SQUEEZE = 0.18    # extra desat inside hue 0-60 deg (feather 15 deg)
SPLIT_MAX_SH = 0.16        # max shadow tint blend (warmest plate)
SPLIT_MAX_HL = 0.10        # max highlight tint blend
TEMP_COOL, TEMP_WARM = -60.0, 45.0   # temp range mapped 0..1 for split-tone
SHADOW_TINT = np.array([0.07, 0.13, 0.27])   # muted Oxford-blue slate
HILITE_TINT = np.array([0.82, 0.90, 0.98])   # pale cool cyan
EDGE_BUSY0, EDGE_BUSY1 = 11.0, 20.0  # edge-density ramp for the busy gate
LC_MAX = 0.35              # max local-contrast (detail) reduction
VIG_BASE, VIG_SPAN = 0.10, 0.08
VIG_TINT = np.array([0.05, 0.09, 0.20])      # deep navy vignette tint
BLOOM_AMT = 0.10
OVERLAY_OPAQUE_FRAC = 0.5  # below this -> treat as overlay: tone ops only


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def sstep(a, b, x):
    return smoothstep((x - a) / (b - a))


def _box1d(a: np.ndarray, r: int, axis: int) -> np.ndarray:
    """Mean filter of width 2r+1 along axis, edge-padded, via cumsum."""
    if r < 1:
        return a
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r + 1, r)
    ap = np.pad(a, pad, mode="edge")
    c = np.cumsum(ap, axis=axis)
    n = a.shape[axis]
    lo = [slice(None)] * 2
    hi = [slice(None)] * 2
    hi[axis] = slice(2 * r + 1, 2 * r + 1 + n)
    lo[axis] = slice(0, n)
    return (c[tuple(hi)] - c[tuple(lo)]) / (2 * r + 1)


def _boxes_for_gauss(sigma: float, n: int = 3):
    """Box widths whose n-fold iteration approximates a gaussian (Kuckir)."""
    w_ideal = np.sqrt((12.0 * sigma * sigma / n) + 1.0)
    wl = int(np.floor(w_ideal))
    if wl % 2 == 0:
        wl -= 1
    wu = wl + 2
    m_ideal = ((12.0 * sigma * sigma - n * wl * wl - 4.0 * n * wl - 3.0 * n)
               / (-4.0 * wl - 4.0))
    m = int(round(m_ideal))
    return [wl if i < m else wu for i in range(n)]


def gauss_f(channel: np.ndarray, sigma: float) -> np.ndarray:
    """Deterministic gaussian blur (3-pass box approximation) of a float
    channel; sigma in pixels, edge-padded so borders don't darken."""
    if sigma <= 0.05:
        return channel
    out = channel
    for w in _boxes_for_gauss(sigma):
        r = (w - 1) // 2
        if r < 1:
            continue
        out = _box1d(_box1d(out, r, 0), r, 1)
    return out


def gauss_rgb(rgb: np.ndarray, alpha: np.ndarray, radius: float) -> np.ndarray:
    """Alpha-premultiplied gaussian blur (no halo bleed from transparent px)."""
    if radius <= 0.05:
        return rgb
    a = alpha[..., None]
    pre = np.stack([gauss_f(rgb[..., i] * alpha, radius) for i in range(3)],
                   axis=-1)
    ab = gauss_f(alpha, radius)[..., None]
    return np.where(ab > 1e-4, pre / np.maximum(ab, 1e-4), rgb)


def luma(rgb: np.ndarray) -> np.ndarray:
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def hue_deg(rgb: np.ndarray) -> np.ndarray:
    """Per-pixel HSV hue in degrees (vectorized)."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    c = np.maximum(mx - mn, 1e-9)
    h = np.zeros_like(mx)
    m = mx == r
    h[m] = ((g - b)[m] / c[m]) % 6.0
    m = mx == g
    h[m] = (b - r)[m] / c[m] + 2.0
    m = mx == b
    h[m] = (r - g)[m] / c[m] + 4.0
    return h * 60.0


def measure(rgb01: np.ndarray, alpha01: np.ndarray) -> dict:
    """Same metric definitions as asset_assessment/analyze.py."""
    opaque = alpha01 >= (ALPHA_OPAQUE / 255.0)
    if not opaque.any():
        opaque = np.ones_like(alpha01, dtype=bool)
    px = rgb01[opaque] * 255.0
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    mx, mn = px.max(axis=1), px.min(axis=1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0.0)
    # edge density on a 512px luma copy, opaque-masked
    h, w = rgb01.shape[:2]
    im = Image.fromarray(
        (np.dstack([rgb01, alpha01[..., None]]) * 255).astype(np.uint8),
        "RGBA").resize((512, 512), Image.Resampling.BILINEAR)
    s = np.asarray(im, dtype=np.float64)
    sy = 0.2126 * s[..., 0] + 0.7152 * s[..., 1] + 0.0722 * s[..., 2]
    sm = s[..., 3] >= ALPHA_OPAQUE
    gy, gx = np.gradient(sy)
    edge = float(np.hypot(gx, gy)[sm].mean()) if sm.any() else 0.0
    return {
        "L": float(y.mean()), "Lstd": float(y.std()),
        "S": float(sat.mean()),
        "temp": float((r - b).mean()),
        "pink": float(((r + b) / 2 - g).mean()),
        "edge": edge,
        "opaque_frac": float((alpha01 >= ALPHA_OPAQUE / 255.0).mean()),
    }


def derive_params(m: dict, min_side: int) -> dict:
    """All grading parameters as continuous functions of plate measurements."""
    l = np.clip(m["L"] / 255.0, 0.02, 0.95)

    # 1. mid-key exponent: full normalization would be ln(T)/ln(l);
    #    soften in log space, then clamp.
    p_full = np.log(L_TARGET) / np.log(l)
    p = float(np.clip(p_full ** MIDKEY_STRENGTH, *P_CLAMP))

    # busyness 0..1 from edge density; existing-contrast 0..1 from L std
    busy = float(sstep(EDGE_BUSY0, EDGE_BUSY1, m["edge"]))
    contr = float(np.clip((m["Lstd"] - 40.0) / 35.0, 0.0, 1.0))

    # 2. S-curve blend, reduced when plate is busy or already contrasty
    c = max(0.05, SCURVE_BASE * (1 - 0.5 * contr) * (1 - 0.5 * busy))

    # 3. global desat factor toward S_TARGET (never resaturates: <= 1)
    f_sat = float(np.clip((S_TARGET / max(m["S"], 1e-3)) ** 0.75,
                          SAT_FLOOR, 1.0))

    # 4. split-tone amount from plate temperature (warm -> max cooling)
    warm_n = float(sstep(0.0, 1.0, (m["temp"] - TEMP_COOL)
                         / (TEMP_WARM - TEMP_COOL)))
    a_sh = SPLIT_MAX_SH * warm_n
    a_hl = SPLIT_MAX_HL * warm_n

    # 5. spatial ops (busy plates only)
    blur_px = busy * (min_side / 200.0)
    lc_cut = LC_MAX * busy

    # 6. vignette strength grows gently with plate brightness
    vig = float(VIG_BASE + VIG_SPAN * sstep(0.15, 0.60, l))

    is_overlay = m["opaque_frac"] < OVERLAY_OPAQUE_FRAC
    return {"p": p, "c": c, "f_sat": f_sat, "warm_n": warm_n,
            "a_sh": a_sh, "a_hl": a_hl, "busy": busy, "blur_px": blur_px,
            "lc_cut": lc_cut, "vig": vig, "bloom": BLOOM_AMT,
            "is_overlay": is_overlay}


def grade_plate(img: Image.Image, m: dict, prm: dict) -> Image.Image:
    rgba = np.asarray(img.convert("RGBA"), dtype=np.float64) / 255.0
    rgb = rgba[..., :3].copy()
    alpha = rgba[..., 3]
    h, w = rgb.shape[:2]

    # ---- 1. mid-key power curve (luma-ratio, hue-safe) ----
    y = np.clip(luma(rgb), 1e-6, 1.0)
    y2 = y ** prm["p"]
    rgb *= (y2 / y)[..., None]

    # ---- 2. smoothstep S-curve on luma ----
    y = np.clip(luma(rgb), 1e-6, 1.0)
    y2 = (1 - prm["c"]) * y + prm["c"] * smoothstep(y)
    rgb *= (y2 / y)[..., None]
    rgb = np.clip(rgb, 0.0, 1.2)

    # ---- 3. desaturation: global factor + body-hue-band squeeze ----
    y = luma(rgb)[..., None]
    hue = hue_deg(np.clip(rgb, 0, 1))
    band = np.minimum(sstep(-15.0, 15.0, hue), 1 - sstep(60.0, 90.0, hue))
    band = np.maximum(band, sstep(345.0, 360.0, hue))  # wrap below 0 deg
    f_px = prm["f_sat"] * (1.0 - BODYBAND_SQUEEZE * band)
    rgb = y + (rgb - y) * f_px[..., None]

    # ---- 4. cool split-tone ----
    yl = np.clip(luma(rgb), 0, 1)
    w_sh = (1.0 - yl) ** 2
    w_hl = sstep(0.55, 0.95, yl)
    rgb += (SHADOW_TINT - rgb) * (prm["a_sh"] * w_sh)[..., None]
    rgb += (HILITE_TINT - rgb) * (prm["a_hl"] * w_hl)[..., None]

    if not prm["is_overlay"]:
        # ---- 5. depth blur + local-contrast reduction (busy gate) ----
        if prm["blur_px"] > 0.05:
            rgb = gauss_rgb(rgb, alpha, prm["blur_px"])
        if prm["lc_cut"] > 0.005:
            y = np.clip(luma(rgb), 1e-6, 1.2)
            y_big = gauss_f(y, min(h, w) / 70.0)
            y2 = y_big + (y - y_big) * (1.0 - prm["lc_cut"])
            rgb *= (np.maximum(y2, 0) / y)[..., None]

        # ---- 7. slight bloom ----
        yl = np.clip(luma(rgb), 0, 1)
        hm = sstep(0.70, 0.95, yl) * alpha
        glow = np.stack(
            [gauss_f(rgb[..., i] * hm, min(h, w) / 55.0) for i in range(3)],
            axis=-1)
        rgb += glow * prm["bloom"]

        # ---- 6. cool-navy tinted vignette ----
        yy, xx = np.mgrid[0:h, 0:w]
        nx = (xx / (w - 1) - 0.5) * 2.0
        ny = (yy / (h - 1) - 0.5) * 2.0
        d = np.sqrt(nx * nx + ny * ny) / np.sqrt(2.0)
        vmask = sstep(0.55, 1.0, d) ** 1.2
        a_v = prm["vig"] * vmask
        rgb = rgb * (1 - a_v[..., None]) + VIG_TINT * (a_v * 0.5)[..., None]

    # filmic soft shoulder, then hard clip
    s = 0.92
    over = rgb > s
    rgb[over] = s + (1 - s) * np.tanh((rgb[over] - s) / (1 - s))
    rgb = np.clip(rgb, 0.0, 1.0)

    out = np.dstack([rgb, alpha[..., None]])
    return Image.fromarray((out * 255.0 + 0.5).astype(np.uint8), "RGBA")


LOG_COLS = ("plate, L, Lstd, S, temp, edge, op%, p_midkey, c_scurve, f_sat, "
            "warm_n, a_sh, a_hl, busy_n, blur_px, lc_cut, vignette, bloom, "
            "overlay, L_out, S_out, temp_out").split(", ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC_DEFAULT)
    ap.add_argument("--dst", default=DST_DEFAULT)
    ap.add_argument("--only", nargs="*", default=None,
                    help="substring filters; grade matching plates only")
    ap.add_argument("--log", default=LOG_PATH)
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(args.src)
                   if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))
    if args.only:
        files = [f for f in files if any(s in f for s in args.only)]
    if not files:
        sys.exit("no plates matched")
    os.makedirs(args.dst, exist_ok=True)

    rows = []
    for fn in files:
        src_path = os.path.join(args.src, fn)
        img = Image.open(src_path)
        rgba = np.asarray(img.convert("RGBA"), dtype=np.float64) / 255.0
        m = measure(rgba[..., :3], rgba[..., 3])
        prm = derive_params(m, min(img.size))
        out = grade_plate(img, m, prm)
        out_name = os.path.splitext(fn)[0] + ".png"
        out.save(os.path.join(args.dst, out_name))

        o = np.asarray(out, dtype=np.float64) / 255.0
        m2 = measure(o[..., :3], o[..., 3])
        rows.append([fn, f"{m['L']:.1f}", f"{m['Lstd']:.1f}", f"{m['S']:.3f}",
                     f"{m['temp']:+.1f}", f"{m['edge']:.1f}",
                     f"{100*m['opaque_frac']:.0f}", f"{prm['p']:.3f}",
                     f"{prm['c']:.3f}", f"{prm['f_sat']:.3f}",
                     f"{prm['warm_n']:.3f}", f"{prm['a_sh']:.3f}",
                     f"{prm['a_hl']:.3f}", f"{prm['busy']:.3f}",
                     f"{prm['blur_px']:.2f}", f"{prm['lc_cut']:.3f}",
                     f"{prm['vig']:.3f}", f"{prm['bloom']:.3f}",
                     "Y" if prm["is_overlay"] else "",
                     f"{m2['L']:.1f}", f"{m2['S']:.3f}", f"{m2['temp']:+.1f}"])
        print(f"graded {fn}: L {m['L']:.0f}->{m2['L']:.0f}  "
              f"S {m['S']:.2f}->{m2['S']:.2f}  temp {m['temp']:+.0f}->"
              f"{m2['temp']:+.0f}  busy {prm['busy']:.2f}")

    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    import numpy as _np
    Lo = _np.array([float(r[1]) for r in rows])
    Ln = _np.array([float(r[-3]) for r in rows])
    So = _np.array([float(r[3]) for r in rows])
    Sn = _np.array([float(r[-2]) for r in rows])
    To = _np.array([float(r[4]) for r in rows])
    Tn = _np.array([float(r[-1]) for r in rows])
    with open(args.log, "w") as f:
        f.write("# ULTIMATE GRADE LOG - Sweetardio background pop\n\n")
        f.write(f"Engine: `background_pop_studies/grade.py` · source "
                f"`{args.src}` -> output `{args.dst}` · {len(rows)} plates\n\n")
        f.write("Targets derived from Phase 1 measurements: mid-key anchor "
                "L* = 130 (midpoint of darkest body 54 / brightest body 206), "
                "stage saturation 0.30 (body mean 0.629), split-tone COOL "
                "(bodies measure +62.3 warm). Every parameter below is a "
                "continuous function of the plate's measured "
                "L/S/busyness/temperature.\n\n")
        f.write("| " + " | ".join(LOG_COLS) + " |\n")
        f.write("|" + "---|" * len(LOG_COLS) + "\n")
        for r in rows:
            f.write("| " + " | ".join(r) + " |\n")
        f.write("\n## Cohesion summary (opaque-pixel means)\n\n")
        f.write("| metric | before (min / mean / max) | after (min / mean / "
                "max) |\n|---|---|---|\n")
        f.write(f"| L | {Lo.min():.0f} / {Lo.mean():.0f} / {Lo.max():.0f} | "
                f"{Ln.min():.0f} / {Ln.mean():.0f} / {Ln.max():.0f} |\n")
        f.write(f"| S | {So.min():.2f} / {So.mean():.2f} / {So.max():.2f} | "
                f"{Sn.min():.2f} / {Sn.mean():.2f} / {Sn.max():.2f} |\n")
        f.write(f"| temp R-B | {To.min():+.0f} / {To.mean():+.0f} / "
                f"{To.max():+.0f} | {Tn.min():+.0f} / {Tn.mean():+.0f} / "
                f"{Tn.max():+.0f} |\n")
        f.write(f"\nL spread (std) {Lo.std():.1f} -> {Ln.std():.1f}; "
                f"S spread {So.std():.2f} -> {Sn.std():.2f}; "
                f"temp spread {To.std():.1f} -> {Tn.std():.1f}.\n")
    print(f"\nlog written to {args.log}")


if __name__ == "__main__":
    main()
