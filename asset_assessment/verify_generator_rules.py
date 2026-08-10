#!/usr/bin/env python3
"""Verify generator.py eligibility rules against the actual asset files.

Rule under test: churro, twinkie, poptarts and ice-cream characters must NOT
get what_are_thosez (footwear) - INCLUDING the Gorbhouse overlay, which is a
what_are_thosez asset attached through its own code path (the bug found in
the 2026-06 batch review: twinkie/poptarts got trash-can slippers because
GORBHOUSE_CHARS bypassed EXCLUDE_WAT_CHARS).

Two phases:
  1. static per-character table using generator.py's own eligibility
     functions (is_wat_excluded / gets_gorbhouse_overlay)
  2. empirical: seeded generate_random_combination() trials; FAIL if any
     excluded character's layer stack contains a path under
     traits/what_are_thosez (no exemptions - Gorbhouse counts)

Usage: python3 asset_assessment/verify_generator_rules.py
"""

import os
import re
import sys

sys.path.insert(0, ".")
import generator as g


def base_names(char_files):
    return sorted({g.char_base_name(f) for f in char_files})


def resolves(char_name, char_files):
    """The art generator.py will draw for a character: every file whose base
    name matches it exactly. Empty means the character has no art."""
    return [f for f in char_files if g.char_base_name(f) == char_name]


def main():
    char_files = g.get_files(g.CHARACTERZ)
    names = base_names(char_files)
    must_exclude = ("churro", "twinkie", "poptart", "ice_cream", "gummy_bear")

    print(f"{'character (base name)':<38}{'WAT?':<6}{'offset':<8}"
          f"{'gorb':<6}{'resolves':<9}rule check")
    bad_rule, bad_resolve = [], []
    for n in names:
        excluded = g.is_wat_excluded(n)
        gorb = g.gets_gorbhouse_overlay(n)
        # offset applies when footwear-less and not in NO_OFFSET_CHARS
        no_off = any(ex.lower() in n.lower()
                     for ex in getattr(g, "NO_OFFSET_CHARS",
                                       g.EXCLUDE_WAT_CHARS))
        offset = "lower" if not no_off else "fixed"
        files = resolves(n, char_files)
        should_be_excluded = any(k in n.lower() for k in must_exclude)
        # excluded characters must get NO footwear: neither random WAT
        # nor the gorbhouse overlay
        ok = (not should_be_excluded) or (excluded and not gorb)
        status = "OK" if ok else "VIOLATION: gets footwear"
        if not ok:
            bad_rule.append(n)
        if not files:
            bad_resolve.append(n)
        print(f"{n[:37]:<38}{'no' if excluded else 'YES':<6}{offset:<8}"
              f"{'yes' if gorb else '-':<6}"
              f"{'yes' if files else 'NO!':<9}{status}")

    print(f"\nintended-rule violations ({len(bad_rule)}): {bad_rule}")
    print(f"characters whose layers never resolve ({len(bad_resolve)}): "
          f"{bad_resolve}")

    # phase 2: empirical layer-stack audit. Catches ANY code path that
    # attaches a what_are_thosez asset to an excluded character, including
    # paths the static table doesn't model.
    import random
    random.seed(1234)
    trials, hits = 600, []
    wat_dir = os.path.join(g.TRAITS_DIR, g.WHAT_ARE_THOSEZ)
    for _ in range(trials):
        layers, char_name = g.generate_random_combination()
        if not any(k in char_name.lower() for k in must_exclude):
            continue
        wat_paths = [l["path"] for l in layers
                     if os.path.normpath(l["path"]).startswith(
                         os.path.normpath(wat_dir))]
        if wat_paths:
            hits.append((char_name, [os.path.basename(p)
                                     for p in wat_paths]))
    print(f"\nempirical audit: {trials} seeded combos, "
          f"footwear-on-excluded hits: {len(hits)}")
    for c, ps in hits[:10]:
        print(f"  {c}: {ps}")

    # phase 3: character-locked armz. A locked arm on a non-matching
    # character is a violation; also report how often each locked arm
    # showed up on its own character so we know the pairing actually fires.
    random.seed(4321)
    lock_hits, lock_ok = [], {k: 0 for k in g.ARMZ_CHAR_LOCK}
    armz_dir = os.path.join(g.TRAITS_DIR, g.ARMZ)
    for _ in range(trials):
        layers, char_name = g.generate_random_combination()
        arms = [os.path.basename(l["path"]) for l in layers
                if os.path.normpath(l["path"]).startswith(
                    os.path.normpath(armz_dir))]
        for a in arms:
            if a not in g.ARMZ_CHAR_LOCK:
                continue
            if g.armz_allowed(a, char_name):
                lock_ok[a] += 1
            else:
                lock_hits.append((char_name, a))
    print(f"\narmz lock audit: {trials} seeded combos, "
          f"locked-arm-on-wrong-character hits: {len(lock_hits)}")
    for c, a in lock_hits[:10]:
        print(f"  {c}: {a}")
    if g.ARMZ_CHAR_LOCK:
        print("locked-arm appearances on their own character:")
        for a, cnt in sorted(lock_ok.items()):
            print(f"  {a}: {cnt}")
    else:
        print("  (ARMZ_CHAR_LOCK is empty — every arm is generic)")

    # phase 3b: SYNTHETIC lock. With no locks defined, phase 3 passes no
    # matter what the arm draw does, so it cannot catch a regression in the
    # rule it exists to test. Inject a lock, re-run, and require both halves:
    # the locked arm must never land on another character, and it must
    # actually reach its own. This is the check that fails against the old
    # `random.choice(all_arm_files)` draw, which ignored locks unless the
    # character had one of its own.
    syn_arm = sorted(g.get_files(g.ARMZ))[0]
    syn_char = "sugar_cube"
    saved = g.ARMZ_CHAR_LOCK
    g.ARMZ_CHAR_LOCK = dict(saved, **{syn_arm: [syn_char]})
    random.seed(5678)
    syn_wrong, syn_right = [], 0
    try:
        for _ in range(trials):
            layers, char_name = g.generate_random_combination()
            arms = [os.path.basename(l["path"]) for l in layers
                    if os.path.normpath(l["path"]).startswith(
                        os.path.normpath(armz_dir))]
            if syn_arm not in arms:
                continue
            if g.armz_allowed(syn_arm, char_name):
                syn_right += 1
            else:
                syn_wrong.append(char_name)
    finally:
        g.ARMZ_CHAR_LOCK = saved
    print(f"\nsynthetic lock ({syn_arm} -> {syn_char}), {trials} combos: "
          f"{len(syn_wrong)} on the wrong character, {syn_right} on its own")
    for c in syn_wrong[:10]:
        print(f"  leaked onto {c}")
    if syn_right == 0:
        print("  WARNING: the locked arm never appeared at all — the lock "
              "override is not firing")

    rate_bad = check_optional_rates()

    if bad_rule or hits or lock_hits or syn_wrong or syn_right == 0 or rate_bad:
        sys.exit(1)


