#!/usr/bin/env python3
"""The scrolling starfield plate: the character reads as flying left to right.

DIFFERENT IN KIND from everything else in dynamic/. The weather states grade
a plate that already exists; this IS the plate. There is no mint art
underneath it to protect, so the protect mask here only decides where the
character sits on top, not what may be touched.

THE MOTION RUNS THE OTHER WAY TO THE ILLUSION. The character is fixed in
frame, so the stars travel RIGHT TO LEFT to read as the character flying
LEFT TO RIGHT. Getting that backwards makes it fly backwards, which is the
one thing everyone notices. The rainbow trail obeys the same rule and for
the same reason, and it DID ship backwards once -- which is why the
direction is now something verify_direction() measures rather than
something a comment claims.

Seamless by the same construction as the weather loops: stars live on a
torus one tile wider than the canvas and travel a WHOLE number of tiles per
loop, so frame N is frame 0. Parallax comes from three depth bands at 1x,
2x and 3x -- the far band is what makes it read as depth rather than as a
texture sliding past.

This module renders the field procedurally. The SHIPPING plate is the
owner's own GIF, upscaled nearest-neighbour (its sparkles are hard-edged
pixel art, and a smooth resample rounds them into blobs); this exists to
prototype the motion, to render a field at any canvas size without a
source, and as the fallback if the art is ever regenerated.

Both paths then draw the 8-BIT RAINBOW TRAIL -- the thing the "Blank" in
Nyan_Blank.gif was blanking -- on the source grid, so it upscales with the
sparkles and shares their pixel size. Its height is per TOKEN rather than
per plate, because it leaves the character's own middle and the cast's
bodies sit 251px apart vertically; see centre_dy().

    python3 dynamic/starfield.py --verify     # THE GATE
    python3 dynamic/starfield.py --write      # rebuild the reference plate
    python3 dynamic/starfield.py --strip x.png
"""

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# The owner's source art, at the repo root.
GIF_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Nyan_Blank.gif")

# The SOURCE field, sampled off the owner's GIF: a single flat colour, no
# gradient. #00008B is X11 "dark blue" rather than navy -- worth naming,
# because navy (#000080) is a different colour and the two get used
# interchangeably. 159,616 of the frame's 160,000 pixels are exactly this.
SOURCE_FIELD = (0, 0, 139)

# The SHIPPING field. Oxford Blue is darker and desaturated against
# #00008B (L* 21.6 vs 15.5, chroma 32 vs 79), which is what the plate
# family is graded for -- cool, desaturated, out of the characters' hue
# bands (see background_pop_studies/grade.py). #00008B is the one saturated
# primary in the set and reads as a flat swatch beside the graded plates;
# Oxford Blue reads as deep space, and the white sparkles gain contrast
# rather than lose it because the field went DOWN in luma, not up.
OXFORD_BLUE = (0, 33, 71)

FIELD = OXFORD_BLUE
STAR = (255, 255, 255)

# (count, arm length, thickness, brightness, blur, tiles per loop)
#
# Three bands, and the SPEED is the depth cue: near stars cross the frame
# three times while far stars cross once. Sizes are authored at the mint
# canvas and scale with it, so a 512px loop and a 1393px still show the
# same field rather than the same pixel counts.
BANDS = (
    (150, 7,  2, 0.55, 1.1, 1),   # far   — small, dim, slow
    (46,  13, 3, 0.85, 0.7, 2),   # mid
    (16,  22, 5, 1.00, 0.4, 3),   # near  — large, bright, fast
)

MARGIN = 0.06          # torus overhang, as a fraction of width
CANVAS = 1393.0        # the size BANDS is authored at


def _plus(draw, x, y, arm, thick, value):
    """One sparkle. A plus, not a dot -- it is what the reference draws, and
    it is what still reads as a star rather than as dust at small sizes."""
    h = thick / 2.0
    draw.rectangle([x - arm, y - h, x + arm, y + h], fill=value)
    draw.rectangle([x - h, y - arm, x + h, y + arm], fill=value)


