#!/usr/bin/env python3
"""Register an AI-enhanced skin ball back onto the 1393x1393 trait canvas.

An image generator hands back a ball at some arbitrary size, usually on a flat
green/magenta key field rather than real transparency. The compositor needs the
opposite: a 1393x1393 RGBA canvas with the ball at an exact size and an exact
centre, because the eyes and mouth are drawn at fixed canvas coordinates and
will not move to meet a ball that has drifted.

This does the whole conversion:
  1. key out a flat backdrop (auto-detects green or magenta) and despill the
     colour that bled into the edge pixels
  2. optionally drop stray specks left over from keying
  3. crop to the ball, resize it to the target trait's measured footprint, and
     paste it onto a transparent 1393x1393 canvas at the target's centre
  4. re-measure the result and report what the compositor will do with it

Target geometry is measured live from the skin file being replaced, so it stays
correct if the assets change. Nothing is overwritten unless you pass --replace.

Usage (from repo root):
  python3 asset_assessment/register_skin.py enhanced.png "layer-Skin_Black (3).png"
  python3 asset_assessment/register_skin.py enhanced.png "layer-Skin_Gold_Foil (1).png" \
      --preview /tmp/gold_ab.png            # before/after comparison
  python3 asset_assessment/register_skin.py enhanced.png "layer-Skin_Alien (2).png" \
      --replace                             # write into traits/skinz/

See SKIN_ENHANCE_PROMPTS.md for the prompts that produce the input, and for
the acceptance checklist to run against the preview.
"""

import argparse
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator  # noqa: E402

ALPHA_THRESH = 128  # matches generator._opaque_bbox
KEYS = {
    # name: (backdrop rgb, channel metric)
    "green": (0, 255, 0),
    "magenta": (255, 0, 255),
}


# ── keying ──────────────────────────────────────────────────────────────

def _keyness(im, key):
    """Per-pixel 'how much like the backdrop' map, 0..255 (L mode).

    green:   G above the brighter of R/B
    magenta: the dimmer of R/B above G
    """
    r, g, b = im.convert("RGB").split()
    if key == "green":
        return ImageChops.subtract(g, ImageChops.lighter(r, b))
    return ImageChops.subtract(ImageChops.darker(r, b), g)


