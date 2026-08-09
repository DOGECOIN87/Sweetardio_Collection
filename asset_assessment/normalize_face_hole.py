#!/usr/bin/env python3
"""Resize a character's face hole to a target width without moving its body.

The cast's holes render between 179 and 260px — the widest face is 1.45x the
narrowest — and the hole is the whole of the visible face now that every body
draws over the skin ball. register_character.py fixes this for NEW art by
scaling the entire asset until its hole matches, but that is no use here: the
bodies are already the size they should be, so the hole has to move on its own.

The transform is a per-angle radial warp about the ball centre:

    for every ray from (690, 601), find the hole's rim radius r_hole,
    remap so that rim lands at the target radius R_t, and taper the
    displacement back to zero by an outer radius R_o.

Three properties make it safe for this pipeline:

  * Beyond R_o nothing moves, so the body's silhouette, its bbox and its
    placement are untouched. R_o is chosen per ray from where the body's
    outer edge actually is, so it can never reach the outline.
  * It is anchored at the ball centre, the one point the compositor pins the
    face to, so the hole stays centred where the eyes and mouth land.
  * Every ray is scaled independently, so an out-of-round hole (a tall
    ellipse, a rounded square) comes out CIRCULAR at the target radius — the
    holes end up the same shape as well as the same size.

The cost is that the art in the annulus between the hole and R_o is stretched
or compressed to make room. Enlarging a hole eats the body art around it;
that is unavoidable, since the face has to come from somewhere. Look at the
result — past about a 1.35x enlargement the surrounding texture visibly
smears.

Sampling is done on premultiplied RGBA so the rim does not pick up a halo
from transparent pixels, which audit_edges.py would flag.

Usage (from repo root):
  python3 asset_assessment/normalize_face_hole.py --target 250 --dry-run
  python3 asset_assessment/normalize_face_hole.py --target 250
  python3 asset_assessment/normalize_face_hole.py Nutty_Bar.png --target 250
  python3 asset_assessment/normalize_face_hole.py --target 250 --out-dir /tmp/x

--target is in RENDERED pixels: the per-character CHAR_SCALE is divided out,
because what has to match is what the viewer sees, not what is in the file.
Pass --file-space to target file pixels instead.
"""

import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")
import generator as g  # noqa: E402

BACKUP_DIR = "characterz_originals"
N_ANGLES = 720          # rays; 0.5 deg is finer than the rim's own steps
ALPHA_SOLID = 50        # alpha above this counts as body
EDGE_MARGIN = 0.90      # keep R_o this far inside the body's outer edge


def load(path):
    im = Image.open(path).convert("RGBA")
    if im.size != (g.CANVAS_SIZE, g.CANVAS_SIZE):
        im = im.resize((g.CANVAS_SIZE,) * 2, Image.Resampling.LANCZOS)
    return im


def hole_mask(alpha):
    """The enclosed transparent component nearest the ball centre."""
    solid = alpha > ALPHA_SOLID
    holes = ndimage.binary_fill_holes(solid) & ~solid
    lab, n = ndimage.label(holes)
    bx, by = g.CHAR_SCALE_PIVOT
    best, pick = None, None
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if len(ys) < 6000:
            continue
        d = (xs.mean() - bx) ** 2 + (ys.mean() - by) ** 2
        if best is None or d < best:
            best, pick = d, (lab == i)
    return pick, solid


def ray_radii(hole, solid, angles, max_r):
    """Per-angle (hole rim radius, body outer-edge radius)."""
    bx, by = g.CHAR_SCALE_PIVOT
    rs = np.arange(0, max_r, 0.5)
    # sample both masks along every ray at once
    xs = bx + np.cos(angles)[:, None] * rs[None, :]
    ys = by + np.sin(angles)[:, None] * rs[None, :]
    h = ndimage.map_coordinates(hole.astype(np.float32), [ys, xs],
                                order=1, mode="constant", cval=0) > 0.5
    s = ndimage.map_coordinates(solid.astype(np.float32), [ys, xs],
                                order=1, mode="constant", cval=0) > 0.5
    r_hole = np.zeros(len(angles))
    r_edge = np.zeros(len(angles))
    for i in range(len(angles)):
        hi = np.nonzero(h[i])[0]
        r_hole[i] = rs[hi[-1]] if len(hi) else 0.0
        # first radius past the rim where the body stops being solid
        start = int(hi[-1]) + 1 if len(hi) else 0
        gap = np.nonzero(~s[i][start:])[0]
        r_edge[i] = rs[start + gap[0]] if len(gap) else rs[-1]

    # Smooth both radii CIRCULARLY before they are used as a warp field.
    # Without this the field is discontinuous at the cardinal angles: a ray
    # travelling exactly along a pixel row samples the rim mask exactly,
    # while a diagonal ray samples it interpolated, so r_hole jumps by up to
    # half a pixel at 0/90/180/270 deg — and a half-pixel step in a
    # displacement field shows up as a hairline crack radiating out of the
    # hole. A circular median kills the isolated spikes, then a short box
    # blur takes the remaining stair-steps out. Both wrap, so there is no
    # seam at theta=0 either.
    r_hole = ndimage.median_filter(r_hole, size=9, mode="wrap")
    r_hole = ndimage.uniform_filter1d(r_hole, size=9, mode="wrap")
    r_edge = ndimage.median_filter(r_edge, size=9, mode="wrap")
    r_edge = ndimage.uniform_filter1d(r_edge, size=9, mode="wrap")
    return r_hole, r_edge