def render(size, t=0.0, seed=0, field=None, rainbow=True, dy=0):
    """The plate at loop position t, as an RGB uint8 array (h, w, 3)."""
    w, h = size
    t = float(t) % 1.0
    k = w / CANVAS                      # scale sprites with the canvas
    m = int(w * MARGIN)
    tile = w + 2 * m
    rng = np.random.default_rng(seed ^ 0x57A25)

    out = np.zeros((h, w, 3), dtype=np.float32)
    out[...] = np.asarray(field or FIELD, dtype=np.float32) / 255.0

    for count, arm, thick, bright, blur, tiles in BANDS:
        layer = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(layer)
        x0 = rng.random(count) * tile
        y0 = rng.random(count) * h
        # RIGHT TO LEFT: subtract, so the character flies left to right.
        xs = (x0 - tile * tiles * t) % tile - m
        sizes = rng.uniform(0.7, 1.3, count)
        for x, y, s in zip(xs, y0, sizes):
            _plus(draw, x, y, max(1.0, arm * k * s), max(1.0, thick * k), 255)
        if blur * k > 0.1:
            layer = layer.filter(ImageFilter.GaussianBlur(blur * k))
        a = (np.asarray(layer, dtype=np.float32) / 255.0 * bright)[..., None]
        out = out + (np.asarray(STAR, dtype=np.float32) / 255.0 - out) * a

    out = (np.clip(out, 0, 1) * 255.0 + 0.5).astype(np.uint8)
    # The trail goes over the stars, and it is built on the SOURCE GRID and
    # nearest-scaled to whatever this is rendering at -- so a 512px proof and
    # the 1393px plate show the same rainbow rather than the same pixel
    # counts, the rule BANDS already follows.
    if rainbow:
        out = _rainbow_over(out, t * BLOCKS_PER_LOOP, dy=dy)
    return out


# ------------------------------------------------------------- the source
#
# The owner's GIF, prepared for use as a plate. Two things are done to it
# and both are measured rather than assumed:
#
#   UPSCALE with NEAREST. The source is 400x400 against a 1393 canvas -- a
#   3.48x blow-up, and the smallest plate otherwise shipping is 1254. The
#   sparkles are hard-edged pixel art, so nearest keeps every edge crisp
#   and makes the scale read as deliberate; a smooth resample rounds them
#   into blobs and it becomes the softest asset in the set.
#
#   CLEAN the residue. "Blank" means the Nyan cat was removed, and the
#   removal left 760 pixels across the loop that are neither the field nor
#   a star: a green-teal speck, 507px of a second blue (#003366), and
#   traces of the rainbow's yellow. They are snapped back to the field.
#
#   RECOLOUR the field. Cleaning leaves exactly two colours -- SOURCE_FIELD
#   and the sparkles -- so the swap to Oxford Blue is a substitution, not a
#   hue rotation, and the sparkles are untouched by construction. Do the
#   clean FIRST: the residue is nearer the source field than the target is,
#   so recolouring first would strand it as visible specks.
FIELD_SNAP = 0        # sum-of-channels distance; 0 = anything not exactly
                      # the source field colour and not a star gets snapped


# --------------------------------------------------------- the rainbow trail
#
# The 8-bit rainbow the "Blank" in Nyan_Blank.gif refers to: the cat and its
# trail were erased from the source, and this puts the trail back.
#
# IT IS DRAWN ON THE SOURCE GRID, at 400x400, and rides the SAME
# nearest-neighbour upscale as the sparkles. That is the whole reason it
# reads as 8-bit rather than as a vector ribbon: one rainbow pixel is
# exactly one star pixel, 3.4825 canvas px on a side, and both staircase
# with the same tooth. Drawing it at 1393 and calling for hard edges would
# put a second, finer pixel grid on the one plate.
#
# It is painted AFTER the clean and the recolour and BEFORE the resize. The
# order matters in both directions: the clean snaps anything that is neither
# field nor star back to the field, so a rainbow laid down first would be
# erased by it, and the recolour rewrites every non-star pixel, so a rainbow
# laid down between them would come back Oxford Blue.
#
# The stars pass BEHIND it, which is the same depth order the source GIF
# had and the only one that makes sense -- a trail leaving the character is
# the nearest thing in the frame.
SRC_GRID = 400         # the source GIF's own resolution
CANVAS_PER_SRC = CANVAS / SRC_GRID          # 3.4825

