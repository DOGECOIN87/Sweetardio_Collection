#!/usr/bin/env python3
"""Rename background plates from cryptic export names to collection names.

Renames each plate consistently across BOTH the graded active folder
(traits/backgroundz) and the ungraded source folder
(traits/backgroundz_originals), and fixes every place that references a
plate by filename:
  - traits/eyez_compat.json   (keys in the "blocked" map)
  - generator.py BG_OVERLAY_PAIRS (keys and values, e.g. the lawn pairing)

Input: a JSON mapping {old_filename: new_name}. new_name may omit the
extension and may contain spaces (they are sanitised to underscores; the
extension is preserved from the original file). Entries whose new_name is
empty/null are left unchanged.

Usage:
  python3 asset_assessment/rename_plates.py mapping.json [--apply]
Without --apply it is a DRY RUN (prints what it would do, touches nothing).
"""

import json
import os
import re
import subprocess
import sys

GRADED = "traits/backgroundz"
ORIG = "traits/backgroundz_originals"
COMPAT = "traits/eyez_compat.json"
GENERATOR = "generator.py"


def sanitize(name: str, ext: str) -> str:
    name = name.strip()
    if name.lower().endswith(ext.lower()):
        name = name[: -len(ext)]
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9._-]", "", name)
    return name + ext


def git_mv(src, dst, apply):
    if not apply:
        print(f"    would: git mv {src} -> {dst}")
        return
    subprocess.run(["git", "mv", src, dst], check=True)


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: rename_plates.py mapping.json [--apply]")
    apply = "--apply" in sys.argv
    mapping = json.load(open(sys.argv[1]))

    # build old->new (sanitised), skipping no-ops / blanks
    resolved = {}
    for old, new in mapping.items():
        if not new:
            continue
        ext = os.path.splitext(old)[1] or ".png"
        new_fn = sanitize(str(new), ext)
        if new_fn == old:
            continue
        resolved[old] = new_fn

    # collision check
    seen = {}
    for old, new in resolved.items():
        seen.setdefault(new, []).append(old)
    dupes = {n: o for n, o in seen.items() if len(o) > 1}
    if dupes:
        print("ERROR: target name collisions:")
        for n, o in dupes.items():
            print(f"  {n} <- {o}")
        sys.exit(1)

    print(f"{'DRY RUN' if not apply else 'APPLYING'}: {len(resolved)} renames\n")
    for old, new in resolved.items():
        print(f"  {old}\n    -> {new}")
        for folder in (GRADED, ORIG):
            src = os.path.join(folder, old)
            # the graded JPG source is written out as .png, so the graded
            # file may have a .png extension even if the original was .jpg
            if not os.path.exists(src) and folder == GRADED:
                alt = os.path.splitext(old)[0] + ".png"
                src = os.path.join(folder, alt)
                dst = os.path.join(folder, os.path.splitext(new)[0] + ".png")
            else:
                dst = os.path.join(folder, new)
            if os.path.exists(src):
                git_mv(src, dst, apply)
            else:
                print(f"    (missing in {folder}, skipped)")

    # --- update eyez_compat.json keys ---
    if os.path.exists(COMPAT):
        data = json.load(open(COMPAT))
        blocked = data.get("blocked", {})
        new_blocked = {resolved.get(k, k): v for k, v in blocked.items()}
        data["blocked"] = new_blocked
        if apply:
            json.dump(data, open(COMPAT, "w"), indent=1)
        print(f"\n  {'updated' if apply else 'would update'} {COMPAT} "
              f"({sum(1 for k in blocked if k in resolved)} keys renamed)")

    # --- update BG_OVERLAY_PAIRS in generator.py ---
    gen = open(GENERATOR).read()
    changed = 0
    for old, new in resolved.items():
        for quoted in (f'"{old}"', f"'{old}'"):
            if quoted in gen:
                gen = gen.replace(quoted, quoted.replace(old, new))
                changed += 1
    if apply and changed:
        open(GENERATOR, "w").write(gen)
    print(f"  {'updated' if apply else 'would update'} {GENERATOR} "
          f"({changed} filename references)")

    if not apply:
        print("\nDRY RUN only. Re-run with --apply to perform the renames.")


if __name__ == "__main__":
    main()
