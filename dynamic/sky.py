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
# Six visual states, collapsed from Open-Meteo's ~100 WMO codes by
# weather.py. Six is the ceiling: past that they stop reading as distinct
# and start reading as noise.
#
# These stack ON TOP of the sky grade (multiplicative on exposure/sat,
# additive on contrast/lift), so rain at night is darker than rain at noon
# without either table knowing about the other.
#
#   diffuse   px of blur -- overcast and fog genuinely soften a scene
#   haze/amt  colour the plate is lerped toward (fog)
#   particles which sprite pass to run, and how dense
WEATHER_STATES = {
    "clear": dict(),

    "overcast": dict(
        exposure=0.90, contrast=-0.14, lift=0.020, sat=0.82, diffuse=1.6),

    # Fog is the strongest of the six and nearly free: the protect mask
    # means the plate can be hazed while the character is not, which is
    # literal atmospheric perspective -- the character pops forward without
    # a single pixel of it changing.
    "fog": dict(
        exposure=0.96, contrast=-0.30, lift=0.135, sat=0.52, diffuse=3.6,
        haze=(0.72, 0.755, 0.80), haze_amt=0.34),

    "rain": dict(
        exposure=0.78, contrast=-0.05, lift=0.028, sat=0.72, diffuse=0.8,
        particles="rain", density=1.0),

    "snow": dict(
        exposure=0.99, contrast=-0.11, lift=0.055, sat=0.58, diffuse=0.6,
        particles="snow", density=1.0),

    "storm": dict(
        exposure=0.54, contrast=0.10, lift=0.015, sat=0.60, diffuse=1.0,
        sh_tint=(0.05, 0.06, 0.13), sh_amt=0.22,
        particles="rain", density=1.9),
}


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


