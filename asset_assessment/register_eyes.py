#!/usr/bin/env python3
"""Register every eye asset onto one size and one baseline.

Measured before this pass (opaque bbox, threshold 128, canvas 1393):

    width           236 .. 288   (median 277)
    centre x        -7.0 .. +25.5 from the ball's x centre (690)
    centre y       -36.5 .. -16.5 from the ball's y centre (601)

Three consequences, all visible on a rendered strip of the whole set:

  * `layer-art_mattrick_011.png` sits +25.5px right of centre while every
    other eye is within +/-12, so its brows read as slid across the face.
  * Googly (236) and file_...62b0 (245) are NARROWER than the 250px face
    hole, so they do not overlap its rim -- and that overlap is the
    collection's face style, not an accident (CLAUDE.md: median eye 277
    against a 250 hole, ratio ~1.11, "for every character").
  * The 20px spread in vertical centre means the eyes sit at different
    heights on a ball that is pinned in exactly one place.

The pass scales each asset about its own opaque-bbox centre to TARGET_W, then
translates that centre onto (BALL_CX, TARGET_CY). Both are whole-canvas
operations on a 1393 canvas, so the output is still canvas-native and
_render_layer() never has to resize it.

WIDTH IS LOAD-BEARING: ball_fit() sizes the skin ball from the eye's opaque
width, so normalising the widths also makes the ball one size for every eye
pairing instead of ball_fit ranging 1.063..1.134. That is the direction the
"one face, one size" rule already points, but it means verify_face_coverage.py
MUST be re-run afterwards -- a smaller ball on the widest pairings could stop
short of a hole rim.

Originals are backed up to traits/eyez_originals/ (a sibling of traits/eyez,
never inside it -- the generator mints every .png in a trait folder).

Usage (from repo root):
  python3 asset_assessment/register_eyes.py --report
  python3 asset_assessment/register_eyes.py
  python3 asset_assessment/register_eyes.py --restore
"""

import argparse
import os
import shutil
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from generator import EYEZ, TRAITS_DIR, _opaque_bbox  # noqa: E402

EYE_DIR = os.path.join(TRAITS_DIR, EYEZ)
BACKUP_DIR = os.path.join(TRAITS_DIR, "eyez_originals")
CANVAS = 1393
BALL_CX = 690.0            # generator.CHAR_SCALE_PIVOT[0]
TARGET_W = 277.0           # the cast median, and 1.11x the 250px face hole
TARGET_CY = 572.0          # median measured centre (601 - 29)


def measure(path):
    x0, y0, x1, y1 = _opaque_bbox(path)
    return {"w": x1 - x0, "h": y1 - y0,
            "cx": (x0 + x1) / 2.0, "cy": (y0 + y1) / 2.0}


def register(path):
    """Scale to TARGET_W about the art's own centre, then move that centre
    onto (BALL_CX, TARGET_CY). Returns a new canvas-sized RGBA image."""
    m = measure(path)
    img = Image.open(path).convert("RGBA")
    if img.size != (CANVAS, CANVAS):
        img = img.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS)

    factor = TARGET_W / max(m["w"], 1)
    # scale about the art's centre so the centre stays put, then translate
    nw, nh = round(CANVAS * factor), round(CANVAS * factor)
    scaled = img.resize((nw, nh), Image.Resampling.LANCZOS)
    # where the art's centre landed inside the scaled canvas
    sx, sy = m["cx"] * factor, m["cy"] * factor
    out = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    out.paste(scaled, (round(BALL_CX - sx), round(TARGET_CY - sy)))
    return out


def eye_files(d=None):
    d = d or EYE_DIR
    return sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))


def report():
    print(f"{'eye':<46}{'w':>6}{'h':>6}{'cx-690':>9}{'cy-601':>9}")
    for f in eye_files():
        m = measure(os.path.join(EYE_DIR, f))
        print(f"{f[:46]:<46}{m['w']:6.0f}{m['h']:6.0f}"
              f"{m['cx']-690:+9.1f}{m['cy']-601:+9.1f}")


def apply():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for f in eye_files():
        src = os.path.join(EYE_DIR, f)
        bak = os.path.join(BACKUP_DIR, f)
        if not os.path.exists(bak):
            shutil.copy2(src, bak)
        before = measure(bak)
        register(bak).save(src)          # always from the backup: idempotent
        after = measure(src)
        print(f"{f[:44]:<44} w {before['w']:3.0f}->{after['w']:3.0f}  "
              f"cx {before['cx']-690:+6.1f}->{after['cx']-690:+5.1f}  "
              f"cy {before['cy']-601:+6.1f}->{after['cy']-601:+5.1f}")


def restore():
    for f in eye_files(BACKUP_DIR):
        dst = os.path.join(EYE_DIR, f)
        if os.path.exists(dst):
            shutil.copy2(os.path.join(BACKUP_DIR, f), dst)
            print(f"restored {f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--restore", action="store_true")
    args = ap.parse_args()
    if args.report:
        report()
    elif args.restore:
        restore()
    else:
        apply()


if __name__ == "__main__":
    main()
