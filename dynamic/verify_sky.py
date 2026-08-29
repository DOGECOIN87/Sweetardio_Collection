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
     differ per state on purpose -- fog is meant to hide things and
     overcast is not -- so this catches a state drifting past its OWN
     intent, not a state being stronger than its neighbour.
  9. Every state weather.py can PRODUCE is a state sky.py can grade. The
     two tables are written independently -- one from the WMO code list,
     one from the art direction -- and a mapping to a state that does not
     exist raises a KeyError at render time, on somebody's token, rather
     than here. This is the same class of check verify_trait_names.py
     runs over the trait tables, for the same reason.

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
from dynamic import weather as wxmod

PROOF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proof")
OPAQUE = 255

# How much of the tornado funnel has to clear the character. Measured at
# 73% worst case over 3 tokens x 12 seeds when the placement was set, so
# this is a floor with room under it, not a value fitted to the current
# numbers -- it should catch a funnel walked back toward the middle, not
# fire on a slightly wider body.
FUNNEL_MIN_VISIBLE = 0.60

# The least of the plate's own brightness-normalised micro-contrast each
# state promises to leave behind, measured against THE SAME PHASE WITH NO
# WEATHER so the number is what the weather costs and not what the hour
# costs. These are FLOORS with room under the measured values -- they
# should catch a state that has drifted into burying the background, not
# fire because a plate was busy.
#
# CHECKED AT BOTH ENDS OF THE DAY, because the hazing states get steadily
# worse as the sky darkens and a day-only check would never see it:
# lerping an already-dark plate toward a bright haze crushes its relative
# contrast far harder than doing the same to a bright one. Measured across
# all eight phases, every state fell monotonically from noon to night --
# fog 43% -> 23%, blizzard 50% -> 31%, tornado 68% -> 48% -- so `night` is
# the binding case and `day` is kept as the guard against a future state
# that does not follow that shape.
#
# Floors are set ~20% under the NIGHT measurement, over two tokens:
# overcast 72, fog 23, rain 87, snow 85, storm 116, blizzard 31,
# tornado 48.
#
# fog and blizzard are the loosest because obscuring IS the state; they
# earn it by doing it in a BAND along the ground instead of over the whole
# frame, which is what took fog from 24% to 45% at day and gave the upper
# half of every plate back. storm scores above 100% because its own
# particles add high-frequency energy on top of the plate's.
PLATE_DETAIL_PHASES = ("day", "night")
PLATE_DETAIL_FLOOR = {
    "overcast": 0.62, "fog": 0.18, "rain": 0.76, "snow": 0.72,
    "storm": 0.92, "blizzard": 0.25, "tornado": 0.40,
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

                # 1. character, stickers and overlays untouched
                if not np.array_equal(out[protected], b[protected]):
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
        st = skymod.grade_static(base, "blue_dusk", weather)
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
            for weather, floor in PLATE_DETAIL_FLOOR.items():
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
    missing_floor = sorted(set(skymod.WEATHER_STATES) - set(PLATE_DETAIL_FLOOR))
    if missing_floor:
        failures.append(f"{missing_floor} declare no plate-detail floor — "
                        f"a new state must say what it leaves of the plate")

    # 9. weather.py can only ask for states sky.py actually has
    producible = {p for p in (set(wxmod.WMO_STATES.values())
                              | set(wxmod.DEFAULT_MIX)
                              | {wxmod.FALLBACK, "blizzard", "tornado"})
                  if p is not None}
    unknown = sorted(producible - set(skymod.WEATHER_STATES))
    if unknown:
        failures.append(f"weather.py can produce {unknown}, which sky.py "
                        f"cannot grade")
    else:
        print(f"  all {len(producible)} states weather.py can produce are "
              f"gradeable")
    # and classify() must never invent the one state it cannot know about
    tornadoes = [c for c in wxmod.WMO_STATES
                 if wxmod.classify(c, 200.0) == "tornado"]
    if tornadoes:
        failures.append(f"classify() returned 'tornado' for WMO {tornadoes}; "
                        f"there is no WMO code for a tornado")

    print(f"\n{checked} renders checked "
          f"({len(skymod.SKY_STATES)} phases x "
          f"{len(skymod.WEATHER_STATES) + 1} weather x {len(toks)} tokens)")
    if failures:
        print(f"\nFAIL — {len(failures)} problem(s):")
        for f in failures[:20]:
            print("  " + f)
        sys.exit(1)
    print("OK — every grade left the character, stickers, overlays and "
          "alpha bit-identical to the mint, and every weather loop is "
          "seamless.")


if __name__ == "__main__":
    main()
