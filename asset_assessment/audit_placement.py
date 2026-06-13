#!/usr/bin/env python3
"""Audit character asset placement and derive the CHAR_Y_ADJUST table.

Face rule reminder: the skin ball, eyes and mouth live at FIXED canvas
positions, and every character's face hole is drawn around the ball center
(~690, 601). The ONLY safe way to normalize placement is a per-character
vertical trim (dy) — generator.py applies the same dy to body, skin, eyes,
mouth and arms, so the under/overlay skinz relationship is preserved
exactly. This tool therefore never proposes scaling or horizontal moves;
it measures and aligns STANDING BOTTOMS.

Measurements (sparkle-proof):
  * main body bbox  = largest 4-connected opaque component (decorative
    sparkles around some characters are separate small components)
  * face hole       = enclosed transparent component nearest the ball
    center; flagged if its center drifts > HOLE_TOL from the ball

Alignment targets (from the owner-approved batches):
  * offset-eligible characters (get +150 when footwear-less): standing
    bottom -> GROUND_STAND (957); footwear-less bottom lands at 1107,
    inside the approved 1084-1109 ground band
  * fixed characters (NO_OFFSET_CHARS, e.g. churro/twinkie/bears):
    bottom -> GROUND_FIXED (1111, the churro line)
  * ice creams: cone tip -> GROUND_CONE (1290, the family majority)

Owner-tuned values are kept verbatim (poptart -65, twinkie +45: the owner
asked for deliberate overshoot) — listed in KEEP_OWNER_TUNED.

Usage: python3 asset_assessment/audit_placement.py
Prints the measured table and the ready-to-paste CHAR_Y_ADJUST dict.
"""

import os
import re
import sys
from collections import deque

import numpy as np
from PIL import Image

sys.path.insert(0, ".")
import generator as g

CANVAS = 1393
BALL_CENTER = (690, 601)
HOLE_TOL = 40          # px; face hole farther than this from the ball = flag
GROUND_STAND = 957     # standing bottom for offset-eligible characters
GROUND_FIXED = 1111    # standing bottom for NO_OFFSET characters (churro line)
GROUND_CONE = 1290     # ice-cream cone tip line
DY_MIN = 12            # trims smaller than this are noise; omit from table

KEEP_OWNER_TUNED = {"poptart": -65, "twinkie": 45}


def load_alpha(path):
    im = Image.open(path).convert("RGBA")
    if im.size != (CANVAS, CANVAS):
        im = im.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS)
    return np.array(im)[:, :, 3]


def components(mask):
    lbl = np.zeros(mask.shape, dtype=np.int32)
    cur = 0
    H, W = mask.shape
    for sy, sx in zip(*np.where(mask)):
        if lbl[sy, sx]:
            continue
        cur += 1
        q = deque([(sy, sx)])
        lbl[sy, sx] = cur
        while q:
            y, x = q.popleft()
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] \
                        and not lbl[ny, nx]:
                    lbl[ny, nx] = cur
                    q.append((ny, nx))
    return lbl, cur


def measure(path, ds=4):
    """(main-body bbox, face-hole center) at full-res coords (ds-coarse)."""
    a = load_alpha(path)
    op = (a > 50)[::ds, ::ds]
    lbl, n = components(op)
    if n == 0:
        return None, None
    main = max(range(1, n + 1), key=lambda i: (lbl == i).sum())
    ys, xs = np.where(lbl == main)
    bbox = (xs.min() * ds, ys.min() * ds,
            xs.max() * ds + ds - 1, ys.max() * ds + ds - 1)

    inv_lbl, m = components(~op)
    border = (set(inv_lbl[0, :]) | set(inv_lbl[-1, :])
              | set(inv_lbl[:, 0]) | set(inv_lbl[:, -1]))
    best, best_d = None, None
    for i in range(1, m + 1):
        if i in border:
            continue
        hy, hx = np.where(inv_lbl == i)
        if len(hy) * ds * ds < 6000:      # ignore tiny decorative gaps
            continue
        cx, cy = hx.mean() * ds, hy.mean() * ds
        d = (cx - BALL_CENTER[0]) ** 2 + (cy - BALL_CENTER[1]) ** 2
        if best_d is None or d < best_d:
            best_d, best = d, (round(cx), round(cy))
    return bbox, best


def char_table():
    """base name -> primary character file (generator's resolution order)."""
    char_files = g.get_files(g.CHARACTERZ)
    names = {}
    for f in char_files:
        n = (f.replace("layer-after_skinz_", "")
              .replace("before_skinz_", "").replace("after_skinz_", "")
              .replace(".png", ""))
        n = re.sub(r"\s*\(\d+\)", "", n).strip()
        names.setdefault(n, f)
    return names


def main():
    rows, dy_table, flags = [], {}, []
    for name, fname in sorted(char_table().items()):
        bbox, hole = measure(os.path.join(g.TRAITS_DIR, g.CHARACTERZ, fname))
        if bbox is None:
            flags.append(f"{name}: no opaque pixels?!")
            continue
        # The generator enlarges some characters about the ball center before
        # compositing; mirror that here so the measured bottom (and the face
        # hole) reflect what actually lands on the canvas.
        f = g.char_scale(name)
        if abs(f - 1.0) > 1e-6:
            px, py = g.CHAR_SCALE_PIVOT
            x0, y0, x1, y1 = bbox
            bbox = (px + f * (x0 - px), py + f * (y0 - py),
                    px + f * (x1 - px), py + f * (y1 - py))
            if hole:
                hole = (round(px + f * (hole[0] - px)),
                        round(py + f * (hole[1] - py)))
        bottom = round(bbox[3])
        no_off = any(k.lower() in name.lower() for k in g.NO_OFFSET_CHARS)
        if "ice_cream" in name.lower():
            target, mode = GROUND_CONE, "cone"
        elif no_off:
            target, mode = GROUND_FIXED, "fixed"
        else:
            target, mode = GROUND_STAND, "stand"

        owner = next((dy for k, dy in KEEP_OWNER_TUNED.items()
                      if k in name.lower()), None)
        dy = owner if owner is not None else target - bottom
        if owner is None and abs(dy) < DY_MIN:
            dy = 0
        if dy:
            dy_table[name] = dy

        hole_s = "none"
        if hole:
            dx = hole[0] - BALL_CENTER[0]
            dyh = hole[1] - BALL_CENTER[1]
            hole_s = f"({hole[0]},{hole[1]}) d=({dx:+d},{dyh:+d})"
            if abs(dx) > HOLE_TOL or abs(dyh) > HOLE_TOL:
                flags.append(f"{name}: face hole {hole} is > {HOLE_TOL}px "
                             f"from the ball center {BALL_CENTER}")
        rows.append((name, mode, bottom, target, dy,
                     "owner" if owner is not None else "", hole_s))

    print("%-32s %-6s %6s %6s %5s %-6s %s"
          % ("character", "mode", "bottom", "target", "dy", "src", "face hole vs ball"))
    for r in rows:
        print("%-32s %-6s %6d %6d %+5d %-6s %s" % r)

    print("\nflags (%d):" % len(flags))
    for f in flags:
        print("  " + f)

    print("\nCHAR_Y_ADJUST = {")
    for k in sorted(dy_table, key=lambda k: (-abs(dy_table[k]), k)):
        print(f'    "{k.lower()}": {dy_table[k]},')
    print("}")
    return dy_table


if __name__ == "__main__":
    main()