# The canonical Nyan palette, ungraded. `grade.py` normalises a plate cool,
# desaturated and mid-key so a CHARACTER reads in front of it, and FIELD is
# recoloured to Oxford Blue for exactly that reason -- but the field is the
# backdrop and this is the subject. Muting six primaries into the plate
# family's band is not a quieter rainbow, it is not a rainbow: the motif is
# the saturation.
#
# Do not expect SUBJECT_SEPARATION to take the edge off it, either. Measured
# over six characters, the trail lifts that pass's band-pass reading of the
# plate from 1.25-1.90 to 2.93-3.48 -- past `busy0` (2.5), but only just, so
# the strength it computes is 0.004-0.021 and the pass is still off to three
# decimal places. Six flat stripes are the same kind of nothing to a
# band-pass as one flat colour; it detects texture, not saturation. What
# keeps the trail off the character is that it is BEHIND it and cut short of
# it, which is geometry rather than grading.
RAINBOW = (
    (255,   0,   0),
    (255, 153,   0),
    (255, 255,   0),
    ( 51, 255,   0),
    (  0, 153, 255),
    (102,  51, 255),
)

# All in SOURCE-GRID pixels; the canvas equivalent is 3.4825x each.
#
# GEOMETRY IS MEASURED AGAINST THE CAST, not chosen. The trail is cut off
# flat at `LEAD` and the cut has to be hidden, or the token shows a rainbow
# rectangle ending in mid-air. Composited over all 14 STARFIELD_CHARS x 3
# rolls, every one of those 42 renders covers canvas x 709..722 continuously
# from y 388 to y 850 -- so the cut goes at x 207 (canvas 721). BAND_TOP is
# only the DEFAULT height; centre_dy() moves it per token (see below), and
# verify_cover() re-measures the whole thing rather than trusting any of it.
STRIPE = 16            # px per stripe; 6 of them is 96 (canvas 334)
STEP = 8               # the wave's unit: half a stripe
BLOCK = 14             # px per zig-zag block (canvas 49)
WAVE = (0, 1, 2, 1)    # a triangle, in STEPs, about its own middle
BAND_TOP = 130         # top of the band at wave offset 0 (canvas 453)
LEAD = 207             # the flat cut, behind the body (canvas 721)

# Blocks the wave advances over one whole loop. THE SEAM RULE: this must be
# a whole number of WAVE cycles, exactly as the stars travel a whole number
# of tiles, or frame N is not frame 0. 12 blocks is one per GIF frame, and
# 12 % 4 == 0.
BLOCKS_PER_LOOP = 12


def rainbow_index(phase, n=SRC_GRID, dy=0):
    """Stripe index per source pixel at `phase` blocks advanced; -1 = none.

    THE WAVE TRAVELS RIGHT TO LEFT, with the stars, because the trail is
    being laid down BEHIND a character flying left to right: its material is
    stationary in the world and the camera rides the character, so on screen
    it streams away towards the left edge. Run it the other way and the
    trail appears to feed INTO the character's back, which is the same
    mistake this module's header warns about for the stars themselves --
    and it is the one thing everyone notices.

    The blocks are anchored at the LEADING edge and counted leftwards, so
    the cut stays exactly where it was measured while the wave slides
    through it. `b` therefore grows to the LEFT, which is why the phase is
    SUBTRACTED: f(b, p+1) = f(b+1, p) puts what block b+1 was showing onto
    block b, and block b+1 is the one further left. verify_direction()
    measures which way it actually moves rather than re-deriving that.

    `dy` shifts the whole band, in source px -- see centre_dy().
    """
    x = np.arange(n)[None, :]
    y = np.arange(n)[:, None]
    b = np.floor_divide(LEAD - x, BLOCK)
    off = (np.asarray(WAVE)[(b - int(phase)) % len(WAVE)] - 1) * STEP
    idx = np.floor_divide(y - (BAND_TOP + int(dy) + off), STRIPE)
    return np.where((x < LEAD) & (idx >= 0) & (idx < len(RAINBOW)), idx, -1)


