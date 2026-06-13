#!/usr/bin/env python3
"""Deterministic mint allocator: compose exactly N unique tokens with hard
legendary-background quotas, on top of generator.py's weighted, compat-aware
random pipeline.

Composition rules:
  * legendary plates in traits/backgrounds_pop are rare 1/1-style art: each
    one appears EXACTLY --leg-each times (default 50). 13 plates x 50 = 650.
  * the remaining tokens get a normal traits/backgroundz plate exactly as the
    live generator picks them (skin weights, eye<->bg and char<->bg compat,
    footwear/gorbhouse/arm-lock rules all apply).
  * legendary tokens reuse the same anti-camouflage rule against the
    legendary plate (a character that would melt into it is re-rolled), so
    legendaries stay "best" too.
  * every token is a UNIQUE trait combination.

Outputs a trait-distribution report and writes the full manifest to
output/mint_manifest.json (token id -> traits). Reproducible by --seed.

Usage (from repo root):
  python3 asset_assessment/build_mint.py [--n 4444] [--leg-each 50] [--seed 4444]
"""

import argparse
import json
import os
import random
import sys
from collections import Counter

sys.path.insert(0, ".")
sys.path.insert(0, "asset_assessment")
import generator as g
from verify_separation import at_risk, plate_stats   # noqa: E402
from build_char_compat import char_table              # noqa: E402

LEG_DIR = "backgrounds_pop"
TRAIT_KEYS = ("character", "bg", "skin", "eye", "mouth", "arm", "wat", "sticker")


def traits_of(layers, char):
    t = {k: None for k in TRAIT_KEYS}
    t["character"] = char
    t["bg"] = os.path.basename(layers[0]["path"])   # layer 0 is always the plate
    for l in layers[1:]:
        p, b = l["path"], os.path.basename(l["path"])
        for key, d in (("skin", g.SKINZ), ("eye", g.EYEZ), ("mouth", g.MOUTHZ),
                       ("arm", g.ARMZ), ("wat", g.WHAT_ARE_THOSEZ),
                       ("sticker", g.STICKERZ)):
            if os.path.join(g.TRAITS_DIR, d) in p:
                t[key] = b
    return t


def sig(t):
    return tuple(t[k] for k in TRAIT_KEYS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4444)
    ap.add_argument("--leg-each", type=int, default=50)
    ap.add_argument("--seed", type=int, default=4444)
    args = ap.parse_args()
    random.seed(args.seed)

    legs = sorted(f for f in os.listdir(os.path.join(g.TRAITS_DIR, LEG_DIR))
                  if f.endswith(".png"))
    leg_total = len(legs) * args.leg_each
    if leg_total > args.n:
        sys.exit(f"{len(legs)} legendaries x {args.leg_each} = {leg_total} "
                 f"exceeds n={args.n}")

    # measure each legendary plate + each character body for the camo check
    leg_stats = {f: plate_stats(os.path.join(g.TRAITS_DIR, LEG_DIR, f))
                 for f in legs}
    char_stats = {n: plate_stats(os.path.join(g.TRAITS_DIR, g.CHARACTERZ, f))
                  for n, f in char_table().items()}

    def camo(char, leg):
        c = char_stats.get(char)
        return c is not None and at_risk(c["L"], c["S"], c["hue"], leg_stats[leg])

    # which token slots are legendary, and which plate each one is
    forced = [None] * args.n
    slots = random.sample(range(args.n), leg_total)
    picks = [leg for leg in legs for _ in range(args.leg_each)]
    random.shuffle(picks)
    for slot, leg in zip(slots, picks):
        forced[slot] = leg

    manifest, seen = {}, set()
    for i in range(args.n):
        leg = forced[i]
        fb = (LEG_DIR, leg) if leg is not None else None
        for _attempt in range(2000):
            layers, char = g.generate_random_combination(force_bg=fb)
            if leg is not None and camo(char, leg):
                continue                           # re-roll camouflaging char
            t = traits_of(layers, char)
            if sig(t) not in seen:
                seen.add(sig(t))
                t["legendary"] = leg is not None
                manifest[i + 1] = t
                break
        else:
            sys.exit(f"token {i+1}: could not find a unique non-camo combo")

    # ---- report ----
    def dist(key):
        return Counter(t[key] for t in manifest.values())

    print(f"minted {len(manifest)}/{args.n} unique tokens (seed {args.seed})\n")
    leg_d = {f: sum(1 for t in manifest.values() if t["bg"] == f) for f in legs}
    bad = {f: n for f, n in leg_d.items() if n != args.leg_each}
    print(f"legendary backgrounds (target {args.leg_each} each):")
    for f in legs:
        print(f"  {os.path.splitext(f)[0]:28} {leg_d[f]}")
    print(f"  -> all exactly {args.leg_each}? {'YES' if not bad else 'NO ' + str(bad)}")
    print(f"  legendary tokens total: {sum(leg_d.values())} "
          f"({100*sum(leg_d.values())/args.n:.1f}%)\n")

    print("skins:")
    for s, n in dist("skin").most_common():
        tag = s.split("Skin_")[-1].split(" (")[0].replace(".png", "")
        print(f"  {tag:18} {n:5}  {100*n/args.n:5.2f}%")

    # quality: no camouflage and no eye<->bg clash anywhere
    cw, ew = g.load_char_blocklist(), g.load_eyez_blocklist()
    camo_v = sum(1 for t in manifest.values()
                 if not t["legendary"] and t["bg"] in cw.get(t["character"], []))
    camo_v += sum(1 for t in manifest.values()
                  if t["legendary"] and camo(t["character"],
                                              t["bg"]))
    eye_v = sum(1 for t in manifest.values()
                if t["eye"] in ew.get(t["bg"], []))
    print(f"\nquality: camouflage={camo_v}  eye-clash={eye_v}  "
          f"unique={len(seen)}/{args.n}  distinct_chars={len(dist('character'))}")

    os.makedirs("output", exist_ok=True)
    out = "output/mint_manifest.json"
    with open(out, "w") as f:
        json.dump(manifest, f)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
