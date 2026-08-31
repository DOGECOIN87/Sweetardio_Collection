#!/usr/bin/env python3
"""Remove cut-out residue -- stray pixels OUTSIDE an asset's own outline.

Several stickers, arms and footwear assets ship with small disconnected blobs
sitting off the art: the ghost of a lasso path left behind when the piece was
cut from its background. Measured across the three classes, 28 assets carried
979 such components totalling 3,183 px. On the Pepe and Shiba slipper bases it
is literally a dotted arc tracing the outline of the right slipper; on the
bunny overlay it is a detached smear of the baked drop shadow floating in the
gap between the two slippers; on the stickers it is a scatter of 1-77 px specks
hugging the die-cut border, plus hair wisps that escaped it.

They are easy to miss on a dark plate and obvious on a light one, which is why
they survived this long.

WHAT COUNTS AS A SPECK, and why the threshold is safe
-----------------------------------------------------
A component is removed when it is BOTH under SPECK_FRAC of the asset's largest
component AND under SPECK_ABS px. Both conditions, because either alone is
wrong: a fractional test on its own would eat a genuinely small asset, and an
absolute one would eat fine detail on a large one.

The margin is enormous, which is what makes this safe rather than a judgement
call. Across all three classes the largest speck found is 340 px, while the
SMALLEST legitimate part -- the Military Brat's second glove -- is 16,208 px.
That is a 48x gap with nothing in between, so no threshold inside it can be
wrong. A pair of slippers is two components and an arm is two gloves; those
are parts, not specks, and they sit far above the line.

WHAT IS DELIBERATELY NOT TOUCHED
--------------------------------
The EDGE. audit_art_quality.py flags the three sabers at fringe 88 against a
cast median near 2, and the Cookie Monster slippers at 21-23. That is a wide
band of semi-transparent pixels around the art -- a glow on a lightsaber and
fur on a puppet, i.e. the art doing its job. Trimming it would be a different
operation on intentional design, so this tool only ever removes pixels that
are DISCONNECTED from the piece.

Alpha inside the kept components is preserved bit-for-bit. Some residue is
fully opaque and sits at the art's extremity, so removing it can pull the
SOLID bounding box (alpha > 200) in by a pixel or two. That is load-bearing
for FOOTWEAR only -- generator.WAT_SCALE_PIVOT was solved against the sole
line measured at that threshold, and a moved sole would misplace every wearer
-- so the tool REFUSES to touch a footwear asset whose solid bbox would move.
Measured, none do. Stickers composite at a fixed position and arms hang off
ARM_SCALE_PIVOT, so neither reads its own bbox; four stickers shift by 1-4 px
there and nothing consumes it.

Originals go to traits/<class>_prespeckle/, a SIBLING of the trait folder.
Never inside it: generator.get_files() mints every .png in a trait folder, so
a backup kept there would mint as a trait. And never "<class>_originals",
which is already taken and means something different -- see backup_dir(). The tool always cleans FROM the
backup, so re-running it is idempotent rather than compounding.

Usage:
  python3 asset_assessment/despeckle_traits.py --report   # measure only
  python3 asset_assessment/despeckle_traits.py --apply
  python3 asset_assessment/despeckle_traits.py --restore
"""

import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g  # noqa: E402

CLASSES = [g.STICKERZ, g.ARMZ, g.WHAT_ARE_THOSEZ]

# A pixel this faint is still a pixel: the residue is mostly alpha 10-40, so a
# higher floor would simply not see the thing being removed.
VISIBLE = 8
SPECK_FRAC = 0.02      # of the asset's largest component
SPECK_ABS = 500        # px; the largest real speck measured is 340
SOLID = 200            # the threshold the footwear geometry was measured at


