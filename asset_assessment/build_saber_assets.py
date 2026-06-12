#!/usr/bin/env python3
"""Rebuild the lightsaber armz traits from scratch (owner reference 2026-06).

Target look: the collection's gloved fists hold the owner's real chrome hilt
(traits/saber_parts/vader_hilt.png) and the blade is a THIN laser beam — a
white-hot core inside a saturated palette body with a strong neon bloom.

For each of the three saber files the script:
  1. fits each blade half's axis from the original blade footprint (PCA)
  2. cuts the gloved fist (plus its keylines) from the original art
  3. affine-warps the real chrome hilt PNG to align with the blade axis,
     emitter end at the blade origin, pommel extending inward toward the glove
  4. draws the beam as distance-to-ray fields: white core -> palette body ->
     deep rim, then a 3-radius gaussian bloom at full luminance
  5. stacks beam -> hilt -> glove and writes the trait

Palette: Zaffre #0313A6, Hollywood Cerise #F715AB, Fluor. Cyan #34EDF3.

Usage:
  python3 asset_assessment/build_saber_assets.py          # /tmp previews
  python3 asset_assessment/build_saber_assets.py --apply  # traits/armz
"""

import math
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

ARMZ = "traits/armz"
BACKUP = "traits/armz_originals"
HILT_PNG = "traits/saber_parts/vader_hilt.png"
CANVAS = 1393

SABERS = {
    "Sweetardio_114 (4).png": (0x03, 0x13, 0xA6),   # Zaffre
    "Sweetardio_114 (5).png": (0xF7, 0x15, 0xAB),   # Hollywood Cerise
    "Sweetardio_114 (6).png": (0x34, 0xED, 0xF3),   # Fluorescent Cyan
}

# ---- beam profile (px, at 1393 canvas) -----------------------------------
CORE_W  =  4.5        # white-hot core half-width
BODY_W  = 10.0        # saturated palette body half-width
RIM_W   = 13.5        # deep rim half-width (bloom takes over beyond this)
BLOOM   = [(7, 0.85), (18, 0.50), (42, 0.28)]   # (sigma, opacity)

# ---- hilt placement -------------------------------------------------------
HILT_LEN = 280.0      # desired hilt length in canvas px


def src(fname):
    p = os.path.join(BACKUP, fname)
    return Image.open(p if os.path.exists(p)
                      else os.path.join(ARMZ, fname)).convert("RGBA")


# ======================= hilt PNG helpers ==================================

def _detect_hilt():
    """Return (padded_crop_image, emitter_xy, pommel_xy) in crop coords."""
    im = Image.open(HILT_PNG).convert("RGBA")
    arr = np.array(im)
    alpha = arr[:, :, 3]

    rows_hit = np.any(alpha > 0, axis=1)
    cols_hit = np.any(alpha > 0, axis=0)
    rmin, rmax = np.where(rows_hit)[0][[0, -1]]
    cmin, cmax = np.where(cols_hit)[0][[0, -1]]

    pad = 40
    r0, r1 = max(0, rmin - pad), min(arr.shape[0], rmax + pad + 1)
    c0, c1 = max(0, cmin - pad), min(arr.shape[1], cmax + pad + 1)
    crop = Image.fromarray(arr[r0:r1, c0:c1])

    ca = np.array(crop)[:, :, 3]
    ys, xs = np.where(ca > 50)
    pts = np.stack([xs, ys], axis=1).astype(np.float64)
    cent = pts.mean(axis=0)
    cov = np.cov((pts - cent).T)
    evals, evecs = np.linalg.eigh(cov)
    major = evecs[:, np.argmax(evals)]          # principal direction
    perp  = evecs[:, np.argmin(evals)]

    proj = (pts - cent) @ major
    p_min, p_max = proj.min(), proj.max()

    def perp_width(end_proj, window=35):
        near = np.abs(proj - end_proj) < window
        if near.sum() < 5:
            return 9999.0
        pp = (pts[near] - cent) @ perp
        return float(pp.max() - pp.min())

    w_min = perp_width(p_min)
    w_max = perp_width(p_max)

    end_min_xy = cent + major * p_min
    end_max_xy = cent + major * p_max

    if w_min < w_max:
        emitter, pommel = end_min_xy, end_max_xy
    else:
        emitter, pommel = end_max_xy, end_min_xy

    return crop, np.array(emitter), np.array(pommel)


# cache so we only load once
_HILT_CACHE = None

def hilt_parts():
    global _HILT_CACHE
    if _HILT_CACHE is None:
        _HILT_CACHE = _detect_hilt()
    return _HILT_CACHE


