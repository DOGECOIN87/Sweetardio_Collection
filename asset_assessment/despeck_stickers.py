#!/usr/bin/env python3
"""Delete the cut-out debris orbiting a die-cut sticker.

These are fragments of the original lasso cut left floating outside the white
border -- on a light plate they vanish, on a dark one they read as a scatter
of white dots around the sticker. 112 of them across 17 of the 23 files.

THEY HIDE FROM THE OBVIOUS CHECKS, which is why the set kept measuring clean:

  * A component count at `alpha > 2` or `> 20` does not see them. Each bright
    speck is joined to the body by a film of alpha <= 8 ghost bleed, so at a
    low threshold it is part of the main blob. What the low threshold DOES
    surface is 30-80 separate fragments per file, all capped at alpha 8 --
    genuinely invisible debris, and a decoy: it looks like the whole problem.
  * A count at `alpha > 80` or higher over-reports instead: raising the cut
    fragments the ARTWORK, so the extra components are the sticker's own thin
    parts, not specks.
  * "Opaque pixels far from the body" misses them too, at any sane distance:
    they hug the border, 3-6px out. At 6px the set reads 0.

The one framing that works is a component analysis at `alpha > 128` -- high
enough that the ghost film no longer bridges, low enough that the artwork is
still one piece. Mr Owl: 16 components, 15 of them specks totalling 52px, the
largest 12px, several at full alpha 255.

Every speck measured lies OUTSIDE the filled body, on all 17 files, so none of
this is detached artwork -- the run asserts it rather than assuming it.

  python3 asset_assessment/despeck_stickers.py --report
  python3 asset_assessment/despeck_stickers.py
"""

import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g  # noqa: E402

CORE = 128       # the one threshold at which body is whole and specks are loose
GHOST = 2        # anything above this paints something, however faintly
HALO = 3         # px of ghost film around a speck to take with it
PROTECT = 2      # px around the body that a speck's halo may never eat into
BACKUP_SUFFIX = "_prespeck"


def analyse(arr):
    """(main body mask, speck mask) at the CORE threshold."""
    al = arr[:, :, 3]
    core = al > CORE
    lab, n = ndi.label(core)
    if n == 0:
        return None, None
    sz = np.array(ndi.sum(core, lab, range(1, n + 1)))
    main = lab == (int(np.argmax(sz)) + 1)
    return main, core & ~main


def despeck(arr):
    main, specks = analyse(arr)
    if main is None:
        return None, 0, 0
    # NOTE: do not return early when there is no bright speck. The ghost-floor
    # stage below is the one that catches a fragment peaking below CORE, and a
    # file can be free of bright specks and still carry those.

    # the speck's own ghost film goes with it, but never within PROTECT px of
    # the body -- that band is the die-cut border's own soft outer glow
    near_body = ndi.binary_dilation(main, iterations=PROTECT)
    halo = (ndi.binary_dilation(specks, iterations=HALO)
            & (arr[:, :, 3] > GHOST) & ~near_body)
    kill = specks | halo

    # SECOND STAGE, and it is not optional. The CORE pass only catches debris
    # whose PEAK clears 128. A fragment that tops out at, say, alpha 94 is
    # still plainly visible on a dark plate and is invisible to that pass --
    # Mr Owl kept one at 94 and the Hunny Pot one at 102 after the first
    # stage cleared every bright speck. So sweep again at the ghost floor:
    # anything not joined to the body at alpha > GHOST is debris, whatever its
    # peak. This also takes the 30-80 alpha<=8 fragments per file that were
    # never visible but are junk all the same.
    al2 = arr[:, :, 3].copy()
    al2[kill] = 0
    vis = al2 > GHOST
    lab2, n2 = ndi.label(vis)
    if n2 > 1:
        sz2 = np.array(ndi.sum(vis, lab2, range(1, n2 + 1)))
        keep = lab2 == (int(np.argmax(sz2)) + 1)
        kill = kill | (vis & ~keep)

    # nothing removed may sit inside the body: that would be artwork
    if (kill & ndi.binary_fill_holes(main)).any():
        raise AssertionError("a speck lies inside the body — inspect, do not run")

    out = arr.copy()
    out[:, :, 3][kill] = 0
    return out, int(specks.sum()), int(kill.sum())


def main_cli():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="default: every sticker")
    ap.add_argument("--report", action="store_true", help="measure, write nothing")
    args = ap.parse_args()

    d = os.path.join(g.TRAITS_DIR, g.STICKERZ)
    files = args.files or sorted(f for f in os.listdir(d)
                                 if f.lower().endswith(".png"))
    tot = hit = 0
    for f in files:
        p = os.path.join(d, f)
        a0 = np.asarray(Image.open(p).convert("RGBA"))
        out, nsp, nkill = despeck(a0)
        if out is None or nkill == 0:
            print(f"  {f:36.36s} clean")
            continue
        hit += 1
        tot += nsp
        print(f"  {f:36.36s} {nsp:3d} speck px + {nkill - nsp:3d} halo px removed"
              f"{'   (report)' if args.report else ''}")
        if args.report:
            continue
        # the body itself must come through untouched
        m0, _ = analyse(a0)
        assert (out[:, :, 3][m0] == a0[:, :, 3][m0]).all(), f"{f}: body alpha moved"
        assert (out[:, :, :3] == a0[:, :, :3]).all(), f"{f}: colour moved"
        bd = os.path.join(g.TRAITS_DIR, g.STICKERZ + BACKUP_SUFFIX)
        os.makedirs(bd, exist_ok=True)
        bak = os.path.join(bd, f)
        if not os.path.exists(bak):
            shutil.copy2(p, bak)
        Image.fromarray(out).save(p)
    print(f"\n{tot} specks across {hit} file(s)"
          f"{' would be' if args.report else ''} removed")


if __name__ == "__main__":
    main_cli()
