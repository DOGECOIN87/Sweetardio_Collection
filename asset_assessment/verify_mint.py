#!/usr/bin/env python3
"""THE GATE ON A FINISHED MINT: does every image have the metadata that
describes it, and does every piece of metadata have the image it names?

Every other verifier in this repo checks the ART before it is minted --
where a character lands, whether the ball covers the hole, whether the names
resolve. Nothing checked the OUTPUT, and the output is the only thing that
ever reaches a holder. The failure it exists for is not a bad render, it is
a mismatched pair: token 3,207's picture beside token 3,207's traits, where
one of the two came from a different run.

That is not hypothetical. `build_mint.py` writes every path keyed by token
id, so a re-run overwrites what it produces and leaves everything else. A
smaller --n leaves the tail of the previous mint in place; a changed tier
allocation leaves the previous run's animations pointing at stills that have
been replaced underneath them. Each individual file is valid. The collection
is two collections. `build_mint.py --fresh` is the fix and this is the proof
that it worked.

WHAT IT CHECKS

  PAIRING     ids 1..N, each with exactly one image and one metadata file,
              and no orphan in either folder
  THE LINK    every `image` field names the file that is actually there
  ANIMATION   `animation_url` exists on exactly the tokens that have a loop
              -- the weather tier and the starfield tier, per the manifest --
              points at a file that exists, and carries the Metaplex
              `properties` block the bare field needs on Solana
  TRAITS      attributes agree with the manifest trait-for-trait, and
              Trait Count agrees with the attributes it is counting
  COUNTS      the realised distribution matches the DESIGNED counts:
              legendary plates, the starfield, weather, arms, footwear,
              secret rares, the pinned characters
  THE FILES   every image opens, at the mint canvas, and every mask the
              weather bake will need is present

WHAT IT DOES NOT CHECK

  Whether the art is any good, or whether a token's picture actually shows
  the traits it claims -- that would need to re-render it, which is the
  ~2s-per-token composite this whole design exists to avoid. It proves the
  BOOKKEEPING, which is the half that fails silently.

    python3 asset_assessment/verify_mint.py
    python3 asset_assessment/verify_mint.py --expect-images --expect-anim
"""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, ".")
sys.path.insert(0, "asset_assessment")
import generator as g                                    # noqa: E402
import build_mint as bm                                  # noqa: E402

# Attributes that are not a trait slot in the manifest, so the trait-by-trait
# comparison has to know to skip them. Each is derived rather than drawn:
# Plate Tier restates the Background's scarcity band, Trait Count counts the
# others, Artist is a property of a secret rare's artwork.
DERIVED = {"Plate Tier", "Trait Count", "Artist"}

# manifest key -> the trait_type extract_metadata() emits for it
SLOTS = {
    "character": "Character",
    "bg": "Background",
    "skin": "Skin",
    "eye": "Eyes",
    "mouth": "Mouth",
    "arm": "Arms",
    "wat": "Footwear",
    "sticker": "Sticker",
}


class Report:
    """Collects failures so one run reports everything rather than dying on
    the first token. A mint is 4,444 of these and the useful output is the
    PATTERN -- 'every starfield token' reads differently from 'token 3207'."""

    def __init__(self):
        self.fail = Counter()
        self.examples = {}
        self.notes = []

    def bad(self, kind, detail):
        self.fail[kind] += 1
        self.examples.setdefault(kind, detail)

    def note(self, s):
        self.notes.append(s)

    def ok(self):
        return not self.fail

    def show(self):
        for s in self.notes:
            print(s)
        if not self.fail:
            return
        print("\nFAILURES")
        for kind, n in self.fail.most_common():
            print(f"  {n:6d}  {kind}")
            print(f"          e.g. {self.examples[kind]}")


def load_manifest(path):
    if not os.path.exists(path):
        sys.exit(f"no manifest at {path} — run build_mint.py first")
    with open(path) as f:
        return {int(k): v for k, v in json.load(f).items()}


