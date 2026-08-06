#!/usr/bin/env python3
"""Rebuild trait assets from an AI-enhanced reference sheet.

When a generator is handed catalog/<class>_reference_sheet.png it tends to
return the whole SHEET re-rendered rather than one asset per image: flat RGB,
the gray matte and sheet chrome baked in, reflowed to whatever aspect ratio the
model outputs, often with a drop shadow added. This recovers canvas-ready
assets from that.

The naive approach — key out the matte and keep what is left — fails on this
art. A mid-gray matte sits inside the tonal range of half the assets: the
shadow side of every skin ball and the whole of the Cyborg eye's metal bezel
key out along with the background, punching holes through them.

So instead of trusting the model for the silhouette, this transplants:

    SHAPE comes from the original asset's alpha channel.
    TEXTURE comes from the enhanced art.

That is also what the pipeline actually needs. The original alpha is exact, so
the footprint, position and proportion are right by construction, the edge is
clean with no matte fringe, and anything the model did to the outline — a
sphere where there was an ellipse, a stretched eye — is corrected rather than
inherited. What survives is the part worth keeping: the rendering.

  1. find the sheet's grid from its label bands (full-width dark rows)
  2. per cell, locate the art by a low threshold, fill its holes, and take the
     largest blob — a bbox only, so tone-matched regions cost nothing
  3. resize that crop to the original asset's footprint, over a plate of its
     own edge colour so no matte can leak in at the rim
  4. apply the original alpha and paste onto a 1393x1393 canvas in place

Cell order matches render_ref_sheet.py, which sorts assets by display name.

  python3 asset_assessment/extract_sheet.py returned.png eyez
  python3 asset_assessment/extract_sheet.py returned.png skinz --debug

Output is canvas-ready — register_trait.py is for the one-asset-per-image path,
and is not needed here. Verify with render_sample_sheet.py before installing.
"""

import argparse
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g  # noqa: E402

CLASSES = {"skinz": g.SKINZ, "eyez": g.EYEZ, "mouthz": g.MOUTHZ}


def parse_args():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheet", help="the returned (enhanced) sheet image")
    ap.add_argument("trait_class", choices=sorted(CLASSES))
    ap.add_argument("--cols", type=int, default=3, help="cells per row")
    ap.add_argument("--tol", type=int, default=20,
                    help="difference from the matte that counts as art when "
                         "locating it (low: only the bbox is taken from this)")
    ap.add_argument("--out-dir", default=None,
                    help="default output/<class>_enhanced")
    ap.add_argument("--debug", action="store_true",
                    help="write a grid+bbox overlay to check the detection")
    return ap.parse_args()


# ── sheet geometry ──────────────────────────────────────────────────────

