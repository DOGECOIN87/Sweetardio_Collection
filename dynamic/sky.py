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


def luma(rgb):
    return (_LUMA[0] * rgb[..., 0] + _LUMA[1] * rgb[..., 1]
            + _LUMA[2] * rgb[..., 2])


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


# ------------------------------------------------------------------ sky
#
# ONE STATE. The collection ships a single lighting condition -- the one
# every plate was approved at in ULTIMATE_GRADE_LOG.md and every one of the
# 123 trait assets is authored to -- and `day` is defined to be the
# identity: it changes nothing at all.
#
# There used to be eight. high_noon, golden dawn and dusk, blue dawn and
# dusk, twilight and night were a real time-of-day trait driven by
# solar.py's NOAA solar position, and they are RETIRED: the collection is
# not changing anybody's hour. Keeping seven tuned grade tables and a whole
# verification axis for something that never renders is the failure this
# codebase's own history keeps recording, so they are gone rather than
# commented out. They are in git if a night edition is ever wanted.
#
# The `phase` parameter survives on every entry point. It costs nothing,
# it keeps is_identity() meaning what it says, and it is where a second
# lighting condition would go back if one is ever added.
SKY_STATES = {
    "day": dict(),  # identity -- the canonical mint, and the only one
}

# ------------------------------------------------------------- weather
#
# Seven visual states in two tiers, collapsed from Open-Meteo's ~100 WMO
# codes by weather.py.
#
# THERE IS NO 'clear' STATE. A clear sky is the absence of weather, not a
# weather worth grading: the minted token already IS the clear-sky render,
# so a state that reproduced it would be a name for doing nothing. Pass
# weather=None instead, which every function here accepts, and a service
# should serve the ORIGINAL MINTED BYTES rather than re-encode a copy of
# them -- see is_identity(). That is the state most holders are in most of
# the time, and it must cost the plate nothing at all.
#
# The first FOUR are the ordinary sky, and that is the ceiling: past it
# they stop reading as distinct and start reading as noise -- drizzle and
# light rain are the same trait however different the code is.
#
# `overcast` was the fifth and is RETIRED. It was the weakest state in the
# table by every measure taken here: it sat dE 3.3 from `rain` and 4.8 from
# `snow` on the plate, closer to both than DISTINCT_DE would let a new
# state be, and what it actually drew was a mild grey grade with a drifting
# shadow -- a filter over the art rather than weather happening in it. The
# states that survived all put something IN the frame: a fog bank, falling
# particles, a drift, a funnel, a waterline. A cloudy sky puts nothing
# there, and a cloudy sky is what most of the world has most of the time,
# so it was also the state most likely to be permanently laid over a
# holder's plate for nothing. weather.py maps its WMO codes to None now.
#
# The last two are SEVERE, and they are a different kind of thing rather
# than more of the same. They are allowed past the ordinary-sky ceiling
# because they are not competing with it: a holder sees `rain` most
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
#   diffuse   px of blur -- fog and driven snow genuinely soften a scene
#   haze/amt  colour the plate is lerped toward (fog)
#   sh_tint   shadow colour; a weather state that declares one OVERRIDES
#             the phase's, because severe weather changes what colour the
#             shadows are and not merely how much of them there is
#   particles which sprite pass to run, and how dense
WEATHER_STATES = {
    # Fog ROLLS ALONG THE GROUND; it is not a filter over the whole frame.
    # Flat full-frame haze was the single biggest reason the plate stopped
    # being readable -- it took the background's detail down to 24% of the
    # mint's and its chroma to 41%, over the entire plate, for a trait the
    # holder did not choose and cannot turn off. Banded, the same haze is
    # denser than it was where it sits and the upper half of the plate is
    # given back untouched.
    #
    # `band` gates the haze AND the diffusion together, so the fog bank is
    # soft and the sky above it stays sharp. The bank's top edge undulates
    # and rolls, which is what makes it read as fog rather than as a
    # gradient someone laid over the bottom of the picture.
    "fog": dict(
        exposure=0.98, contrast=-0.16, lift=0.070, sat=0.74, diffuse=4.2,
        haze=(0.72, 0.755, 0.80), haze_amt=0.62, drift=0.040,
        band=dict(top=0.52, feather=0.30, amp=0.075)),

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
        exposure=1.06, contrast=-0.17, lift=0.075, sat=0.52, diffuse=2.0,
        haze=(0.90, 0.93, 0.96), haze_amt=0.52,
        sh_tint=(0.66, 0.70, 0.76), sh_amt=0.10,
        particles="blizzard", density=1.9, drift=0.042,
        band=dict(top=0.52, feather=0.34, amp=0.070),
        # Snow SETTLES. The driven snow is the event and the drift along
        # the bottom is the evidence it has been going on a while, which
        # is what separates a blizzard from heavy snow at a glance. Its
        # surface undulates like real drifts rather than sitting level,
        # and it is opaque where it lies -- but it lies in the bottom
        # eighth of the frame, so it costs the plate almost nothing.
        accum=dict(top=0.88, feather=0.045, amp=0.030,
                   tint=(0.94, 0.96, 0.98), amount=0.94)),

    # The tornado is the one state that is a SHAPE rather than a field.
    # Every other weather here changes the whole plate uniformly; a funnel
    # is an object standing in it, which is exactly why it reads as the
    # rarest thing in the set and why it needs its own pass (_funnel).
    #
    # The tone half is a supercell, not a night: green-brown, lifted and
    # flat, with the saturation pulled out of everything the funnel is not.
    # The funnel carries this state, so the tone half does not have to.
    # It used to darken and desaturate the whole plate hard enough to make
    # the funnel visible -- 14% of the plate's chroma survived, the worst
    # in the set -- which is the wrong lever: the funnel now has a LIT RIM
    # (see TORNADO_RIM_TINT) and reads by local contrast instead, so the
    # supercell grade can stay light enough to leave the background alone.
    "tornado": dict(
        exposure=0.80, contrast=-0.04, lift=0.022, sat=0.74, diffuse=0.7,
        haze=(0.34, 0.35, 0.26), haze_amt=0.14,
        sh_tint=(0.13, 0.14, 0.09), sh_amt=0.18,
        particles="tornado", density=1.0, drift=0.030,
        # Debris blown ACROSS THE PLATE, not just orbiting the trunk. A
        # tornado throws things a long way from itself, and it is what
        # tells the eye the whole scene is inside the event rather than
        # watching one from a safe distance.
        blown="debris", blown_density=2.5),

    # THE ONLY STATE THAT TOUCHES THE CHARACTER. Everything else in this
    # file composites behind the figure and comes out bit-identical to the
    # mint; a flood cannot, because water the character is standing in
    # front of is not a flood, it is a puddle backdrop. So `submerge` runs
    # AFTER the protect blend, over the finished frame, and only below the
    # waterline. See _submerge() for what that costs and what still holds.
    #
    # The waterline sits at 0.60 of the canvas: the face composites at
    # y=601 of 1393 (CLAUDE.md, "Canvas and face rule") and every body's
    # base is lower still, so this is chest-deep on the cast -- the figure
    # is unmistakably IN the water while its face, the thing a holder
    # bought, stays above it. Fully submerging the cast would drown the art.
    #
    # The tone half is what a flood day actually looks like: the rain has
    # stopped, the light is flat and the sky is dishwater. The drama is in
    # the water, not in the grade.
    "flooded": dict(
        exposure=0.94, contrast=-0.12, lift=0.030, sat=0.80, diffuse=0.5,
        haze=(0.44, 0.48, 0.50), haze_amt=0.10,
        sh_tint=(0.10, 0.15, 0.18), sh_amt=0.14, drift=0.024,
        submerge=dict(
            level=0.60,           # waterline, fraction of canvas height
            amp=0.016,            # how far the surface undulates
            feather=0.004,        # softness of the waterline itself
            refract=0.009,        # sideways displacement under water
            refract_freq=8.0,     # wobbles down the depth
            refract_cycles=2,     # integer -> seamless
            reflect=0.46,         # mirrored sky/figure under the surface
            reflect_fade=0.10,    # how fast that reflection dies with depth
            tint=(0.15, 0.33, 0.40),
            tint_amt=0.30,        # at the surface
            deep_amt=0.72,        # at the bottom of the frame
            darken=0.40,
            foam=0.60,            # the bright line where air meets water
            foam_width=0.005,
            caustic=0.13,
            caustic_cycles=1),
        particles="rain", density=0.7),
}

