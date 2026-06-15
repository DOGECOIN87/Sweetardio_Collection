#!/usr/bin/env python3
"""Build a measured footwear (what_are_thosez) <-> background compatibility map.

Footwear (bunny slippers, pepe, shiba, ...) is a small accent that sits at the
character's feet. Like the character body, a footwear piece that melts into the
plate beneath it (same luminance + saturation + hue) reads as an unappealing
camouflage, so this BLOCKS exactly those (footwear, plate) pairs using the same
figure-ground rule as build_char_compat.py / verify_separation.py, and adds a
gentle SOFT weight over the rest so the generator biases toward the
best-popping footwear on each plate while keeping variety.

The generator picks the BACKGROUND first, then the footwear, so the table is
keyed by plate -> [blocked footwear base-name] (mirrors traits/eyez_compat.json
and the generator's load_wat_blocklist()/load_wat_weights()). A missing file or
empty entry = everything allowed.

Footwear base-names match generator.py's wat_base_name(): the "_base" file with
its "_Base (n)" suffix stripped (e.g. "layer-Bunny_Slippers_Base (1).png" ->
"layer-Bunny_Slippers"). The gorbhouse trash-can is excluded (it is applied via
its own deterministic code path, not the weighted footwear pool).

Writes traits/wat_compat.json:
  {"mode": "anti-camouflage", "src": ..., "strength": ...,
   "blocked": {bg_file: [footwear_base, ...]},
   "weights": {bg_file: {footwear_base: w, ...}}}

Usage (from repo root):
  python3 asset_assessment/build_wat_compat.py [--src traits/backgroundz]
          [--strength 0.8] [--dry-run]
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
    """Higher = the footwear pops more against the plate. Same three
    figure-ground channels as build_char_compat.pair_score: luminance contrast
    + extra saturation + hue separation (toward complementary)."""
    return (abs(c["L"] - p["L"]) / 100.0
            + max(0.0, c["S"] - p["S"]) / 0.5
            + hue_dist(c["hue"], p["hue"]) / 180.0)


def wat_base_name(fname):
    """File name -> generator footwear base-name (EXACT same rule as
    generator.wat_base_name): the "_base" file with its "_Base (n)" suffix
    stripped. Returns None for non-base files (overlays, strays)."""
    m = re.match(r"(.+?)_base(?:\s*\(\d+\))?\.png$", fname, re.IGNORECASE)
    return m.group(1) if m else None


def footwear_table():
    """base footwear-name -> its _base file, for the CURRENT generator pool
    (gorbhouse excluded — it has its own code path)."""
    bases = {}
    for f in g.get_files(g.WHAT_ARE_THOSEZ):
        b = wat_base_name(f)
        if b and "gorbhouse" not in b.lower():
            bases.setdefault(b, f)
    return bases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="traits/backgroundz")
    ap.add_argument("--strength", type=float, default=0.8,
                    help="how hard to favour the best pairings (0 = uniform, "
                         "1 = linear in score). Gentle so every non-camouflage "
                         "footwear stays well represented.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    plates = {}
    for f in sorted(os.listdir(args.src)):
        if f.lower().endswith((".png", ".jpg")) and f not in SKIP_PLATES:
            plates[f] = plate_stats(os.path.join(args.src, f))

    foot = footwear_table()
    # measure each footwear base in the SAME convention as the plates (only its
    # opaque pixels count, so the mostly-transparent slipper image is fine)
    foot_stats = {b: plate_stats(os.path.join(g.TRAITS_DIR, g.WHAT_ARE_THOSEZ, f))
                  for b, f in foot.items()}

    blocked, weights = {}, {}
    print(f"footwear: {', '.join(sorted(foot))}\n")
    print(f"{'plate':<40}{'blocked footwear (camouflage)'}")
    for bg in sorted(plates):
        p = plates[bg]
        risky = sorted(b for b, c in foot_stats.items()
                       if at_risk(c["L"], c["S"], c["hue"], p))
        if risky:
            blocked[bg] = risky
        wd = {b: round(pair_score(c, p) ** args.strength, 3)
              for b, c in foot_stats.items() if b not in risky}
        if wd:
            weights[bg] = wd
        short = ", ".join(r[:22] for r in risky)
        print(f"{bg[:39]:<40}{len(risky)}/{len(foot)}  {short}")

    n_pairs = sum(len(v) for v in blocked.values())
    print(f"\nanti-camouflage: {n_pairs} blocked (footwear,plate) pairs across "
          f"{len(blocked)} plates; {len(plates)} plates, {len(foot)} footwear")
    print(f"pairing weights: strength={args.strength} over "
          f"{sum(len(v) for v in weights.values())} (footwear,plate) pairs")
    # safety: never let a plate block ALL footwear (would strand the slot)
    for bg, bad in blocked.items():
        if len(bad) >= len(foot):
            print(f"  WARNING: {bg} would block every footwear!")

    if not args.dry_run:
        out = os.path.join(g.TRAITS_DIR, "wat_compat.json")
        with open(out, "w") as f:
            json.dump({"mode": "anti-camouflage", "src": args.src,
                       "strength": args.strength,
                       "blocked": blocked, "weights": weights}, f, indent=1)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
