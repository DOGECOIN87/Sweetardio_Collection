#!/usr/bin/env python3
"""Check every character's face hole renders at the one cast-wide size.

The face assembly — skin ball, eyes, mouth — is the SAME size for every
character (generator.py composites it without CHAR_SCALE). So the hole it
shows through has to be the same size too, or the face reads bigger on one
character than another. The cast used to run 179-260px rendered, a 1.45x
spread, because CHAR_SCALE shrank the hole and the ball together.

The invariant, for every character:

    file hole width x CHAR_SCALE  ==  generator.FACE_HOLE_WIDTH

CHAR_SCALE still applies to the BODY, so a 0.74 ice cream needs a 338px hole
in its file to render 250, while an unscaled body needs 250. That is why this
cannot be checked by looking at the art alone.

verify_face_coverage.py is the other half of the pair and catches the
opposite failure: a hole too BIG for the ball leaks the background plate.
This one catches a hole too SMALL, which leaks nothing — it just shows a ring
of skin ball around the face and reads as a shrunken head.

Fix a flagged character with:
    python3 asset_assessment/normalize_face_hole.py <asset> --target 250

Usage: python3 asset_assessment/audit_face_holes.py [--tol 6]
Exit status is 1 if any character is off, so it can gate a build.
"""

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")
import generator as g  # noqa: E402

from normalize_face_hole import hole_mask, load  # noqa: E402


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tol", type=float, default=6.0,
                    help="allowed deviation in rendered px (default 6)")
    args = ap.parse_args()

    target = g.FACE_HOLE_WIDTH
    print(f"target rendered hole width: {target}px  (tolerance +/-{args.tol})\n")
    print(f"{'character':<30}{'scale':>6}{'file hole':>12}"
          f"{'rendered':>11}{'delta':>8}{'roundness':>11}")

    bad = []
    for f in sorted(g.get_files(g.CHARACTERZ)):
        name = g.char_base_name(f)
        im = load(os.path.join(g.TRAITS_DIR, g.CHARACTERZ, f))
        hole, _ = hole_mask(np.array(im.getchannel("A")))
        if hole is None:
            print(f"{name:<30}{'':>6}{'NO HOLE':>12}")
            bad.append((name, "no enclosed face hole"))
            continue
        ys, xs = np.nonzero(hole)
        fw = int(xs.max() - xs.min() + 1)
        fh = int(ys.max() - ys.min() + 1)
        sc = g.char_scale(name)
        rendered = fw * sc
        delta = rendered - target
        round_ = fh / fw
        flag = ""
        if abs(delta) > args.tol:
            flag = "  OFF"
            bad.append((name, f"renders {rendered:.0f}px, {delta:+.0f} off"))
        print(f"{name:<30}{sc:>6.2f}{f'{fw}x{fh}':>12}"
              f"{rendered:>11.0f}{delta:>+8.0f}{round_:>11.2f}{flag}")

    print()
    if bad:
        print(f"{len(bad)} character(s) off the cast face-hole width:")
        for name, why in bad:
            print(f"  {name:<28} {why}")
        print("\nFix with: python3 asset_assessment/normalize_face_hole.py "
              f"<asset> --target {target}")
        return 1
    print(f"All {len(g.get_files(g.CHARACTERZ))} characters render a "
          f"{target}px face hole.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