def paint_rainbow(a, phase, dy=0):
    """Paint the trail over a source-grid RGB array, in place."""
    idx = rainbow_index(phase, n=a.shape[0], dy=dy)
    for i, c in enumerate(RAINBOW):
        a[idx == i] = c
    return a


def _rainbow_over(rgb, phase, dy=0):
    """Paint the trail over an RGB array of ANY size (the procedural path).

    The index is built at SRC_GRID and blown up with NEAREST, so the trail
    keeps the source grid's tooth at every output size instead of getting a
    finer staircase the bigger the render is.
    """
    h, w = rgb.shape[:2]
    idx = rainbow_index(phase, dy=dy)
    if (h, w) != (SRC_GRID, SRC_GRID):
        idx = np.asarray(
            Image.fromarray((idx + 1).astype(np.uint8), "L")
            .resize((w, h), Image.Resampling.NEAREST), dtype=np.int16) - 1
    out = rgb.copy()
    for i, c in enumerate(RAINBOW):
        out[idx == i] = c
    return out


def band_bbox(dy=0):
    """(top, bottom) of the swept band on the CANVAS, wave included.

    What has to stay behind the character, and what verify_cover() checks.
    """
    lo = (BAND_TOP + dy - STEP) * CANVAS_PER_SRC
    hi = (BAND_TOP + dy + len(RAINBOW) * STRIPE + STEP) * CANVAS_PER_SRC
    return lo, hi


# ------------------------------------------ centring the trail per token
#
# THE BAND IS NOT AT ONE HEIGHT FOR THE WHOLE CAST, and it cannot be. The
# face composites at a fixed canvas position for every character ("one face,
# one size", CLAUDE.md) but the BODY does not: measured over the 14
# STARFIELD_CHARS x 6 rolls, the body's own vertical centre runs 501..752, a
# 251px spread, against a fixed band centred at 620. At one height the trail
# leaves the marshmallow near its shoulders and the waffle near its knees.
#
# It is also not a per-character table, because the same character sits at
# different heights depending on what it rolled: footwear, VERTICAL_OFFSET
# and FOOTWEARLESS_DY move a body by up to 220px between two rolls of ONE
# character (gold_waffle 501..721). So the anchor has to be measured on the
# placed art, per token.
#
# ANCHOR ON THE BODY, CLAMP ON EVERYTHING. The trail should leave the middle
# of the character, so the anchor is the CHARACTER layer's own bbox -- not
# the footwear, which would drag it down to the shoe line, and not the arms,
# which swing a saber 1200px up the frame. But what has to HIDE the cut is
# whatever is actually in front of it, body and ball and footwear alike, so
# the clamp uses the full silhouette. Note the body alone cannot serve as
# the clamp: the cut at x 721 runs straight through the face hole, so the
# body layer's cover there is split in two and the skin ball fills the gap.
FIGURE_PAD = 12        # canvas px of cut column that must be covered


def _figure(layers, gen, body_only=False):
    """The placed silhouette, as a bool array. `body_only` = the character.

    Built from gen._render_layer(), which is the same function create_image
    composites with, so the placement cannot drift from the real render.
    """
    czs = os.path.normpath(os.path.join(gen.TRAITS_DIR, gen.CHARACTERZ))
    out = None
    for i, l in enumerate(layers):
        if i == 0:
            continue                        # the plate is not the figure
        if body_only and not os.path.normpath(
                l["path"]).startswith(czs + os.sep):
            continue
        img = gen._render_layer(l)
        if img is None:
            continue
        a = np.asarray(img.getchannel("A")) >= 128
        out = a if out is None else (out | a)
    return out


