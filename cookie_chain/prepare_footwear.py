#!/usr/bin/env python3
"""Re-cut the footwear outlines for the Cookie Chain Edition.

    python3 prepare_footwear.py              # traits/what_are_thosez -> assets/what_are_thosez
    python3 prepare_footwear.py --sheet out.png

The five footwear sets are photographs cut out with a lasso, and the cut
shows: a chewed, stepped outline on the Bunny base; a dark ragged line round
Pepe and a grey halo round the Gorbhouse cans on any light plate; a soft
drop shadow baked under both Cookie Monster files (lit from straight above,
so it fights the collection's top-left key and doubles the compositor's own
GROUND_SHADOW) and a detached smear of one under the Bunny overlay.

Each file is re-cut the same way:

1. SOLID OBJECT. alpha >= 0.6, pieces under 2% of the largest dropped, pin-
   holes filled (real openings such as the Gorbhouse lid handle stay open).
   A baked shadow never reaches 0.6, so it falls away here.
2. ONE SMOOTH EDGE. The mask is smoothed at 4x (gaussian, re-thresholded)
   and resampled down, so the outline is anti-aliased and follows the
   object rather than the lasso.
3. COLOUR FROM THE OBJECT. The outer 4px rim takes the colour of the
   nearest pixel at least 4px inside, which removes the baked dark / light
   ring (measured 3-4px deep) without touching anything deeper in the art.

4. THE BACK PIECE STAYS BEHIND THE FRONT. Each base is drawn behind the
   body and its overlay in front, and where the two outline the same
   slipper the base ran a few px wider -- a thin crescent, darker than the
   front piece, that read as a dotted line round the Bunny once the outline
   was smoothed (6,515 px). The base is trimmed to its overlay's outline
   except where it is meant to show on its own: the ankle stubs and heel,
   found as everything more than 8px outside the overlay and grown back to
   the overlay's edge.

The `alpha > 200` sole line is what WAT_SCALE_PIVOT and every footwear
placement were solved against, so the run asserts it moves by at most 2px.
Outputs keep their filenames, so every compositor rule keyed on them holds.
The main collection's art in traits/ is never modified.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cc_common as cc  # noqa: E402

SRC = cc.REPO_ROOT / "traits" / "what_are_thosez"
OUT = cc.ASSETS / "what_are_thosez"
SS = 4
CORE = 0.6           # object alpha threshold: above any baked shadow
SMOOTH = 1.0         # outline smoothing, final px
RIM = 4.0            # rim recoloured from this far inside, final px -- measured:
                     # the baked rings run 3-4px deep (Bunny, Gorbhouse dark,
                     # Shiba light), so a 2px rim left half of each behind
OPENING = 200        # an enclosed hole this big is part of the design
MAX_SOLE_SHIFT = 2


def fill_small_holes(mask, max_px=OPENING):
    """Fill pinholes; keep real openings (the Gorbhouse lid handles, 496 and
    775 px, and a 255 px gap in the Pepe base)."""
    holes = ndimage.binary_fill_holes(mask) & ~mask
    lab, n = ndimage.label(holes)
    if not n:
        return mask
    sizes = ndimage.sum(holes, lab, range(1, n + 1))
    small = np.zeros(n + 1, bool)
    small[1:] = sizes < max_px
    return mask | small[lab]


def solid_bbox(a):
    ys, xs = np.nonzero(a > 200)
    return xs.min(), ys.min(), xs.max(), ys.max()


def recut(path):
    rgba = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32)
    a = rgba[..., 3] / 255
    rgb = rgba[..., :3]

    core = a >= CORE
    lab, n = ndimage.label(core, structure=np.ones((3, 3)))
    if n > 1:
        sizes = ndimage.sum(core, lab, range(1, n + 1))
        keep = np.zeros(n + 1, bool)
        keep[1:] = sizes >= 0.02 * sizes.max()
        core = keep[lab]
    core = fill_small_holes(core)

    # smooth at 4x, inside a padded crop around the object
    ys, xs = np.nonzero(core)
    pad = 12
    y0, y1 = max(0, ys.min() - pad), min(a.shape[0], ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(a.shape[1], xs.max() + pad + 1)
    crop = core[y0:y1, x0:x1].astype(np.float32)
    big = np.asarray(Image.fromarray((crop * 255).astype(np.uint8)).resize(
        ((x1 - x0) * SS, (y1 - y0) * SS), Image.Resampling.BILINEAR)) / 255.0
    big = ndimage.gaussian_filter(big, SMOOTH * SS) > 0.5
    big = fill_small_holes(big, OPENING * SS * SS)
    small = np.asarray(Image.fromarray((big * 255).astype(np.uint8)).resize(
        (x1 - x0, y1 - y0), Image.Resampling.BOX)).astype(np.float32) / 255
    new_a = np.zeros_like(a)
    new_a[y0:y1, x0:x1] = small

    # rim colour from at least RIM px inside the object
    inside = ndimage.distance_transform_edt(new_a > 0.5)
    trusted = (inside >= RIM) & (a >= 0.95)
    _, (iy, ix) = ndimage.distance_transform_edt(~trusted, return_indices=True)
    rim = (new_a > 0) & ~trusted
    out_rgb = rgb.copy()
    out_rgb[rim] = rgb[iy[rim], ix[rim]]
    out_rgb[new_a == 0] = 0

    out = np.dstack([out_rgb, new_a * 255]).round().clip(0, 255).astype(np.uint8)
    before, after = solid_bbox(rgba[..., 3]), solid_bbox(out[..., 3])
    shift = max(abs(int(p) - int(q)) for p, q in zip(before, after))
    assert shift <= MAX_SOLE_SHIFT, f"{path.name}: solid bbox moved {before} -> {after}"
    removed = int(((a > 0.02) & (new_a == 0)).sum())
    return Image.fromarray(out, "RGBA"), before, after, removed


SETS = {
    "Bunny": ["layer-Bunny_Slippers_Base (1).png", "layer-Bunny_Slippers_Overlay (1).png"],
    "Shiba": ["layer-Shiba_Base (1).png", "layer-Shiba_Overlay_Left (1).png",
              "layer-Shiba_Overlay_Right (1).png"],
    "Pepe": ["layer-Pepe_Base (1).png", "layer-Pepe_Overlay (1).png"],
    "Cookie Monster": ["Cookie_Monster_Slippers_Base.png", "Cookie_Monster_Slippers_Overlay.png"],
    "Gorbhouse": ["Gorbhouse_base.png", "Gorbhouse_overlay.png"],
}


def sheet(path):
    """Before / after, each pair composited as worn, over dark and light."""
    rows = []
    for name, files in SETS.items():
        pair = []
        for folder in (SRC, OUT):
            im = Image.new("RGBA", (cc_canvas(), cc_canvas()), (0, 0, 0, 0))
            for f in files:
                im.alpha_composite(Image.open(folder / f).convert("RGBA"))
            pair.append(im.crop((320, 800, 1140, 1290)))
        tile = Image.new("RGB", (820 * 4, 490))
        for j, im in enumerate(pair):
            for k, col in enumerate([(28, 28, 34), (214, 214, 208)]):
                bg = Image.new("RGBA", im.size, col + (255,))
                bg.alpha_composite(im)
                tile.paste(bg.convert("RGB"), ((k * 2 + j) * 820, 0))
        rows.append(tile)
    out = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)))
    for i, r in enumerate(rows):
        out.paste(r, (0, i * r.height))
    out.save(path, quality=92)


def cc_canvas():
    return 1393


def trim_base(base, overlays, near=8, grow=12):
    """Trim the base's crescent outside its overlay(s); keep stubs and heel."""
    b = np.asarray(base).copy()
    O = np.zeros(b.shape[:2], bool)
    for o in overlays:
        O |= np.asarray(o)[..., 3] > 127
    B = b[..., 3] > 0
    peek = B & ~O
    d = ndimage.distance_transform_edt(~O)
    seeds = peek & (d > near)
    own = ndimage.binary_dilation(seeds, mask=peek, iterations=grow) if seeds.any() else seeds
    keep = ndimage.binary_dilation(O, iterations=1) | own
    cut = int((B & ~keep).sum())
    b[~keep] = 0
    return Image.fromarray(b, "RGBA"), cut


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sheet", help="write a before/after sheet here")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for files in SETS.values():
        done = {}
        for f in files:
            img, before, after, removed = recut(SRC / f)
            done[f] = img
            print(f"{f:40s} solid {before} -> {after}, {removed} px of halo/shadow/debris removed")
        base = next(f for f in files if "_base" in f.lower())
        trimmed, cut = trim_base(done[base], [done[f] for f in files if f != base])
        sb0 = solid_bbox(np.asarray(done[base])[..., 3])
        sb1 = solid_bbox(np.asarray(trimmed)[..., 3])
        # the trim pulls the base's SIDES in to its overlay by design; what
        # placement depends on is the sole line, so that is what must hold
        assert abs(int(sb0[3]) - int(sb1[3])) <= MAX_SOLE_SHIFT, (base, sb0, sb1)
        done[base] = trimmed
        print(f"{base:40s} trimmed {cut} px of crescent outside its overlay; "
              f"solid {sb0} -> {sb1}")
        for f, img in done.items():
            img.save(OUT / f, optimize=True)
    if args.sheet:
        sheet(args.sheet)
        print(f"sheet -> {args.sheet}")


if __name__ == "__main__":
    main()