def detect_key(im):
    """Guess the backdrop from the image corners. Returns a key name or None."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    inset = max(2, min(w, h) // 100)
    corners = [(inset, inset), (w - 1 - inset, inset),
               (inset, h - 1 - inset), (w - 1 - inset, h - 1 - inset)]

    # An image that is already properly cut out has transparent corners.
    if im.mode == "RGBA":
        alpha = im.getchannel("A")
        if all(alpha.getpixel(c) < ALPHA_THRESH for c in corners):
            return None

    scores = {}
    for key in KEYS:
        km = _keyness(rgb, key)
        scores[key] = sum(km.getpixel(c) for c in corners) / len(corners)
    best = max(scores, key=scores.get)
    return best if scores[best] >= 60 else None


def apply_key(im, key, tol, soft, despill):
    """Knock the backdrop out to alpha 0 and pull its colour off the fringe."""
    im = im.convert("RGBA")
    keyness = _keyness(im, key)

    # keyness <= tol stays fully opaque; >= tol+soft is fully cut; linear
    # between the two so the anti-aliased rim keeps a soft edge.
    span = max(1, soft)
    lut = [255 if v <= tol else
           (0 if v >= tol + span else round(255 * (1 - (v - tol) / span)))
           for v in range(256)]
    cut = keyness.point(lut)
    im.putalpha(ImageChops.darker(im.getchannel("A"), cut))

    if despill:
        r, g, b, a = im.split()
        if key == "green":
            # green may not sit above the brighter of the other two channels
            excess = ImageChops.subtract(g, ImageChops.lighter(r, b))
            g = ImageChops.subtract(g, excess)
        else:
            # magenta lifts R and B together above G; pull the shared excess
            # off both so the hue difference between them survives
            excess = ImageChops.subtract(ImageChops.darker(r, b), g)
            r = ImageChops.subtract(r, excess)
            b = ImageChops.subtract(b, excess)
        im = Image.merge("RGBA", (r, g, b, a))
    return im


# ── cleanup ─────────────────────────────────────────────────────────────

def drop_strays(im, min_blob):
    """Keep only the largest opaque blob; erase specks left by keying."""
    mask = im.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESH else 0)
    w, h = mask.size
    px = mask.load()
    seen = bytearray(w * h)
    blobs = []  # (size, [pixels])

    for sy in range(h):
        for sx in range(w):
            if px[sx, sy] == 0 or seen[sy * w + sx]:
                continue
            stack, cells = [(sx, sy)], []
            seen[sy * w + sx] = 1
            while stack:
                x, y = stack.pop()
                cells.append((x, y))
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] \
                            and px[nx, ny]:
                        seen[ny * w + nx] = 1
                        stack.append((nx, ny))
            blobs.append((len(cells), cells))

    if len(blobs) <= 1:
        return im, 0
    blobs.sort(key=lambda b: b[0], reverse=True)
    alpha = im.getchannel("A")
    ap = alpha.load()
    removed = 0
    for size, cells in blobs[1:]:
        if size > min_blob:
            continue  # big enough to be intentional; leave it and warn
        for x, y in cells:
            ap[x, y] = 0
        removed += 1
    im.putalpha(alpha)
    return im, removed


def opaque_bbox(im):
    mask = im.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESH else 0)
    return mask.getbbox()


# ── main flow ───────────────────────────────────────────────────────────

def parse_args():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("enhanced", help="the AI-generated ball image")
    ap.add_argument("target", help="skin filename in traits/skinz/ to match")
    ap.add_argument("--key", choices=["auto", "green", "magenta", "none"],
                    default="auto", help="backdrop to knock out (default auto)")
    ap.add_argument("--tol", type=int, default=40,
                    help="keyness below this stays fully opaque")
    ap.add_argument("--soft", type=int, default=40,
                    help="keyness width of the soft edge above --tol")
    ap.add_argument("--no-despill", action="store_true",
                    help="keep backdrop colour that bled into the fringe")
    ap.add_argument("--fit", choices=["exact", "contain"], default="exact",
                    help="exact: match the target W and H (may stretch); "
                         "contain: keep the source aspect inside that box")
    ap.add_argument("--shrink", type=int, default=0,
                    help="erode the alpha edge by N px to kill a halo")
    ap.add_argument("--keep-strays", action="store_true",
                    help="do not remove specks outside the main blob")
    ap.add_argument("--min-blob", type=int, default=256,
                    help="stray blobs larger than this are kept and warned about")
    ap.add_argument("--out", default=None,
                    help="output path (default output/skinz_registered/<target>)")
    ap.add_argument("--replace", action="store_true",
                    help="write straight into traits/skinz/<target>")
    ap.add_argument("--preview", default=None,
                    help="write a before/after comparison PNG here")
    return ap.parse_args()


def main():
    args = parse_args()
    skin_dir = os.path.join(generator.TRAITS_DIR, generator.SKINZ)
    target_path = os.path.join(skin_dir, args.target)
    if not os.path.exists(target_path):
        sys.exit(f"no such skin: {target_path}\n"
                 f"available: {', '.join(generator.get_files(generator.SKINZ))}")

    # target footprint, measured from the asset being replaced
    tx0, ty0, tx1, ty1 = generator._opaque_bbox(target_path)
    tw, th = tx1 - tx0, ty1 - ty0
    tcx, tcy = (tx0 + tx1) // 2, (ty0 + ty1) // 2
    print(f"target  {args.target}")
    print(f"        {tw}x{th} px, centre ({tcx}, {tcy}) on "
          f"{generator.CANVAS_SIZE}x{generator.CANVAS_SIZE}")

    # measured/loaded up front: --replace overwrites this very file
    widest_eyes = os.path.join(
        generator.TRAITS_DIR, generator.EYEZ,
        max(generator.get_files(generator.EYEZ),
            key=lambda f: (lambda b: b[2] - b[0])(generator._opaque_bbox(
                os.path.join(generator.TRAITS_DIR, generator.EYEZ, f)))))
    old_fit, _ = generator.ball_fit(target_path, widest_eyes)
    before_img = Image.open(target_path).convert("RGBA")

    src = Image.open(args.enhanced).convert("RGBA")
    print(f"source  {os.path.basename(args.enhanced)}  {src.width}x{src.height}")

    key = detect_key(src) if args.key == "auto" else (
        None if args.key == "none" else args.key)
    if key:
        print(f"        keying out {key} backdrop "
              f"(tol {args.tol}, soft {args.soft})")
        src = apply_key(src, key, args.tol, args.soft, not args.no_despill)
    else:
        print("        no backdrop keyed (already transparent, or --key none)")
        if src.getchannel("A").getextrema()[0] == 255:
            print("        WARNING: image is fully opaque — nothing to cut out. "
                  "Pass --key green/magenta if it has a flat backdrop.")

    if args.shrink:
        alpha = src.getchannel("A")
        for _ in range(args.shrink):
            alpha = alpha.filter(ImageFilter.MinFilter(3))
        src.putalpha(alpha)
        print(f"        eroded alpha edge by {args.shrink}px")

    if not args.keep_strays:
        src, removed = drop_strays(src, args.min_blob)
        if removed:
            print(f"        removed {removed} stray speck(s)")

    bbox = opaque_bbox(src)
    if bbox is None:
        sys.exit("nothing opaque left after keying — try a higher --tol")
    ball = src.crop(bbox)
    bw, bh = ball.size
    print(f"        ball found at {bw}x{bh} "
          f"(aspect {bw/bh:.3f} vs target {tw/th:.3f})")

    if args.fit == "exact":
        ball = ball.resize((tw, th), Image.LANCZOS)
        px, py = tx0, ty0
        if abs(bw / bh - tw / th) > 0.04:
            print(f"        note: stretched {abs(bw/bh - tw/th)/(tw/th)*100:.1f}% "
                  f"to hit the target footprint — use --fit contain to avoid it")
    else:
        scale = min(tw / bw, th / bh)
        nw, nh = max(1, round(bw * scale)), max(1, round(bh * scale))
        ball = ball.resize((nw, nh), Image.LANCZOS)
        px, py = tcx - nw // 2, tcy - nh // 2
        print(f"        scaled to {nw}x{nh}, centred (aspect preserved)")

    canvas = Image.new("RGBA", (generator.CANVAS_SIZE, generator.CANVAS_SIZE),
                       (0, 0, 0, 0))
    canvas.paste(ball, (px, py), ball)

    out = args.out or (target_path if args.replace else os.path.join(
        "output", "skinz_registered", args.target))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    canvas.save(out)

    # ── verify ──────────────────────────────────────────────────────────
    rx0, ry0, rx1, ry1 = opaque_bbox(canvas)
    rcx, rcy = (rx0 + rx1) // 2, (ry0 + ry1) // 2
    dx, dy = rcx - tcx, rcy - tcy
    print(f"\nwrote   {out}")
    print(f"        {rx1-rx0}x{ry1-ry0} px, centre ({rcx}, {rcy})  "
          f"drift ({dx:+d}, {dy:+d})")
    if abs(dx) > 1 or abs(dy) > 1:
        print("        WARNING: centre drifted — eyes will not sit in the ball")

    generator._bbox_cache.pop(out, None)  # may be the file we just overwrote
    new_fit, _ = generator.ball_fit(out, widest_eyes)
    print(f"        ball_fit upscale {old_fit:.3f}x -> {new_fit:.3f}x "
          f"(vs widest eyes, {os.path.basename(widest_eyes)})")

    if args.preview:
        write_preview(before_img, canvas, args.preview)
        print(f"        preview {args.preview}")

    if not args.replace and out != target_path:
        print(f"\nnot installed. To use it:  cp '{out}' '{target_path}'"
              f"\n(or re-run with --replace)")


def write_preview(before_img, after_img, out_path, pad=24, cell=520):
    """Side-by-side of the old and new ball on neutral gray, at trait scale."""
    tiles = []
    for label, im in (("before", before_img), ("after", after_img)):
        x0, y0, x1, y1 = opaque_bbox(im)
        crop = im.crop((x0 - pad, y0 - pad, x1 + pad, y1 + pad))
        plate = Image.new("RGBA", crop.size, (128, 128, 128, 255))
        plate.alpha_composite(crop)
        tiles.append((label, plate.convert("RGB").resize(
            (cell, round(cell * crop.height / crop.width)), Image.LANCZOS)))

    h = max(t.height for _, t in tiles)
    sheet = Image.new("RGB", (sum(t.width for _, t in tiles), h + 30), (20, 20, 20))
    try:
        fnt = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    except OSError:
        fnt = ImageFont.load_default()
    draw = ImageDraw.Draw(sheet)
    x = 0
    for label, tile in tiles:
        sheet.paste(tile, (x, 0))
        draw.text((x + 6, h + 6), label, fill=(235, 235, 235), font=fnt)
        x += tile.width
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    sheet.save(out_path)


if __name__ == "__main__":
    main()
