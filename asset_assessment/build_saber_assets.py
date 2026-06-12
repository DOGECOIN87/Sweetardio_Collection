#!/usr/bin/env python3
"""Rebuild the lightsaber armz traits from scratch (owner reference 2026-06).

Target look (owner's mockup): the collection's gloved fists hold a
realistic chrome/black hilt, and the blade is a THIN laser beam — a
white-hot core inside a saturated palette body with a strong neon bloom —
instead of the original fat cartoon blade.

For each of the three saber files the script:
  1. fits each saber's axis from the original blade footprint (PCA) and
     finds the emitter point + the old hilt's span along the axis
  2. cuts the gloved fist (plus its keylines) out of the original art
  3. draws an analytic hilt in (u,v) axis space: black emitter shroud,
     clamp ring with side lever, chrome barrel with dots + control box,
     black mid band, longitudinally-ridged grip, chrome pommel — outlined
     near-black then Fluorescent Cyan, matching the collection keyline
  4. draws the beam as distance-to-ray fields: white core, palette body,
     deep rim, then a 3-radius gaussian bloom at full luminance
  5. stacks beam -> hilt -> glove and writes the trait

Palette: Zaffre #0313A6, Hollywood Cerise #F715AB, Fluor. Cyan #34EDF3.

Usage:
  python3 asset_assessment/build_saber_assets.py          # /tmp previews
  python3 asset_assessment/build_saber_assets.py --apply  # traits/armz
"""

import os
import sys

import numpy as np
from PIL import Image, ImageFilter

ARMZ = "traits/armz"
BACKUP = "traits/armz_originals"
CANVAS = 1393
CYAN_KEY = (0x34, 0xED, 0xF3)

SABERS = {
    "Sweetardio_114 (4).png": (0x03, 0x13, 0xA6),   # Zaffre
    "Sweetardio_114 (5).png": (0xF7, 0x15, 0xAB),   # Hollywood Cerise
    "Sweetardio_114 (6).png": (0x34, 0xED, 0xF3),   # Fluorescent Cyan
}

# ---- beam profile (px, at 1393 canvas) --------------------------------
CORE_W = 4.5        # white-hot core half-width
BODY_W = 10.0       # saturated palette body half-width
RIM_W = 13.5        # deep rim half-width (then bloom takes over)
BLOOM = [(7, 0.85), (18, 0.50), (42, 0.28)]   # (sigma, opacity)

# ---- hilt dimensions along u (0 = emitter tip -> pommel) --------------
HILT_LEN = 360.0
HILT_W = 92.0       # main barrel full width


def src(fname):
    p = os.path.join(BACKUP, fname)
    return Image.open(p if os.path.exists(p)
                      else os.path.join(ARMZ, fname)).convert("RGBA")


# ======================= geometry from the original ====================

def blade_footprint(arr):
    """Colored blade pixels (the fat cartoon blade), keylines eroded."""
    alpha = arr[:, :, 3].astype(np.float32)
    rgb = arr[:, :, :3].astype(np.float32)
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    colored = (alpha > 128) & (sat > 0.35) & (mx > 60)
    m = Image.fromarray((colored * 255).astype(np.uint8), "L")
    m = m.filter(ImageFilter.MinFilter(5))
    m = m.filter(ImageFilter.MaxFilter(25)).filter(ImageFilter.MinFilter(25))
    return (np.array(m) > 128) & (alpha > 128)


def glove_mask(arr):
    """Big white fist blobs + their black/cyan keylines."""
    alpha = arr[:, :, 3]
    white = (alpha > 200) & (arr[:, :, :3].min(axis=2) > 150)
    m = Image.fromarray((white * 255).astype(np.uint8), "L")
    # opening kills the blade's 18px white stripe + hilt highlights, the
    # fat fingers survive
    m = m.filter(ImageFilter.MinFilter(21)).filter(ImageFilter.MaxFilter(21))
    # reach over the fist's keylines
    m = m.filter(ImageFilter.MaxFilter(15))
    return (np.array(m) > 128) & (alpha > 4)


