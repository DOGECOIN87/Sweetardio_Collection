#!/usr/bin/env python3
"""Gate on the one rule the dynamic sky pass must never break.

    The effect touches the background plate and NOTHING else.

Everything else in dynamic/ is a matter of taste and can be tuned by eye.
This cannot: if a grade leaks onto the character, the collection has 4,444
tokens whose art changes with the weather, which is not what was asked for
and is not something a holder can opt out of.

So this asserts it numerically, over every sky phase and every weather
state, for every sample token it finds:

  1. Wherever the protect mask is fully opaque, the output is BIT-IDENTICAL
     to the minted PNG. Not "close" -- equal.

     ONE STATE IS EXEMPT, and the exemption is checked rather than waived.
     `flooded` puts the character IN the water, which cannot be done from
     behind it -- water the figure stands in front of is a puddle backdrop,
     not a flood. So for a state where sky.touches_character() is True this
     asserts the same equality ABOVE the highest the water can ever reach,
     and separately that the water stays clear of the face. Every other
     state is held to the whole mask, as before. Alpha (check 3) is never
     exempt at any depth.
  2. `day` with NO weather returns the mint unchanged in full, since that
     grade is defined to be the identity. There is no `clear` state -- the
     mint already is one -- so this is the None case.
  3. The alpha channel is preserved bit-for-bit, the same discipline
     shade_skin_balls.py and shade_eyes.py hold to, because anything that
     moved alpha would move the face geometry downstream.
  4. Something actually happened in the plate region -- a pass that silently
     did nothing would otherwise sail through checks 1-3.
  5. No weather at all is spatially free and is the identity at `day`, and
     every NAMED state moves. The dynamic layer must not cost image quality
     in the state where it is doing nothing -- and since that state is now
     the absence of a state, a named one that failed to move would be a
     state for doing nothing, which is what `clear` was.
  6. Every weather loop is SEAMLESS: the frame at t=1 is bit-identical to
     the frame at t=0. A visible jump at the wrap is the one thing that
     makes an ambient effect look cheap, and it is invisible in a filmstrip
     -- only a numeric check catches it.
  7. The tornado funnel is actually VISIBLE. It is the one effect with a
     position, and the protect mask puts it behind a character that sits
     at a fixed canvas position -- so a funnel seeded toward the middle is
     a tornado nobody can see. Nothing else in the pass can fail this way,
     because nothing else has a location. Measured as the fraction of the
     funnel's own weight that survives the mask, per token per seed.
  8. THE PLATE STAYS READABLE. The background is a trait the holder chose
     and cannot turn off, so a weather state is not allowed to bury it.
     Each state declares how much of the plate's own detail it promises to
     leave, and this measures the promise against the render. The budgets
     differ per state on purpose -- fog is meant to hide things and rain
     is not -- so this catches a state drifting past its OWN intent, not a
     state being stronger than its neighbour. The table is checked BOTH
     ways: a state with no floor fails, and a floor for a state that no
     longer exists fails too, so a retired state cannot leave a rule
     behind that looks like it is still being enforced.

The weather is no longer LIVE, so there is no WMO table left to
cross-check against. build_mint.py allocates the states at exact counts
and validates its own table against sky.WEATHER_STATES at import; that is
where the "can everything asked for actually be rendered" check now lives,
next to the table it guards.

Exits non-zero on any failure.

    python3 dynamic/verify_sky.py
"""

import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import ImageFilter

from dynamic import sky as skymod

PROOF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proof")
OPAQUE = 255

# How much of the tornado funnel has to clear the character. Measured at
# 73% worst case over 3 tokens x 12 seeds when the placement was set, so
# this is a floor with room under it, not a value fitted to the current
# numbers -- it should catch a funnel walked back toward the middle, not
# fire on a slightly wider body.
FUNNEL_MIN_VISIBLE = 0.60

# The lowest the water may reach before it starts drowning the face. The
# face hole is FACE_HOLE_WIDTH (250) wide about y=601 of a 1393 canvas, so
# its underside sits at 0.521; a waterline below this number is under the
# chin of every character in the cast. Kept here rather than in sky.py
# because it is a fact about the ART, not about the water.
FACE_UNDERSIDE = (601 + 250 / 2) / 1393