def place_hilt(tgt_emitter, tgt_blade_dir, flip_perp=False):
    """Return a (CANVAS x CANVAS) RGBA with the hilt positioned.

    tgt_emitter  – (x, y) canvas coords where the emitter tip lands
    tgt_blade_dir – unit vector pointing outward along the blade
    flip_perp    – mirror the hilt across its own long axis first
                   (use for the second blade to create a symmetric look)
    """
    crop, src_e, src_p = hilt_parts()
    if flip_perp:
        crop = crop.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        h_crop = crop.size[1]
        src_e = np.array([src_e[0], h_crop - 1 - src_e[1]])
        src_p = np.array([src_p[0], h_crop - 1 - src_p[1]])

    h_ep  = src_p - src_e
    h_len = np.linalg.norm(h_ep)
    h_ep_dir = h_ep / h_len

    # Hilt emitter-to-pommel must point opposite to blade
    tgt_ep = -np.array(tgt_blade_dir, dtype=np.float64)
    tgt_ep /= np.linalg.norm(tgt_ep)

    angle_h = math.atan2(h_ep_dir[1], h_ep_dir[0])
    angle_t = math.atan2(tgt_ep[1],   tgt_ep[0])
    rot     = angle_t - angle_h

    inv_s  = h_len / HILT_LEN   # inverse scale (src px per canvas px)
    cos_r  = math.cos(rot)
    sin_r  = math.sin(rot)

    # PIL AFFINE: (x_src, y_src) = M @ (x_dst, y_dst, 1)
    # Forward:  p_dst = (HILT_LEN/h_len) * R @ (p_src - src_e) + tgt_e
    # Inverse:  p_src = inv_s * R^T @ (p_dst - tgt_e) + src_e
    ex, ey = float(tgt_emitter[0]), float(tgt_emitter[1])

    a = cos_r  * inv_s
    b = sin_r  * inv_s
    c = src_e[0] - a * ex - b * ey

    d = -sin_r * inv_s
    e =  cos_r * inv_s
    f = src_e[1] - d * ex - e * ey

    return crop.transform(
        (CANVAS, CANVAS),
        Image.Transform.AFFINE,
        (a, b, c, d, e, f),
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )


# ======================= geometry from the original =======================

def blade_footprint(arr):
    alpha = arr[:, :, 3].astype(np.float32)
    rgb   = arr[:, :, :3].astype(np.float32)
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    colored = (alpha > 128) & (sat > 0.35) & (mx > 60)
    m = Image.fromarray((colored * 255).astype(np.uint8), "L")
    m = m.filter(ImageFilter.MinFilter(5))
    m = m.filter(ImageFilter.MaxFilter(25)).filter(ImageFilter.MinFilter(25))
    return (np.array(m) > 128) & (alpha > 128)


def glove_mask(arr):
    alpha = arr[:, :, 3]
    white = (alpha > 200) & (arr[:, :, :3].min(axis=2) > 150)
    m = Image.fromarray((white * 255).astype(np.uint8), "L")
    m = m.filter(ImageFilter.MinFilter(21)).filter(ImageFilter.MaxFilter(21))
    m = m.filter(ImageFilter.MaxFilter(15))
    return (np.array(m) > 128) & (alpha > 4)


def saber_geometry(arr, half):
    blade = blade_footprint(arr) & half
    ys, xs = np.where(blade)
    pts = np.stack([xs, ys], axis=1).astype(np.float64)
    c   = pts.mean(axis=0)
    cov = np.cov((pts - c).T)
    evals, evecs = np.linalg.eigh(cov)
    d = evecs[:, np.argmax(evals)]
    if np.dot(c - np.array([CANVAS / 2, CANVAS / 2]), d) < 0:
        d = -d
    proj  = (pts - c) @ d
    inner = c + d * np.percentile(proj, 0.5)
    return inner, d


# ============================ beam painting ================================

def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def draw_beam(E, d, pal):
    yy, xx = np.mgrid[0:CANVAS, 0:CANVAS].astype(np.float32)
    px = xx - float(E[0])
    py = yy - float(E[1])
    s  = px * float(d[0]) + py * float(d[1])
    v  = -px * float(d[1]) + py * float(d[0])

    # round start cap tucked 6 px inside the hilt tip
    deff = np.sqrt(v ** 2 + np.minimum(s + 6, 0) ** 2)

    lift  = np.array(pal, np.float32)
    lift  = lift / lift.max() * 255.0
    deep  = lift * 0.62
    white = np.array([255, 255, 255], np.float32)

    body_a = 1 - smoothstep(RIM_W - 2.0, RIM_W, deff)
    t_body = smoothstep(CORE_W, BODY_W, deff)
    t2     = smoothstep(BODY_W, RIM_W,  deff)
    col    = (white[None, None] * (1 - t_body[..., None])
              + lift[None,  None] * t_body[..., None])
    col    = col * (1 - t2[..., None]) + deep[None, None] * t2[..., None]

    rgb = col  * body_a[..., None]
    a   = body_a * 255.0

    bloom_a = np.zeros_like(a)
    for sigma, op in BLOOM:
        bloom_a = np.maximum(bloom_a,
                             np.exp(-0.5 * (deff / sigma) ** 2) * op * 255)
    bloom_rgb = np.broadcast_to(lift, (CANVAS, CANVAS, 3))

    out_a = np.maximum(a, bloom_a)
    w_b   = np.where(out_a > 0, a / np.maximum(out_a, 1e-3), 0)[..., None]
    out_rgb = rgb * w_b + bloom_rgb * (1 - w_b) * (bloom_a[..., None] / 255.0) \
              / np.maximum(out_a[..., None] / 255.0, 1e-3)
    out = np.concatenate([np.clip(out_rgb, 0, 255),
                          np.clip(out_a, 0, 255)[..., None]], axis=2)
    return Image.fromarray(out.astype(np.uint8), "RGBA")


# ============================ assembly =====================================

def build_file(fname, pal):
    im  = src(fname)
    arr = np.array(im)
    yy, xx = np.mgrid[0:CANVAS, 0:CANVAS]
    halves = [
        ((xx + yy) >= CANVAS, False),   # upper-right blade, no flip
        ((xx + yy)  < CANVAS, True),    # lower-left  blade, flip hilt
    ]

    glove = glove_mask(arr)
    glove_img = Image.fromarray(
        np.where(glove[..., None], arr, 0).astype(np.uint8), "RGBA")

    beams  = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    hilts  = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    for half_mask, flip in halves:
        E, d = saber_geometry(arr, half_mask)
        beams.alpha_composite(draw_beam(E, d, pal))
        hilts.alpha_composite(place_hilt(E, d, flip_perp=flip))

    out = beams
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