def warp(im, target_r, report=None):
    """Remap so the hole's rim becomes a circle of radius target_r."""
    a = np.array(im.getchannel("A"))
    hole, solid = hole_mask(a)
    if hole is None:
        raise ValueError("no enclosed face hole found")

    bx, by = g.CHAR_SCALE_PIVOT
    H, W = a.shape
    max_r = float(np.hypot(max(bx, W - bx), max(by, H - by)))
    angles = np.linspace(0, 2 * np.pi, N_ANGLES, endpoint=False)
    r_hole, r_edge = ray_radii(hole, solid, angles, max_r)

    # taper radius: inside the body's own edge, and always outside the target
    r_out = np.maximum(r_edge * EDGE_MARGIN, target_r * 1.05)
    tight = int((r_out <= target_r * 1.06).sum())

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx, dy = xx - bx, yy - by
    r = np.hypot(dx, dy)
    th = np.mod(np.arctan2(dy, dx), 2 * np.pi)

    # Interpolate the two radii LINEARLY in angle rather than snapping to the
    # nearest ray. At 720 rays a nearest lookup quantises the field into 0.5
    # deg wedges, which is a ~2px arc step out at the rim — visible as
    # faceting on the hole's edge.
    idx = th / (2 * np.pi) * N_ANGLES
    i0 = np.floor(idx).astype(int) % N_ANGLES
    i1 = (i0 + 1) % N_ANGLES
    frac = idx - np.floor(idx)
    rh = r_hole[i0] * (1 - frac) + r_hole[i1] * frac
    ro = r_out[i0] * (1 - frac) + r_out[i1] * frac

    # inverse map: destination radius -> source radius
    with np.errstate(divide="ignore", invalid="ignore"):
        inner = r * np.where(target_r > 0, rh / target_r, 1.0)
        t = np.clip((r - target_r) / np.maximum(ro - target_r, 1e-6), 0, 1)
        outer = rh + t * (ro - rh)
    r_src = np.where(r <= target_r, inner, np.where(r < ro, outer, r))

    scale = np.where(r > 1e-6, r_src / np.maximum(r, 1e-6), 1.0)
    sx = bx + dx * scale
    sy = by + dy * scale

    src = np.array(im).astype(np.float32)
    al = src[:, :, 3:4] / 255.0
    pre = np.concatenate([src[:, :, :3] * al, src[:, :, 3:4]], axis=2)
    outp = np.empty_like(pre)
    for c in range(4):
        outp[:, :, c] = ndimage.map_coordinates(
            pre[:, :, c], [sy, sx], order=1, mode="constant", cval=0)
    oa = np.clip(outp[:, :, 3:4], 0, 255)
    rgb = np.where(oa > 0, outp[:, :, :3] / np.maximum(oa / 255.0, 1e-6), 0)
    res = np.concatenate([np.clip(rgb, 0, 255), oa], axis=2).astype(np.uint8)

    if report is not None:
        report.update(hole_r_min=float(r_hole.min()),
                      hole_r_max=float(r_hole.max()),
                      grow=float(target_r / max(r_hole.mean(), 1e-6)),
                      tight_rays=tight)
    return Image.fromarray(res, "RGBA")


def hole_size(path_or_im):
    im = load(path_or_im) if isinstance(path_or_im, str) else path_or_im
    hole, _ = hole_mask(np.array(im.getchannel("A")))
    if hole is None:
        return None
    ys, xs = np.nonzero(hole)
    return (int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("assets", nargs="*",
                    help="filenames in traits/characterz (default: all)")
    ap.add_argument("--target", type=float, required=True,
                    help="hole WIDTH to normalise to, in rendered px")
    ap.add_argument("--file-space", action="store_true",
                    help="treat --target as file px (ignore CHAR_SCALE)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-dir", help="write here instead of in place "
                                      "(no backup taken)")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    assets = args.assets or sorted(g.get_files(g.CHARACTERZ))
    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)

    print(f"{'character':<30}{'scale':>6}{'hole now':>12}{'target':>9}"
          f"{'grow':>7}{'after':>12}   note")
    failures = []
    for asset in assets:
        src = os.path.join(g.TRAITS_DIR, g.CHARACTERZ, asset)
        name = g.char_base_name(asset)
        sc = 1.0 if args.file_space else g.char_scale(name)
        tgt_file = args.target / sc
        im = load(src)
        before = hole_size(im)
        if before is None:
            print(f"{name:<30}{sc:>6.2f}{'NO HOLE':>12}")
            failures.append(name)
            continue
        rep = {}
        try:
            out = warp(im, tgt_file / 2.0, rep)
        except ValueError as e:
            print(f"{name:<30}{sc:>6.2f}   {e}")
            failures.append(name)
            continue
        after = hole_size(out)
        note = ""
        if rep["tight_rays"]:
            note = f"{rep['tight_rays']} rays had no room to taper"
        print(f"{name:<30}{sc:>6.2f}{f'{before[0]}x{before[1]}':>12}"
              f"{tgt_file:>9.0f}{rep['grow']:>7.2f}"
              f"{f'{after[0]}x{after[1]}':>12}   {note}")

        if args.dry_run:
            continue
        if args.out_dir:
            out.save(os.path.join(args.out_dir, asset))
        else:
            if not args.no_backup:
                os.makedirs(BACKUP_DIR, exist_ok=True)
                stem, ext = os.path.splitext(asset)
                bak = os.path.join(BACKUP_DIR, f"{stem}_pre_hole{ext}")
                if not os.path.exists(bak):
                    shutil.copy2(src, bak)
            out.save(src)

    if args.dry_run:
        print("\ndry run: nothing written")
    if failures:
        print(f"\nno hole found for: {failures}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
