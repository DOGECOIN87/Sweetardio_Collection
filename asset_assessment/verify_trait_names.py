#!/usr/bin/env python3
"""Gate on the trait NAMES the way verify_face_coverage.py gates on geometry.

Exits non-zero when a name is structurally wrong. It cannot tell you a name
is a bad DESCRIPTION of the art — only a person looking at the art can do
that, which is how four ice creams kept the wrong names for months. What it
does catch is every way a name can silently detach from the thing it names:

  1. STALE KEY     — a TRAIT_NAMES entry whose asset is not on disk. This is
                     the rename bug: rename the file, forget the table, and
                     the asset quietly falls back to a prettified filename
                     while the old name sits there looking authoritative.
  2. NO ENTRY      — an asset with no TRAIT_NAMES entry, so its mint metadata
                     shows _fallback_display_name(). Fine for the background
                     overlays (they never surface as a trait value); a defect
                     anywhere else.
  3. DUPLICATE     — two assets in one class sharing a display name, which
                     makes them indistinguishable in a token's attributes.
  4. DEAD CONFIG   — a key in CHAR_Y_ADJUST / EXCLUDE_WAT_CHARS / GORBHOUSE_
                     CHARS / FACE_HOLE_BOTTOM_OVERRIDE matching no character.
                     Per-character values are tuned to the ART and must follow
                     it through a rename; a key that matches nothing is a
                     value that silently stopped applying.
  5. SHADOWED KEY  — a CHAR_Y_ADJUST key that never wins its own lookup
                     because a longer key always covers it (the gold_waffle /
                     waffle hazard, from the other side).

Usage:
  python3 asset_assessment/verify_trait_names.py          # report + exit code
  python3 asset_assessment/verify_trait_names.py --quiet  # exit code only
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generator as g
from build_char_compat import base_name

# Assets allowed to have no TRAIT_NAMES entry, with the reason. The overlay
# halves of BG_OVERLAY_PAIRS are composited onto their partner plate and are
# skipped by extract_metadata(), so they never appear as a Background value.
ALLOWED_FALLBACK = {
    (g.BACKGROUNDZ, fn): "BG_OVERLAY_PAIRS overlay, never a trait value"
    for fn in g.BG_OVERLAY_PAIRS.values()
}


def wat_base(filename):
    m = re.match(r"(.+?)_base(?:\s*\(\d+\))?\.png$", filename, re.IGNORECASE)
    return m.group(1) if m else None


def keys_on_disk(cat):
    """The keys TRAIT_NAMES *should* hold for this class, from the files."""
    files = g.get_files(cat)
    if cat == g.CHARACTERZ:
        return {base_name(f): f for f in files}
    if cat == g.WHAT_ARE_THOSEZ:
        out = {}
        for f in files:
            b = wat_base(f)
            if b:
                out["Gorbhouse" if "gorbhouse" in b.lower() else b] = f
        return out
    return {f: f for f in files}


CLASSES = [
    (g.CHARACTERZ, "CHARACTERZ"), (g.BACKGROUNDZ, "BACKGROUNDZ"),
    (g.SKINZ, "SKINZ"), (g.EYEZ, "EYEZ"), (g.MOUTHZ, "MOUTHZ"),
    (g.ARMZ, "ARMZ"), (g.WHAT_ARE_THOSEZ, "WHAT_ARE_THOSEZ"),
    (g.STICKERZ, "STICKERZ"),
]


def main():
    quiet = "--quiet" in sys.argv
    failures = []
    notes = []

    for cat, label in CLASSES:
        disk = keys_on_disk(cat)
        table = g.TRAIT_NAMES.get(cat, {})

        for key in sorted(set(table) - set(disk)):
            failures.append(f"{label}: STALE KEY {key!r} -> {table[key]!r} "
                            f"(no such asset on disk)")

        for key in sorted(set(disk) - set(table)):
            why = ALLOWED_FALLBACK.get((cat, disk[key]))
            msg = (f"{label}: NO ENTRY for {key!r}, falls back to "
                   f"{g.trait_name(cat, key)!r}")
            (notes if why else failures).append(
                f"{msg}  [{why}]" if why else msg)

        by_name = {}
        for key in disk:
            by_name.setdefault(g.trait_name(cat, key), []).append(key)
        for name, keys in sorted(by_name.items()):
            if len(keys) > 1:
                failures.append(f"{label}: DUPLICATE NAME {name!r} shared by "
                                f"{sorted(keys)}")

    # ---- per-character config keyed by substring ----
    chars = [base_name(f) for f in g.get_files(g.CHARACTERZ)]
    lowered = [c.lower() for c in chars]

    substring_tables = [
        ("CHAR_Y_ADJUST", list(g.CHAR_Y_ADJUST)),
        ("EXCLUDE_WAT_CHARS", list(g.EXCLUDE_WAT_CHARS)),
    ]
    for extra in ("GORBHOUSE_CHARS", "FACE_HOLE_BOTTOM_OVERRIDE",
                  "ARM_CHAR_DY"):
        if hasattr(g, extra):
            substring_tables.append((extra, list(getattr(g, extra))))

    for tname, keys in substring_tables:
        for key in keys:
            if not any(key.lower() in c for c in lowered):
                failures.append(f"{tname}: DEAD KEY {key!r} matches no "
                                f"character (rename leftover?)")

    # a CHAR_Y_ADJUST key that never wins any lookup is shadowed dead weight
    for key in g.CHAR_Y_ADJUST:
        wins = False
        for c in lowered:
            hits = [k for k in g.CHAR_Y_ADJUST if k in c]
            if hits and max(hits, key=len) == key:
                wins = True
                break
        if not wins and any(key.lower() in c for c in lowered):
            failures.append(f"CHAR_Y_ADJUST: SHADOWED KEY {key!r} never wins "
                            f"its own lookup; a longer key always covers it")

    if not quiet:
        total = sum(len(keys_on_disk(c)) for c, _ in CLASSES)
        print(f"checked {total} named assets across {len(CLASSES)} classes")
        for n in notes:
            print(f"  note: {n}")
        for f in failures:
            print(f"  FAIL: {f}")
        print("OK — every name resolves" if not failures
              else f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
