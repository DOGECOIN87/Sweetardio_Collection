#!/usr/bin/env python3
"""The scrolling starfield plate: the character reads as flying left to right.

DIFFERENT IN KIND from everything else in dynamic/. The weather states grade
a plate that already exists; this IS the plate. There is no mint art
underneath it to protect, so the protect mask here only decides where the
character sits on top, not what may be touched.

THE MOTION RUNS THE OTHER WAY TO THE ILLUSION. The character is fixed in
frame, so the stars travel RIGHT TO LEFT to read as the character flying
LEFT TO RIGHT. Getting that backwards makes it fly backwards, which is the
one thing everyone notices.

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
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

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


def render(size, t=0.0, seed=0, field=None):
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

    return (np.clip(out, 0, 1) * 255.0 + 0.5).astype(np.uint8)


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


def from_gif(path, size=(1393, 1393), clean=True, field=None):
    """Load an animated GIF as a list of plate frames at the mint canvas.

    `field` recolours the flat backdrop (default: the shipping FIELD).
    Pass SOURCE_FIELD to keep the GIF's own #00008B.
    """
    from PIL import ImageSequence
    src = np.asarray(SOURCE_FIELD, dtype=np.int16)
    dst = np.asarray(field if field is not None else FIELD, dtype=np.int16)
    frames = []
    for f in ImageSequence.Iterator(Image.open(path)):
        a = np.asarray(f.convert("RGB")).astype(np.int16)
        star = a.min(-1) >= 200
        if clean:
            d = np.abs(a - src).sum(-1)
            a[(d > FIELD_SNAP) & (~star)] = src
        a[~star] = dst
        frames.append(Image.fromarray(a.astype(np.uint8), "RGB")
                      .resize(size, Image.Resampling.NEAREST))
    return frames


def behind(token_rgba, protect, size=None, t=0.0, seed=0, plate=None):
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
        sky = render((w, h), t=t, seed=seed).astype(np.float32) / 255.0
    out = tok[..., :3] * pr + sky * (1.0 - pr)
    return Image.fromarray(
        (np.dstack([np.clip(out, 0, 1), tok[..., 3:4]]) * 255.0 + 0.5)
        .astype(np.uint8), "RGBA")
