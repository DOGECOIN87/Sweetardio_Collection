#!/usr/bin/env python3
"""Write catalog/NAMES.md: every asset in traits/, with its display name.

The names come from generator.trait_name() — the same lookup
extract_metadata() uses to fill a token's attributes — so the catalog and the
mint metadata cannot drift apart. Run it after adding, removing or renaming
any asset, alongside render_traitsheet.py for that class.

  python3 asset_assessment/dump_trait_names.py
  python3 asset_assessment/dump_trait_names.py --out /tmp/names.md
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generator as g
from build_char_compat import base_name   # the generator's own char mapping

RETIRED_DIR = "secret_rarez_retired"

# Names the owner has confirmed are DELIBERATE even though they do not
# describe the art. Checked by eye 2026-08 and kept on the owner's call, so a
# later audit does not "fix" them the way the ice creams genuinely needed
# fixing. Keyed (category, TRAIT_NAMES key) -> why it stays.
INTENTIONAL = {
    ("backgroundz", "Coder_Chick.png"):
        "Pastel unicorn wallpaper. Kept on the owner's call.",
    ("backgroundz", "Druski.png"):
        "A blonde woman with a flag and confetti; the comedian himself is not "
        "in frame. Kept — the still comes from his content.",
    ("backgroundz", "Legendary_Tenders.png"):
        "The word NOTHING repeated over a star field. Kept on the owner's "
        "call; the Legendary_ prefix is load-bearing either way.",
    ("armz", "layer-layer-layer-layer-Military_Brat.png"):
        "Two cartoon gloves, one pointing, one open — no weapon. It is the "
        "de-facto unarmed arm (lifts 3 of 27 figures against the AK15's 18). "
        "Kept on the owner's call.",
}


def wat_base(filename):
    """The footwear base name, matching generator's own inline matcher."""
    m = re.match(r"(.+?)_base(?:\s*\(\d+\))?\.png$", filename, re.IGNORECASE)
    return m.group(1) if m else None


def build():
    overlays = set(g.BG_OVERLAY_PAIRS.values())
    out = []
    w = out.append

    w("# Asset names\n")
    w("Every asset currently in `traits/`, with the display name the mint "
      "metadata")
    w("shows for it. Generated from `TRAIT_NAMES` in `generator.py` — the same")
    w("lookup `extract_metadata()` uses, so this file and a token's attributes")
    w("cannot disagree. Regenerate with "
      "`asset_assessment/dump_trait_names.py`.\n")
    w("A **†** marks a name that deliberately does not describe its art; see")
    w("[Deliberate names](#deliberate-names) at the end.\n")

    def table(title, rows, note=None, cat=None):
        w(f"## {title} ({len(rows)})\n")
        if note:
            w(note + "\n")
        w("| Name | File |")
        w("|------|------|")
        for name, filename in rows:
            mark = " †" if (cat, filename) in INTENTIONAL else ""
            w(f"| {name}{mark} | `{filename}` |")
        w("")

    chars = [(g.trait_name(g.CHARACTERZ, base_name(f)), f)
             for f in g.get_files(g.CHARACTERZ)]
    table("Characters", sorted(chars), cat=g.CHARACTERZ)

    bgs = g.get_files(g.BACKGROUNDZ)
    std = [(g.trait_name(g.BACKGROUNDZ, f), f) for f in bgs
           if not g.is_legendary_bg(f) and f not in overlays]
    leg = [(g.trait_name(g.BACKGROUNDZ, f), f) for f in bgs
           if g.is_legendary_bg(f)]
    ovl = [(g.trait_name(g.BACKGROUNDZ, o), o) for o in sorted(overlays)]
    table("Backgrounds — standard", sorted(std), cat=g.BACKGROUNDZ)
    table("Backgrounds — legendary", sorted(leg),
          "Drawn only when a token is pinned to a legendary plate; the "
          "`Legendary_`\nfilename prefix is what `is_legendary_bg()` matches "
          "on.", cat=g.BACKGROUNDZ)
    table("Backgrounds — overlays", sorted(ovl),
          "Not plates in their own right. `BG_OVERLAY_PAIRS` draws each of "
          "these\nover its partner plate (Whitehouse Lawn, Mars), so they "
          "never appear as a\nBackground value on their own.", cat=g.BACKGROUNDZ)

    for cat, title in ((g.SKINZ, "Skins"), (g.EYEZ, "Eyes"),
                       (g.MOUTHZ, "Mouths"), (g.ARMZ, "Arms")):
        table(title, sorted((g.trait_name(cat, f), f)
                            for f in g.get_files(cat)), cat=cat)

    wats = {}
    for f in g.get_files(g.WHAT_ARE_THOSEZ):
        b = wat_base(f)
        if b:
            wats["Gorbhouse" if "gorbhouse" in b.lower() else b] = f
    table("Footwear",
          sorted((g.trait_name(g.WHAT_ARE_THOSEZ, k), v)
                 for k, v in wats.items()),
          "One entry per wearable pair. Each ships as a `_Base` plus one or "
          "more\n`_Overlay` files (Shiba has a left and a right), which is why "
          "the folder\nholds 11 PNGs for 5 names.", cat=g.WHAT_ARE_THOSEZ)

    table("Stickers", sorted((g.trait_name(g.STICKERZ, f), f)
                             for f in g.get_files(g.STICKERZ)),
          cat=g.STICKERZ)

    retired_path = os.path.join(g.TRAITS_DIR, RETIRED_DIR)
    retired = sorted(f for f in os.listdir(retired_path)
                     if f.endswith(".png")) if os.path.isdir(retired_path) else []
    w(f"## Secret Rarez — retired ({len(retired)})\n")
    w("The 1/1 tier is **retired**: `traits/secret_rarez` is empty, so nothing "
      "here")
    w("mints. The art is kept in `traits/secret_rarez_retired`, and")
    w("`secret_rare_number()` reads that folder rather than a names table, so "
      "moving")
    w("it back restores the tier with its original numbering. Names fall back "
      "from")
    w("the filenames. `catalog/traitsheet_secret_rarez.png` is the record of "
      "the")
    w("tier as it stood.\n")
    w("| # | Name | File |")
    w("|--:|------|------|")
    for i, f in enumerate(retired, 1):
        w(f"| {i} | {g._fallback_display_name(f)} | `{f}` |")
    w("")

    w("## Deliberate names\n")
    w("Every asset was checked by eye against its art in 2026-08. These are "
      "the")
    w("names that do **not** describe what is in the frame and are staying "
      "that")
    w("way on the owner's call. They are listed here so the next audit reads "
      "this")
    w("instead of re-opening them — unlike the four ice creams, which were "
      "named")
    w("after flavours they were not and did need correcting (see `CLAUDE.md`).\n")
    w("| Name | Class | Why it stays |")
    w("|------|-------|--------------|")
    for (cat, key), why in sorted(INTENTIONAL.items(),
                                  key=lambda kv: g.trait_name(*kv[0])):
        w(f"| {g.trait_name(cat, key)} | `{cat}` | {why} |")
    w("")

    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="catalog/NAMES.md")
    a = ap.parse_args()
    with open(a.out, "w") as fh:
        fh.write(build())
    print(f"wrote {a.out}")