def backup_dir(cls):
    """A name that CANNOT collide with an existing folder.

    Not "<class>_originals": that convention is already taken and does not
    mean the same thing everywhere. traits/armz_originals holds RETIRED art --
    the seven per-character katanas and knives that were replaced by one
    generic file each -- and it happens to contain three filenames that are
    also live assets, with DIFFERENT pixels. A tool that treated it as its own
    backup would read the retired art as the "original", clean that, and write
    the result over the live asset. (It did not, because those three carry no
    specks, but the collision is real.) traits/backgroundz_originals is a
    third meaning again: generator.BACKGROUNDZ_FALLBACK reads it at mint time.
    """
    return os.path.join(g.TRAITS_DIR, f"{cls}_prespeckle")


def specks(alpha):
    """Mask of components that are residue rather than part of the piece."""
    m = alpha > VISIBLE
    lab, n = ndimage.label(m)
    if n <= 1:
        return np.zeros_like(m), 0
    sizes = np.array(ndimage.sum(m, lab, range(1, n + 1)))
    biggest = sizes.max()
    ids = [i + 1 for i, s in enumerate(sizes)
           if s < biggest * SPECK_FRAC and s < SPECK_ABS]
    if not ids:
        return np.zeros_like(m), 0
    return np.isin(lab, ids), len(ids)


def solid_bbox(alpha):
    ys, xs = np.nonzero(alpha > SOLID)
    if len(ys) == 0:
        return None
    return int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if not (args.apply or args.restore):
        args.report = True

    total_files = total_comps = total_px = 0
    for cls in CLASSES:
        live, back = os.path.join(g.TRAITS_DIR, cls), backup_dir(cls)

        if args.restore:
            if not os.path.isdir(back):
                print(f"{cls}: no backup to restore from")
                continue
            for f in sorted(os.listdir(back)):
                if f.endswith(".png"):
                    shutil.copy2(os.path.join(back, f), os.path.join(live, f))
            print(f"{cls}: restored from {back}")
            continue

        if args.apply:
            os.makedirs(back, exist_ok=True)

        print(f"\n## {cls}")
        for f in sorted(os.listdir(live)):
            if not f.endswith(".png"):
                continue
            # Always read the ORIGINAL when one exists, so a second run cleans
            # the same input rather than re-cleaning its own output.
            src = os.path.join(back, f)
            if not os.path.exists(src):
                src = os.path.join(live, f)
                if args.apply:
                    shutil.copy2(src, os.path.join(back, f))
                    src = os.path.join(back, f)

            im = Image.open(src).convert("RGBA")
            arr = np.array(im)
            sp, n = specks(arr[..., 3])
            if n == 0:
                continue
            px = int(sp.sum())
            total_files += 1
            total_comps += n
            total_px += px

            out = arr.copy()
            out[sp] = 0          # alpha AND colour: a removed speck leaves nothing

            # Some residue is fully opaque and sits at the art's extremity, so
            # removing it can pull the solid bounding box in by a pixel or two.
            # That is only load-bearing for FOOTWEAR: generator.WAT_SCALE_PIVOT
            # was solved against the sole line measured at alpha > SOLID, so a
            # moved sole would misplace every wearer. Stickers composite at a
            # fixed position and arms hang off ARM_SCALE_PIVOT, so neither
            # reads its own bbox and a pixel there costs nothing.
            before, after = solid_bbox(arr[..., 3]), solid_bbox(out[..., 3])
            delta = (tuple(b - a for b, a in zip(before, after))
                     if before and after else None)
            if cls == g.WHAT_ARE_THOSEZ and before != after:
                sys.exit(f"{f}: removing specks moved the SOLID bounding box "
                         f"{before} -> {after}. Footwear geometry is measured "
                         f"at alpha>{SOLID} and would shift with it -- refusing "
                         f"to touch this asset.")
            note = "" if before == after else f"  bbox {delta}"
            print(f"  {f[:46]:46} {n:4} specks  {px:6} px{note}")
            if args.apply:
                Image.fromarray(out, "RGBA").save(os.path.join(live, f))

    if not args.restore:
        verb = "removed" if args.apply else "would remove"
        print(f"\n{verb} {total_comps} stray components ({total_px} px) "
              f"from {total_files} assets")
        if not args.apply:
            print("re-run with --apply to write, --restore to undo")


if __name__ == "__main__":
    main()
