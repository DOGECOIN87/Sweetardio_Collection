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


def pair_score(c, p):
    """Higher = the character pops more against the plate. Sum of the three
    figure-ground channels (the strong-separation mirror of at_risk's weak
    one): luminance contrast + how much more saturated the character is +
    hue separation (toward complementary)."""
    return (abs(c["L"] - p["L"]) / 100.0
            + max(0.0, c["S"] - p["S"]) / 0.5
            + hue_dist(c["hue"], p["hue"]) / 180.0)


def base_name(fname):
    """File name -> generator character base-name (EXACT same stripping as
    generate_random_combination: strips the layer-after_skinz_/before_skinz_/
    after_skinz_ prefixes and a trailing ' (n)', but NOT a bare 'layer-')."""
    n = (fname.replace("layer-after_skinz_", "")
              .replace("before_skinz_", "").replace("after_skinz_", "")
              .replace(".png", ""))
    return re.sub(r"\s*\(\d+\)", "", n).strip()


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
    blocked, weights = {}, {}
    print(f"{'character':<30}{'blocked plates (camouflage)'}")
    for name in sorted(chars):
        # measure the character body in the SAME convention as the plates
        cm = plate_stats(os.path.join(g.TRAITS_DIR, g.CHARACTERZ, chars[name]))
        risky = sorted(f for f, p in plates.items()
                       if at_risk(cm["L"], cm["S"], cm["hue"], p))
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
    print(f"\nanti-camouflage: {n_pairs} blocked (char,plate) pairs across "
          f"{len(blocked)} characters; {len(plates)} plates, {len(chars)} chars")
    print(f"pairing weights: strength={args.strength} over "
          f"{sum(len(v) for v in weights.values())} (char,plate) pairs")
    # safety: never let a character lose ALL of its backgrounds
    for name, bad in blocked.items():
        if len(bad) >= len(plates):
            print(f"  WARNING: {name} would be blocked on every plate!")

    if not args.dry_run:
        out = os.path.join(g.TRAITS_DIR, "char_compat.json")
        with open(out, "w") as f:
            json.dump({"mode": "anti-camouflage", "src": args.src,
                       "strength": args.strength,
                       "blocked": blocked, "weights": weights}, f, indent=1)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