def centre_dy(layers, gen):
    """The band offset for THIS token, in source px, rounded to the grid.

    A fractional offset would resample the trail off the source pixel grid
    and cost it the hard 8-bit edge that is the whole point, so it is a
    whole number of source pixels -- 3.4825 canvas px of resolution, which
    is finer than the 251px spread it is correcting for by a wide margin.
    """
    body = _figure(layers, gen, body_only=True)
    fig = _figure(layers, gen)
    if body is None or fig is None:
        return 0
    lead = int(round(LEAD * CANVAS_PER_SRC))
    swept = (len(RAINBOW) * STRIPE + 2 * STEP) * CANVAS_PER_SRC

    ys = np.nonzero(body.any(1))[0]
    mid = (ys.min() + ys.max()) / 2.0                     # the body's centre
    want = mid - swept / 2.0                              # band top, canvas

    # the run of cover the cut actually has, the one the body sits in
    runs = cover_runs(fig, lead)
    if not runs:
        return 0
    inside = [r for r in runs if r[0] <= mid <= r[1]]
    top, bot = (inside[0] if inside
                else min(runs, key=lambda r: min(abs(r[0] - mid),
                                                 abs(r[1] - mid))))
    if bot - top >= swept:
        want = min(max(want, top), bot - swept)           # clamp into cover
    else:
        want = top + (bot - top - swept) / 2.0            # too short: centre
    default = (BAND_TOP - STEP) * CANVAS_PER_SRC
    return int(round((want - default) / CANVAS_PER_SRC))


def cover_runs(fig, lead=None, pad=FIGURE_PAD):
    """Contiguous vertical runs where the figure covers the whole cut column.

    One definition, used to place the band and again to check it, so the
    gate cannot be measuring something else than the placement did.
    """
    if lead is None:
        lead = int(round(LEAD * CANVAS_PER_SRC))
    col = fig[:, max(0, lead - pad):lead + 1].all(1)
    runs, start = [], None
    for y in range(col.size):
        if col[y] and start is None:
            start = y
        elif not col[y] and start is not None:
            runs.append((start, y - 1))
            start = None
    if start is not None:
        runs.append((start, col.size - 1))
    return runs


def from_gif(path, size=(1393, 1393), clean=True, field=None,
             rainbow=True, dy=0):
    """Load an animated GIF as a list of plate frames at the mint canvas.

    `field` recolours the flat backdrop (default: the shipping FIELD).
    Pass SOURCE_FIELD to keep the GIF's own #00008B.
    `rainbow=False` renders the bare field the GIF ships as, which is what
    the ladder and the before/after proofs want.
    """
    from PIL import ImageSequence
    src = np.asarray(SOURCE_FIELD, dtype=np.int16)
    dst = np.asarray(field if field is not None else FIELD, dtype=np.int16)
    raw = [np.asarray(f.convert("RGB")).astype(np.int16)
           for f in ImageSequence.Iterator(Image.open(path))]
    # The seam rule, asserted rather than assumed: the wave has to advance a
    # whole number of its own cycles over the loop, exactly as the stars
    # travel a whole number of tiles. Break it and frame N is not frame 0 --
    # a step at the wrap, invisible in a filmstrip and obvious in the loop.
    if rainbow and BLOCKS_PER_LOOP % len(WAVE):
        raise ValueError(
            f"BLOCKS_PER_LOOP {BLOCKS_PER_LOOP} is not a whole number of "
            f"WAVE cycles ({len(WAVE)}): the loop would not close")
    return [_plate_frame(a, i * BLOCKS_PER_LOOP / float(len(raw)), size,
                         clean, src, dst, rainbow, dy)
            for i, a in enumerate(raw)]


def _plate_frame(a, phase, size, clean, src, dst, rainbow, dy=0):
    """One source frame -> one plate. Cleaned, recoloured, then the trail."""
    a = a.copy()
    star = a.min(-1) >= 200
    if clean:
        d = np.abs(a - src).sum(-1)
        a[(d > FIELD_SNAP) & (~star)] = src
    a[~star] = dst
    if rainbow:
        paint_rainbow(a, phase, dy=dy)
    return (Image.fromarray(a.astype(np.uint8), "RGB")
            .resize(size, Image.Resampling.NEAREST))