# The least of the plate's own brightness-normalised micro-contrast each
# state promises to leave behind, measured against THE SAME PHASE WITH NO
# WEATHER so the number is what the weather costs and not what the hour
# costs. These are FLOORS with room under the measured values -- they
# should catch a state that has drifted into burying the background, not
# fire because a plate was busy.
#
# RE-MEASURED AT `day`, which is now the only phase there is. The old
# floors were set from `night`, where every hazing state scored far worse
# -- lerping an already-dark plate toward a bright haze crushes its
# relative contrast much harder than doing the same to a bright one, and
# the fall from noon to night was monotonic across all seven states. With
# the time-of-day trait retired those numbers describe a render nobody
# will ever see, and leaving them would have left every floor about twice
# as loose as it should be.
#
# Floors are ~20% under the worst of three tokens at day:
# fog 41, rain 89, snow 85, storm 116, blizzard 51, tornado 71, flooded 56.
#
# fog and blizzard are the loosest because obscuring IS the state; they
# earn it by doing it in a BAND along the ground instead of over the whole
# frame, which is what took fog from 24% to 45% and gave the upper half of
# every plate back. storm scores above 100%, and flooded and tornado score
# well for how much they change, because particles, refraction and a
# mirrored surface ADD high-frequency energy rather than hazing it away.
PLATE_DETAIL_PHASES = ("day",)
PLATE_DETAIL_FLOOR = {
    "fog": 0.33, "rain": 0.71, "snow": 0.68, "storm": 0.93,
    "blizzard": 0.41, "tornado": 0.57, "flooded": 0.45,
}


def plate_detail(rgb, plate):
    """Brightness-normalised band-pass energy over the exposed plate.

    The same measure background_pop_studies uses to rank a plate's business
    -- a band-pass rather than a high-pass, because a high-pass reads film
    grain and calls a smooth plate busy. Normalised by mean luma so that
    merely darkening a plate does not register as destroying its detail.
    """
    y = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    img = Image.fromarray(np.clip(y, 0, 255).astype(np.uint8), "L")
    near = np.asarray(img.filter(ImageFilter.GaussianBlur(2.0)),
                      dtype=np.float64)
    far = np.asarray(img.filter(ImageFilter.GaussianBlur(8.0)),
                     dtype=np.float64)
    return float(np.abs(near - far)[plate].mean()
                 / max(float(y[plate].mean()), 1.0))


def tokens():
    out = []
    for i in range(1, 100):
        b = os.path.join(PROOF_DIR, f"token_{i}.png")
        m = os.path.join(PROOF_DIR, f"token_{i}_mask.png")
        if os.path.exists(b) and os.path.exists(m):
            out.append((i, b, m))
    return out


