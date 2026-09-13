#!/usr/bin/env python3
"""Build a measured character <-> background compatibility map for generator.py.

A camouflaged character (it melts into the plate) is the clearest "unappealing"
pairing, so this blocks exactly the (character, plate) pairs that the
figure-ground rule in verify_separation.py flags AT RISK: luminance,
saturation AND hue separation all weak at once. That is the same rule the
background grading pass was tuned against, so this only blocks the residual
camouflage pairs the grading could not fully fix.

The generator picks the CHARACTER first, then the background, so the table is
keyed by character base-name -> [blocked plate files] (mirrors the shape of
traits/eyez_compat.json). A missing file or empty entry = everything allowed.

Writes traits/char_compat.json:
  {"mode": "anti-camouflage", "src": ..., "blocked": {char_name: [bg, ...]}}

Usage (from repo root):
  python3 asset_assessment/build_char_compat.py [--src traits/backgroundz]
          [--dry-run]
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "asset_assessment")
import generator as g
from verify_separation import at_risk, hue_dist, plate_stats   # noqa: E402

# overlays are foreground figures stored in the plates folder, never a plate
SKIP_PLATES = set(g.BG_OVERLAY_PAIRS.values())

# ---- rule 2: a WASHOUT clash (luminance AND hue both weak) ----------------
# OFF BY DEFAULT (thresholds 0), and the reason is measured, not squeamish.
#
# The rule itself is sound. at_risk() demands all three channels weak at once,
# and that AND is too strict: a pairing can match in hue AND in value and
# still pass purely because the character out-saturates the plate, and
# saturation alone does not separate figure from ground. The worked example is
# og_gummy_bear (hot magenta, hue 322, S 0.63) on Starburst (hue gap 0,
# luminance gap 11) and Pink_Abyss (hue gap 15, luminance gap 2) -- pink on
# pink, the bear's top half melting into the plate, and NEITHER was blocked
# because the bear reads +0.27 and +0.30 more saturated than they do.
#
# WHAT IT COSTS. At its gentlest useful setting (22 / 25) it blocks 202 of
# 1728 pairs, and that is enough to make the rarity fit UNSOLVABLE: the eye
# deviation goes 0.23 -> 1.01 and stays there, oscillating 0.95-1.03 over
# eight solver passes without converging. Character blocks reach the eyes
# because eyez_compat blocks certain eyes on certain plates, so changing which
# plates get drawn moves the eye shares in a way the eye gains cannot correct.
# The same two pairings blocked BY NAME below cost nothing at all: eyes 0.23,
# mouths 0.16, backgrounds 0.23, i.e. the fit the collection already had.
#
# So: a targeted block is free and a broad rule is not. Turn this on only if
# the owner accepts a ~1.0 point eye deviation against a +/-0.6 resolution,
# and re-solve calibrate_rarity.py afterwards knowing it will not converge.
WASH_DL = 0.0         # luminance gap below this is "no value separation"
WASH_DH = 0.0         # hue gap below this is "no hue separation"

# Allocator-only plates are EXEMPT from rule 2 and from MANUAL_BLOCKS.
# Those slots re-roll the character when it camouflages, and a re-roll cannot
# change a FORCED character -- which is exactly how the chase characters ended
# up barred from every legendary and starfield token (see CLAUDE.md). The
# starfield additionally has its own curated cast list, STARFIELD_CHARS, so a
# second overlapping rule there would be redundant as well as risky.
# Rule 1 (at_risk) still applies everywhere: it was always this narrow.

# ---- owner overrides ------------------------------------------------------
# "I never want to see X on Y", by judgement rather than measurement, and the
# cheapest lever there is -- see the cost note above.
# THIS IS THE PLACE FOR IT: char_compat.json is REGENERATED from measurement
# every time this script runs, so a pairing blocked by hand in the JSON is
# silently lost on the next rebuild. Entries here survive.
# Keyed by character base-name -> plate filenames. Unknown names raise, so a
# typo or a renamed asset fails loudly instead of quietly blocking nothing.
MANUAL_BLOCKS = {
    # Measured worst two for the magenta bear; both read as pink-on-pink.
    "og_gummy_bear": ["Starburst.png", "Pink_Abyss.png"],
}


def washout(c, p):
    """True when the pairing has neither value nor hue separation."""
    weak_L = abs(c["L"] - p["L"]) < WASH_DL
    weak_H = p["S"] < 0.15 or hue_dist(c["hue"], p["hue"]) < WASH_DH
    return weak_L and weak_H


def pair_score(c, p):
    """Higher = the character pops more against the plate. Sum of the three
    figure-ground channels (the strong-separation mirror of at_risk's weak
    one): luminance contrast + how much more saturated the character is +
    hue separation (toward complementary)."""
    return (abs(c["L"] - p["L"]) / 100.0
            + max(0.0, c["S"] - p["S"]) / 0.5
            + hue_dist(c["hue"], p["hue"]) / 180.0)


def base_name(fname):
    """File name -> generator character base-name. Delegates to
    generator.char_base_name so this cannot drift from the stripping the
    generator actually uses; kept as a name here because callers import it."""
    return g.char_base_name(fname)


def char_table():
    """base char-name -> primary file, for the CURRENT generator cast."""
    names = {}
    for f in g.get_files(g.CHARACTERZ):
        names.setdefault(base_name(f), f)
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="traits/backgroundz")
    ap.add_argument("--strength", type=float, default=0.8,
                    help="how hard to favour the best pairings (0 = uniform, "
                         "1 = linear in score). Kept gentle so every "
                         "non-camouflage plate stays well represented.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    plates = {}
    for f in sorted(os.listdir(args.src)):
        if f.lower().endswith((".png", ".jpg")) and f not in SKIP_PLATES:
            plates[f] = plate_stats(os.path.join(args.src, f))

    chars = char_table()
    for name, pls in MANUAL_BLOCKS.items():
        if name not in chars:
            sys.exit(f"MANUAL_BLOCKS: {name!r} is not a character")
        for f in pls:
            if f not in plates:
                sys.exit(f"MANUAL_BLOCKS[{name!r}]: no plate {f!r}")
    blocked, weights = {}, {}
    print(f"{'character':<30}{'blocked plates (camouflage)'}")
    for name in sorted(chars):
        # measure the character body in the SAME convention as the plates
        cm = plate_stats(os.path.join(g.TRAITS_DIR, g.CHARACTERZ, chars[name]))
        manual = set(MANUAL_BLOCKS.get(name, ()))
        risky = sorted(
            f for f, p in plates.items()
            if at_risk(cm["L"], cm["S"], cm["hue"], p)
            or (not g.is_allocator_only_bg(f)
                and (washout(cm, p) or f in manual)))
        if risky:
            blocked[name] = risky
        # soft pairing preference over the NON-blocked plates: weight rounded
        # to 3 dp, gentle exponent so variety is preserved (not a hard filter)
        wd = {f: round(pair_score(cm, p) ** args.strength, 3)
              for f, p in plates.items() if f not in risky}
        if wd:
            weights[name] = wd
        short = ", ".join(os.path.splitext(r)[0][:18] for r in risky[:3])
        more = f" (+{len(risky)-3})" if len(risky) > 3 else ""
        print(f"{name:<30}{len(risky):>2}/{len(plates)}  {short}{more}")

    n_pairs = sum(len(v) for v in blocked.values())
    print(f"\nblocked: {n_pairs} (char,plate) pairs across "
          f"{len(blocked)} characters; {len(plates)} plates, {len(chars)} chars")
    print(f"  rule 1 anti-camouflage (L and S and H weak), all plates")
    print(f"  rule 2 washout (L<{WASH_DL:.0f} and H<{WASH_DH:.0f}), "
          f"weighted plates only")
    print(f"  owner overrides: {sum(len(v) for v in MANUAL_BLOCKS.values())} pairs")
    print(f"pairing weights: strength={args.strength} over "
          f"{sum(len(v) for v in weights.values())} (char,plate) pairs")
    # safety: never let a character lose ALL of its backgrounds
    for name, bad in blocked.items():
        if len(bad) >= len(plates):
            print(f"  WARNING: {name} would be blocked on every plate!")

    if not args.dry_run:
        out = os.path.join(g.TRAITS_DIR, "char_compat.json")
        with open(out, "w") as f:
            json.dump({"mode": "anti-camouflage+washout", "src": args.src,
                       "strength": args.strength,
                       "blocked": blocked, "weights": weights}, f, indent=1)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
