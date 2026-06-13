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
from verify_separation import at_risk, plate_stats   # noqa: E402

# overlays are foreground figures stored in the plates folder, never a plate
SKIP_PLATES = set(g.BG_OVERLAY_PAIRS.values())


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
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    plates = {}
    for f in sorted(os.listdir(args.src)):
        if f.lower().endswith((".png", ".jpg")) and f not in SKIP_PLATES:
            plates[f] = plate_stats(os.path.join(args.src, f))

    chars = char_table()
    blocked = {}
    print(f"{'character':<30}{'blocked plates (camouflage)'}")
    for name in sorted(chars):
        # measure the character body in the SAME convention as the plates
        cm = plate_stats(os.path.join(g.TRAITS_DIR, g.CHARACTERZ, chars[name]))
        risky = sorted(f for f, p in plates.items()
                       if at_risk(cm["L"], cm["S"], cm["hue"], p))
        if risky:
            blocked[name] = risky
        short = ", ".join(os.path.splitext(r)[0][:18] for r in risky[:3])
        more = f" (+{len(risky)-3})" if len(risky) > 3 else ""
        print(f"{name:<30}{len(risky):>2}/{len(plates)}  {short}{more}")

    n_pairs = sum(len(v) for v in blocked.values())
    print(f"\nanti-camouflage: {n_pairs} blocked (char,plate) pairs across "
          f"{len(blocked)} characters; {len(plates)} plates, {len(chars)} chars")
    # safety: never let a character lose ALL of its backgrounds
    for name, bad in blocked.items():
        if len(bad) >= len(plates):
            print(f"  WARNING: {name} would be blocked on every plate!")

    if not args.dry_run:
        out = os.path.join(g.TRAITS_DIR, "char_compat.json")
        with open(out, "w") as f:
            json.dump({"mode": "anti-camouflage", "src": args.src,
                       "blocked": blocked}, f, indent=1)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