def main():
    toks = tokens()
    if not toks:
        sys.exit("no sample tokens in dynamic/proof; "
                 "run: python3 dynamic/render.py --tokens 3")

    failures = []
    checked = 0
    for idx, bpath, mpath in toks:
        base = Image.open(bpath).convert("RGBA")
        mask = Image.open(mpath).convert("L")
        b = np.asarray(base)
        m = np.asarray(mask)
        protected = m >= OPAQUE
        plate = m == 0
        n_prot = int(protected.sum())
        n_plate = int(plate.sum())
        print(f"token {idx}: {n_prot:,} protected px, {n_plate:,} plate px")
        if n_prot == 0:
            failures.append(f"token {idx}: protect mask is empty")
            continue

        for phase in skymod.SKY_STATES:
            for weather in [None] + list(skymod.WEATHER_STATES):
                out = np.asarray(
                    skymod.apply_sky(base, mask, phase, weather, seed=idx))
                checked += 1
                tag = f"token {idx} {phase}+{weather}"

                # 1. character, stickers and overlays untouched -- above
                #    the waterline only, for the one state that submerges
                if skymod.touches_character(weather):
                    top = skymod.waterline(weather)[0]
                    dry = protected & (
                        np.arange(b.shape[0])[:, None] < int(top * b.shape[0]))
                    if not np.array_equal(out[dry], b[dry]):
                        d = int(np.abs(out[dry].astype(int)
                                       - b[dry].astype(int)).max())
                        failures.append(
                            f"{tag}: protected pixels ABOVE the waterline "
                            f"changed (max delta {d})")
                elif not np.array_equal(out[protected], b[protected]):
                    d = int(np.abs(out[protected].astype(int)
                                   - b[protected].astype(int)).max())
                    failures.append(f"{tag}: protected pixels changed "
                                    f"(max delta {d})")

                # 3. alpha preserved bit-for-bit
                if not np.array_equal(out[..., 3], b[..., 3]):
                    failures.append(f"{tag}: alpha channel changed")

                # 2 / 4. identity where promised, effect where required
                same_plate = np.array_equal(out[plate], b[plate])
                if phase == "day" and weather is None:
                    if not same_plate:
                        failures.append(f"{tag}: identity grade altered "
                                        f"the plate")
                elif n_plate and same_plate:
                    failures.append(f"{tag}: pass did nothing to the plate")

    # 1b. a submerging state must keep the water off the face, and must
    #     actually reach the character rather than only the plate
    for weather in skymod.WEATHER_STATES:
        if not skymod.touches_character(weather):
            continue
        top, bottom = skymod.waterline(weather)
        if bottom <= FACE_UNDERSIDE:
            failures.append(
                f"{weather}: water reaches {bottom:.3f}, at or above the "
                f"face underside {FACE_UNDERSIDE:.3f} — it would drown the "
                f"one part of the token a holder looks at")
        if not (0.0 < top < bottom < 1.0):
            failures.append(f"{weather}: waterline {top:.3f}..{bottom:.3f} "
                            f"is not inside the canvas")
        wet_px = 0
        for idx, bpath, mpath in toks:
            m = np.asarray(Image.open(mpath).convert("L"))
            rows = np.arange(m.shape[0])[:, None]
            wet_px += int(((m >= OPAQUE)
                           & (rows >= int(bottom * m.shape[0]))).sum())
        if wet_px == 0:
            failures.append(f"{weather}: submerges nothing — no protected "
                            f"pixel falls below the waterline")
        print(f"  '{weather}' submerges: water {top:.2f}..{bottom:.2f}, "
              f"face underside {FACE_UNDERSIDE:.2f}, {wet_px:,} character "
              f"px under water")

    # 5. no weather is free; every named state moves
    if skymod.is_spatial(None) or skymod.has_motion(None):
        failures.append("None declares motion or a spatial op — a clear sky "
                        "must cost the plate nothing")
    if not skymod.is_identity("day", None):
        failures.append("day + no weather is not the identity grade")
    still = [wx for wx in skymod.WEATHER_STATES if not skymod.has_motion(wx)]
    if still:
        failures.append(f"{still} are named states that do not move — a "
                        f"state for doing nothing is what 'clear' was")
    print(f"  no weather is free and the identity at day; all "
          f"{len(skymod.WEATHER_STATES)} named states move")

    # 6. seamless loops
    base = Image.open(toks[0][1]).convert("RGBA").resize(
        (512, 512), Image.Resampling.LANCZOS)
    mask = Image.open(toks[0][2]).convert("L").resize(
        (512, 512), Image.Resampling.LANCZOS)
    for weather in skymod.WEATHER_STATES:
        st = skymod.grade_static(base, "day", weather)
        a = np.asarray(skymod.frame(st, mask, t=0.0, seed=1), dtype=int)
        b = np.asarray(skymod.frame(st, mask, t=1.0, seed=1), dtype=int)
        checked += 2
        if not np.array_equal(a, b):
            failures.append(f"{weather}: loop is not seamless "
                            f"(max delta {int(np.abs(a - b).max())})")
    print(f"  loop seamlessness checked for "
          f"{len(skymod.WEATHER_STATES)} weather states")

    # 7. the funnel is not hidden behind the character
    worst = None
    for idx, bpath, mpath in toks:
        pr = (np.asarray(Image.open(mpath).convert("L"), dtype=np.float32)
              / 255.0)
        h, w = pr.shape
        for seed in range(1, 13):
            col = skymod._funnel((w, h), 1.0, seed, 0.25)[0]
            total = float(col.sum())
            if total <= 0.0:
                failures.append(f"token {idx} seed {seed}: funnel is empty")
                continue
            vis = float((col * (1.0 - pr)).sum()) / total
            checked += 1
            if worst is None or vis < worst[0]:
                worst = (vis, idx, seed)
            if vis < FUNNEL_MIN_VISIBLE:
                failures.append(
                    f"token {idx} seed {seed}: only {vis * 100:.0f}% of the "
                    f"funnel clears the character (need "
                    f"{FUNNEL_MIN_VISIBLE * 100:.0f}%)")
    if worst:
        print(f"  funnel visibility: worst {worst[0] * 100:.0f}% "
              f"(token {worst[1]}, seed {worst[2]}), "
              f"floor {FUNNEL_MIN_VISIBLE * 100:.0f}%")

    # 8. the plate stays readable
    #
    # The table is validated BEFORE it is used, both ways. A stale entry is
    # not a reporting problem here -- apply_sky() raises KeyError on a
    # state that no longer exists, so iterating the floors first would
    # crash with a stack trace instead of naming the retired state, which
    # is exactly what happened the first time `overcast` was removed.
    missing_floor = sorted(set(skymod.WEATHER_STATES) - set(PLATE_DETAIL_FLOOR))
    if missing_floor:
        failures.append(f"{missing_floor} declare no plate-detail floor — "
                        f"a new state must say what it leaves of the plate")
    stale_floor = sorted(set(PLATE_DETAIL_FLOOR) - set(skymod.WEATHER_STATES))
    if stale_floor:
        failures.append(f"{stale_floor} have a plate-detail floor but are "
                        f"not weather states — a retired state left its "
                        f"rule behind")
    measurable = [(w, f) for w, f in PLATE_DETAIL_FLOOR.items()
                  if w in skymod.WEATHER_STATES]

    worst_leg = None
    for idx, bpath, mpath in toks:
        base_i = Image.open(bpath).convert("RGBA")
        mask_i = Image.open(mpath).convert("L")
        plate_i = np.asarray(mask_i) == 0
        for ph in PLATE_DETAIL_PHASES:
            ref = np.asarray(skymod.apply_sky(base_i, mask_i, ph, None,
                                              seed=idx))
            d0 = plate_detail(ref[..., :3].astype(np.float64), plate_i)
            checked += 1
            if d0 <= 0.0:
                failures.append(f"token {idx} {ph}: reference plate has no "
                                f"detail to measure against")
                continue
            for weather, floor in measurable:
                out = np.asarray(skymod.apply_sky(base_i, mask_i, ph,
                                                  weather, seed=idx, t=0.25))
                kept = (plate_detail(out[..., :3].astype(np.float64),
                                     plate_i) / d0)
                checked += 1
                if worst_leg is None or kept - floor < worst_leg[0]:
                    worst_leg = (kept - floor, weather, ph, idx, kept, floor)
                if kept < floor:
                    failures.append(
                        f"token {idx} {ph}+{weather}: leaves "
                        f"{kept * 100:.0f}% of the plate's detail, under its "
                        f"{floor * 100:.0f}% floor")
    if worst_leg:
        print(f"  plate legibility: tightest '{worst_leg[1]}' at "
              f"{worst_leg[2]} on token {worst_leg[3]} — "
              f"{worst_leg[4] * 100:.0f}% kept "
              f"(floor {worst_leg[5] * 100:.0f}%)")

    print(f"\n{checked} renders checked "
          f"({len(skymod.SKY_STATES)} phases x "
          f"{len(skymod.WEATHER_STATES) + 1} weather x {len(toks)} tokens)")
    if failures:
        print(f"\nFAIL — {len(failures)} problem(s):")
        for f in failures[:20]:
            print("  " + f)
        sys.exit(1)
    subs = [w for w in skymod.WEATHER_STATES if skymod.touches_character(w)]
    print("OK — every grade left the character, stickers, overlays and "
          "alpha bit-identical to the mint, and every weather loop is "
          "seamless.")
    if subs:
        print(f"     ({', '.join(subs)} excepted below the waterline, by "
              f"design, and checked above it.)")


if __name__ == "__main__":
    main()