def _particles(size, kind, density, seed):
    """A soft particle field as a float 0..1 array.

    Deliberately STYLIZED, not photoreal. The cast is flat cartoon over lit
    spheres; photoreal rain in front of a Twinkie looks like a compositing
    error. Soft, chunky, low-opacity marks sit with the art.

    Two depth bands -- far ones small, faint and blurred, near ones larger
    and sharper -- which is what gives the plate depth. Both are behind the
    character regardless, because the caller masks the whole effect layer.

    Seeded by token id, so a given token's rain always falls the same way.
    It is that token's weather, not a different random field every refresh.
    """
    w, h = size
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), dtype=np.float32)

    # (count, size, opacity, blur) per band
    if kind == "rain":
        bands = [(int(260 * density), 34, 0.16, 2.6),
                 (int(90 * density), 66, 0.30, 1.1)]
    else:
        bands = [(int(300 * density), 5, 0.30, 2.4),
                 (int(110 * density), 11, 0.55, 1.0)]

    for count, extent, opacity, blur in bands:
        layer = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(layer)
        xs = rng.integers(-extent, w + extent, count)
        ys = rng.integers(-extent, h + extent, count)
        if kind == "rain":
            # Falling down and to the right, matching the collection's
            # cast-shadow convention rather than fighting it.
            lean = 0.27
            lens = rng.integers(int(extent * 0.6), extent, count)
            for x, y, ln in zip(xs, ys, lens):
                draw.line([(x, y), (x + ln * lean, y + ln)],
                          fill=255, width=2)
        else:
            rads = rng.integers(max(2, extent // 3), extent, count)
            for x, y, r in zip(xs, ys, rads):
                draw.ellipse([x - r, y - r, x + r, y + r], fill=255)
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
        out = np.maximum(out, np.asarray(layer, dtype=np.float32)
                         / 255.0 * opacity)
    return out


def apply_sky(base, protect, phase="day", weather="clear",
              seed=0, strength=1.0):
    """Grade the background of a finished token render.

    base     : RGBA PIL image -- the minted token, unmodified.
    protect  : L PIL image    -- the mask create_image(mask_path=...) wrote.
    phase    : a key of SKY_STATES (from solar.sun_phase()).
    weather  : a key of WEATHER_STATES.
    seed     : token id; makes the particle field stable per token.
    strength : 0..1 global dial on the whole effect, for previewing.

    Returns a new RGBA image the same size. The character is untouched.
    """
    if phase not in SKY_STATES:
        raise KeyError(f"unknown sky phase {phase!r}")
    if weather not in WEATHER_STATES:
        raise KeyError(f"unknown weather {weather!r}")

    sky, wet = SKY_STATES[phase], WEATHER_STATES[weather]
    if base.mode != "RGBA":
        base = base.convert("RGBA")
    if protect.size != base.size:
        protect = protect.resize(base.size, Image.Resampling.LANCZOS)

    # Combine the two tables. Exposure and saturation multiply, contrast and
    # lift add, so weather modifies whatever the sky already did.
    exposure = sky.get("exposure", 1.0) * wet.get("exposure", 1.0)
    contrast = sky.get("contrast", 0.0) + wet.get("contrast", 0.0)
    lift = sky.get("lift", 0.0) + wet.get("lift", 0.0)
    sat = sky.get("sat", 1.0) * wet.get("sat", 1.0)
    vignette = sky.get("vignette", 0.0)
    sh_tint = sky.get("sh_tint", (0.06, 0.09, 0.20))
    sh_amt = sky.get("sh_amt", 0.0) + wet.get("sh_amt", 0.0)
    hi_tint = sky.get("hi_tint", (0.90, 0.94, 1.00))
    hi_amt = sky.get("hi_amt", 0.0)

    # DAY + CLEAR is the identity grade, and it is also the single most
    # requested state -- most holders, most of the time, are in daylight. It
    # must cost nothing rather than spend a full pass computing a no-op.
    if strength <= 1e-4 or (
            abs(exposure - 1.0) < 1e-4 and abs(contrast) < 1e-4
            and lift < 1e-5 and abs(sat - 1.0) < 1e-4
            and sh_amt < 1e-4 and hi_amt < 1e-4 and abs(vignette) < 1e-4
            and wet.get("haze_amt", 0.0) < 1e-4
            and wet.get("diffuse", 0.0) <= 0.05
            and not wet.get("particles")):
        return base.copy()

    arr = np.asarray(base, dtype=_F) / _F(255.0)
    rgb, alpha = arr[..., :3].copy(), arr[..., 3]
    h, w = rgb.shape[:2]

    fx = _tone(rgb.copy(), exposure, contrast, lift, sat,
               sh_tint, sh_amt, hi_tint, hi_amt)

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

    # Particles, screened in so they glow rather than paint over.
    if wet.get("particles"):
        p = _particles((w, h), wet["particles"],
                       wet.get("density", 1.0), seed)[..., None]
        tint = _c((0.80, 0.86, 0.98) if wet["particles"] == "rain"
                  else (1.0, 1.0, 1.0))
        fx = fx + (tint - fx) * p

    # Vignette, tinted with the shadow colour so it belongs to the phase.
    if abs(vignette) > 1e-4:
        v = (_vig_field(h, w) * _F(vignette))[..., None]
        fx = fx * (1.0 - v) + _c(sh_tint) * v * _F(0.5)

    # Filmic shoulder then clip, matching grade.py's tail so a plate that
    # passes through both passes never hard-clips twice.
    s = 0.92
    over = fx > s
    fx[over] = s + (1 - s) * np.tanh((fx[over] - s) / (1 - s))
    fx = np.clip(fx, 0.0, 1.0)

    # THE RULE: blend only where the plate is exposed. p == 1 is character,
    # sticker or overlay and comes through untouched.
    p = (np.asarray(protect.convert("L"), dtype=_F) / _F(255.0))
    p = np.clip(p + (1.0 - p) * _F(1.0 - strength), 0.0, 1.0)[..., None]
    out = rgb * p + fx * (1.0 - p)

    return Image.fromarray(
        (np.dstack([np.clip(out, 0, 1), alpha[..., None]]) * 255.0 + 0.5)
        .astype(np.uint8), "RGBA")


def describe(phase, weather):
    """Display strings for the two dynamic metadata attributes."""
    return (phase.replace("_", " ").title(), weather.title())
