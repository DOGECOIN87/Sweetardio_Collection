#!/usr/bin/env python3
"""Compress a character's art vertically about the ball centre.

Why this exists rather than just lowering CHAR_SCALE: CHAR_SCALE is a
UNIFORM scale, so it cannot change a character's proportions. Shrinking a
body that is too tall makes it a smaller body that is still too tall, and it
drags the face down with it (CHAR_SCALE scales body, ball, eyes and mouth
together — see CLAUDE.md). The Nutty Bar was the case that forced the issue:
at 1059px tall against a cast median of 771 it read as a plank, and every
CHAR_SCALE that fixed its height left it a narrower plank with a smaller face.

A vertical-only squash keeps the width and keeps the face at full size, and
changes the one thing that was actually wrong — the aspect ratio.

Two properties make it safe for this pipeline:

  * It scales about the BALL CENTRE (CHAR_SCALE_PIVOT, ~690/601), so the face
    hole stays pinned exactly where the compositor expects it. Nothing moves
    to follow a body that drifted, so this is the only pivot that works.
  * It makes a tall face hole ROUNDER, toward the cast's round holes. The
    Nutty Bar's hole was the cast's only TALL ellipse (247x294), which is why
    it needed a FACE_HOLE_BOTTOM_OVERRIDE at all; squashed it lands at
    247x250, essentially the cast median, and the override can go.

The cost is that the art's own texture is compressed by the same factor — a
wafer grid gets 15% flatter at 0.85. Look at the result before keeping it;
past ~0.75 the distortion starts to read as a squashed render rather than a
shorter bar.

Always writes a backup of the original next to it unless --no-backup.

Usage (from repo root):
  python3 asset_assessment/squash_character.py Nutty_Bar.png --factor 0.85
  python3 asset_assessment/squash_character.py Nutty_Bar.png -f 0.85 --dry-run
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


def body_and_hole(path):
    """(body bbox, hole bbox) for a character asset, in canvas coords."""
    im = Image.open(path).convert("RGBA")
    if im.size != (g.CANVAS_SIZE, g.CANVAS_SIZE):
        im = im.resize((g.CANVAS_SIZE,) * 2, Image.Resampling.LANCZOS)
    a = np.array(im.getchannel("A")) > 50
    ys, xs = np.nonzero(a)
    body = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))

    holes = ndimage.binary_fill_holes(a) & ~a
    lab, n = ndimage.label(holes)
    bx, by = g.CHAR_SCALE_PIVOT
    best, hole = None, None
    for i in range(1, n + 1):
        hy, hx = np.nonzero(lab == i)
        if len(hy) < 6000:
            continue
        d = (hx.mean() - bx) ** 2 + (hy.mean() - by) ** 2
        if best is None or d < best:
            best = d
            hole = (int(hx.min()), int(hy.min()), int(hx.max()), int(hy.max()))
    return body, hole


def squash(path, factor, out_path):
    """Compress vertically about CHAR_SCALE_PIVOT's y, keeping the canvas."""
    im = Image.open(path).convert("RGBA")
    if im.size != (g.CANVAS_SIZE, g.CANVAS_SIZE):
        im = im.resize((g.CANVAS_SIZE,) * 2, Image.Resampling.LANCZOS)
    W, H = im.size
    _, py = g.CHAR_SCALE_PIVOT
    scaled = im.resize((W, max(1, round(H * factor))), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # the pivot row must land back on itself: y' = py + factor*(y - py)
    canvas.paste(scaled, (0, round(py - py * factor)))
    canvas.save(out_path)
    return out_path


def describe(label, body, hole):
    w, h = body[2] - body[0], body[3] - body[1]
    s = f"  {label:<10} body {w}x{h}  aspect {h / w:.2f}"
    if hole:
        hw, hh = hole[2] - hole[0], hole[3] - hole[1]
        cx, cy = (hole[0] + hole[2]) // 2, (hole[1] + hole[3]) // 2
        bx, by = g.CHAR_SCALE_PIVOT
        s += (f"   hole {hw}x{hh} at ({cx},{cy}) "
              f"d=({cx - bx:+d},{cy - by:+d}) bottom {hole[3]}")
    return s


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("asset", help="filename inside traits/characterz")
    ap.add_argument("-f", "--factor", type=float, required=True,
                    help="vertical scale, <1 shortens (0.85 = 15% shorter)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    if not 0.4 <= args.factor <= 1.5:
        sys.exit(f"factor {args.factor} is outside the sane range 0.4-1.5")

    src = os.path.join(g.TRAITS_DIR, g.CHARACTERZ, args.asset)
    if not os.path.exists(src):
        sys.exit(f"no such asset: {src}")

    name = g.char_base_name(args.asset)
    before_body, before_hole = body_and_hole(src)
    print(f"{args.asset}  (character {name!r}, CHAR_SCALE "
          f"{g.char_scale(name)})")
    print(describe("before", before_body, before_hole))

    tmp = src + ".squashed.png"   # PIL picks the writer from the extension
    squash(src, args.factor, tmp)
    after_body, after_hole = body_and_hole(tmp)
    print(describe(f"x{args.factor}", after_body, after_hole))

    # what the placement table has to become to keep the feet where they were
    sc = g.char_scale(name)
    _, py = g.CHAR_SCALE_PIVOT
    old_bottom = py + sc * (before_body[3] - py) + g.char_y_adjust(name)
    new_dy = round(old_bottom - (py + sc * (after_body[3] - py)))
    print(f"\n  CHAR_Y_ADJUST[{name.lower()!r}]: {g.char_y_adjust(name)} "
          f"-> {new_dy}   (keeps the bottom on canvas row {old_bottom:.0f})")
    if after_hole:
        print(f"  face hole bottom {after_hole[3]} vs cast "
              f"FACE_HOLE_BOTTOM {g.FACE_HOLE_BOTTOM} — re-check "
              f"FACE_HOLE_BOTTOM_OVERRIDE with verify_face_coverage.py")

    if args.dry_run:
        os.remove(tmp)
        print("\ndry run: nothing written")
        return 0

    if not args.no_backup:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stem, ext = os.path.splitext(args.asset)
        bak = os.path.join(BACKUP_DIR, f"{stem}_pre_squash{ext}")
        if os.path.exists(bak):
            sys.exit(f"backup {bak} already exists — refusing to overwrite "
                     f"it (that would lose the true original)")
        shutil.copy2(src, bak)
        print(f"\nbacked up original -> {bak}")
    os.replace(tmp, src)
    print(f"wrote {src}")
    print("\nNow: re-derive CHAR_Y_ADJUST above, then run "
          "verify_face_coverage.py and verify_placement.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