def check_optional_rates(trials=2500, tol=1.2,
                         seeds=(1, 7, 42)):
    """The ad-hoc render path must sample the SAME collection build_mint mints.

    Arms, footwear and stickers are declared once, as exact counts in the
    "optional" block of traits/rarity_weights.json; build_mint slot-allocates
    them and generator derives its roll rates from them. Nothing stopped the
    two drifting when they were declared separately, and they did: sheets
    rendered arms at 34.7% against a mint of 15.9%, so every sample sheet
    overstated how armed the collection was by more than double, invisibly.

    Returns True on failure."""
    import collections
    import json
    import random as _r
    try:
        with open(g.RARITY_PATH) as f:
            o = json.load(f)["optional"]
    except (OSError, ValueError, KeyError):
        print("\noptional-rate check: no rarity_weights.json optional block, "
              "skipped")
        return False
    n = o["supply"]
    target = {"arm": sum(o["arms"].values()) / n,
              "wat": sum(o["footwear"].values()) / n,
              "sticker": o["sticker_total"] / n}
    # AVERAGED over several seeds. One seed is not enough to judge this: the
    # seed-to-seed stdev is ~0.65 points at n=3000, so a single fixed seed can
    # sit 2.6 sigma out and fail a configuration that is actually correct.
    # That happened while this check was being written.
    got = collections.Counter()
    for sd in seeds:
        _r.seed(sd)
        for _ in range(trials):
            layers, _c = g.generate_random_combination()
            for key, d in (("arm", g.ARMZ), ("wat", g.WHAT_ARE_THOSEZ),
                           ("sticker", g.STICKERZ)):
                pref = os.path.normpath(os.path.join(g.TRAITS_DIR, d)) + os.sep
                if any(os.path.normpath(l["path"]).startswith(pref)
                       for l in layers[1:]):
                    got[key] += 1
    trials *= len(seeds)
    print(f"\noptional-trait rates, ad-hoc path vs mint "
          f"({trials} tokens over {len(seeds)} seeds, "
          f"tolerance {tol:.1f} points):")
    bad = False
    for k in ("arm", "wat", "sticker"):
        act = 100.0 * got[k] / trials
        tgt = 100.0 * target[k]
        d = act - tgt
        flag = ""
        if abs(d) > tol:
            bad, flag = True, "   <-- DRIFTED"
        print(f"  {k:<8} ad-hoc {act:6.2f}%   mint {tgt:6.2f}%   "
              f"delta {d:+5.2f}{flag}")
    return bad


if __name__ == "__main__":
    main()
