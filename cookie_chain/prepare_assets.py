#!/usr/bin/env python3
"""Build the Cookie Chain Edition stickers and edition plaque from source art.

    python3 cookie_chain/prepare_assets.py            # stickers + plaque
    python3 cookie_chain/prepare_assets.py --sheet    # also write a review sheet

Sources live in cookie_chain/assets/sticker_sources/ (the nine legacy Cookie
Chain overlays and the thirteen official dapp logos) and
cookie_chain/assets/plaque_source.png. Outputs are full 1393x1393 overlays in
cookie_chain/assets/stickerz/ and cookie_chain/assets/branding/.

WHY THIS EXISTS. The previous release's stickers were the source art scaled
into a corner with a 6px white outline grown by a SQUARE max-filter over the
raw alpha. That outline followed every defect in the alpha it was grown from:
a dotted grey halo round Out of Order, a ragged fur line on Shorts Doggo, a
dark matte ring inside the white on Real as a Doughnut and Candy Shop, and
interiors that were never opaque (Cookiebox reads alpha ~0.94 across the whole
cube, so the plate showed through it). Each sticker was also sized by its
longest side alone, so a wordmark came out 40px tall beside a 200px badge.

What a sticker is here -- one die-cut vinyl piece:

1. DEBRIS OUT. Anything not attached to the artwork is dropped: components
   under 2% of the largest that are not enclosed by it.
2. A SOLID CORE. The art's own alpha is thresholded, its holes filled, and the
   result smoothed -- so the art is fully opaque inside its silhouette and the
   fringe is one clean anti-aliased edge, not a semi-transparent smear.
3. COLOUR FROM THE ART, NOT THE MATTE. Edge pixels whose alpha the source
   left low are recoloured from the nearest trusted pixel (distance
   transform), so no dark or grey matte survives at the boundary.
4. ONE DIE-CUT. The core is closed (bridging letter gaps and tiny notches),
   dilated by a EUCLIDEAN distance -- round corners, not the square ones a
   max-filter makes -- smoothed, and filled white. Everything is built at 4x
   and resampled down premultiplied, so the cut is anti-aliased.
5. A CAST SHADOW down and to the right, from the collection's top-left key
   light, so the piece sits ON the plate rather than being pasted over it.
6. SIZED BY AREA. Every sticker's die-cut targets the same area inside one
   bounding box, so a round badge, a tall character and a wide wordmark all
   carry the same visual weight in the corner.

Alpha outside the die-cut is exactly 0 and the run asserts each output is one
connected piece (shadow excluded).
"""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

CC_ROOT = Path(__file__).resolve().parent
ASSETS = CC_ROOT / "assets"
SRC = ASSETS / "sticker_sources"
OUT = ASSETS / "stickerz"
PLAQUE_SRC = ASSETS / "plaque_source.png"
PLAQUE_OUT = ASSETS / "branding" / "cookie_chain_edition.png"

CANVAS = 1393
SS = 4                      # supersampling factor for every mask operation

# ---- placement: the bottom-left corner, mirrored by the plaque -------------
STICKER_CENTER_X = 188
STICKER_BOTTOM_Y = 1348      # die-cut bottom; the plaque body ends at 1365
TARGET_AREA = 27000          # die-cut px^2 at final size (a 185px disc)
MAX_W, MAX_H = 238, 212      # die-cut box, final px
WORDMARK_MAX_W = 286         # a wide wordmark may run longer, never taller

BORDER = 6.5                 # white border width, final px
SHADOW = {"dx": 3, "dy": 4, "blur": 4.5, "opacity": 0.42}