def loop_layers(layers, out_dir, tid, gen, gif=GIF_PATH, size=None,
                dy=0):
    """Render a token's seamless starfield loop by RE-COMPOSITING it once per
    plate frame, and return the frames.

    This is the one place the shipping path differs from the weather bake,
    and the reason is structural. A weather loop is a GRADE over a finished
    token, so bake_weather.py can work from the PNG plus its protect mask and
    never needs the layer stack. Here the plate itself moves, and the
    grounding shadow and the subject-separation pocket are painted ONTO the
    plate before the character goes down -- so a frame built by swapping the
    plate under a finished PNG loses both, and the character floats (see
    behind() below, which does exactly that and is a proof path only).

    Re-compositing is affordable precisely because this tier is ultra-rare:
    10 tokens x 12 frames is 120 composites, where the 444 weather tokens
    would have been 16,000.
    """
    import copy
    frames = []
    plates = from_gif(gif, size=(gen.CANVAS_SIZE, gen.CANVAS_SIZE),
                      dy=dy)
    os.makedirs(out_dir, exist_ok=True)
    for i, plate in enumerate(plates):
        pp = os.path.join(out_dir, f"_plate_{tid}_{i:02d}.png")
        plate.save(pp)
        ls = [dict(l) for l in layers]
        ls[0] = {"path": pp, "offset": False}
        tmp = os.path.join(out_dir, f"_f_{tid}_{i:02d}.png")
        gen.create_image(ls, tmp)
        im = Image.open(tmp).convert("RGB")
        if size and im.size != (size, size):
            im = im.resize((size, size), Image.Resampling.LANCZOS)
        frames.append(im.copy())
        os.remove(pp)
        os.remove(tmp)
    return frames


def centre_layers(layers, out_dir, tid, gen, gif=GIF_PATH):
    """Swap layers[0] for a plate whose trail is centred on THIS character.

    Returns (layers, dy, plate_path). The caller composites the still with
    the returned stack, passes `dy` to loop_layers() so the 12 frames agree
    with it, and deletes `plate_path` when it is done.

    THE PLATE IS PER TOKEN, which is what centring costs. Every other plate
    in the collection is one file composited under 4,000 characters; this
    one is redrawn for each of the 22 tokens that draw it, because where the
    trail leaves the body is a property of the pairing and not of the plate.
    traits/backgroundz/Starfield.png stays the dy=0 reference -- it is what
    the trait sheet, the catalog and any ad-hoc render show, and it is what
    build_mint checks for before it will mint the tier at all.

    CALL IT AFTER extract_metadata(). It rewrites the layer stack, and the
    Background attribute is read off layers[0]'s filename -- hand it the
    swapped stack and every starfield token's Background becomes
    "_plate_17".
    """
    dy = centre_dy(layers, gen)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"_plate_{tid}.png")
    from_gif(gif, size=(gen.CANVAS_SIZE, gen.CANVAS_SIZE), dy=dy)[0].save(path)
    out = [dict(l) for l in layers]
    out[0] = {"path": path, "offset": False}
    return out, dy, path