def saber_geometry(arr, half):
    """Per saber half: emitter point E (beam origin) + outward direction."""
    blade = blade_footprint(arr) & half
    ys, xs = np.where(blade)
    pts = np.stack([xs, ys], axis=1).astype(np.float64)
    c = pts.mean(axis=0)
    cov = np.cov((pts - c).T)
    evals, evecs = np.linalg.eigh(cov)
    d = evecs[:, np.argmax(evals)]          # blade axis
    # outward = away from canvas center
    if np.dot(c - np.array([CANVAS / 2, CANVAS / 2]), d) < 0:
        d = -d
    proj = (pts - c) @ d
    inner = c + d * np.percentile(proj, 0.5)   # where the blade emerged
    return inner, d


# ============================ painting =================================

def axis_fields(E, d, ss):
    """Along-axis s (outward from E) and signed perpendicular v, at
    supersample factor ss."""
    n = CANVAS * ss
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    px = xx / ss - E[0]
    py = yy / ss - E[1]
    s = px * d[0] + py * d[1]
    v = -px * d[1] + py * d[0]
    return s, v


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def draw_beam(E, d, pal):
    """Thin neon beam: white core -> palette body -> rim, then bloom."""
    s, v = axis_fields(E, d, 1)
    # round start cap tucked 6px inside the hilt tip
    deff = np.sqrt(v ** 2 + np.minimum(s + 6, 0) ** 2)

    lift = np.array(pal, np.float32)
    lift = lift / lift.max() * 255.0        # full-luminance palette
    deep = lift * 0.62
    white = np.array([255, 255, 255], np.float32)

    rgb = np.zeros((CANVAS, CANVAS, 3), np.float32)
    a = np.zeros((CANVAS, CANVAS), np.float32)

    body_a = 1 - smoothstep(RIM_W - 2.0, RIM_W, deff)
    t_body = smoothstep(CORE_W, BODY_W, deff)        # 0 core -> 1 rim
    col = white[None, None] * (1 - t_body[..., None]) \
        + (lift * (1 - t_body[..., None] * 0) + 0)[None, None] * 0
    # explicit three-stop ramp: white -> lift -> deep
    t2 = smoothstep(BODY_W, RIM_W, deff)
    col = (white[None, None] * (1 - t_body[..., None])
           + lift[None, None] * t_body[..., None])
    col = col * (1 - t2[..., None]) + deep[None, None] * t2[..., None]

    rgb = col * body_a[..., None]
    a = body_a * 255.0

    # bloom: gaussian falloff of distance, tinted full-luminance
    bloom_a = np.zeros_like(a)
    for sigma, op in BLOOM:
        bloom_a = np.maximum(bloom_a,
                             np.exp(-0.5 * (deff / sigma) ** 2) * op * 255)
    bloom_rgb = np.broadcast_to(lift, (CANVAS, CANVAS, 3))

    out_a = np.maximum(a, bloom_a)
    w = np.where(out_a > 0, a / np.maximum(out_a, 1e-3), 0)[..., None]
    out_rgb = rgb * w + bloom_rgb * (1 - w) * (bloom_a[..., None] / 255.0) \
        / np.maximum(out_a[..., None] / 255.0, 1e-3)
    out = np.concatenate([np.clip(out_rgb, 0, 255),
                          np.clip(out_a, 0, 255)[..., None]], axis=2)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def draw_hilt(E, d, ss=2):
    """Analytic chrome/black hilt along the axis, emitter tip at E."""
    s, v = axis_fields(E, d, ss)
    u = -s                       # u grows from emitter tip toward pommel
    n = CANVAS * ss

    base = np.zeros((n, n, 3), np.float32)
    inside = np.zeros((n, n), np.float32)

    def cyl(shade_w):
        """Cylinder shading across v for a section of half-width shade_w."""
        x = np.clip(np.abs(v) / shade_w, 0, 1)
        lam = 0.45 + 0.62 * np.sqrt(np.maximum(0, 1 - x ** 2))
        spec = np.exp(-0.5 * ((v + shade_w * 0.34) / (shade_w * 0.16)) ** 2)
        return np.clip(lam + spec * 0.5, 0, 1.35)

    # (u0, u1, half_width, base RGB, is_chrome)
    sections = [
        (0,   16,  26, (24, 24, 28), False),     # emitter shroud nub
        (16,  42,  40, (38, 38, 44), False),     # clamp ring
        (42,  158, 46, (188, 192, 200), True),   # chrome barrel
        (158, 204, 52, (30, 30, 36), False),     # mid band / activation
        (204, 336, 48, (52, 52, 58), False),     # grip (ridged below)
        (336, 360, 44, (180, 184, 192), True),   # pommel cap
    ]
    for u0, u1, hw, col, chrome in sections:
        m = (u >= u0) & (u < u1) & (np.abs(v) <= hw)
        sh = cyl(hw)
        c = np.array(col, np.float32)
        col_field = c[None, None] * sh[..., None]
        if not chrome:
            col_field = c[None, None] * (0.55 + 0.45 * sh[..., None])
        base = np.where(m[..., None], col_field, base)
        inside = np.maximum(inside, m.astype(np.float32))

    # clamp side lever (small nub on one side of the clamp ring)
    lever = (u >= 18) & (u < 40) & (v > 38) & (v < 56)
    base = np.where(lever[..., None],
                    np.array([30, 30, 36], np.float32)[None, None] *
                    (0.6 + 0.4 * cyl(56)[..., None]), base)
    inside = np.maximum(inside, lever.astype(np.float32))

    # chrome barrel details: 3 dark dots + small side control box
    for du in (70, 100, 130):
        dot = ((u - du) ** 2 + (v + 12) ** 2) < 7 ** 2
        base = np.where(dot[..., None],
                        np.array([40, 40, 46], np.float32)[None, None], base)
    box = (u >= 120) & (u < 152) & (v > 24) & (v < 44)
    base = np.where(box[..., None],
                    np.array([34, 34, 40], np.float32)[None, None] *
                    (0.7 + 0.3 * cyl(44)[..., None]), base)
    inside = np.maximum(inside, box.astype(np.float32))

    # grip ridges: longitudinal chrome strips over the dark grip
    grip = (u >= 208) & (u < 332)
    ridge = grip & (np.abs((np.abs(v) % 16) - 8) < 3.4) & (np.abs(v) <= 44)
    base = np.where(ridge[..., None],
                    np.array([168, 172, 180], np.float32)[None, None] *
                    cyl(48)[..., None], base)

    # outline: near-black 3px, then cyan keyline 2.5px (collection style)
    ins = Image.fromarray((inside * 255).astype(np.uint8), "L")
    grow1 = np.array(ins.filter(ImageFilter.MaxFilter(7)),
                     np.float32) / 255 > 0.5
    grow2 = np.array(ins.filter(ImageFilter.MaxFilter(13)),
                     np.float32) / 255 > 0.5
    dark_line = grow1 & (inside < 0.5)
    cyan_line = grow2 & ~grow1
    base = np.where(dark_line[..., None],
                    np.array([10, 12, 20], np.float32)[None, None], base)
    base = np.where(cyan_line[..., None],
                    np.array(CYAN_KEY, np.float32)[None, None], base)
    alpha = (inside > 0.5) | dark_line | cyan_line

    out = np.concatenate([np.clip(base, 0, 255),
                          (alpha * 255)[..., None]], axis=2)
    img = Image.fromarray(out.astype(np.uint8), "RGBA")
    return img.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS)


# ============================ assembly =================================

def build_file(fname, pal):
    im = src(fname)
    arr = np.array(im)
    yy, xx = np.mgrid[0:CANVAS, 0:CANVAS]
    halves = [(xx + yy) >= CANVAS, (xx + yy) < CANVAS]   # B upper-right, A lower-left

    glove = glove_mask(arr)
    glove_img = Image.fromarray(
        np.where(glove[..., None], arr, 0).astype(np.uint8), "RGBA")

    out = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    hilts = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    for half in halves:
        E, d = saber_geometry(arr, half)
        out.alpha_composite(draw_beam(E, d, pal))
        hilts.alpha_composite(draw_hilt(E, d))
    out.alpha_composite(hilts)
    out.alpha_composite(glove_img)
    return out


def main():
    apply_mode = "--apply" in sys.argv
    os.makedirs("/tmp/saber_build", exist_ok=True)
    for fname, pal in SABERS.items():
        img = build_file(fname, pal)
        if apply_mode:
            img.save(os.path.join(ARMZ, fname))
            print("wrote", os.path.join(ARMZ, fname))
        else:
            p = os.path.join("/tmp/saber_build", fname)
            img.save(p)
            print("wrote", p)


if __name__ == "__main__":
    main()