# What each particle field is lerped TOWARD. Rain is a cold near-white,
# snow and driven snow are white, and the tornado is the only dark one --
# a funnel subtracts light from the plate rather than adding it.
PARTICLE_TINT = {
    "rain": (0.80, 0.86, 0.98),
    "snow": (1.00, 1.00, 1.00),
    "blizzard": (1.00, 1.00, 1.00),
    "tornado": (0.78, 0.78, 0.75),
    "debris": (0.15, 0.13, 0.10),
}

# The funnel is the one particle field that cannot be drawn in a single
# colour. The column itself is condensation and it is PALER than the
# supercell grade behind it -- that is what keeps it visible at every phase
# from high noon to night, where a dark funnel disappears into a dark sky
# the moment the sun goes down. The debris it throws is dirt, and dirt is
# DARKER than everything. Give them one shared tint and whichever one loses
# the argument turns into a row of pale bubbles floating beside the trunk.
TORNADO_DEBRIS_TINT = (0.13, 0.12, 0.10)

# The lit edge of the funnel. A funnel that separates only by being paler
# than the sky needs the sky kept dark to be seen, and a dark sky is a
# background nobody can read -- which is the whole reason the tone half of
# `tornado` is as gentle as it is. A RIM is local contrast instead: a
# bright edge reads against a light plate and a dark one alike, so the
# funnel stops depending on how murky the grade is. It sits on the upper
# LEFT flank, the collection's key light.
TORNADO_RIM_TINT = (0.86, 0.87, 0.84)
_TORNADO_RIM = 0.46


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

    # Torn-up ground blown across the frame. Two tiles across for every
    # one down, so it leans shallower than rain and steeper than driven
    # snow -- debris is heavy and does not travel as flat as a snowflake.
    # Sparse on purpose: this is the only DARK particle field, and dark
    # marks over a plate cost legibility far faster than bright ones.
    # Three bands rather than two: the far haze of grit, the mid field,
    # and a near band of large pieces moving at three times the far band's
    # speed. The third band is what stops it reading as texture -- a
    # tornado throws whole objects, not only dust.
    "debris": dict(
        tiles=(2, 1), shape="streak", width=4, sway=0.0, margin=220,
        bands=((240, 20, 0.26, 2.6), (95, 40, 0.42, 1.3),
               (26, 76, 0.58, 0.7))),
}