def behind(token_rgba, protect, size=None, t=0.0, seed=0, plate=None,
           dy=0):
    """Composite a finished token over the starfield.

    `protect` is the mint mask -- the union of every layer except the plate
    -- so this puts the starfield exactly where the old plate was and
    leaves the figure alone. `plate` overrides the procedural field with a
    prepared frame (see from_gif).

    THIS IS A PROOF PATH, NOT THE SHIPPING ONE. The grounding shadow and
    the subject-separation pocket are baked into the OLD plate's pixels, so
    swapping the plate here discards them and the character floats. The
    real path swaps layers[0] BEFORE create_image() composites, which draws
    the shadow onto the starfield instead -- and for this plate the answer
    turned out to be to switch the shadow off entirely, since a character
    in open space has nothing to cast onto.
    """
    if size is not None and token_rgba.size != size:
        token_rgba = token_rgba.resize(size, Image.Resampling.LANCZOS)
        protect = protect.resize(size, Image.Resampling.LANCZOS)
    w, h = token_rgba.size
    tok = np.asarray(token_rgba.convert("RGBA"), dtype=np.float32) / 255.0
    pr = (np.asarray(protect.convert("L"), dtype=np.float32) / 255.0)[..., None]
    if plate is not None:
        sky = np.asarray(plate.convert("RGB").resize(
            (w, h), Image.Resampling.NEAREST), dtype=np.float32) / 255.0
    else:
        sky = render((w, h), t=t, seed=seed,
                     dy=dy).astype(np.float32) / 255.0
    out = tok[..., :3] * pr + sky * (1.0 - pr)
    return Image.fromarray(
        (np.dstack([np.clip(out, 0, 1), tok[..., 3:4]]) * 255.0 + 0.5)
        .astype(np.uint8), "RGBA")


# ------------------------------------------------------------- the gates
#
# Two things about the rainbow can break silently, and neither shows up in
# a filmstrip, so both are measured rather than eyeballed.


def verify_seam(gif=GIF_PATH):
    """The loop closes: the plate one frame PAST the end is the first frame.

    The stars come off a 12-frame GIF and are seamless by construction; the
    rainbow is drawn on top and could not be. It closes only because the
    wave advances BLOCKS_PER_LOOP blocks over the loop and that is a whole
    number of WAVE cycles -- a step at the wrap is exactly the thing that
    makes an ambient loop look cheap, and it is invisible in stills.
    """
    from PIL import ImageSequence
    src = np.asarray(SOURCE_FIELD, dtype=np.int16)
    dst = np.asarray(FIELD, dtype=np.int16)
    raw = [np.asarray(f.convert("RGB")).astype(np.int16)
           for f in ImageSequence.Iterator(Image.open(gif))]
    size = (SRC_GRID, SRC_GRID)
    first = _plate_frame(raw[0], 0, size, True, src, dst, True)
    # The GIF loops, so the frame after the last one is the GIF's own frame 0
    # again -- carrying the wave on to where it would have advanced to.
    wrap = _plate_frame(raw[0], BLOCKS_PER_LOOP, size, True, src, dst, True)
    return np.array_equal(np.asarray(first), np.asarray(wrap))


def verify_direction():
    """The wave travels LEFT, with the stars. Measured, not reasoned about.

    This exists because the first version of rainbow_index() had a comment
    saying "right to left" above code that ran the other way -- the sign of
    the phase and the direction `b` counts in cancel out in a way that reads
    correct either way. Cross-correlating two consecutive phases cannot be
    argued with.
    """
    a = rainbow_index(0)
    b = rainbow_index(1)
    lo, hi = 3 * BLOCK, LEAD - 3 * BLOCK
    best = None
    for shift in range(-2 * BLOCK, 2 * BLOCK + 1):
        m = (np.roll(a, shift, axis=1)[:, lo:hi] == b[:, lo:hi]).mean()
        if best is None or m > best[1]:
            best = (shift, m)
    return best[0] < 0, best[0]


