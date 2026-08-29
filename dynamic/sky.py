#!/usr/bin/env python3
"""The dynamic sky pass: time of day and weather, on the BACKGROUND ONLY.

The rule this whole module is built around, and the reason it is a grade
rather than a re-render:

    The effect touches the background plate and NOTHING else. Every other
    trait -- body, skin ball, eyes, mouth, arms, footwear, stickers and the
    paired background overlays -- composites on top exactly as minted, pixel
    for pixel.

So the pass is a pure function of the plate region:

    out = base * protect  +  effect(base) * (1 - protect)

where `protect` is the mask create_image() writes at mint-build time (the
union of every layer except layers[0]). Because the mask keeps its
anti-aliased edge values, the blend feathers across the silhouette instead
of stair-stepping it. Nothing is re-composited, no trait art is opened, and
the character comes out bit-identical to the mint.

Two consequences worth knowing:

  * The grounding shadow and the subject-separation pocket are baked into
    the plate pixels, so they grade WITH the plate. That is correct -- they
    are stage, not character.
  * Weather particles are drawn into the effect layer, so they are masked
    by the same protect mask and always fall BEHIND the character. There is
    deliberately no in-front pass.

The collection's key light does not move. CLAUDE.md pins it to the upper
left and all 123 trait assets are authored to it, so a night render that
relit the scene would take every character out of register with the cast.
Sun altitude therefore drives exposure, contrast, saturation, split-tone and
vignette -- never a new light direction. What falls down and to the right
(rain lean, vignette weighting) follows the existing convention.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# Rec.709, the same definition background_pop_studies/grade.py uses. The two
# passes stack on the same plates, so they must agree on what luma means.
_LUMA = (0.2126, 0.7152, 0.0722)

# Everything downstream stays float32. A bare tuple through np.asarray comes
# back float64, which silently upcasts the whole 1393x1393x3 plate and
# doubles the memory traffic of every remaining op -- measured at 2.2x
# slower end to end, for no visible difference at 8 bits out.
_F = np.float32


def _c(triple):
    """A colour constant as float32, so it never upcasts the plate."""
    return np.asarray(triple, dtype=_F)


# The radial falloff field depends only on the canvas size, and the canvas is
# a fixed 1393 for this collection -- so it is computed once per size and
# reused, rather than rebuilt (via a pair of 31MB int64 mgrid arrays) on
# every single render.
_VIG_CACHE = {}


def _vig_field(h, w):
    if (h, w) not in _VIG_CACHE:
        ny = np.linspace(-1.0, 1.0, h, dtype=_F)[:, None]
        nx = np.linspace(-1.0, 1.0, w, dtype=_F)[None, :]
        d = np.sqrt(nx * nx + ny * ny) / _F(np.sqrt(2.0))
        _VIG_CACHE[(h, w)] = smoothstep((d - 0.55) / 0.45) ** 1.2
    return _VIG_CACHE[(h, w)]


def luma(rgb):
    return (_LUMA[0] * rgb[..., 0] + _LUMA[1] * rgb[..., 1]
            + _LUMA[2] * rgb[..., 2])


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


# ------------------------------------------------------------------ sky
#
# Eight states, keyed by the phase names solar.sun_phase() returns.
#
#   exposure  multiplier on luma (hue-safe: applied as a luma ratio)
#   contrast  signed S-curve blend; negative FLATTENS, which is what low
#             light actually does -- night is not just a darker day
#   lift      raises blacks (haze/scatter); the giveaway for fog and snow
#   sat       chroma multiplier
#   sh_tint / sh_amt   colour pulled into the shadows
#   hi_tint / hi_amt   colour pulled into the highlights
#   vignette  added corner falloff, tinted with sh_tint
#
# DAY IS DELIBERATELY IDENTITY. It is the grade the plates were approved at
# in ULTIMATE_GRADE_LOG.md, and it covers most of every holder's daylight
# hours. The dynamic layer should read as a reward for checking in at dusk,
# not as a filter permanently laid over the owner's art.
SKY_STATES = {
    "high_noon": dict(
        exposure=1.06, contrast=0.04, lift=0.0, sat=0.97,
        sh_tint=(0.10, 0.14, 0.24), sh_amt=0.05,
        hi_tint=(0.98, 0.99, 1.00), hi_amt=0.06, vignette=-0.02),

    "day": dict(),  # identity -- the canonical mint

    # Dawn and dusk sit at the SAME solar altitude and are the most visible
    # split in the table, so they get separate grades: morning light is
    # rose and paler (cold ground, less dust in the air), evening light is
    # amber and deeper.
    "golden_dawn": dict(
        exposure=0.87, contrast=0.03, lift=0.015, sat=1.04,
        sh_tint=(0.17, 0.14, 0.23), sh_amt=0.17,
        hi_tint=(1.00, 0.83, 0.78), hi_amt=0.26, vignette=0.05),
    "golden_dusk": dict(
        exposure=0.85, contrast=0.07, lift=0.0, sat=1.11,
        sh_tint=(0.21, 0.11, 0.16), sh_amt=0.18,
        hi_tint=(1.00, 0.74, 0.40), hi_amt=0.32, vignette=0.07),

    "blue_dawn": dict(
        exposure=0.66, contrast=-0.03, lift=0.03, sat=0.84,
        sh_tint=(0.07, 0.10, 0.24), sh_amt=0.32,
        hi_tint=(0.64, 0.74, 0.97), hi_amt=0.24, vignette=0.11),
    "blue_dusk": dict(
        exposure=0.60, contrast=-0.05, lift=0.01, sat=0.79,
        sh_tint=(0.05, 0.07, 0.21), sh_amt=0.36,
        hi_tint=(0.52, 0.63, 0.95), hi_amt=0.28, vignette=0.13),

    "twilight": dict(
        exposure=0.45, contrast=-0.08, lift=0.012, sat=0.66,
        sh_tint=(0.04, 0.06, 0.17), sh_amt=0.45,
        hi_tint=(0.55, 0.65, 0.92), hi_amt=0.30, vignette=0.17),

    "night": dict(
        exposure=0.30, contrast=-0.12, lift=0.008, sat=0.55,
        sh_tint=(0.03, 0.05, 0.14), sh_amt=0.54,
        hi_tint=(0.60, 0.70, 0.95), hi_amt=0.34, vignette=0.21),
}

# ------------------------------------------------------------- weather
#
# Eight visual states in two tiers, collapsed from Open-Meteo's ~100 WMO
# codes by weather.py.
#
# The first SIX are the ordinary sky. Six is the ceiling there: past that
# they stop reading as distinct and start reading as noise -- drizzle and
# light rain are the same trait however different the code is.
#
# The last two are SEVERE, and they are a different kind of thing rather
# than more of the same. They are allowed to break the six-state ceiling
# because they are not competing with it: a holder sees `overcast` most
# weeks of the year and `blizzard` a handful of times, so a state that
# reads as an EVENT does not add to the noise the ceiling exists to stop.
# What they must not do is arrive by accident, which is why weather.py
# gates them on more than a WMO code (see BLIZZARD_WIND_KMH there, and the
# note that `tornado` has no WMO code at all).
#
# These stack ON TOP of the sky grade (multiplicative on exposure/sat,
# additive on contrast/lift), so rain at night is darker than rain at noon
# without either table knowing about the other.
#
#   diffuse   px of blur -- overcast and fog genuinely soften a scene
#   haze/amt  colour the plate is lerped toward (fog)
#   sh_tint   shadow colour; a weather state that declares one OVERRIDES
#             the phase's, because severe weather changes what colour the
#             shadows are and not merely how much of them there is
#   particles which sprite pass to run, and how dense
WEATHER_STATES = {
    "clear": dict(),

    "overcast": dict(
        exposure=0.90, contrast=-0.14, lift=0.020, sat=0.82, diffuse=1.6,
        drift=0.030),

    # Fog is the strongest of the six and nearly free: the protect mask
    # means the plate can be hazed while the character is not, which is
    # literal atmospheric perspective -- the character pops forward without
    # a single pixel of it changing.
    "fog": dict(
        exposure=0.96, contrast=-0.30, lift=0.135, sat=0.52, diffuse=3.6,
        haze=(0.72, 0.755, 0.80), haze_amt=0.34, drift=0.055),

    "rain": dict(
        exposure=0.78, contrast=-0.05, lift=0.028, sat=0.72, diffuse=0.8,
        particles="rain", density=1.0),

    "snow": dict(
        exposure=0.99, contrast=-0.11, lift=0.055, sat=0.58, diffuse=0.6,
        particles="snow", density=1.0),

    "storm": dict(
        exposure=0.54, contrast=0.10, lift=0.015, sat=0.60, diffuse=1.0,
        sh_tint=(0.05, 0.06, 0.13), sh_amt=0.22,
        particles="rain", density=1.9, flash=True),

    # ---- severe ----
    #
    # A blizzard is NOT heavy snow. Snow is a slow vertical fall against a
    # plate you can still read; a blizzard is a horizontal drive plus a
    # whiteout, and the whiteout is the half that carries it. So this is
    # the only state that pushes lift and haze together hard enough to
    # take the plate most of the way to white -- the plate nearly goes,
    # while the character, held out by the protect mask, does not move a
    # pixel. That contrast is the whole read, and it is the same trick fog
    # plays, at the other end of the scale.
    "blizzard": dict(
        exposure=1.10, contrast=-0.30, lift=0.170, sat=0.20, diffuse=2.6,
        haze=(0.90, 0.93, 0.96), haze_amt=0.44,
        sh_tint=(0.66, 0.70, 0.76), sh_amt=0.18,
        particles="blizzard", density=2.4, drift=0.048),

    # The tornado is the one state that is a SHAPE rather than a field.
    # Every other weather here changes the whole plate uniformly; a funnel
    # is an object standing in it, which is exactly why it reads as the
    # rarest thing in the set and why it needs its own pass (_funnel).
    #
    # The tone half is a supercell, not a night: green-brown, lifted and
    # flat, with the saturation pulled out of everything the funnel is not.
    "tornado": dict(
        exposure=0.60, contrast=-0.05, lift=0.030, sat=0.42, diffuse=1.3,
        haze=(0.30, 0.31, 0.22), haze_amt=0.34,
        sh_tint=(0.11, 0.12, 0.07), sh_amt=0.26,
        particles="tornado", density=1.0, drift=0.036),
}

# What each particle field is lerped TOWARD. Rain is a cold near-white,
# snow and driven snow are white, and the tornado is the only dark one --
# a funnel subtracts light from the plate rather than adding it.
PARTICLE_TINT = {
    "rain": (0.80, 0.86, 0.98),
    "snow": (1.00, 1.00, 1.00),
    "blizzard": (1.00, 1.00, 1.00),
    "tornado": (0.60, 0.59, 0.54),
}

# The funnel is the one particle field that cannot be drawn in a single
# colour. The column itself is condensation and it is PALER than the
# supercell grade behind it -- that is what keeps it visible at every phase
# from high noon to night, where a dark funnel disappears into a dark sky
# the moment the sun goes down. The debris it throws is dirt, and dirt is
# DARKER than everything. Give them one shared tint and whichever one loses
# the argument turns into a row of pale bubbles floating beside the trunk.
TORNADO_DEBRIS_TINT = (0.13, 0.12, 0.10)


def _tone(rgb, exposure, contrast, lift, sat, sh_tint, sh_amt,
          hi_tint, hi_amt):
    """The tone/colour half of the pass, IN PLACE on a float32 array.

    Written for memory traffic rather than for clarity, because it runs over
    1393x1393x3 and it is the whole cost of a render. Two identities do most
    of the saving:

      * Exposure as a luma ratio is y*k/y == k for a SCALAR k, so it is just
        a scalar multiply. The ratio form only earns its cost when the
        multiplier varies per pixel, which here it does not.
      * Saturation about luma is luma-PRESERVING, so the split-tone weights
        can reuse the luma computed for the saturation step.

    Together those take the pass from four full-frame luma computations to
    two, and every remaining op writes into its own operand.
    """
    # 1. exposure
    if abs(exposure - 1.0) > 1e-4:
        rgb *= _F(exposure)

    # 2. signed S-curve; negative FLATTENS toward mid grey, which is what
    #    low light actually does -- night is not merely a darker day
    if abs(contrast) > 1e-4:
        y = np.clip(luma(rgb), 1e-6, 1.0)
        curved = (smoothstep(y) if contrast > 0
                  else _F(0.5) + (y - _F(0.5)) * _F(0.55))
        k = abs(contrast)
        y2 = y * _F(1.0 - k)
        y2 += curved * _F(k)
        np.maximum(y2, 0.0, out=y2)
        y2 /= y
        rgb *= y2[..., None]

    # 3. black lift -- scattered light never lets shadows reach zero
    if lift > 1e-5:
        rgb *= _F(1.0 - lift)
        rgb += _F(lift)

    # 4. saturation about luma, and 5. split-tone off the SAME luma
    y = luma(rgb)
    if abs(sat - 1.0) > 1e-4:
        yc = y[..., None]
        rgb -= yc
        rgb *= _F(sat)
        rgb += yc

    # Split-tone: shadows and highlights pulled to separate colours. This is
    # what actually sells a time of day -- a uniform blue cast reads as a
    # filter, a navy shadow under a cold highlight reads as night.
    yl = np.clip(y, 0.0, 1.0, out=y)
    if sh_amt > 1e-4:
        w = (1.0 - yl) ** 2
        w *= _F(sh_amt)
        rgb += (_c(sh_tint) - rgb) * w[..., None]
    if hi_amt > 1e-4:
        w = smoothstep((yl - _F(0.55)) / _F(0.40))
        w *= _F(hi_amt)
        rgb += (_c(hi_tint) - rgb) * w[..., None]
    return rgb


# ------------------------------------------------------------- animation
#
# Weather is the half of the trait that MOVES, and the useful structural
# fact is that almost none of the cost moves with it: the tone grade, the
# haze and the diffusion are byte-for-byte identical in every frame of a
# loop. Only the particle field and a couple of cheap modulations change.
#
# So a loop renders as ONE graded plate plus N cheap frames -- which is also
# exactly how a live client-side view would work: ship a single graded still
# and run the particles in a canvas. The expensive half is static; the half
# that animates is nearly free.
#
# Every motion here LOOPS SEAMLESSLY, because a visible jump at the wrap is
# the one thing that makes an ambient effect look cheap:
#
#   rain / snow / blizzard
#                particles live on a torus of (w+2m) x (h+2m) and travel a
#                WHOLE number of tiles per loop, so frame N == frame 0
#   snow sway    sinusoidal, an integer number of cycles per loop
#   fog / cloud  a blurred noise field rolled by exactly its own width
#   lightning    bumps placed away from the loop boundary
#   funnel       sway, banding, orbit and rise all integer cycles per loop
#
# The rain lean is DERIVED from that tile geometry rather than set by hand,
# so the streaks always point along the direction they actually travel. On
# the square canvas it works out at 1/3 -- down and to the right, matching
# the collection's cast-shadow convention rather than fighting it.
# One row per particle kind, because the three differ in every axis that
# matters and an if/else chain hid that. Read across a row and the motion
# design is right there:
#
#   tiles    (across, down) whole tiles travelled per loop -> seamless, and
#            the streak lean is DERIVED from it, so a mark always points
#            along the direction it actually travels
#   shape    "streak" (a leaning line) or "flake" (a soft disc)
#   width    stroke width for a streak
#   sway     sideways drift as a multiple of the band's extent; integer
#            cycles per loop
#   margin   how far outside the frame the torus reaches. It has to exceed
#            the longest mark a band can draw, or the leading edge of the
#            frame runs thin: blizzard streaks reach 156px sideways, which
#            is why they need more than rain's 80.
#   bands    (count, extent, opacity, blur) far band first. The near band
#            is bigger, sharper and moves at twice the speed; that
#            parallax is what gives the plate depth.
#
# rain and snow are unchanged from the values the proof sheets were
# approved at, and the RNG is drawn in the same order per shape, so their
# fields come out bit-identical.
_PARTICLE_KINDS = {
    "rain": dict(
        tiles=(1, 3), shape="streak", width=2, sway=0.0, margin=80,
        bands=((260, 34, 0.16, 2.6), (90, 66, 0.30, 1.1))),

    "snow": dict(
        tiles=(0, 1), shape="flake", width=0, sway=1.6, margin=80,
        bands=((300, 5, 0.30, 2.4), (110, 11, 0.55, 1.0))),

    # Driven snow: three tiles across for every one down, so the lean comes
    # out at 3 -- a shallow streak running down and to the RIGHT, which is
    # the direction CLAUDE.md already sends every cast shadow in the
    # collection. Wind that blew the other way would fight the key light.
    # There is no sway: a flake flutters, a driven flake does not.
    "blizzard": dict(
        tiles=(3, 1), shape="streak", width=3, sway=0.0, margin=200,
        bands=((420, 26, 0.34, 2.0), (150, 52, 0.62, 0.9))),
}

_SNOW_SWAY_CYCLES = 1     # integer -> seamless

_NOISE_CACHE = {}


def _noise_field(h, w, seed, blur):
    """A soft zero-mean noise field, cached. Rolling it is seamless."""
    key = (h, w, seed, round(blur, 2))
    if key not in _NOISE_CACHE:
        rng = np.random.default_rng(seed)
        small = rng.random((max(2, h // 40), max(2, w // 40)))
        img = Image.fromarray(
            (small * 255).astype(np.uint8), "L").resize(
                (w, h), Image.Resampling.BICUBIC).filter(
                    ImageFilter.GaussianBlur(blur))
        f = np.asarray(img, dtype=_F) / _F(255.0)
        _NOISE_CACHE[key] = f - f.mean()
    return _NOISE_CACHE[key]


def _flash(t):
    """Lightning as a function of loop position: a hard strike and its
    weaker echo, both well away from t=0 so the loop point stays clean."""
    a = 0.0
    for centre, width, amp in ((0.34, 0.018, 1.0), (0.39, 0.013, 0.5)):
        a += amp * float(np.exp(-((t - centre) / width) ** 2))
    return min(a, 1.0)


def _particles(size, kind, density, seed, t=0.0):
    """A soft particle field as a float 0..1 array, at loop position t.

    Deliberately STYLIZED, not photoreal. The cast is flat cartoon over lit
    spheres; photoreal rain in front of a Twinkie reads as a compositing
    error. Soft, chunky, low-opacity marks sit with the art.

    Two depth bands -- far ones small, faint and blurred, near ones larger,
    sharper and moving at twice the speed. That parallax is what gives the
    plate depth. Both are behind the character regardless, because the
    caller masks the whole effect layer.

    Seeded by token id, so a given token's rain always falls the same way.
    It is that token's weather, not a different random field every refresh.
    """
    w, h = size
    cfg = _PARTICLE_KINDS[kind]
    m = cfg["margin"]
    tile_w, tile_h = w + 2 * m, h + 2 * m
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), dtype=_F)

    across, down = cfg["tiles"]
    streak = cfg["shape"] == "streak"
    # streaks point along their own velocity vector
    lean = (tile_w * across) / float(tile_h * down)

    for depth, (count, extent, opacity, blur) in enumerate(cfg["bands"]):
        count = int(count * density)
        speed = depth + 1          # near band twice as fast -> parallax
        layer = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(layer)
        x0 = rng.random(count) * tile_w
        y0 = rng.random(count) * tile_h
        xs = (x0 + tile_w * across * speed * t) % tile_w - m
        ys = (y0 + tile_h * down * speed * t) % tile_h - m

        if streak:
            lens = rng.integers(int(extent * 0.6), extent, count)
            for x, y, ln in zip(xs, ys, lens):
                draw.line([(x, y), (x + ln * lean, y + ln)],
                          fill=255, width=cfg["width"])
        else:
            phase = rng.random(count) * 2.0 * np.pi
            if cfg["sway"]:
                xs = xs + np.sin(2.0 * np.pi * _SNOW_SWAY_CYCLES * t
                                 + phase) * (extent * cfg["sway"])
            rads = rng.integers(max(2, extent // 3), extent, count)
            for x, y, r in zip(xs, ys, rads):
                draw.ellipse([x - r, y - r, x + r, y + r], fill=255)

        layer = layer.filter(ImageFilter.GaussianBlur(blur))
        out = np.maximum(out, np.asarray(layer, dtype=_F)
                         / _F(255.0) * _F(opacity))
    return out


# ------------------------------------------------------------- the funnel
#
# The tornado is the one weather state that is a SHAPE rather than a field,
# and that is what makes it read as the most severe of the eight: rain,
# snow and fog change the whole plate uniformly, while a funnel is an
# object standing in it.
#
# It is built per frame in numpy rather than baked into grade_static(),
# because its placement is seeded per token and its centreline writhes.
# Everything that varies with t is an INTEGER number of cycles per loop, so
# the funnel at t=1 is the funnel at t=0:
#
#   sway    the centreline snakes, _SWAY_CYCLES cycles per loop
#   band    the helical banding climbs the trunk, _SPINS spins per loop
#   debris  orbits _TURNS times and rises exactly one canvas height
#   skirt   the ground dust is the shared noise field rolled by its width
#
# THE FUNNEL IS PLACED OFF THE FACE COLUMN ON PURPOSE. The character
# composites at a fixed canvas position around x=690 of 1393 (CLAUDE.md,
# "Canvas and face rule") and the protect mask puts the whole effect layer
# behind it -- so a centred funnel is a tornado you cannot see. It is
# seeded to the left or right quarter instead, and only its sway crosses
# back toward the middle.
#
# It is lit from the upper left like everything else in the collection: the
# trunk's left flank keeps more of the plate's own value and its right
# flank takes the full darkening, so the column reads as a cylinder rather
# than as a flat cut-out. Adding a funnel that ignored the key light would
# put it out of register with all 123 trait assets.
_TORNADO_SWAY_CYCLES = 1
_TORNADO_SPINS = 3        # coarse helical bands climbing the trunk
_TORNADO_SPINS2 = 6       # a finer band on top, so it reads as debris
_TORNADO_TURNS = 2
_TORNADO_OPACITY = 0.84
_TORNADO_SKIRT = 0.42
_TORNADO_DEBRIS = 0.62

_GRID_CACHE = {}


def _grid(h, w):
    """(v, x) broadcast grids: v is 0..1 top to bottom, x is pixels.

    Cached for the same reason _vig_field is -- the canvas is a fixed size
    and rebuilding a pair of full-frame float arrays per frame is pure
    memory traffic.
    """
    if (h, w) not in _GRID_CACHE:
        _GRID_CACHE[(h, w)] = (np.linspace(0.0, 1.0, h, dtype=_F)[:, None],
                               np.arange(w, dtype=_F)[None, :])
    return _GRID_CACHE[(h, w)]


def _funnel_axis(v, cx0, phase, s, w, t):
    """The snaking centreline, as a function of height.

    v may be the full column grid or a scalar, so the trunk and the ground
    skirt below it are guaranteed to agree on where the funnel actually is
    -- computing the skirt's centre separately is how it ends up sliding
    out from under the tip.
    """
    ang = (_F(2.0 * np.pi) * (_F(1.25) * v
                              + _F(_TORNADO_SWAY_CYCLES * t)) + phase)
    return cx0 + np.sin(ang) * (_F(w * 0.030) * (_F(0.35) + _F(0.65) * s))


def _funnel(size, density, seed, t=0.0):
    """The tornado, as (column, debris) float 0..1 arrays at loop position t.

    Each is in the same form as _particles() returns -- how much of each
    pixel is lerped toward a tint -- so the protect mask puts both behind
    the character like every other effect here. They come back separately
    only because they are lerped toward OPPOSITE tints; see
    TORNADO_DEBRIS_TINT for why one colour cannot do both.
    """
    w, h = size
    v, xs = _grid(h, w)
    rng = np.random.default_rng(seed ^ 0x70F0AD)

    # Left or right edge, never the face column. The offsets are far
    # enough out that the funnel's widest point still clears a wide body:
    # at 0.36 the trunk spans 0.00-0.28 of the canvas against a character
    # that starts around 0.25, and verify_sky.py measures what actually
    # survives the protect mask rather than trusting that arithmetic.
    side = -1.0 if rng.random() < 0.5 else 1.0
    cx0 = _F(w * (0.5 + side * (0.28 + 0.08 * rng.random())))
    phase = _F(rng.random() * 2.0 * np.pi)
    tip = _F(0.70 + 0.08 * rng.random())

    # Taper: wide where it leaves the cloud deck, a thin trunk at the tip.
    # The exponent is what makes it concave -- a straight cone reads as a
    # traffic bollard, not as a funnel.
    s = np.clip(v / tip, 0.0, 1.0)
    r = _F(w * 0.024) + _F(w * 0.115) * (1.0 - s) ** _F(1.8)
    cx = _funnel_axis(v, cx0, phase, s, w, t)

    u = (xs - cx) / r                       # -1..1 across the column
    inside = r - np.abs(xs - cx)
    feather = _F(0.22) * r + _F(6.0)
    body = smoothstep(inside / feather) * smoothstep((tip - v) / _F(0.06))

    # Helical banding climbing the trunk, at two frequencies. One sine
    # alone reads as a smooth searchlight beam; the second, faster band is
    # what turns it into a column of debris. Both climb an INTEGER number
    # of times per loop, so the texture wraps with everything else.
    band = (_F(0.5)
            + _F(0.35) * np.sin(_F(2.0 * np.pi)
                                * (_F(7.0) * v - _F(_TORNADO_SPINS * t))
                                + phase)
            + _F(0.15) * np.sin(_F(2.0 * np.pi)
                                * (_F(17.0) * v - _F(_TORNADO_SPINS2 * t))
                                + _F(1.7) * phase))

    # cylinder shading, key light upper left
    lit = np.clip(_F(0.5) - _F(0.5) * u, 0.0, 1.0)

    out = body * (_F(0.45) + _F(0.55) * band) * (_F(1.0) - _F(0.30) * lit)
    out *= _F(_TORNADO_OPACITY)

    # Ground dust where the tip meets the plate, broken up by the same
    # noise field the drifting states use so it is not a clean ellipse.
    tip_x = _funnel_axis(tip, cx0, phase, _F(1.0), w, t)
    dx = (xs - tip_x) / _F(w * 0.17)
    dy = (v - tip) / _F(0.055)
    skirt = smoothstep(_F(1.0) - (dx * dx + dy * dy)) * _F(_TORNADO_SKIRT)
    n = _noise_field(h, w, seed | 3, max(h, w) / 26.0)
    skirt *= np.clip(_F(1.0) + _F(2.4) * np.roll(
        n, int(round(t * w)), axis=1), 0.0, 1.6)
    np.maximum(out, skirt, out=out)

    # Debris orbiting the trunk and rising, drawn with PIL because a few
    # hundred small marks are cheaper to rasterise than to broadcast. It is
    # weighted toward the ground -- a tornado picks its debris up from
    # under itself, so an even spread up the whole column reads wrong --
    # and each mark is stretched ALONG its orbit, which is what stops a
    # field of circles from reading as bubbles.
    deb = np.zeros((h, w), dtype=_F)
    count = int(190 * density)
    if count:
        layer = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(layer)
        th0 = rng.random(count) * 2.0 * np.pi
        v0 = rng.random(count) ** 0.55            # biased toward the ground
        k = 1.05 + 0.75 * rng.random(count)
        rad = rng.integers(3, 9, count)
        vv = (v0 - t) % 1.0                       # rises; one tile per loop
        th = th0 + 2.0 * np.pi * _TORNADO_TURNS * t
        ss = np.clip(vv / float(tip), 0.0, 1.0)
        rr = w * 0.024 + w * 0.115 * (1.0 - ss) ** 1.8
        cc = np.asarray(_funnel_axis(vv.astype(_F), cx0, phase,
                                     ss.astype(_F), w, t), dtype=float)
        px = cc + np.cos(th) * k * rr
        py = vv * h
        # sin(theta) is depth: a speck on the near side of the orbit is
        # larger and more opaque than the same speck behind the trunk.
        near = 0.40 + 0.60 * (0.5 + 0.5 * np.sin(th))
        for x, y, rd, nr, sv in zip(px, py, rad, near, ss):
            if sv >= 1.0:
                continue                          # below the tip, no funnel
            ex, ey = rd * nr * 1.9, rd * nr * 0.8
            draw.ellipse([x - ex, y - ey, x + ex, y + ey],
                         fill=int(255 * nr))
        deb = np.asarray(layer.filter(ImageFilter.GaussianBlur(1.1)),
                         dtype=_F) / _F(255.0) * _F(_TORNADO_DEBRIS)

    return np.clip(out, 0.0, 1.0, out=out), deb


def _combine(sky, wet):
    """Merge the sky and weather tables into one parameter set.

    Exposure and saturation multiply, contrast and lift add, so weather
    modifies whatever the sky already did -- rain at night comes out darker
    than rain at noon without either table knowing the other exists.

    `sh_tint` is the exception: it is a COLOUR, and two colours do not
    combine by multiplying or adding, so a weather state that declares one
    replaces the phase's outright while `sh_amt` still sums. That is the
    right shape for what it describes -- heavy weather changes what colour
    the shadows are, not just how much of them there is. A blizzard's
    shadows are the whiteout, not the dusk behind it.

    It also has to be READ at all. The key was declared on `storm` from the
    start and silently dropped here, so storm's shadows have been taking
    whatever tint the phase supplied instead of the navy storm asked for.
    Honouring it moves storm and nothing else: measured over three tokens,
    the plate shifts dE 1.2 at `day` and 1.4-6.4 across the rest, largest
    at the golden and blue phases where the phase's own rose or blue tint
    is furthest from storm's navy. None of it reaches the character -- the
    protect mask is upstream of all of this. The alternative was to add two
    more states carrying a parameter that does nothing.
    """
    return dict(
        exposure=sky.get("exposure", 1.0) * wet.get("exposure", 1.0),
        contrast=sky.get("contrast", 0.0) + wet.get("contrast", 0.0),
        lift=sky.get("lift", 0.0) + wet.get("lift", 0.0),
        sat=sky.get("sat", 1.0) * wet.get("sat", 1.0),
        vignette=sky.get("vignette", 0.0),
        sh_tint=wet.get("sh_tint", sky.get("sh_tint", (0.06, 0.09, 0.20))),
        sh_amt=sky.get("sh_amt", 0.0) + wet.get("sh_amt", 0.0),
        hi_tint=sky.get("hi_tint", (0.90, 0.94, 1.00)),
        hi_amt=sky.get("hi_amt", 0.0))


# Ops that alter the plate SPATIALLY -- blur, particles, a drifting field.
# 'clear' declares none of them, which is what makes it free: a clear sky
# can tone-grade the plate but it can never soften or resample it.
_SPATIAL_KEYS = ("diffuse", "particles", "drift", "flash")


def has_motion(weather):
    """True if this weather state actually moves.

    A state with no motion must never be exported as an animation. Encoding
    N identical frames of a still costs resolution and a lossy round-trip
    to say nothing at all -- see animate.py.
    """
    wet = WEATHER_STATES[weather]
    return bool(wet.get("particles") or wet.get("flash")
                or wet.get("drift", 0.0) > 1e-4)


def is_spatial(weather):
    """True if this weather state blurs, resamples or draws over the plate."""
    wet = WEATHER_STATES[weather]
    return (wet.get("diffuse", 0.0) > 0.05
            or bool(wet.get("particles")) or bool(wet.get("flash"))
            or wet.get("drift", 0.0) > 1e-4)


def is_identity(phase, weather):
    """True if this grade is a no-op -- day + clear, and nothing else.

    A service should check this FIRST and serve the original minted bytes
    unchanged rather than re-encoding them. The dynamic layer must never
    cost image quality in the state where it is doing nothing, and that is
    the state most holders are in most of the time.
    """
    sky, wet = SKY_STATES[phase], WEATHER_STATES[weather]
    p = _combine(sky, wet)
    return (abs(p["exposure"] - 1.0) < 1e-4 and abs(p["contrast"]) < 1e-4
            and p["lift"] < 1e-5 and abs(p["sat"] - 1.0) < 1e-4
            and p["sh_amt"] < 1e-4 and p["hi_amt"] < 1e-4
            and abs(p["vignette"]) < 1e-4
            and wet.get("haze_amt", 0.0) < 1e-4
            and wet.get("diffuse", 0.0) <= 0.05
            and not wet.get("particles"))


def grade_static(base, phase="day", weather="clear"):
    """The frame-invariant half: tone, haze and diffusion.

    Split out because it is the whole cost of a render and it does not
    change across a loop. Call once, then pass the result to frame() as
    many times as there are frames.
    """
    sky, wet = SKY_STATES[phase], WEATHER_STATES[weather]
    p = _combine(sky, wet)
    arr = np.asarray(base.convert("RGBA"), dtype=_F) / _F(255.0)
    rgb, alpha = arr[..., :3].copy(), arr[..., 3]

    fx = _tone(rgb.copy(), p["exposure"], p["contrast"], p["lift"],
               p["sat"], p["sh_tint"], p["sh_amt"], p["hi_tint"],
               p["hi_amt"])

    # Fog: lerp the plate toward the haze colour. The character is excluded
    # by the mask, so this alone reads as depth.
    if wet.get("haze_amt", 0.0) > 1e-4:
        fx += (_c(wet["haze"]) - fx) * _F(wet["haze_amt"])

    # Diffusion: overcast and fog genuinely soften a scene.
    if wet.get("diffuse", 0.0) > 0.05:
        blurred = Image.fromarray(
            (np.clip(fx, 0, 1) * 255).astype(np.uint8), "RGB").filter(
                ImageFilter.GaussianBlur(wet["diffuse"]))
        fx = np.asarray(blurred, dtype=_F) / _F(255.0)

    return {"fx": fx, "rgb": rgb, "alpha": alpha, "p": p, "wet": wet}


def frame(static, protect, t=0.0, seed=0, strength=1.0):
    """One frame of a loop, from a cached grade_static() result."""
    fx = static["fx"].copy()
    rgb, alpha, p, wet = (static["rgb"], static["alpha"],
                          static["p"], static["wet"])
    h, w = rgb.shape[:2]

    # Drifting density: what makes fog and overcast read as WEATHER rather
    # than as a flat filter. Rolling the field is seamless by construction.
    if wet.get("drift", 0.0) > 1e-4:
        field = _noise_field(h, w, seed | 1, max(h, w) / 22.0)
        rolled = np.roll(field, int(round(t * w)), axis=1)
        fx = fx + rolled[..., None] * _F(wet["drift"])

    # Particles, lerped toward the kind's tint. For rain, snow and driven
    # snow that reads as screening them in -- they glow rather than paint
    # over. The tornado uses the same one line with a DARK tint, because a
    # funnel subtracts light from the plate; nothing else about the
    # compositing needs to know which of the two it is doing.
    if wet.get("particles"):
        kind = wet["particles"]
        dens = wet.get("density", 1.0)
        if kind == "tornado":
            col, deb = _funnel((w, h), dens, seed, t)
            fx = fx + (_c(PARTICLE_TINT[kind]) - fx) * col[..., None]
            fx = fx + (_c(TORNADO_DEBRIS_TINT) - fx) * deb[..., None]
        else:
            part = _particles((w, h), kind, dens, seed, t)[..., None]
            fx = fx + (_c(PARTICLE_TINT[kind]) - fx) * part

    # Lightning, on the plate only like everything else here.
    if wet.get("flash") and t > 0.0:
        a = _flash(t)
        if a > 1e-3:
            fx = fx + (_c((0.86, 0.90, 1.0)) - fx) * _F(a * 0.55)

    # Vignette, tinted with the shadow colour so it belongs to the phase.
    if abs(p["vignette"]) > 1e-4:
        v = (_vig_field(h, w) * _F(p["vignette"]))[..., None]
        fx = fx * (1.0 - v) + _c(p["sh_tint"]) * v * _F(0.5)

    # Filmic shoulder then clip, matching grade.py's tail so a plate that
    # passes through both passes never hard-clips twice.
    s = 0.92
    over = fx > s
    fx[over] = s + (1 - s) * np.tanh((fx[over] - s) / (1 - s))
    fx = np.clip(fx, 0.0, 1.0)

    # THE RULE: blend only where the plate is exposed. pr == 1 is character,
    # sticker or overlay and comes through untouched.
    pr = np.asarray(protect.convert("L"), dtype=_F) / _F(255.0)
    pr = np.clip(pr + (1.0 - pr) * _F(1.0 - strength), 0.0, 1.0)[..., None]
    out = rgb * pr + fx * (1.0 - pr)

    return Image.fromarray(
        (np.dstack([np.clip(out, 0, 1), alpha[..., None]]) * 255.0 + 0.5)
        .astype(np.uint8), "RGBA")


def apply_sky(base, protect, phase="day", weather="clear",
              seed=0, strength=1.0, t=0.0):
    """Grade the background of a finished token render (a single still).

    base     : RGBA PIL image -- the minted token, unmodified.
    protect  : L PIL image    -- the mask create_image(mask_path=...) wrote.
    phase    : a key of SKY_STATES (from solar.sun_phase()).
    weather  : a key of WEATHER_STATES.
    seed     : token id; makes the particle field stable per token.
    strength : 0..1 global dial on the whole effect, for previewing.
    t        : 0..1 position in the weather loop.

    Returns a new RGBA image the same size. The character is untouched.
    """
    if phase not in SKY_STATES:
        raise KeyError(f"unknown sky phase {phase!r}")
    if weather not in WEATHER_STATES:
        raise KeyError(f"unknown weather {weather!r}")
    if base.mode != "RGBA":
        base = base.convert("RGBA")
    if protect.size != base.size:
        protect = protect.resize(base.size, Image.Resampling.LANCZOS)

    # DAY + CLEAR is the identity grade, and it is also the single most
    # requested state -- most holders, most of the time, are in daylight. It
    # must cost nothing rather than spend a full pass computing a no-op.
    if strength <= 1e-4 or is_identity(phase, weather):
        return base.copy()

    return frame(grade_static(base, phase, weather), protect,
                 t=t, seed=seed, strength=strength)


def describe(phase, weather):
    """Display strings for the two dynamic metadata attributes."""
    return (phase.replace("_", " ").title(), weather.title())