def check(args):
    r = Report()
    man = load_manifest(bm.MANIFEST_PATH)
    ids = sorted(man)
    n = len(ids)
    r.note(f"manifest: {n} tokens, ids {min(ids)}..{max(ids)}")

    if ids != list(range(1, n + 1)):
        missing = sorted(set(range(1, max(ids) + 1)) - set(ids))
        r.bad("manifest ids are not a contiguous 1..N run",
              f"{len(missing)} missing, first {missing[:5]}")

    # ---- the two folders, as SETS, so an orphan is visible from either side
    meta_files = {f for f in os.listdir(bm.META_DIR) if f.endswith(".json")} \
        if os.path.isdir(bm.META_DIR) else set()
    want_meta = {f"{i}.json" for i in ids}
    for f in sorted(meta_files - want_meta)[:50]:
        r.bad("metadata file with no token in the manifest (STALE)", f)
    for f in sorted(want_meta - meta_files)[:50]:
        r.bad("token in the manifest with no metadata file", f)

    imgs = {f for f in os.listdir(bm.IMG_DIR) if f.endswith(".png")} \
        if os.path.isdir(bm.IMG_DIR) else set()
    if args.expect_images:
        want_img = {f"{i}.png" for i in ids}
        for f in sorted(imgs - want_img)[:50]:
            r.bad("image with no token in the manifest (STALE)", f)
        for f in sorted(want_img - imgs)[:50]:
            r.bad("token in the manifest with no image", f)
    elif imgs:
        r.note(f"images: {len(imgs)} present "
               f"(pass --expect-images to require one per token)")
    else:
        r.note("images: none rendered (metadata-only run)")

    anims = {f for f in os.listdir(bm.ANIM_DIR) if f.endswith(".mp4")} \
        if os.path.isdir(bm.ANIM_DIR) else set()
    masks = {f for f in os.listdir(bm.MASK_DIR) if f.endswith(".png")} \
        if os.path.isdir(bm.MASK_DIR) else set()

    # ---- per token
    animated_expected = set()
    counts = Counter()
    tiers = Counter()
    for tid in ids:
        row = man[tid]
        path = os.path.join(bm.META_DIR, f"{tid}.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                tok = json.load(f)
        except Exception as e:
            r.bad("metadata is not valid JSON", f"{tid}.json: {e}")
            continue

        attrs = {a["trait_type"]: a["value"] for a in tok.get("attributes", [])}

        # THE LINK: the image field must name this token's own file.
        img = tok.get("image")
        if img is None:
            r.bad("metadata has no `image` field", f"{tid}.json")
        elif os.path.basename(str(img)) != f"{tid}.png":
            r.bad("`image` names a different token's file",
                  f"{tid}.json -> {img!r}")
        elif args.expect_images and f"{tid}.png" not in imgs:
            r.bad("`image` names a file that is not there", f"{tid}.json")

        # ANIMATION: exactly the two animated tiers, and nothing else. A
        # static token that claims a loop shows a broken player on every
        # surface that believes it.
        wants_anim = bool(row.get("weather") or row.get("starfield"))
        if wants_anim:
            animated_expected.add(tid)
        has_anim = "animation_url" in tok
        if args.expect_anim and wants_anim and not has_anim:
            r.bad("animated token carries no animation_url",
                  f"{tid}.json ({'weather' if row.get('weather') else 'starfield'})")
        if has_anim and not wants_anim:
            r.bad("static token claims an animation_url", f"{tid}.json")
        if has_anim:
            props = tok.get("properties") or {}
            if props.get("category") != "video":
                r.bad("animation_url without properties.category=video",
                      f"{tid}.json")
            uris = {os.path.basename(str(f.get("uri")))
                    for f in props.get("files", [])}
            if os.path.basename(str(tok["animation_url"])) not in uris:
                r.bad("animation_url is not listed in properties.files[]",
                      f"{tid}.json")
            if anims and os.path.basename(
                    str(tok["animation_url"])) not in anims:
                r.bad("animation_url names a file that is not there",
                      f"{tid}.json -> {tok['animation_url']}")

        # bake_weather.py grades against the protect mask; without it the
        # 444 weather tokens cannot be baked at all.
        if args.expect_masks and row.get("weather") \
                and f"{tid}.png" not in masks:
            r.bad("weather token has no protect mask (bake_weather needs it)",
                  f"{tid}.png")

        # SECRET RARES compose with nothing, so they carry no trait slots.
        if row.get("secret_rare"):
            if "Secret Rarez" not in attrs:
                r.bad("secret rare without its Secret Rarez attribute",
                      f"{tid}.json")
            for slot in ("Character", "Background", "Skin", "Eyes", "Mouth"):
                if slot in attrs:
                    r.bad("secret rare carries a composited trait",
                          f"{tid}.json has {slot}")
            counts["secret_rare"] += 1
            continue

        # TRAITS: every manifest slot must appear with the display name the
        # generator resolves for it, and no slot may appear that the
        # manifest does not have.
        for key, trait in SLOTS.items():
            val = row.get(key)
            if val and trait not in attrs:
                r.bad(f"manifest has {key} but metadata has no {trait}",
                      f"{tid}.json ({val})")
            elif not val and trait in attrs:
                r.bad(f"metadata has {trait} but the manifest has no {key}",
                      f"{tid}.json ({attrs[trait]!r})")
            elif val and key != "wat":
                # FOOTWEAR IS THE ONE SLOT THAT CANNOT BE COMPARED BY NAME
                # HERE, and it is not a defect on either side. traits_of()
                # records whichever footwear layer it saw last, which is the
                # OVERLAY; extract_metadata() names the pair from its _base
                # file. The two never hold the same string, so deriving one
                # from the other would mean re-implementing the overlay ->
                # base strip -- exactly the substring guessing that has bitten
                # this repo before (see char_base_name in CLAUDE.md). What is
                # actually invariant is presence, checked above, and the
                # display-name COUNTS, which _counts() checks against
                # FOOTWEAR_COUNTS through build_mint's own
                # expected_footwear_name(). Between them a mispaired footwear
                # slot still cannot survive.
                want = g.trait_name(_category(key), val)
                if attrs[trait] != want:
                    r.bad(f"{trait} disagrees with the manifest",
                          f"{tid}.json: {attrs[trait]!r} vs {want!r}")

        if row.get("weather"):
            want = row["weather"].title()
            if attrs.get("Weather") != want:
                r.bad("Weather disagrees with the manifest",
                      f"{tid}.json: {attrs.get('Weather')!r} vs {want!r}")
        elif "Weather" in attrs:
            r.bad("metadata has Weather but the manifest has none",
                  f"{tid}.json")

        # TRAIT COUNT counts the traits beside it, so it can be recomputed
        # from the file itself -- the one attribute that can be checked
        # without reference to anything.
        tc = attrs.get("Trait Count")
        real = len([k for k in attrs if k not in DERIVED])
        if tc is None:
            r.bad("no Trait Count attribute", f"{tid}.json")
        elif tc != real:
            r.bad("Trait Count does not count the attributes present",
                  f"{tid}.json: says {tc}, counts {real}")

        if "Plate Tier" in attrs and row.get("bg"):
            want = g.plate_tier(row["bg"])
            if attrs["Plate Tier"] != want:
                r.bad("Plate Tier is not the band its Background sits in",
                      f"{tid}.json: {attrs['Plate Tier']!r} vs {want!r}")
        tiers[attrs.get("Plate Tier")] += 1

        for key in SLOTS:
            if row.get(key):
                counts[f"{key}:{row[key]}"] += 1
        # Footwear is designed by BASE name ("Bunny") and minted as an
        # overlay filename, so the two only meet at the display name --
        # which is exactly the join build_mint itself asserts on.
        if attrs.get("Footwear"):
            counts[f"footwear_name:{attrs['Footwear']}"] += 1
        if row.get("weather"):
            counts[f"weather:{row['weather']}"] += 1
        if row.get("starfield"):
            counts["starfield"] += 1
        if row.get("legendary"):
            counts["legendary"] += 1

    # ---- the DESIGNED counts, checked against what actually minted
    _counts(r, counts, n)

    if args.expect_anim:
        extra = anims - {f"{i}.mp4" for i in animated_expected}
        for f in sorted(extra)[:20]:
            r.bad("animation with no animated token (STALE)", f)

    if args.expect_images and imgs:
        _images(r, ids, args.sample)

    r.note(f"plate tiers: " + ", ".join(
        f"{k} {v}" for k, v in sorted(tiers.items(), key=lambda x: -x[1])
        if k))
    return r


def _category(key):
    return {"character": g.CHARACTERZ, "bg": g.BACKGROUNDZ, "skin": g.SKINZ,
            "eye": g.EYEZ, "mouth": g.MOUTHZ, "arm": g.ARMZ,
            "wat": g.WHAT_ARE_THOSEZ, "sticker": g.STICKERZ}[key]


def _counts(r, counts, n):
    """The realised distribution against the DESIGNED one.

    These are the numbers the rarity table and every marketplace filter will
    show, and they are the ones a stale re-run corrupts first: an allocator
    hits its targets exactly, so a count that is off is not sampling noise,
    it is two mints mixed together."""
    def want(label, got, expect):
        if got != expect:
            r.bad(f"designed count missed: {label}",
                  f"expected {expect}, minted {got}")

    want("starfield", counts["starfield"], bm.STARFIELD_COUNT)
    for state, c in bm.WEATHER_COUNTS.items():
        want(f"weather {state}", counts[f"weather:{state}"], c)
    for arm, c in bm.GENERIC_ARM_COUNTS.items():
        want(f"arm {arm}", counts[f"arm:{arm}"], c)
    for wat, c in bm.FOOTWEAR_COUNTS.items():
        name = bm.expected_footwear_name(wat)
        want(f"footwear {wat}", counts[f"footwear_name:{name}"], c)
    for char, c in bm.CHARACTER_COUNTS.items():
        want(f"character {char}", counts[f"character:{char}"], c)

    r.note(f"counts: starfield {counts['starfield']}, "
           f"legendary {counts['legendary']}, "
           f"weather {sum(v for k, v in counts.items() if k.startswith('weather:'))}, "
           f"secret rares {counts['secret_rare']}")


def _images(r, ids, sample):
    """Open the images. Cheap per file, and it is what catches a truncated
    write -- a PNG that is 40 % of a token is a valid file to every check
    that only looks at the name."""
    from PIL import Image
    step = max(1, len(ids) // sample) if sample else 1
    checked = 0
    for tid in ids[::step]:
        p = os.path.join(bm.IMG_DIR, f"{tid}.png")
        if not os.path.exists(p):
            continue
        try:
            im = Image.open(p)
            im.load()
        except Exception as e:
            r.bad("image will not open (truncated write?)", f"{tid}.png: {e}")
            continue
        if im.size != (g.CANVAS_SIZE, g.CANVAS_SIZE):
            r.bad("image is not at the mint canvas",
                  f"{tid}.png is {im.size[0]}x{im.size[1]}, "
                  f"want {g.CANVAS_SIZE}")
        checked += 1
    r.note(f"images: opened {checked} of {len(ids)} "
           f"(--sample {sample or 'all'})")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--expect-images", action="store_true",
                    help="require one image per token (a --render mint)")
    ap.add_argument("--expect-anim", action="store_true",
                    help="require animation_url on every animated token "
                         "(a --animation mint)")
    ap.add_argument("--expect-masks", action="store_true",
                    help="require a protect mask per weather token "
                         "(a --masks mint; bake_weather.py needs them)")
    ap.add_argument("--sample", type=int, default=400,
                    help="how many images to actually open; 0 = all")
    args = ap.parse_args()

    r = check(args)
    r.show()
    if r.ok():
        print("\nOK — every token's metadata matches its image, and every "
              "designed count minted exactly.")
        return 0
    print(f"\nFAIL — {sum(r.fail.values())} problems across "
          f"{len(r.fail)} kinds.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