# Per-sticker treatment. `core`: alpha threshold for the solid core (higher
# cuts a soft halo off). `close`: gap bridged by the die-cut, final px.
# `shape`: replace the silhouette with a geometric badge for square app icons.
# `open`: px of opening on the core (removes a fuzzy dotted halo).
# `soft`: keep the source's own soft edge (fur) over the white backing.
STICKERS = {
    # legacy Cookie Chain overlays
    "Anime_Detective.png": ("legacy/Anime_Detective.png", {}),
    "Armed_Hero.png": ("legacy/Armed_Hero.png", {}),
    "Chibi_Monster.png": ("legacy/Chibi_Monster.png", {"core": 0.55}),
    "Cookiebox.png": ("legacy/Cookiebox.png", {}),
    "Emyr.png": ("legacy/Emyr.png", {}),
    "Morsel.png": ("legacy/Morsel.png", {"core": 0.6}),
    "Out_Of_Order.png": ("legacy/Out_Of_Order.png", {"core": 0.8, "open": 1.5}),
    "Poptart_Cat.png": ("legacy/Poptart_Cat.png", {"close": 4}),
    "Shorts_Doggo.png": ("legacy/Shorts_Doggo.png", {"soft": True, "close": 5}),
    # official Cookie Chain Apps Registry logos
    "Baked_Bazaar.png": ("dapp_logos/baked_bazaar.png", {"shape": "circle"}),
    "Candy_Shop.png": ("dapp_logos/candy_shop.png", {}),
    "CookBook.png": ("dapp_logos/cook_book.png", {"close": 11, "wordmark": True}),
    "CookOven.png": ("dapp_logos/cook_oven.png", {"close": 11, "wordmark": True}),
    "Cookie_Chat.png": ("dapp_logos/cookie_chat.png", {}),
    "Cookie_Lock.png": ("dapp_logos/cookie_lock.png", {"close": 11, "wordmark": True}),
    "Cookie_MCP.png": ("dapp_logos/cookie_mcp.png", {}),
    "Cookie_Quads.png": ("dapp_logos/cookie_quads.png", {"shape": "circle", "ring": True}),
    "CookieScan.png": ("dapp_logos/cookie_scan.png", {"shape": "circle", "ring": True}),
    "CookieSwap.png": ("dapp_logos/cookie_swap.png", {"shape": "circle"}),
    "GORBOY.png": ("dapp_logos/gorboy.png", {"shape": "circle", "inset": 0.035}),
    "MomoSwap.png": ("dapp_logos/momo_swap.png", {"core": 0.6}),
    "Nightly_Wallet.png": ("dapp_logos/nightly_wallet.png", {"shape": "roundrect"}),
}


# ---- helpers ----------------------------------------------------------------

def disk_close(mask, r):
    """Binary closing with a Euclidean disk of radius r (px)."""
    if r <= 0:
        return mask
    pad = int(np.ceil(r)) + 2
    m = np.pad(mask, pad)
    grown = ndimage.distance_transform_edt(~m) <= r
    shrunk = ndimage.distance_transform_edt(grown) > r
    return shrunk[pad:-pad, pad:-pad]


def disk_open(mask, r):
    if r <= 0:
        return mask
    eroded = ndimage.distance_transform_edt(mask) > r
    return ndimage.distance_transform_edt(~eroded) <= r


def smooth_mask(mask, sigma):
    """Round off stair-steps: blur a binary mask and re-threshold at 0.5."""
    return ndimage.gaussian_filter(mask.astype(np.float32), sigma) > 0.5


def fill_small_holes(mask, max_frac=0.015):
    """Fill enclosed holes smaller than max_frac of the mask's area."""
    holes = ndimage.binary_fill_holes(mask) & ~mask
    lab, n = ndimage.label(holes)
    if n == 0:
        return mask
    sizes = ndimage.sum(holes, lab, range(1, n + 1))
    small = np.zeros(n + 1, bool)
    small[1:] = sizes < max_frac * mask.sum()
    return mask | small[lab]


def drop_debris(alpha):
    """Zero every piece of the alpha not attached to the artwork."""
    lab, n = ndimage.label(alpha > 0.03, structure=np.ones((3, 3)))
    if n <= 1:
        return alpha
    sizes = ndimage.sum(np.ones_like(alpha), lab, range(1, n + 1))
    biggest = sizes.max()
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes >= 0.02 * biggest
    hull = ndimage.binary_fill_holes(np.isin(lab, np.nonzero(keep)[0]))
    for i in range(1, n + 1):
        if not keep[i] and hull[lab == i].all():
            keep[i] = True              # enclosed detail (an eye, a dot)
    return np.where(keep[lab], alpha, 0.0)