_SNOW_SWAY_CYCLES = 1     # integer -> seamless

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


# ------------------------------------------------------------ ground band
#
# Weather that sits in a BAND along the bottom of the plate rather than
# over all of it. Fog rolls along the ground and snow settles on it, and
# both were previously applied flat across the whole frame -- which is the
# single biggest reason the plate stopped being readable. A band puts the
# effect where the effect actually is and gives the upper two-thirds of
# the background back.
#
# The top edge undulates, because a fog bank with a straight edge reads as
# a gradient and a snow line with one reads as a rectangle. It is a sum of
# three sines in x, each advancing an INTEGER number of cycles per loop, so
# the bank rolls and still wraps exactly.
#
#   top      where the band's top edge sits, 0 = top of frame, 1 = bottom
#   feather  how far above that it fades out, in fractions of height
#   amp      how far the top edge undulates
_BAND_HARMONICS = ((1.0, 1, 0.60), (2.3, 2, 0.28), (4.1, 3, 0.12))

_UNDULATE_CACHE = {}


def _undulate(w, seed, t):
    """A 1 x w wave along the bottom edge's top line, at loop position t."""
    t = float(t) % 1.0
    key = (w, seed, round(t, 6))
    if key not in _UNDULATE_CACHE:
        if len(_UNDULATE_CACHE) > 512:
            _UNDULATE_CACHE.clear()
        rng = np.random.default_rng(seed ^ 0xBA4D)
        xs = np.linspace(0.0, 1.0, w, dtype=_F)[None, :]
        out = np.zeros((1, w), dtype=_F)
        for freq, cycles, amp in _BAND_HARMONICS:
            out += _F(amp) * np.sin(
                _F(2.0 * np.pi) * (_F(freq) * xs + _F(cycles * t))
                + _F(rng.random() * 2.0 * np.pi))
        _UNDULATE_CACHE[key] = out
    return _UNDULATE_CACHE[key]