def verify_cover(gen, rolls=3, seed=1000, pad=12):
    """The flat cut at LEAD is hidden by the body, for every eligible pair.

    THE ONE WAY THIS FEATURE FAILS UGLY. The trail has to stop somewhere,
    and it stops on a straight vertical line; if the body does not cover
    that line over the band's full swept height, the token shows a rainbow
    rectangle ending in mid-air. It cannot be settled per character by eye
    because the cover depends on the arm and the footwear that rolled with
    it, so it is measured over the protect mask of real composites.

    Returns (ok, rows) with the margin each render leaves above and below
    the band -- how much further the cover runs than the rainbow needs.
    """
    import random as _random
    lead = int(round(LEAD * CANVAS_PER_SRC))
    rows, ok = [], True
    for i, char in enumerate(gen.STARFIELD_CHARS):
        for r in range(rolls):
            _random.seed(seed + i * 17 + r)
            layers, _ = gen.generate_random_combination(
                force_bg=(gen.BACKGROUNDZ, gen.STARFIELD_BG),
                force_char=char)
            # the SHIPPING placement, not the default one
            dy = centre_dy(layers, gen)
            top, bot = band_bbox(dy)
            top, bot = int(np.floor(top)), int(np.ceil(bot))
            fig = _figure(layers, gen)
            col = fig[:, max(0, lead - pad):lead + 1].all(1)
            covered = bool(col[max(0, top):bot + 1].all()) and top >= 0
            up = top - 1
            while up >= 0 and col[up]:
                up -= 1
            dn = bot + 1
            while dn < col.size and col[dn]:
                dn += 1
            body = _figure(layers, gen, body_only=True)
            ys = np.nonzero(body.any(1))[0]
            off = (top + bot) // 2 - (ys.min() + ys.max()) // 2
            rows.append((char, r, covered, top - up - 1, dn - bot - 1,
                         dy, int(off)))
            ok = ok and covered
    return ok, rows


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help="rebuild traits/backgroundz/Starfield.png (frame 0)")
    ap.add_argument("--strip", metavar="PNG", default=None,
                    help="write the 12 plate frames as a filmstrip")
    ap.add_argument("--verify", action="store_true",
                    help="THE GATE: the loop closes and the cut is hidden")
    ap.add_argument("--rolls", type=int, default=3,
                    help="rolls per character for --verify")
    a = ap.parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rc = 0

    if a.write:
        dst = os.path.join(root, "traits", "backgroundz", "Starfield.png")
        from_gif(GIF_PATH)[0].save(dst)
        print(f"wrote {os.path.relpath(dst, root)}")

    if a.strip:
        frames = from_gif(GIF_PATH, size=(256, 256))
        sheet = Image.new("RGB", (256 * len(frames), 256))
        for i, f in enumerate(frames):
            sheet.paste(f, (256 * i, 0))
        sheet.save(a.strip)
        print(f"wrote {a.strip}")

    if a.verify:
        seam = verify_seam()
        print(f"seam   frame {BLOCKS_PER_LOOP} == frame 0: "
              f"{'OK' if seam else 'FAIL'}")
        left, shift = verify_direction()
        print(f"dir    wave travels {shift:+d}px/frame "
              f"({'LEFT, with the stars' if left else 'RIGHT — BACKWARDS'}): "
              f"{'OK' if left else 'FAIL'}")
        sys.path.insert(0, root)
        import generator as gen
        print(f"cover  cut at canvas x {LEAD * CANVAS_PER_SRC:.0f}, band "
              f"{len(RAINBOW) * STRIPE + 2 * STEP} src px "
              f"({(len(RAINBOW) * STRIPE + 2 * STEP) * CANVAS_PER_SRC:.0f} "
              f"canvas) swept")
        ok, rows = verify_cover(gen, rolls=a.rolls)
        for char, r, covered, up, dn, dy, off in rows:
            if not covered:
                print(f"  FAIL {char} roll {r}: the cut is exposed "
                      f"(dy {dy:+d})")
        worst = min(rows, key=lambda r: min(r[3], r[4]))
        dys = [r[5] for r in rows]
        offs = [abs(r[6]) for r in rows]
        print(f"       {len(rows)} renders, worst margin "
              f"{min(worst[3], worst[4])}px ({worst[0]})")
        print(f"       dy {min(dys):+d}..{max(dys):+d} src px; band centre is "
              f"within {max(offs)}px of the body's on the worst render, "
              f"{sum(offs) // len(offs)}px on average")
        print(f"cover  {'OK' if ok else 'FAIL'}")
        rc = 0 if (seam and left and ok) else 1

    if not (a.write or a.strip or a.verify):
        ap.print_help()
    return rc


if __name__ == "__main__":
    sys.exit(_main())
