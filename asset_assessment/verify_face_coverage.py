#!/usr/bin/env python3
"""Prove the skin ball covers every character's face hole, for every skin.

When a body draws ON TOP of the skin ball (the collection's rule — no skin is
ever painted over a character), the visible face is whatever shows through the
body's face hole. If the ball does not reach the hole's rim, the gap is not
skin and it is not body: it is a hole straight through to the background
plate, and it only appears for some skin x eye pairs, because `ball_fit`
sizes the ball from the widest eye and each skin ball has its own size and
centre.

So the check has to be combinatorial. For every character x skin x eye it
composites ONLY the body and the ball, at the same relative geometry the
compositor uses, and counts transparent pixels ENCLOSED by the result. A gap
at the silhouette's outer edge is just the shape of the character; a gap in
the middle of it is a leak.

    leak = binary_fill_holes(alpha > 0) & ~(alpha > 0)

Anti-aliasing along the hole rim contributes a handful of pixels, so anything
under --tol (default 200) is noise. A real leak is hundreds to thousands and
has a bbox you can point at.

The fix for a leak is `FACE_HOLE_BOTTOM_OVERRIDE[<char>]` in generator.py,
which grows the ball through `ball_fit`'s `need_h`. Note the value is in
PRE-CHAR_SCALE file space, not composited canvas space.

Usage:
    python3 asset_assessment/verify_face_coverage.py
    python3 asset_assessment/verify_face_coverage.py --char nutty_bar -v
    python3 asset_assessment/verify_face_coverage.py --dump out/  # leak masks

Exit status is 1 if any character leaks, so it can gate a build.
"""

import argparse
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")
import generator as g  # noqa: E402


def char_names():
    """Every base character name, exactly as generate_random_combination
    derives them from the filenames in traits/characterz."""
    return sorted({g.char_base_name(f) for f in g.get_files(g.CHARACTERZ)})


def body_and_skin_layers(char_name):
    """The character's body layer(s) and its skin layer, in composite order,
    with placement neutralised.

    Rather than re-implement generator.py's three-pass character-file lookup
    (and drift from it), this asks the generator for a real combination and
    keeps only the characterz and skinz layers. Placement (`offset`/`dy`) is
    zeroed on both: the body and the ball always share the same dy, so the
    relative geometry this check cares about is untouched, and the result no
    longer depends on which footwear the roll happened to pick.
    """
    layers, _ = g.generate_random_combination(force_char=char_name)
    keep = []
    for layer in layers:
        parent = os.path.basename(os.path.dirname(layer["path"]))
        if parent in (g.CHARACTERZ, g.SKINZ):
            layer = dict(layer)
            layer["offset"] = False
            layer["dy"] = 0
            keep.append(layer)
    return keep


def composite(layers):
    canvas = Image.new("RGBA", (g.CANVAS_SIZE, g.CANVAS_SIZE), (0, 0, 0, 0))
    for layer in layers:
        img = g._render_layer(layer)
        if img is not None:
            canvas = Image.alpha_composite(canvas, img)
    return canvas


def leak(alpha, thresh=0):
    """Transparent pixels enclosed by the composite. Returns (count, bbox,
    mask)."""
    solid = np.array(alpha) > thresh
    filled = ndimage.binary_fill_holes(solid)
    holes = filled & ~solid
    count = int(holes.sum())
    if not count:
        return 0, None, holes
    ys, xs = np.nonzero(holes)
    return count, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())), holes


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tol", type=int, default=200,
                    help="enclosed-pixel count below which a gap is treated "
                         "as rim anti-aliasing (default 200)")
    ap.add_argument("--char", help="check one character only")
    ap.add_argument("--dump", metavar="DIR",
                    help="write a PNG of each leaking composite (leak in red)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print every skin x eye pair, not just the worst")
    args = ap.parse_args()

    chars = [args.char] if args.char else char_names()
    skins = g.get_files(g.SKINZ)
    eyes = g.get_files(g.EYEZ)
    if args.dump:
        os.makedirs(args.dump, exist_ok=True)

    print(f"{len(chars)} characters x {len(skins)} skins x {len(eyes)} eyes "
          f"= {len(chars) * len(skins) * len(eyes)} composites\n")
    print(f"{'character':<32} {'worst leak':>10}  {'skin x eye':<40} bbox")
    print("-" * 110)

    failures = []
    for char in chars:
        base = body_and_skin_layers(char)
        worst = (0, None, None)
        for skin in skins:
            skin_path = os.path.join(g.TRAITS_DIR, g.SKINZ, skin)
            for eye in eyes:
                eye_path = os.path.join(g.TRAITS_DIR, g.EYEZ, eye)
                fscale, fcenter = g.ball_fit(
                    skin_path, eye_path,
                    hole_bottom=g.face_hole_bottom(char))
                layers = []
                for layer in base:
                    layer = dict(layer)
                    if os.path.basename(os.path.dirname(layer["path"])) == g.SKINZ:
                        layer["path"] = skin_path
                        layer["fscale"] = fscale
                        layer["fcenter"] = fcenter
                    layers.append(layer)
                img = composite(layers)
                count, bbox, holes = leak(img.getchannel("A"))
                pair = f"{skin} x {eye}"
                if args.verbose and count:
                    print(f"    {char:<28} {count:>10}  {pair}")
                if count > worst[0]:
                    worst = (count, pair, bbox)
                    if args.dump and count > args.tol:
                        marked = img.copy()
                        red = np.array(marked)
                        red[holes] = (255, 0, 0, 255)
                        Image.fromarray(red).save(
                            os.path.join(args.dump, f"{char}_leak.png"))
        count, pair, bbox = worst
        flag = "  LEAK" if count > args.tol else ""
        print(f"{char:<32} {count:>10}  {(pair or '-'):<40} {bbox or ''}{flag}")
        if count > args.tol:
            failures.append((char, count, pair, bbox))

    print()
    if failures:
        print(f"{len(failures)} character(s) leak background through the face hole:")
        for char, count, pair, bbox in sorted(failures, key=lambda r: -r[1]):
            print(f"  {char:<30} {count:>7}px  worst on {pair}  bbox={bbox}")
        print("\nGrow the ball with FACE_HOLE_BOTTOM_OVERRIDE (pre-CHAR_SCALE "
              "file space) in generator.py.")
        return 1
    print(f"All {len(chars)} characters covered on every skin x eye "
          f"(tolerance {args.tol}px).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