def _band_field(h, w, cfg, seed, t):
    """0 above the band, 1 inside it, feathered across the undulating top."""
    v, _ = _grid(h, w)
    top = _F(cfg["top"]) + _undulate(w, seed, t) * _F(cfg.get("amp", 0.0))
    return smoothstep((v - top) / _F(cfg["feather"]))


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
_TORNADO_OPACITY = 0.96
_TORNADO_SKIRT = 0.62
_TORNADO_DEBRIS = 0.62

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
    """The tornado, as (amount, shade, rim, debris) arrays at position t.

    `amount` is how much of each pixel the funnel covers and `shade` is how
    bright the funnel is there -- they are SEPARATE because a funnel is an
    opaque object with form on it, and folding the form into the coverage
    makes a half-transparent one instead. That was the first version, and
    over a light plate it read as a smudge on the lens rather than as a
    tornado: the shading multiplied the coverage down to about half in the
    core, so the plate showed straight through the trunk.

    `rim` and `debris` are separate again because they are lerped toward
    DIFFERENT tints from the column -- see TORNADO_RIM_TINT and
    TORNADO_DEBRIS_TINT for why one colour cannot do the job.
    """
    w, h = size
    t = float(t) % 1.0
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

    # Cylinder shading from the key light, which CLAUDE.md pins to the
    # upper left at roughly 45 degrees. Two components, because one is not
    # a direction:
    #
    #   across  1 on the left flank, 0 on the right -- the cylinder turning
    #           away from the light
    #   down    1 at the cloud deck, falling toward the tip -- the light
    #           coming from ABOVE as well as from the side
    #
    # With only `across` the funnel was lit from due left: correct in x,
    # flat in y, and measurably brighter at the BOTTOM than the top once
    # the taper was accounted for. Every other asset in the collection is
    # lit at 45 degrees, so a column lit from the side alone sits wrong
    # next to them even when nobody can say why.
    #
    # The column's tint is PALER than the plate, so the lit side must take
    # MORE of it, not less. (It took less while the tint was still dark,
    # and the polarity did not follow the tint when that changed -- which
    # lit the funnel from the RIGHT, the one direction the collection
    # never uses.)
    across = np.clip(_F(0.5) - _F(0.5) * u, 0.0, 1.0)
    down = np.clip(_F(1.0) - v, 0.0, 1.0)
    lit = np.clip(_F(0.62) * across + _F(0.38) * down, 0.0, 1.0)

    shade = (_F(0.45) + _F(0.55) * band) * (_F(0.62) + _F(0.38) * lit)
    out = body * _F(_TORNADO_OPACITY)

    # The lit edge: a narrow band on the left flank only. This is what
    # carries the funnel on a plate that has NOT been darkened, so the
    # tone grade can stay light enough to leave the background readable.
    # ...and the rim rides the same key: strongest where the flank faces
    # up and to the left, fading toward the tip where the light rakes past
    # rather than catching it.
    rim = (body * smoothstep((-u - _F(0.42)) / _F(0.34))
           * (_F(1.0) - _F(0.45) * v) * _F(_TORNADO_RIM))

    # Ground dust where the tip meets the plate, broken up by the same
    # noise field the drifting states use so it is not a clean ellipse.
    tip_x = _funnel_axis(tip, cx0, phase, _F(1.0), w, t)
    dx = (xs - tip_x) / _F(w * 0.17)
    dy = (v - tip) / _F(0.055)
    skirt = smoothstep(_F(1.0) - (dx * dx + dy * dy)) * _F(_TORNADO_SKIRT)
    n = _noise_field(h, w, seed | 3, max(h, w) / 26.0)
    skirt *= np.clip(_F(1.0) + _F(2.4) * np.roll(
        n, int(round(t * w)), axis=1), 0.0, 1.6)
    # Ground dust is lit from open sky rather than shaded by the trunk, so
    # where the skirt is the thicker of the two it brings its own shade.
    shade = np.where(skirt > out, _F(0.92), shade)
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
        v0 = rng.random(count) ** 0.75            # biased toward the ground
        k = 1.05 + 0.75 * rng.random(count)
        # Sized as a FRACTION OF THE CANVAS, like the funnel it orbits, not
        # in absolute pixels. The loops export at 512 while the mint is
        # 1393, so an absolute radius comes out 2.7x oversized in exactly
        # the render anyone actually watches -- the debris stops reading as
        # grit around a funnel and starts reading as boulders.
        rad = w * (0.0022 + 0.0043 * rng.random(count))
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
        deb = np.asarray(
            layer.filter(ImageFilter.GaussianBlur(max(0.6, w / 995.0))),
            dtype=_F) / _F(255.0) * _F(_TORNADO_DEBRIS)

    return (np.clip(out, 0.0, 1.0, out=out),
            np.clip(shade, 0.0, 1.0), np.clip(rim, 0.0, 1.0, out=rim), deb)