def chrome_rows(im, dark_frac=0.85, dark_level=70):
    """Rows that are almost entirely dark are sheet chrome (header, labels).

    Deliberately not a row-mean test: a row full of black eye art is dark on
    average too, but it still has plenty of light matte across it.
    """
    lum = im.convert("L")
    w, h = lum.size
    px = lum.load()
    step = max(1, w // 300)
    xs = range(0, w, step)
    return [sum(1 for x in xs if px[x, y] < dark_level) / len(xs) >= dark_frac
            for y in range(h)]


def cell_bands(im, min_frac=0.05):
    """Contiguous runs of non-chrome rows = the rows of matte cells."""
    chrome = chrome_rows(im)
    h = len(chrome)
    runs, start = [], None
    for y, c in enumerate(chrome):
        if not c and start is None:
            start = y
        elif c and start is not None:
            runs.append((start, y))
            start = None
    if start is not None:
        runs.append((start, h))
    return [r for r in runs if r[1] - r[0] > h * min_frac]


# ── locating the art inside a cell ──────────────────────────────────────

def matte_colour(cell):
    """Median of the cell's border ring — the art sits in the middle."""
    w, h = cell.size
    band = max(2, min(w, h) // 14)
    ring = [cell.getpixel((x, y)) for x in range(0, w, 3) for y in (band, h - 1 - band)]
    ring += [cell.getpixel((x, y)) for y in range(0, h, 3) for x in (band, w - 1 - band)]
    return tuple(sorted(c[i] for c in ring)[len(ring) // 2] for i in range(3))


def _components(mask):
    """All 4-connected blobs in an L mask, largest first."""
    w, h = mask.size
    px = mask.load()
    seen = bytearray(w * h)
    blobs = []
    for sy in range(h):
        for sx in range(w):
            if not px[sx, sy] or seen[sy * w + sx]:
                continue
            stack, cells = [(sx, sy)], []
            seen[sy * w + sx] = 1
            while stack:
                x, y = stack.pop()
                cells.append((x, y))
                for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny*w+nx] \
                            and px[nx, ny]:
                        seen[ny*w+nx] = 1
                        stack.append((nx, ny))
            blobs.append(cells)
    blobs.sort(key=len, reverse=True)
    return blobs


def art_bbox(cell, tol):
    """Bounding box of the artwork in a cell.

    Only the BOX is used, so a hole punched through a tone-matched region
    (a gray bezel, a ball's shadow side) does not matter — the extremes of
    the art are always high-contrast against the matte.
    """
    flat = Image.new("RGB", cell.size, matte_colour(cell))
    diff = ImageChops.difference(cell, flat).convert("L")
    mask = diff.point(lambda v: 255 if v > tol else 0)
    # close small gaps so a blob broken by matte-toned pixels stays one blob
    mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))
    blobs = _components(mask)
    if not blobs:
        return None
    # Assets are inset with matte all round them, so anything touching the
    # crop edge is contamination — a neighbouring empty cell bleeding in, or
    # the matte's own gradient. Dropping it stops the bbox over-reaching and
    # dragging background into the texture.
    w, h = mask.size
    def touches_edge(b):
        return any(x <= 1 or y <= 1 or x >= w - 2 or y >= h - 2 for x, y in b)
    inner = [b for b in blobs if not touches_edge(b)]
    if inner:
        blobs = inner
    # an asset can be several blobs (a PAIR of eyes, a stroke plus its dot):
    # keep every blob within an order of magnitude of the biggest
    keep = [b for b in blobs if len(b) >= len(blobs[0]) * 0.04]
    xs = [x for b in keep for x, _ in b]
    ys = [y for b in keep for _, y in b]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def edge_extend(rgb, tol, radius=None):
    """Bleed the art's own colour outward over the matte around it.

    The original alpha is often a hair larger than the model's version of the
    art, and wherever it reaches past it the matte shows through as a gray
    fringe — a halo around each eye, a crescent on a ball's rim. Filling the
    surround with a single averaged colour does not help: for art that does
    not fill its bounding box, that average IS the matte.

    So push the art's colours outward instead (premultiplied push-pull): blur
    the art with the background masked off, blur the mask the same way, and
    divide, giving every background pixel the average of the real art near it.
    """
    from PIL import ImageMath

    flat = Image.new("RGB", rgb.size, matte_colour(rgb))
    diff = ImageChops.difference(rgb, flat).convert("L")
    mask = diff.point(lambda v: 255 if v > tol else 0)
    mask = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))
    if mask.getbbox() is None:
        return rgb

    r = radius or max(6, max(rgb.size) // 8)
    mb = mask.filter(ImageFilter.BoxBlur(r))
    bands = []
    for band in rgb.split():
        pm = ImageChops.multiply(band, mask)
        pmb = pm.filter(ImageFilter.BoxBlur(r))
        # average of known neighbours; where nothing is known, keep as-is
        # image operand must come first: ImageMath dispatches on it
        bands.append(ImageMath.lambda_eval(
            lambda args: args["convert"](
                args["min"](args["a"] * 255 / args["max"](args["b"], 1), 255),
                "L"),
            a=pmb, b=mb))
    filled = Image.merge("RGB", bands)
    filled.paste(rgb, (0, 0), mask)   # real art wins wherever it exists
    return filled


# ── main ────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    trait_dir = CLASSES[args.trait_class]
    files = sorted(g.get_files(trait_dir),
                   key=lambda f: g.trait_name(trait_dir, f))

    im = Image.open(args.sheet).convert("RGB")
    bands = cell_bands(im)
    rows_needed = (len(files) + args.cols - 1) // args.cols
    print(f"sheet   {os.path.basename(args.sheet)}  {im.width}x{im.height}")
    print(f"        {len(bands)} cell rows detected (need {rows_needed})")
    if len(bands) < rows_needed:
        sys.exit("could not find enough cell rows — check --cols, or the "
                 "sheet layout changed")

    out_dir = args.out_dir or os.path.join(
        "output", f"{args.trait_class}_enhanced")
    os.makedirs(out_dir, exist_ok=True)

    overlay = im.copy()
    draw = ImageDraw.Draw(overlay)
    cw = im.width // args.cols
    print(f"\n{'asset':18s} {'found':>11s} {'aspect vs original':>19s}  target")
    i = 0
    for (y0, y1) in bands[:rows_needed]:
        for c in range(args.cols):
            if i >= len(files):
                break
            fname = files[i]
            i += 1
            label = g.trait_name(trait_dir, fname)
            cx0, cy0 = c * cw + 4, y0 + 4
            cell = im.crop((cx0, cy0, (c + 1) * cw - 4, y1 - 4))
            bb = art_bbox(cell, args.tol)
            if bb is None:
                print(f"{label:18s} NO ART FOUND")
                continue
            draw.rectangle((cx0 + bb[0], cy0 + bb[1], cx0 + bb[2], cy0 + bb[3]),
                           outline=(255, 80, 0), width=3)

            src = cell.crop(bb)
            # the original asset supplies shape, position and proportion
            path = os.path.join(g.TRAITS_DIR, trait_dir, fname)
            ox0, oy0, ox1, oy1 = g._opaque_bbox(path)
            tw, th = ox1 - ox0, oy1 - oy0
            orig_alpha = Image.open(path).convert("RGBA").crop(
                (ox0, oy0, ox1, oy1)).getchannel("A")

            # bleed the art outward first, so wherever the original silhouette
            # reaches past the model's version it picks up art colour, not matte
            plate = edge_extend(src, args.tol)
            tex = plate.resize((tw, th), Image.LANCZOS).convert("RGBA")
            tex.putalpha(orig_alpha)

            canvas = Image.new("RGBA", (g.CANVAS_SIZE, g.CANVAS_SIZE),
                               (0, 0, 0, 0))
            # no mask argument: paste(im, box, im) composites the alpha against
            # itself, squaring it, which eats the anti-aliased edge and shrinks
            # the footprint by a pixel. The canvas is empty here, so a straight
            # block copy is both correct and exact.
            canvas.paste(tex, (ox0, oy0))
            canvas.save(os.path.join(out_dir, fname))

            sw, sh = bb[2] - bb[0], bb[3] - bb[1]
            err = ((sw / sh) / (tw / th) - 1) * 100
            print(f"{label:18s} {sw:5d}x{sh:<5d} {err:+18.1f}%  {tw}x{th} "
                  f"@({ox0},{oy0})")

    if args.debug:
        # deliberately NOT inside out_dir: that directory gets copied wholesale
        # into traits/, and any stray .png there would register as an asset
        dbg = os.path.join("output", f"{args.trait_class}_grid_debug.png")
        overlay.save(dbg)
        print(f"\ngrid overlay {dbg}")
    print(f"\nwrote {i} canvas-ready assets to {out_dir}/")
    print("aspect % is how far the model's version drifted; it has been "
          "corrected back to the original footprint")


if __name__ == "__main__":
    main()
