#!/usr/bin/env python3
"""Render every character as standalone transparent assets, N variants each.

Each asset is the minimum face kit — character body, skin ball, eyes, mouth —
composited through generator.py's production pipeline onto transparency, at
the full 1393 canvas so every file shares the collection's registration (the
face sits at ~(690, 601) in all of them).

The rendering is export_game_assets.render(), unchanged: a transparent plate
stands in for layers[0], GROUND_SHADOW and SUBJECT_SEPARATION are off (both
seat a figure INTO a plate and would bake a grey smudge into a cutout), and
every on-figure shadow — skin, eye, mouth, face inset — is kept. Arms,
footwear and stickers are forced off, so the files carry only the four
required traits.

Trait choice is deterministic and balanced. Each list is shuffled once from
the seed, then dealt round-robin across the cast: every skin, eye and mouth
appears near-equally often, and a character's variants never share a skin,
an eye or a mouth (the step between variants is 1, and every list is longer
than the variant count).

  python3 asset_assessment/export_standalone_characters.py
  python3 asset_assessment/export_standalone_characters.py --variants 3 --out /tmp/x
"""

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator  # noqa: E402
import export_game_assets as ega  # noqa: E402

OUT_DEFAULT = "catalog/standalone_characters"


def cast():
    """Every character base name, via the ONE definition of a name."""
    return sorted({generator.char_base_name(f)
                   for f in generator.get_files(generator.CHARACTERZ)},
                  key=str.lower)


def deal(chars, variants, seed):
    """[(char, variant, skin, eyes, mouth)] with display names from ega's
    tables, balanced round-robin over a seeded shuffle."""
    rng = random.Random(seed)
    skins, eyes, mouths = (list(t) for t in (ega.SKIN, ega.EYES, ega.MOUTH))
    for lst in (skins, eyes, mouths):
        rng.shuffle(lst)
    if variants > min(len(skins), len(eyes), len(mouths)):
        raise SystemExit(f"--variants {variants} cannot keep every variant's "
                         f"traits distinct (only {len(skins)} skins)")
    out = []
    for i, ch in enumerate(chars):
        for v in range(variants):
            k = i * variants + v
            out.append((ch, v + 1, skins[k % len(skins)],
                        eyes[k % len(eyes)], mouths[k % len(mouths)]))
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--variants", type=int, default=2)
    ap.add_argument("--seed", type=int, default=4444)
    ap.add_argument("--only", default=None, help="one character base name")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    chars = cast()
    if args.only:
        chars = [c for c in chars if c == args.only] or sys.exit(
            f"no character named {args.only!r}")

    manifest, paths = [], []
    for ch, v, skin, eye, mouth in deal(chars, args.variants, args.seed):
        random.seed(f"{args.seed}:{ch}:{v}")
        spec = dict(char=ch, skin=skin, eyes=eye, mouth=mouth, arm=None,
                    file=f"{ch}_{v}.png")
        path = os.path.join(args.out, spec["file"])
        ega.render(spec, path)

        alpha = generator.Image.open(path).getchannel("A")
        corners = [alpha.getpixel(p) for p in
                   ((0, 0), (alpha.width - 1, 0), (0, alpha.height - 1),
                    (alpha.width - 1, alpha.height - 1))]
        if any(corners) or alpha.getbbox() is None:
            raise SystemExit(f"{path}: background is not transparent")

        name = generator.trait_name(generator.CHARACTERZ, ch)
        manifest.append({"file": spec["file"], "character": name,
                         "character_key": ch, "variant": v,
                         "attributes": [
                             {"trait_type": "Character", "value": name},
                             {"trait_type": "Skin", "value": skin},
                             {"trait_type": "Eyes", "value": eye},
                             {"trait_type": "Mouth", "value": mouth}]})
        paths.append(path)
        print(f"  {spec['file']:36} {skin:6} / {eye:9} / {mouth}")

    if not args.only:
        with open(os.path.join(args.out, "manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
        sheet = os.path.join(args.out, "_contact_sheet.jpg")
        tmp = ega.contact_sheet(paths, sheet.replace(".jpg", ".png"),
                                cols=args.variants * 3, cell=260)
        generator.Image.open(tmp).convert("RGB").save(sheet, quality=88)
        os.remove(tmp)
        print(f"  {len(paths)} assets, manifest + sheet in {args.out}")


if __name__ == "__main__":
    main()
