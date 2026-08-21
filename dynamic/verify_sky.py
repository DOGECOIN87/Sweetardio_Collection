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
  2. `day` + `clear` returns the mint unchanged in full, since that grade is
     defined to be the identity.
  3. The alpha channel is preserved bit-for-bit, the same discipline
     shade_skin_balls.py and shade_eyes.py hold to, because anything that
     moved alpha would move the face geometry downstream.
  4. Something actually happened in the plate region -- a pass that silently
     did nothing would otherwise sail through checks 1-3.
  5. A weather state that declares no motion applies NO spatial op, so it
     can tone-grade the plate but never soften or resample it -- and at
     `day` it returns the mint bit-for-bit. The dynamic layer must not cost
     image quality in the state where it is doing nothing, which is the
     state most holders are in most of the time.
  6. Every weather loop is SEAMLESS: the frame at t=1 is bit-identical to
     the frame at t=0. A visible jump at the wrap is the one thing that
     makes an ambient effect look cheap, and it is invisible in a filmstrip
     -- only a numeric check catches it.

Exits non-zero on any failure.

    python3 dynamic/verify_sky.py
"""

import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dynamic import sky as skymod

PROOF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proof")
OPAQUE = 255


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
            for weather in skymod.WEATHER_STATES:
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
                if phase == "day" and weather == "clear":
                    if not same_plate:
                        failures.append(f"{tag}: identity grade altered "
                                        f"the plate")
                elif n_plate and same_plate:
                    failures.append(f"{tag}: pass did nothing to the plate")

    # 5. a motionless weather state must be spatially free
    for weather in skymod.WEATHER_STATES:
        if not skymod.has_motion(weather):
            if skymod.is_spatial(weather):
                failures.append(f"{weather}: declares no motion but applies "
                                f"a spatial op — it would soften the plate")
            if not skymod.is_identity("day", weather):
                failures.append(f"day+{weather}: motionless state is not the "
                                f"identity grade")
            print(f"  '{weather}' is motionless: no spatial op, "
                  f"identity at day")

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

    print(f"\n{checked} renders checked "
          f"({len(skymod.SKY_STATES)} phases x "
          f"{len(skymod.WEATHER_STATES)} weather x {len(toks)} tokens)")
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