def _wet(weather):
    """The weather table for a state name, or an empty one for None.

    None is a clear sky: no weather, not a weather that happens to do
    nothing. Every entry point takes it, so a caller never has to name a
    state to say there isn't one.
    """
    return {} if weather is None else WEATHER_STATES[weather]


# ------------------------------------------------------------ the flood
#
# `flooded` is the only state that touches the character, and this is the
# function that does it. It runs AFTER the protect blend, on the finished
# frame, so what it displaces and tints is the composited token -- plate,
# body, footwear and all -- rather than the plate alone.
#
# THAT IS A DELIBERATE BREAK IN THIS MODULE'S ONE RULE, and it is confined
# to below the waterline. Above the line the rule still holds exactly:
# every protected pixel comes back bit-identical to the mint, and
# verify_sky.py checks that separately for a submerging state instead of
# skipping it. Alpha is never touched at any depth -- that is not a taste
# question, it is what the whole cast's face geometry is registered to.
#
# The water is four things stacked, cheapest first:
#
#   refraction   each row under the surface is displaced sideways by a
#                sine of its depth. It is what makes the submerged half
#                read as SEEN THROUGH something rather than tinted.
#   reflection   the frame mirrored about the waterline, strong just under
#                it and dying within a tenth of the canvas. This is the
#                half that actually sells water; tint and wobble alone
#                read as coloured glass.
#   depth        tint and darkening ramping from the surface to the bottom
#                of the frame, so the water has a floor rather than a
#                uniform wash.
#   foam         a bright line exactly on the boundary. Air meeting water
#                is the highest-contrast edge in any real flood photo, and
#                without it the surface is a colour change, not a surface.
#
# Everything that varies with t is an integer number of cycles per loop,
# like every other motion here.
def _submerge(rgb, cfg, seed, t=0.0):
    """Put everything below the waterline under water. rgb is (h, w, 3)."""
    h, w = rgb.shape[:2]
    t = float(t) % 1.0
    v, xs = _grid(h, w)
    rng = np.random.default_rng(seed ^ 0xF10D)
    phase = _F(rng.random() * 2.0 * np.pi)

    # The surface: a level plus the shared undulation, so it rolls like
    # the fog bank and the snow drifts do rather than sitting ruler-flat.
    surf = _F(cfg["level"]) + _undulate(w, seed | 11, t) * _F(cfg["amp"])
    depth = v - surf                                   # >0 under water
    under = smoothstep(depth / _F(cfg["feather"]))

    if float(under.max()) <= 0.0:
        return rgb

    # 1. refraction -- a sideways offset that varies with depth
    off = (_F(cfg["refract"] * w)
           * np.sin(_F(2.0 * np.pi) * (_F(cfg["refract_freq"]) * v
                                       + _F(cfg["refract_cycles"] * t))
                    + phase))
    xi = np.clip(np.rint(xs + off), 0, w - 1).astype(np.intp)
    rows = np.arange(h, dtype=np.intp)[:, None]
    water = rgb[rows, xi]

    # 2. reflection -- the frame mirrored about the surface, fading down
    ys = np.clip(np.rint((surf * _F(2.0) - v) * _F(h)),
                 0, h - 1).astype(np.intp)
    mirror = rgb[ys, np.clip(xi, 0, w - 1)]
    r = (_F(cfg["reflect"])
         * np.exp(-np.maximum(depth, 0.0) / _F(cfg["reflect_fade"])))
    water = water + (mirror - water) * r[..., None]

    # 3. depth -- tint and darken toward the bottom of the frame
    k = np.clip(depth / _F(max(1.0 - cfg["level"], 1e-3)), 0.0, 1.0)
    water = water * (_F(1.0) - _F(cfg["darken"]) * k)[..., None]
    amt = _F(cfg["tint_amt"]) + (_F(cfg["deep_amt"])
                                 - _F(cfg["tint_amt"])) * k
    water = water + (_c(cfg["tint"]) - water) * amt[..., None]

    # Caustics: the bright net of light on a shallow bottom. Rolled by
    # exactly its own width, so it wraps like every other drifting field.
    if cfg.get("caustic", 0.0) > 1e-4:
        n = _noise_field(h, w, seed | 13, max(h, w) / 30.0)
        rolled = np.roll(n, int(round(t * cfg.get("caustic_cycles", 1) * w)),
                         axis=1)
        water = water + (rolled * (_F(1.0) - k) * _F(cfg["caustic"]))[..., None]

    # 4. foam -- the line where air meets water
    if cfg.get("foam", 0.0) > 1e-4:
        band = np.exp(-(depth / _F(cfg["foam_width"])) ** 2)
        water = water + (_F(1.0) - water) * (band * _F(cfg["foam"]))[..., None]

    np.clip(water, 0.0, 1.0, out=water)
    return rgb * (1.0 - under[..., None]) + water * under[..., None]


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
    to say nothing at all -- see animate.py. Since `clear` became None
    rather than a state, every NAMED state moves; this stays as the guard
    that keeps it that way.
    """
    wet = _wet(weather)
    return bool(wet.get("particles") or wet.get("blown") or wet.get("flash")
                or wet.get("band") or wet.get("submerge")
                or wet.get("drift", 0.0) > 1e-4)


def is_spatial(weather):
    """True if this weather state blurs, resamples or draws over the plate."""
    wet = _wet(weather)
    return (wet.get("diffuse", 0.0) > 0.05
            or bool(wet.get("particles")) or bool(wet.get("blown"))
            or bool(wet.get("flash")) or bool(wet.get("band"))
            or bool(wet.get("submerge"))
            or wet.get("drift", 0.0) > 1e-4)


def touches_character(weather):
    """True if this state modifies pixels the protect mask covers.

    THE ONE EXCEPTION to the rule the rest of this module is built on, and
    it exists so the exception is a thing code can ask about rather than a
    thing someone has to remember. `flooded` is the only True today.

    A caller that promises a holder their character is untouched should
    test this, not hardcode a name. verify_sky.py uses it to decide which
    check to run: a state that does NOT touch the character must come back
    bit-identical over the whole mask, and one that does must still come
    back bit-identical ABOVE its waterline.
    """
    return bool(_wet(weather).get("submerge"))


def waterline(weather):
    """(highest, lowest) the water can ever reach, as fractions of height.

    DERIVED from the submerge config rather than declared beside it, so it
    cannot drift from the level the water actually reaches when someone
    retunes the surface.

    Both ends are load-bearing and verify_sky.py checks both:

      highest  above this line a submerging state is still bound by the
               module's rule -- protected pixels come back bit-identical.
      lowest   the water must stay clear of the FACE. The face hole is
               250px wide about y=601 of a 1393 canvas, so its underside
               is at 0.52; water over that line drowns the one part of the
               token a holder actually looks at.

    Returns None for a state that does not submerge.
    """
    cfg = _wet(weather).get("submerge")
    if cfg is None:
        return None
    # `under` is exactly zero at or above the surface, so the feather only
    # matters below it -- subtracted from the top anyway, to be safe rather
    # than exactly right.
    return (cfg["level"] - cfg["amp"] - cfg["feather"],
            cfg["level"] + cfg["amp"])


def is_identity(phase, weather):
    """True if this grade is a no-op -- day with no weather, and nothing else.

    A service should check this FIRST and serve the ORIGINAL MINTED BYTES
    unchanged rather than re-encoding them. The dynamic layer must never
    cost image quality in the state where it is doing nothing, and that is
    the state most holders are in most of the time -- which is exactly why
    there is no `clear` state to render instead.
    """
    sky, wet = SKY_STATES[phase], _wet(weather)
    p = _combine(sky, wet)
    return (abs(p["exposure"] - 1.0) < 1e-4 and abs(p["contrast"]) < 1e-4
            and p["lift"] < 1e-5 and abs(p["sat"] - 1.0) < 1e-4
            and p["sh_amt"] < 1e-4 and p["hi_amt"] < 1e-4
            and wet.get("haze_amt", 0.0) < 1e-4
            and wet.get("diffuse", 0.0) <= 0.05
            and not wet.get("particles") and not wet.get("blown")
            and not wet.get("accum") and not wet.get("submerge"))


def grade_static(base, phase="day", weather=None):
    """The frame-invariant half: tone, haze and diffusion.

    Split out because it is the whole cost of a render and it does not
    change across a loop. Call once, then pass the result to frame() as
    many times as there are frames.

    A BANDED state returns two plates rather than one -- the tone grade
    alone, and the tone grade with the full haze and diffusion on it --
    because the band that mixes them undulates per frame while the two
    endpoints do not. That keeps the expensive half (one tone pass, one
    blur) out of the loop exactly as before; only a lerp moves.
    """
    sky, wet = SKY_STATES[phase], _wet(weather)
    p = _combine(sky, wet)
    arr = np.asarray(base.convert("RGBA"), dtype=_F) / _F(255.0)
    rgb, alpha = arr[..., :3].copy(), arr[..., 3]

    fx = _tone(rgb.copy(), p["exposure"], p["contrast"], p["lift"],
               p["sat"], p["sh_tint"], p["sh_amt"], p["hi_tint"],
               p["hi_amt"])
    dry = fx.copy() if wet.get("band") else None

    # Haze: lerp the plate toward the haze colour. The character is
    # excluded by the mask, so this alone reads as depth.
    if wet.get("haze_amt", 0.0) > 1e-4:
        fx += (_c(wet["haze"]) - fx) * _F(wet["haze_amt"])

    # Diffusion: fog and driven snow genuinely soften a scene.
    if wet.get("diffuse", 0.0) > 0.05:
        blurred = Image.fromarray(
            (np.clip(fx, 0, 1) * 255).astype(np.uint8), "RGB").filter(
                ImageFilter.GaussianBlur(wet["diffuse"]))
        fx = np.asarray(blurred, dtype=_F) / _F(255.0)

    return {"fx": fx, "dry": dry, "rgb": rgb, "alpha": alpha,
            "p": p, "wet": wet}


def frame(static, protect, t=0.0, seed=0, strength=1.0):
    """One frame of a loop, from a cached grade_static() result."""
    # t WRAPS HERE, once, for everything downstream. The tile and roll
    # motions were already exact at t=1 because they go through a modulo,
    # but anything built from sin(2*pi*(k*x + c*t)) is not: adding a whole
    # 2*pi inside a sine is not the identity in floating point, and it came
    # out as a 1/255 jump at the loop point on fog and on the funnel --
    # invisible in a filmstrip, and exactly what verify_sky.py's
    # bit-identical seamlessness check exists to catch.
    t = float(t) % 1.0
    rgb, alpha, p, wet = (static["rgb"], static["alpha"],
                          static["p"], static["wet"])
    h, w = rgb.shape[:2]

    # A banded state mixes the dry tone grade into the hazed, blurred one
    # only where the band lies, so the plate above the bank keeps its own
    # detail and colour. An unbanded state is the hazed plate outright,
    # exactly as before.
    if wet.get("band") is not None and static.get("dry") is not None:
        b = _band_field(h, w, wet["band"], seed | 5, t)[..., None]
        fx = static["dry"] * (1.0 - b) + static["fx"] * b
    else:
        fx = static["fx"].copy()

    # Drifting density: what makes fog read as WEATHER rather than as a
    # flat filter. Rolling the field is seamless by construction.
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
            col, shade, rim, deb = _funnel((w, h), dens, seed, t)
            # The column's colour varies per pixel (banding and the
            # cylinder's own key light), so its tint is an ARRAY, not a
            # constant -- everything else here lerps toward one colour.
            tint = _c(PARTICLE_TINT[kind]) * shade[..., None]
            fx = fx + (tint - fx) * col[..., None]
            fx = fx + (_c(TORNADO_RIM_TINT) - fx) * rim[..., None]
            fx = fx + (_c(TORNADO_DEBRIS_TINT) - fx) * deb[..., None]
        else:
            part = _particles((w, h), kind, dens, seed, t)[..., None]
            fx = fx + (_c(PARTICLE_TINT[kind]) - fx) * part

    # A second, independent particle field blown across the whole plate.
    # Separate from `particles` because the tornado runs both at once: a
    # funnel that is a shape, and the debris it has thrown everywhere else.
    if wet.get("blown"):
        kind = wet["blown"]
        blown = _particles((w, h), kind, wet.get("blown_density", 1.0),
                           seed ^ 0x51DE, t)[..., None]
        fx = fx + (_c(PARTICLE_TINT[kind]) - fx) * blown

    # Settled snow along the bottom. It goes on AFTER the particles,
    # because snow lying on the ground is in front of the snow still
    # falling, and it is on the plate only like everything else -- the
    # mask keeps it behind the character rather than piled against it.
    if wet.get("accum"):
        acc = wet["accum"]
        a = (_band_field(h, w, acc, seed | 9, t)
             * _F(acc.get("amount", 1.0)))[..., None]
        fx = fx + (_c(acc["tint"]) - fx) * a

    # Lightning, on the plate only like everything else here.
    if wet.get("flash") and t > 0.0:
        a = _flash(t)
        if a > 1e-3:
            fx = fx + (_c((0.86, 0.90, 1.0)) - fx) * _F(a * 0.55)

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

    # THE EXCEPTION, and the only one. Everything above happened behind the
    # character; a flood happens in front of the part of it that is under
    # water. It runs here, on the composited frame, because that is the
    # only place the character exists to be submerged -- and it is scaled
    # by `strength` like everything else, so a preview at 0 is still the
    # mint. Alpha is untouched: see below, it never enters this path.
    sub_cfg = wet.get("submerge")
    if sub_cfg is not None and strength > 1e-4:
        flooded = _submerge(np.clip(out, 0.0, 1.0), sub_cfg, seed, t)
        out = out + (flooded - out) * _F(strength)

    return Image.fromarray(
        (np.dstack([np.clip(out, 0, 1), alpha[..., None]]) * 255.0 + 0.5)
        .astype(np.uint8), "RGBA")


def apply_sky(base, protect, phase="day", weather=None,
              seed=0, strength=1.0, t=0.0):
    """Grade the background of a finished token render (a single still).

    base     : RGBA PIL image -- the minted token, unmodified.
    protect  : L PIL image    -- the mask create_image(mask_path=...) wrote.
    phase    : a key of SKY_STATES (from solar.sun_phase()).
    weather  : a key of WEATHER_STATES, or None for a clear sky -- there
               is no 'clear' state, because the mint already is one.
    seed     : token id; makes the particle field stable per token.
    strength : 0..1 global dial on the whole effect, for previewing.
    t        : 0..1 position in the weather loop.

    Returns a new RGBA image the same size. The character is untouched.
    """
    if phase not in SKY_STATES:
        raise KeyError(f"unknown sky phase {phase!r}")
    if weather is not None and weather not in WEATHER_STATES:
        raise KeyError(f"unknown weather {weather!r}")
    if base.mode != "RGBA":
        base = base.convert("RGBA")
    if protect.size != base.size:
        protect = protect.resize(base.size, Image.Resampling.LANCZOS)

    # DAY with no weather is the identity grade, and it is also the single
    # most requested state -- most holders, most of the time, are in clear
    # daylight. It must cost nothing rather than spend a full pass
    # computing a no-op.
    if strength <= 1e-4 or is_identity(phase, weather):
        return base.copy()

    return frame(grade_static(base, phase, weather), protect,
                 t=t, seed=seed, strength=strength)


def describe(phase, weather):
    """Display strings for the two dynamic metadata attributes.

    A clear sky is reported as "Clear" even though there is no state by
    that name -- the absence of weather still has to read as something in
    a metadata field.
    """
    return (phase.replace("_", " ").title(),
            "Clear" if weather is None else weather.title())