def resize_premult(rgba, size):
    """Resample an RGBA float array premultiplied, so no matte bleeds in."""
    im = Image.fromarray(np.clip(rgba * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA")
    im = im.convert("RGBa").resize(size, Image.Resampling.LANCZOS).convert("RGBA")
    return np.asarray(im).astype(np.float32) / 255.0


def load_source(path):
    im = Image.open(path).convert("RGBA")
    arr = np.asarray(im).astype(np.float32) / 255.0
    arr[..., 3] = drop_debris(arr[..., 3])
    a = arr[..., 3]
    ys, xs = np.nonzero(a > 0.03)
    pad = 2
    y0, y1 = max(0, ys.min() - pad), min(a.shape[0], ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(a.shape[1], xs.max() + pad + 1)
    return arr[y0:y1, x0:x1].copy()


def geometric_shape(arr, shape, inset=0.0):
    """Square app icons become a clean badge: a disc or a rounded square."""
    h, w = arr.shape[:2]
    side = max(h, w)
    sq = np.zeros((side, side, 4), np.float32)
    oy, ox = (side - h) // 2, (side - w) // 2
    sq[oy:oy + h, ox:ox + w] = arr
    # fill any transparent corner with the icon's own edge colour first
    a = sq[..., 3]
    if (a < 0.99).any():
        _, (iy, ix) = ndimage.distance_transform_edt(a < 0.99, return_indices=True)
        sq[..., :3] = sq[..., :3][iy, ix]
    big = side * SS
    m = Image.new("L", (big, big), 0)
    e = inset * big
    if shape == "circle":
        ImageDraw.Draw(m).ellipse((e, e, big - 1 - e, big - 1 - e), fill=255)
    else:
        ImageDraw.Draw(m).rounded_rectangle((e, e, big - 1 - e, big - 1 - e),
                                            radius=big * 0.2, fill=255)
    m = np.asarray(m.resize((side, side), Image.Resampling.LANCZOS)).astype(np.float32) / 255
    sq[..., 3] = m
    return sq


def build_sticker(name, src, opts, art_long):
    """Return (RGBA uint8 sticker cropped to its die-cut + shadow, die-cut
    alpha bbox inside it, die-cut area) with the art's longest side at
    `art_long` final px."""
    arr = load_source(src)
    if opts.get("shape"):
        arr = geometric_shape(arr, opts["shape"], opts.get("inset", 0.0))
    h, w = arr.shape[:2]
    s = art_long * SS / max(h, w)
    wsz = (max(1, round(w * s)), max(1, round(h * s)))
    work = resize_premult(arr, wsz)
    a = work[..., 3]

    # 2. solid core
    core = a > opts.get("core", 0.5)
    if opts.get("open"):
        core = disk_open(core, opts["open"] * SS)
    lab, n = ndimage.label(core)
    if n > 1:
        sizes = ndimage.sum(core, lab, range(1, n + 1))
        hull = ndimage.binary_fill_holes(lab == (np.argmax(sizes) + 1))
        keep = [i + 1 for i, sz in enumerate(sizes)
                if sz >= 0.02 * sizes.max() or hull[lab == i + 1].all()]
        core = np.isin(lab, keep)
    # Pinholes in the alpha are defects (Out of Order's body is peppered with
    # them); a real opening -- the inside of the chat bubble, MomoSwap's ring
    # -- is part of the design and stays open, so the white backing shows.
    core = fill_small_holes(core)
    core = smooth_mask(core, 0.9 * SS)
    core = fill_small_holes(core)

    # 3. colour from the art: recolour low-confidence pixels from the nearest
    #    trusted one (straight alpha, so divide the premultiplied resample out)
    rgb = np.where(a[..., None] > 1e-4, work[..., :3] / np.maximum(a[..., None], 1e-4), 0)
    rgb = np.clip(rgb, 0, 1)
    trusted = a > 0.85
    if not trusted.any():
        trusted = a > 0.5
    _, (iy, ix) = ndimage.distance_transform_edt(~trusted, return_indices=True)
    rgb = np.where((a > 0.85)[..., None], rgb, rgb[iy, ix])

    art_a = core.astype(np.float32)
    if opts.get("soft"):
        band = ndimage.distance_transform_edt(~core) <= 1.5 * SS
        art_a = np.maximum(art_a, np.where(band, a, 0.0))

    # 4. die-cut: close, grow by a Euclidean border, smooth, fill
    pad = int((BORDER + opts.get("close", 3) + 8) * SS)
    core_p = np.pad(core, pad)
    cut = disk_close(core_p, opts.get("close", 3) * SS)
    cut = ndimage.binary_fill_holes(cut)
    cut = ndimage.distance_transform_edt(~cut) <= BORDER * SS
    cut = smooth_mask(cut, 0.45 * BORDER * SS)
    cut = ndimage.binary_fill_holes(cut)

    H, W = cut.shape
    out = np.zeros((H, W, 4), np.float32)
    white = np.array([1.0, 1.0, 1.0], np.float32)
    out[..., :3] = white
    out[..., 3] = cut
    art = np.zeros((H, W, 4), np.float32)
    art[pad:pad + core.shape[0], pad:pad + core.shape[1], :3] = rgb
    art[pad:pad + core.shape[0], pad:pad + core.shape[1], 3] = art_a
    if opts.get("ring"):
        # a white-field badge on a white border would lose its edge: give it
        # a hairline of its own darkest colour so the disc still reads.
        ring = ndimage.distance_transform_edt(np.pad(core, pad)) <= 0.9 * SS
        ring &= np.pad(core, pad)
        art[..., :3] = np.where(ring[..., None], [0.82, 0.80, 0.78], art[..., :3])
    aa = art[..., 3:4]
    out[..., :3] = art[..., :3] * aa + out[..., :3] * (1 - aa)
    out[..., 3] = np.maximum(out[..., 3], art[..., 3])
    out[..., 3] *= cut                       # nothing outside the cut, ever

    # resample down, premultiplied
    fw, fh = round(W / SS), round(H / SS)
    small = resize_premult(out, (fw, fh))
    small[..., 3] = np.where(small[..., 3] < 1 / 255, 0, small[..., 3])
    # Lanczos rings: a concave notch in the cut leaves 1/255-level specks a
    # pixel or two off the edge after the downsample. Keep the one piece.
    lab, n = ndimage.label(small[..., 3] > 0, structure=np.ones((3, 3)))
    if n > 1:
        sizes = ndimage.sum(np.ones(lab.shape), lab, range(1, n + 1))
        small[..., 3] = np.where(lab == np.argmax(sizes) + 1, small[..., 3], 0)
    cut_small = small[..., 3] > 0.5
    area = int(cut_small.sum())
    ys, xs = np.nonzero(small[..., 3] > 0)
    bbox = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    return small, bbox, area


def compose_with_shadow(small):
    """Cast shadow (down-right, top-left key) under a cropped sticker."""
    a = Image.fromarray((small[..., 3] * 255).astype(np.uint8), "L")
    m = int(SHADOW["blur"] * 3 + max(SHADOW["dx"], SHADOW["dy"]) + 2)
    w, h = a.size
    sh = Image.new("L", (w + 2 * m, h + 2 * m), 0)
    sh.paste(a, (m + SHADOW["dx"], m + SHADOW["dy"]))
    sh = sh.filter(ImageFilter.GaussianBlur(SHADOW["blur"]))
    sh = np.asarray(sh).astype(np.float32) / 255 * SHADOW["opacity"]
    canvas = np.zeros((h + 2 * m, w + 2 * m, 4), np.float32)
    canvas[..., 3] = sh
    st = np.zeros_like(canvas)
    st[m:m + h, m:m + w] = small
    sa = st[..., 3:4]
    outa = sa[..., 0] + canvas[..., 3] * (1 - sa[..., 0])
    outrgb = (st[..., :3] * sa) / np.maximum(outa[..., None], 1e-6)
    res = np.dstack([outrgb, outa])
    return res, m


def make_sticker(name):
    rel, opts = STICKERS[name]
    src = SRC / rel
    art_long = 180.0
    for _ in range(4):                      # converge on area / box targets
        small, bbox, area = build_sticker(name, src, opts, art_long)
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        max_w = WORDMARK_MAX_W if opts.get("wordmark") else MAX_W
        f = min((TARGET_AREA / area) ** 0.5, max_w / bw, MAX_H / bh)
        if abs(f - 1) < 0.01:
            break
        # the border does not scale with the art, so step on the art only
        art_long *= 1 + (f - 1) * (bw / max(1, bw - 2 * BORDER))
    piece, m = compose_with_shadow(small)
    canvas = np.zeros((CANVAS, CANVAS, 4), np.float32)
    cx = (bbox[0] + bbox[2]) / 2 + m
    x = round(STICKER_CENTER_X - cx)
    y = round(STICKER_BOTTOM_Y - (bbox[3] + m))
    ph, pw = piece.shape[:2]
    canvas[y:y + ph, x:x + pw] = piece
    img = Image.fromarray(np.clip(canvas * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA")

    # one piece (shadow excluded), nothing stray
    body = np.zeros((CANVAS, CANVAS), bool)
    body[y:y + ph, x:x + pw] = np.pad(small[..., 3] > 0, m)
    n = ndimage.label(body, structure=np.ones((3, 3)))[1]
    assert n == 1, f"{name}: die-cut is {n} pieces"
    return img, {"die_cut_area": area, "die_cut_w": int(bw), "die_cut_h": int(bh),
                 "art_long": round(art_long, 1), "source": rel, **opts}


# ---- plaque -------------------------------------------------------------------

PLAQUE_PILL = (34.5, 359.5, 1494.5, 640.5)   # fitted to the source's outer rim
PLAQUE_WIDTH = 390
PLAQUE_MARGIN = (30, 28)


def make_plaque():
    src = Image.open(PLAQUE_SRC).convert("RGB")
    x0, y0, x1, y1 = PLAQUE_PILL
    box = (int(x0) - 2, int(y0) - 2, int(np.ceil(x1)) + 3, int(np.ceil(y1)) + 3)
    crop = src.crop(box)
    w, h = crop.size
    m = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        ((x0 - box[0]) * SS, (y0 - box[1]) * SS, (x1 - box[0]) * SS, (y1 - box[1]) * SS),
        radius=(y1 - y0) / 2 * SS, fill=255)
    m = m.resize((w, h), Image.Resampling.LANCZOS)
    rgba = crop.convert("RGBA")
    rgba.putalpha(m)
    th = round(h * PLAQUE_WIDTH / w)
    small = rgba.convert("RGBa").resize((PLAQUE_WIDTH, th), Image.Resampling.LANCZOS).convert("RGBA")
    arr = np.asarray(small).astype(np.float32) / 255
    piece, mg = compose_with_shadow(arr)
    canvas = np.zeros((CANVAS, CANVAS, 4), np.float32)
    x = CANVAS - PLAQUE_MARGIN[0] - PLAQUE_WIDTH - mg
    y = CANVAS - PLAQUE_MARGIN[1] - th - mg
    ph, pw = piece.shape[:2]
    canvas[y:y + ph, x:x + pw] = piece
    return Image.fromarray(np.clip(canvas * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA")


def review_sheet(path):
    names = sorted(STICKERS)
    cell, cols = 300, 8
    fields = [(24, 24, 30), (236, 236, 236), (122, 168, 92)]
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * len(fields) * cell), (0, 0, 0))
    for i, n in enumerate(names):
        im = Image.open(OUT / n).convert("RGBA").crop((38, 1088, 338, 1388))
        for j, col in enumerate(fields):
            bg = Image.new("RGBA", (cell, cell), col + (255,))
            bg.alpha_composite(im)
            sheet.paste(bg.convert("RGB"), ((i % cols) * cell, ((i // cols) * len(fields) + j) * cell))
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sheet", help="write a review sheet to this path")
    ap.add_argument("--only", nargs="*", help="build only these sticker files")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for name in args.only or sorted(STICKERS):
        img, info = make_sticker(name)
        img.save(OUT / name, optimize=True)
        report[name] = info
        print(f"{name:24s} die-cut {info['die_cut_w']}x{info['die_cut_h']} "
              f"area {info['die_cut_area']}")
    if not args.only:
        stale = {p.name for p in OUT.glob("*.png")} - set(STICKERS)
        for s in stale:
            (OUT / s).unlink()
        (OUT / "STICKER_BUILD.json").write_text(json.dumps(report, indent=2) + "\n")
        PLAQUE_OUT.parent.mkdir(parents=True, exist_ok=True)
        make_plaque().save(PLAQUE_OUT, optimize=True)
        print(f"plaque -> {PLAQUE_OUT.relative_to(CC_ROOT.parent)}")
    if args.sheet:
        review_sheet(args.sheet)


if __name__ == "__main__":
    main()
