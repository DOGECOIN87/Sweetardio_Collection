#!/usr/bin/env python3
"""Verify generator.py eligibility rules against the actual asset files.

Rule under test: churro, twinkie, poptarts and ice-cream characters must NOT
be eligible for what_are_thosez (footwear). This script replays generator.py's
own base-name extraction and exclusion matching for every characterz file and
reports, per character: WAT eligibility, vertical-offset behaviour, gorbhouse
overlay, and whether the character's layer files actually resolve through the
generator's lookup patterns.

Usage: python3 asset_assessment/verify_generator_rules.py
"""

import os
import re
import sys

sys.path.insert(0, ".")
import generator as g


def base_names(char_files):
    names = set()
    for f in char_files:
        # same order as generator.py: longest prefix stripped first
        name = (f.replace("layer-after_skinz_", "")
                .replace("before_skinz_", "").replace("after_skinz_", "")
                .replace(".png", ""))
        name = re.sub(r"\s*\(\d+\)", "", name).strip()
        names.add(name)
    return sorted(names)


def resolves(char_name, char_files):
    """Replay generator.py's layer lookup for a character; True if any
    character layer file is found."""
    found = []
    for f in char_files:
        if f.startswith("before_skinz_") and char_name.lower() in f.lower():
            found.append(f)
            break
    patterns = [f"{char_name}.png", f"after_skinz_{char_name}.png",
                f"layer-after_skinz_{char_name}.png"]
    for p in patterns:
        hit = False
        for f in char_files:
            if f.lower() == p.lower() or (char_name.lower() in f.lower()
                                          and "after_skinz" in f.lower()):
                found.append(f)
                hit = True
                break
        if hit:
            break
    if not found:
        for f in char_files:
            if char_name.lower() in f.lower():
                found.append(f)
                break
    return found


def main():
    char_files = g.get_files(g.CHARACTERZ)
    names = base_names(char_files)
    must_exclude = ("churro", "twinkie", "poptart", "ice_cream")

    print(f"{'character (base name)':<38}{'WAT?':<6}{'offset':<8}"
          f"{'gorb':<6}{'resolves':<9}rule check")
    bad_rule, bad_resolve = [], []
    for n in names:
        excluded = any(ex.lower() in n.lower()
                       for ex in g.EXCLUDE_WAT_CHARS)
        gorb = any(gc.lower() in n.lower() for gc in g.GORBHOUSE_CHARS)
        # offset applies when footwear-less and not in NO_OFFSET_CHARS
        no_off = any(ex.lower() in n.lower()
                     for ex in getattr(g, "NO_OFFSET_CHARS",
                                       g.EXCLUDE_WAT_CHARS))
        offset = "lower" if not no_off else "fixed"
        files = resolves(n, char_files)
        should_be_excluded = any(k in n.lower() for k in must_exclude)
        ok = (not should_be_excluded) or excluded
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


if __name__ == "__main__":
    main()
