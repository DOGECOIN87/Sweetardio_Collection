#!/usr/bin/env python3
"""Deterministic mint allocator: compose exactly N unique tokens with explicit
rarity targets, on top of generator.py's weighted, compat-aware pipeline.

Rarity model (all counts are EXACT, hit by pre-allocating token slots):

  Backgrounds
    * Legendary_* plates (in traits/backgroundz) are 1/1-style rares: each one
      appears EXACTLY --leg-each times (default 30). 4 x 30 = 120.
    * every other token gets a normal weighted/compat plate; Legendary plates
      never appear via the random pick (generator excludes the prefix).

  Arms  (RARE overall: ~16% of the supply hold a weapon, ~84% empty-handed)
    tier            arm                         count
    Mythic          AK15 (Golden AK)             20   <- rarest item in the set
    Legendary       Blue / Pink / Cyan Saber     25 each (75)
    Rare            Dual Uzis                    40
    Rare            AR47                         55
    Uncommon        Military Brat                85
    Uncommon        Nerf Blaster                110
    Uncommon        Cash                         130
    Signature       6 character-locked weapons   32 each (192, only on owner)

  Footwear (what_are_thosez)  RARE (~12%): Gorbhouse + Bunny/Pepe/Shiba/Monster
  Stickers                    UNCOMMON (~18%)

  Legendary-background tokens are kept footwear-free and signature-weapon-free
  so the rare plate + character read cleanly; they may still carry a generic
  arm or a sticker. Every token is a UNIQUE trait combination.

Outputs:
  output/mint_manifest.json          token id -> traits
  output/mint/metadata/<id>.json     OpenSea-compatible token metadata
  output/mint/images/<id>.png        with --render
  output/mint/masks/<id>.png         with --render --masks; the protect mask
                                     the dynamic sky pass grades against
  a full trait-distribution report (also -> output/mint/rarity_report.txt)
Reproducible by --seed.

Usage (from repo root):
  python3 asset_assessment/build_mint.py [--n 4444] [--leg-each 30] [--seed 4444]
  python3 asset_assessment/build_mint.py --render --masks
"""

import argparse
import json
import os
import shutil
import sys
from collections import Counter

sys.path.insert(0, ".")
sys.path.insert(0, "asset_assessment")
import generator as g
from verify_separation import at_risk, plate_stats   # noqa: E402
from build_char_compat import char_table              # noqa: E402
from dynamic import sky as skymod                     # noqa: E402
from dynamic import starfield as sfmod                # noqa: E402
from dynamic.animate import write_mp4                 # noqa: E402

# ---- every path the mint writes, named once ----
# The preflight below deletes exactly these, and the writers at the bottom
# fill exactly these. Spelled twice they drift, and a --fresh that misses a
# folder is worse than no --fresh at all: it leaves the one stale directory
# nobody thought to look in.
OUT_DIR = "output"
MINT_DIR = os.path.join(OUT_DIR, "mint")
IMG_DIR = os.path.join(MINT_DIR, "images")
META_DIR = os.path.join(MINT_DIR, "metadata")
MASK_DIR = os.path.join(MINT_DIR, "masks")
FLOAT_DIR = os.path.join(MINT_DIR, "float_masks")
ANIM_DIR = os.path.join(MINT_DIR, "anim")
# bake_weather.py moves the clear render here on first bake and reads it back
# on every later one, so a stale copy silently re-bakes yesterday's art.
CLEAR_DIR = os.path.join(MINT_DIR, "images_clear")
MANIFEST_PATH = os.path.join(OUT_DIR, "mint_manifest.json")
REPORT_PATH = os.path.join(MINT_DIR, "rarity_report.txt")


def _rebind_out_dir(root):
    """Re-root every path above at `root`. Spelled once, for the reason the
    block above is: a --fresh that deletes one tree while the writers fill
    another is worse than no --fresh at all."""
    g = globals()
    g["OUT_DIR"] = root
    g["MINT_DIR"] = os.path.join(root, "mint")
    for name, leaf in (("IMG_DIR", "images"), ("META_DIR", "metadata"),
                       ("MASK_DIR", "masks"), ("FLOAT_DIR", "float_masks"),
                       ("ANIM_DIR", "anim"), ("CLEAR_DIR", "images_clear")):
        g[name] = os.path.join(g["MINT_DIR"], leaf)
    g["MANIFEST_PATH"] = os.path.join(root, "mint_manifest.json")
    g["REPORT_PATH"] = os.path.join(g["MINT_DIR"], "rarity_report.txt")

TRAIT_KEYS = ("character", "bg", "skin", "eye", "mouth", "arm", "wat", "sticker")

# Weather is deliberately NOT in TRAIT_KEYS, so it is not part of the
# uniqueness signature. Including it would let two tokens that are
# identical in every other trait both mint, "distinguished" only by their
# sky -- which is a weaker guarantee than the collection has today. Every
# token is unique WITHOUT its weather, and the weather is then laid on top.

# ---- arm rarity tiers (filename -> exact mint count) ----
AK15        = "layer-layer-layer-layer-AK15.png"
SABERS      = ["Sweetardio_114 (4).png", "Sweetardio_114 (5).png",
               "Sweetardio_114 (6).png"]
# ---- optional-trait counts: LOADED, not declared here ----
# The exact counts live in the "optional" block of traits/rarity_weights.json,
# which is the single source of truth: generator.py derives its per-token roll
# rates (ARM_RATE / FOOTWEAR_RATE / STICKER_RATE) from the same numbers, so an
# ad-hoc render samples the same collection this allocator mints.
#
# They were declared in both places once, and drifted without anything
# noticing: sheets rendered arms at 34.7% against a mint of 15.9%.
# verify_generator_rules.py now fails if the two disagree.
_OPT = json.load(open(g.RARITY_PATH))["optional"]
GENERIC_ARM_COUNTS = _OPT["arms"]        # filename -> exact mint count
FOOTWEAR_COUNTS = _OPT["footwear"]       # wat base name / "gorbhouse" -> count
STICKER_TOTAL = _OPT["sticker_total"]    # ~95%: a bare token is the rare case
# Character-locked signature weapons (only minted onto their owner).
#
# EMPTY BY DESIGN, mirroring generator.ARMZ_CHAR_LOCK. The katana and knives
# used to be seven per-character files here at 32 each; they are now one
# generic file each, in GENERIC_ARM_COUNTS above. The counts there preserve
# what a collector actually sees, because the metadata only ever showed the
# display name: four minted katanas x 32 = 128 "Katana" tokens and two knives
# x 32 = 64 "Knives", so the trait rarity table does not move. What changes is
# that the weapons now spread across the whole cast instead of being pinned to
# one owner each.
SIGNATURE_ARMS = {}

# ---- footwear rarity (base name as returned by wat_base_name, or "gorbhouse")



# ---- per-character rarity (base character name -> EXACT mint count) ----
# Characters are otherwise drawn uniformly, so every unlisted character shares
# the remaining supply evenly (~139 each at n=4444). Listing a character here
# pins it to an exact count instead, the same way the arm and footwear tiers
# work. Pinned characters are kept off legendary-background slots so the
# legendary camouflage re-roll can never fight a forced character.
#
#   "sugar_cube": 20,        # <- would make sugar cube the rarest in the set
#
# Tiered by how distinctive the body reads, judged off a render of all 27 on
# one plate with one face (not from the filenames). The COMMON tier is
# deliberately left unpinned: legendary-background slots re-roll the character
# when it camouflages against the plate, which a forced character can never
# satisfy, so the legendary slots (4 x --leg-each) have to draw from
# somewhere.
#
#   chase     4 x 60  = 240   the four that look like nothing else in the set
#   uncommon 10 x 130 = 1300  strong, individual silhouettes
#   common   13 unpinned      ~222 each; the cones, torus doughnuts and
#                             squares, which repeat each other's shapes
CHARACTER_COUNTS = {
    # chase
    "og_gummy_bear": 60,      # translucent gradient body, the only humanoid
    "gold_waffle": 60,        # metallic gold, the only one that reads premium
    "churro": 60,             # tall ridged column, unique silhouette
    "zebra_cake": 60,         # hexagonal with stripes, unique outline
    # uncommon
    "chocolate_sandwich_cookie": 130,
    "ding_dong": 130,
    "Nutty_Bar": 130,
    "Twinkie": 130,
    "marshmallow": 130,
    "smores": 130,
    "waffle": 130,
    "cyan_frosted_poptart": 130,
    "rice_crispy_treat": 130,
    "oatmeal_cream_pie": 130,
}


# Unpinned slots must draw from the COMPLEMENT of the pinned set, or a pinned
# count is only a floor: the pinned slots force the character and every other
# slot then draws it again at random on top. That put a 60-target character at
# 157 before this existed.
PINNED_CHARS = frozenset(CHARACTER_COUNTS)


# ---- weather (base name -> EXACT mint count) ----
# 444 of the 4,444 carry an ANIMATED weather state, permanently. This is a
# trait like any other here, not a live overlay: it is drawn once, baked
# into the token's own still and loop, and it never changes again.
#
# That is the whole difference from the earlier design, and it is what
# makes the state safe to put in `attributes`. A value that changed with
# the real sky would be indexed by rarity tools as though it were
# permanent and be wrong within the hour; a value assigned here IS
# permanent, so it belongs in the rarity table alongside the arms.
#
# Tiered the same way the weapons are, by how much of an event the state
# is. rain is weather; a tornado is something that happened to you.
#
#   ordinary  rain 110, snow 95, fog 80, storm 75   = 360
#   severe    blizzard 40, flooded 30, tornado 14    =  84
#
# tornado lands at 14/4,444 (0.32%), which puts it between the AK15 (20)
# and nothing else in the set -- the rarest trait the collection has.
WEATHER_COUNTS = {
    "rain": 110,
    "snow": 95,
    "fog": 80,
    "storm": 75,
    "blizzard": 40,
    "flooded": 30,
    "tornado": 14,
}
WEATHER_TOTAL = sum(WEATHER_COUNTS.values())      # 444

# The allocator and the renderer keep two independent lists of what a
# weather state is -- one here by rarity, one in dynamic/sky.py by art
# direction -- so they are checked against each other at import. A state
# allocated here that sky.py cannot grade would mint 40 tokens pointing at
# an animation that can never be rendered, and nothing else would notice
# until bake_weather.py died 400 tokens in. This is the same class of
# check verify_trait_names.py runs over the trait tables.
_unknown = sorted(set(WEATHER_COUNTS) - set(skymod.WEATHER_STATES))
if _unknown:
    sys.exit(f"WEATHER_COUNTS allocates {_unknown}, which dynamic/sky.py "
             f"cannot render — states are {sorted(skymod.WEATHER_STATES)}")

# Weather is kept OFF legendary-background slots, for exactly the reason
# footwear and signature weapons are: the point of a legendary plate is
# that you can see it, and every weather state is in front of the plate.
# A tornado over a 1-of-50 background hides the thing that made it rare.

# ---- the starfield: the collection's ULTRA-RARE tier ----
#
# 22 of 4444 -- 0.50 %, the rarest COMPOSITED trait in the set: the next
# rarest is Tornado at 14 (0.32 %) but that is a weather state rather than a
# plate, and a legendary plate is 30 (0.68 %). Only the two 1/1 secret rares
# beat it. It is not a hard cap by luck: generator.is_allocator_only_bg
# keeps the plate out of the weighted draw entirely, exactly as the
# Legendary_* plates are kept out, so the only way to mint one is here.
STARFIELD_COUNT = 22

# It is kept off LEGENDARY slots (one rare plate per token -- a starfield
# would simply replace the legendary plate it was supposed to coexist with)
# and off WEATHER slots. The weather exclusion is not squeamishness about
# rain in space: both traits own animation_url, so a token carrying each
# would have two loops and one slot to put them in.
#
# Stickers are deliberately NOT excluded. They allocate from every
# composable slot, legendary included, and the owner asked for them here
# too, so a starfield token can carry one like any other.
if STARFIELD_COUNT and g.STARFIELD_BG not in g.get_files(g.BACKGROUNDZ):
    sys.exit(f"STARFIELD_COUNT is {STARFIELD_COUNT} but "
             f"traits/{g.BACKGROUNDZ}/{g.STARFIELD_BG} is missing — "
             f"rebuild it with dynamic/starfield.py")


# Trait Count is the axis collectors already rank on, and both of its tails
# here are rarer than a Legendary plate: at seed 4444, 5 traits is 135 tokens
# (3.04 %) and 9 traits is 7 (0.16 %), rarer than the Starfield's 22. Neither was
# discoverable, because "carries no arm, no footwear and no sticker" is an
# ABSENCE -- there is no attribute for it, so no marketplace can filter or
# sort on it and no rarity tool can score it.
#
# Emitted as a NUMBER rather than a named band ("Bare", "Full Kit") because
# the number IS the convention: marketplaces sort it natively and rarity tools
# already compute it, so a name would only be a second vocabulary for
# something collectors read at a glance.
#
# Counted AFTER Weather is appended, so an animated token scores the trait it
# actually carries, and placed last because it describes the list.
# Plate Tier is DERIVED -- it restates the Background's scarcity band rather
# than being a trait a token independently carries -- so counting it would add
# a free +1 to every token and move the floor off the five traits every
# composited token actually has (character, background, skin, eyes, mouth).
_NOT_A_TRAIT = {"Trait Count", "Plate Tier"}


def _with_trait_count(meta):
    n = sum(1 for a in meta if a["trait_type"] not in _NOT_A_TRAIT)
    return list(meta) + [{"trait_type": "Trait Count", "value": n}]


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


def expected_arm_name(arm_file):
    return g.trait_name(g.ARMZ, arm_file) if arm_file else None


def expected_footwear_name(wat):
    """Display name for a footwear slot value.

    The gorbhouse case routes through trait_name like every other, rather
    than returning a literal: a hardcoded name here would silently disagree
    with generator.TRAIT_NAMES the moment either side was renamed, and this
    function is what the mint's own consistency check compares against."""
    if not wat:
        return None
    key = "Gorbhouse" if str(wat).lower() == "gorbhouse" else wat
    return g.trait_name(g.WHAT_ARE_THOSEZ, key)


def expected_sticker_name(sticker_file):
    return g.trait_name(g.STICKERZ, sticker_file) if sticker_file else None


def main():
    import random
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4444)
    ap.add_argument("--leg-each", type=int, default=30)
    ap.add_argument("--seed", type=int, default=4444)
    ap.add_argument("--render", action="store_true",
                    help="also render every token PNG to output/mint/images/")
    ap.add_argument("--masks", action="store_true",
                    help="with --render, also write each token's PROTECT "
                         "MASK to output/mint/masks/ for dynamic/sky.py")
    # Solana metadata that is a BUSINESS decision, not a rendering one, so
    # none of it has a default: royalties and payout addresses are the
    # owner's to set. Passing --animation is what turns the dynamic loops
    # from files nobody can find into something a wallet will play -- it
    # also builds properties.files[] and category, which the bare field
    # needs on Solana. See generator.token_metadata().
    ap.add_argument("--animation", default=None, metavar="TEMPLATE",
                    help="animation_url template, '{id}' substituted — "
                         "e.g. '{id}.mp4' or 'ipfs://CID/{id}.mp4'. Applied "
                         "ONLY to the tokens that drew a weather state; the "
                         "other 4,000 are stills and must not claim an "
                         "animation they do not have")
    ap.add_argument("--anim-size", type=int, default=640,
                    help="starfield loop resolution (the STILL is full canvas)")
    ap.add_argument("--anim-ms", type=int, default=70,
                    help="starfield frame duration; 70 is the source GIF's own")
    ap.add_argument("--render-only", default=None, metavar="IDS",
                    help="with --render, composite ONLY these token ids "
                         "(comma-separated). The allocation still runs in "
                         "full, so every token gets its metadata and the ids "
                         "mean the same thing they would in a full mint — "
                         "this only skips the ~2.5s composite for the rest. "
                         "For proof sheets and promos, not for a real mint")
    ap.add_argument("--fresh", action="store_true",
                    help="DELETE any previous mint in output/ first. Required "
                         "to re-mint: a run overwrites only what it produces, "
                         "so without this the folders end up holding two "
                         "different collections mixed together")
    ap.add_argument("--no-weather", action="store_true",
                    help="mint without the animated weather tier at all")
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--royalty-bps", type=int, default=None,
                    help="seller_fee_basis_points, e.g. 500 for 5%%")
    ap.add_argument("--out-dir", default=OUT_DIR,
                    help="where the mint is written (default: output). "
                         "calibrate_rarity.py points this at a scratch dir: "
                         "it builds an allocation per solver step and the "
                         "dirty-tree preflight would otherwise stop it on "
                         "the second one -- and --fresh is not the answer "
                         "there, because it would delete a real mint.")
    args = ap.parse_args()
    random.seed(args.seed)

    # Every mint path hangs off --out-dir, rebound once here so the preflight
    # and the writers below cannot end up pointing at different trees.
    if args.out_dir != OUT_DIR:
        _rebind_out_dir(args.out_dir)

    img_dir = IMG_DIR
    # The protect mask for the dynamic sky pass (dynamic/sky.py): the union
    # of every layer except the background plate, i.e. exactly the pixels a
    # time-of-day or weather grade must never touch.
    #
    # IT HAS TO BE WRITTEN HERE, at mint-build time, because this is the
    # only place the silhouette is known for free. Recovering it from the
    # finished PNG means segmenting the art; recovering it by re-running
    # the pipeline costs a full ~2s composite and all 441MB of traits/ per
    # request, which is why the dynamic layer is a grade over two PNGs and
    # not a re-render. Skip it at mint and the whole feature has no input.
    #
    # It is opt-in because it is not free: the masks run 28-60KB each, so a
    # 4,444 mint adds ~150MB beside the images.
    mask_dir = MASK_DIR
    # The float mask (the corner sticker alone) rides with the protect mask:
    # bake_weather.py needs both to float a sticker on a flood.
    float_dir = FLOAT_DIR
    anim_dir = ANIM_DIR
    clear_dir = CLEAR_DIR

    # ---- a mint NEVER writes into somebody else's output ----
    #
    # Every path here is keyed by token id, so a re-run OVERWRITES what it
    # produces and leaves everything it does not. That is silent and it is
    # wrong in both directions: a smaller --n leaves tokens 3001..4444 from
    # the last run sitting beside the new ones, and any change to the tier
    # allocation (a retired plate, a moved count, this collection's rainbow)
    # leaves the previous run's ANIMATIONS pointing at stills that have been
    # replaced underneath them. The result validates fine file-by-file and
    # is a different collection in every folder.
    #
    # So a dirty tree is fatal unless --fresh says to clear it. It is not
    # the default because deleting a finished 4,444-token render on a typo
    # costs hours, and the whole tree is ~6GB.
    dirty = {d: len(os.listdir(d))
             for d in (img_dir, META_DIR, mask_dir, float_dir,
                       anim_dir, clear_dir)
             if os.path.isdir(d) and os.listdir(d)}
    strays = [p for p in (MANIFEST_PATH, REPORT_PATH) if os.path.exists(p)]
    if dirty or strays:
        if not args.fresh:
            listing = "\n".join(f"    {d}  {n} files"
                                for d, n in sorted(dirty.items()))
            listing += "".join(f"\n    {p}" for p in strays)
            sys.exit(
                f"output/ already holds a previous mint:\n{listing}\n"
                f"  A re-run overwrites what it produces and leaves the rest, "
                f"so the folders would end up holding two different mints.\n"
                f"  Pass --fresh to clear them first, or move output/ aside.")
        for d in dirty:
            shutil.rmtree(d)
        for p in strays:
            os.remove(p)
        print(f"--fresh: cleared {sum(dirty.values())} files from "
              f"{len(dirty)} folders" + (f" and {len(strays)} report files"
                                         if strays else ""))

    os.makedirs(META_DIR, exist_ok=True)
    if args.render:
        os.makedirs(img_dir, exist_ok=True)
        if args.masks:
            os.makedirs(mask_dir, exist_ok=True)
            os.makedirs(float_dir, exist_ok=True)
    elif args.masks:
        sys.exit("--masks needs --render: the mask is a by-product of the "
                 "composite, so there is nothing to write without it")

    render_only = (None if not args.render_only else
                   {int(x) for x in args.render_only.replace(",", " ").split()})

    def render(layers, tid, starfield=False):
        # A subset render for a proof or a promo. Gated HERE rather than at the
        # call sites so it cannot miss one -- the secret rares are rendered
        # from a different branch than the composited tokens.
        if render_only is not None and tid not in render_only:
            return
        # The starfield's rainbow trail leaves the character's own middle, and
        # bodies sit 251px apart vertically across the tier, so its plate is
        # built PER TOKEN rather than read from traits/. Both the still and
        # the loop take the same offset, or the thumbnail and the animation
        # would disagree about where the trail is. This must happen after
        # extract_metadata(): the Background attribute is read off layers[0]'s
        # filename, and the swapped stack carries a temp name.
        plate = None
        dy = 0
        if starfield:
            # Two per-token measurements, in this order. The flat field has
            # no floor in it, so the figure's own frame margins are the
            # whole composition and a body that floats by design (the round
            # CENTERED_CHARS) reads as stuck to the top of the frame with a
            # third of the canvas empty below it. centre_figure lowers the
            # figure onto the field's centre; centre_layers then measures
            # THAT body to put the rainbow on it. Run them the other way
            # round and the trail is drawn for a character that then moves.
            layers, _drop = sfmod.centre_figure(layers, g)
            layers, dy, plate = sfmod.centre_layers(layers, anim_dir, tid, g)
        g.create_image(
            layers, os.path.join(img_dir, f"{tid}.png"),
            mask_path=(os.path.join(mask_dir, f"{tid}.png")
                       if args.masks else None),
            float_mask_path=(os.path.join(float_dir, f"{tid}.png")
                             if args.masks else None))
        # The starfield loop is written HERE, not in a later bake pass, and
        # the reason is that it is the only animated tier whose PLATE moves.
        # bake_weather.py can work from a finished PNG plus its protect mask
        # because a weather state is a grade laid over the token; a moving
        # plate has to go UNDER the grounding shadow and the separation
        # pocket, which exist only while the layer stack does. 10 tokens x 12
        # frames is 120 composites, which is why this is affordable here and
        # would not have been for the 444 weather tokens.
        if starfield and args.animation:
            frames = sfmod.loop_layers(layers, anim_dir, tid, g,
                                       size=args.anim_size, dy=dy)
            if write_mp4(frames, os.path.join(anim_dir, f"{tid}.mp4"),
                         1000.0 / args.anim_ms) is None:
                sys.exit("no ffmpeg — pip install imageio-ffmpeg")
        if plate is not None:
            os.remove(plate)

    bg_dir = os.path.join(g.TRAITS_DIR, g.BACKGROUNDZ)
    legs = sorted(f for f in os.listdir(bg_dir)
                  if f.endswith(".png") and g.is_legendary_bg(f))
    leg_total = len(legs) * args.leg_each
    if leg_total > args.n:
        sys.exit(f"{len(legs)} legendaries x {args.leg_each} = {leg_total} "
                 f"exceeds n={args.n}")

    # 1/1 secret rares: one standalone token each, never composited.
    # The tier holds the two guest-artist pieces -- Radbro Webring and Duhnut
    # Candy Man -- at one token apiece: 1 of 4444 = 0.0225 %, ten times rarer
    # than the Starfield. The 23 assets of the original tier stay retired in
    # traits/secret_rarez_retired; dropping one back in would renumber the
    # set, because secret_rare_number() indexes sorted filenames.
    #
    # Nothing else here is conditional on the tier, and a missing directory is
    # still valid -- it simply empties it.
    sr_dir = os.path.join(g.TRAITS_DIR, g.SECRET_RAREZ)
    secrets = sorted(f for f in os.listdir(sr_dir)
                     if f.endswith(".png") and g.is_secret_rare(f)) \
        if os.path.isdir(sr_dir) else []

    # measure each legendary plate + each character body for the camo check
    leg_stats = {f: plate_stats(os.path.join(bg_dir, f)) for f in legs}
    char_stats = {n: plate_stats(os.path.join(g.TRAITS_DIR, g.CHARACTERZ, f))
                  for n, f in char_table().items()}

    def camo(char, leg):
        c = char_stats.get(char)
        return c is not None and at_risk(c["L"], c["S"], c["hue"], leg_stats[leg])

    N = args.n
    forced_bg   = [None] * N    # legendary filename or None
    forced_arm  = [None] * N    # armz filename or None (None == no arm)
    forced_wat  = [None] * N    # footwear base / "gorbhouse" or None
    forced_stk  = [None] * N    # sticker filename or None
    forced_char = [None] * N    # base character name or None

    forced_wx   = [None] * N    # weather state name or None
    forced_sr   = [None] * N    # secret-rare filename or None
    all_slots = list(range(N))

    # 0) secret rares -> one fixed slot each; excluded from every other pool so
    #    they mint as pure standalone 1/1s.
    sr_slots = random.sample(all_slots, len(secrets))
    for s, srf in zip(sr_slots, secrets):
        forced_sr[s] = srf
    sr_set = set(sr_slots)
    avail = [s for s in all_slots if s not in sr_set]   # composable slots

    # 1) legendary backgrounds -> 50 each
    leg_slots = random.sample(avail, leg_total)
    leg_picks = [leg for leg in legs for _ in range(args.leg_each)]
    random.shuffle(leg_picks)
    for s, leg in zip(leg_slots, leg_picks):
        forced_bg[s] = leg
    is_leg = set(leg_slots)

    # 1a) the starfield -> NON-legendary slots, on an eligible character.
    #     Allocated before everything else that competes for a slot so the
    #     ultra-rare tier is never the thing that gets squeezed out.
    star_free = [s for s in avail if s not in is_leg]
    random.shuffle(star_free)
    if STARFIELD_COUNT > len(star_free):
        sys.exit(f"STARFIELD_COUNT {STARFIELD_COUNT} exceeds the "
                 f"{len(star_free)} non-legendary slots available")
    star_slots = star_free[:STARFIELD_COUNT]
    for s in star_slots:
        forced_bg[s] = g.STARFIELD_BG
    is_star = set(star_slots)

    # 1b) rare characters -> exact counts, and they MAY land on a legendary or
    #     starfield slot. They used to be barred from both, which was a
    #     workaround rather than a decision: those slots re-roll the character
    #     when it camouflages against the plate (or is off STARFIELD_CHARS),
    #     and a re-roll cannot change a FORCED character, so the loop below
    #     would spin out its 4000 attempts and die.
    #
    #     The cost of that workaround was invisible and large: 14 of the 27
    #     characters -- every pinned one, including all four chase bodies --
    #     could NEVER appear on the best backgrounds in the collection. A
    #     Gold Waffle on Legendary Simplex was not rare, it was impossible.
    #
    #     The fix is to check the pairing HERE, where the character is being
    #     placed, instead of leaving it to a re-roll that cannot act. A pinned
    #     character takes a rare-plate slot only when that exact pairing is
    #     already legal, so the main loop never has to re-roll it.
    def char_fits_slot(cname, slot):
        leg = forced_bg[slot]
        if slot in is_leg and camo(cname, leg):
            return False
        if slot in is_star and not g.starfield_allowed(cname):
            return False
        return True

    char_free = list(avail)
    random.shuffle(char_free)
    char_total = sum(CHARACTER_COUNTS.values())
    if char_total > len(char_free):
        sys.exit(f"CHARACTER_COUNTS total {char_total} exceeds the "
                 f"{len(char_free)} slots available")
    taken = set()
    for cname, cnt in CHARACTER_COUNTS.items():
        placed = 0
        for s in char_free:
            if placed == cnt:
                break
            if s in taken or not char_fits_slot(cname, s):
                continue
            forced_char[s] = cname
            taken.add(s)
            placed += 1
        if placed != cnt:
            sys.exit(f"{cname}: placed {placed} of {cnt} -- not enough slots "
                     f"whose plate it may legally pair with")
    # A pinned character cannot also carry a character-locked signature arm.
    is_rarechar = {s for s in range(N) if forced_char[s] is not None}
    # Footwear is a separate question, and the blanket rule that used to live
    # here got it wrong. Forcing footwear onto a pinned slot is unsatisfiable
    # only when THAT character is footwear-excluded (is_wat_excluded: churro,
    # the gummy bear, the ice creams, the poptarts -- 12 of 27). Excluding
    # every pinned slot instead silently stripped slippers from the pinned
    # characters that can wear them, so tiering a character quietly cost it a
    # trait. Only the genuinely excluded ones are held back now.
    no_wat = {s for s in is_rarechar if g.is_wat_excluded(forced_char[s])}

    # 2) signature arms -> NON-legendary slots (owner-locked, footwear-free)
    nonleg = [s for s in avail if s not in is_leg and s not in is_rarechar]
    random.shuffle(nonleg)
    sig_slots = []
    cur = 0
    for arm, cnt in SIGNATURE_ARMS.items():
        chunk = nonleg[cur:cur + cnt]
        cur += cnt
        for s in chunk:
            forced_arm[s] = arm
        sig_slots.extend(chunk)
    sig_set = set(sig_slots)

    # 3) generic arms -> any composable slot without an arm yet
    free_for_arm = [s for s in avail if forced_arm[s] is None]
    random.shuffle(free_for_arm)
    cur = 0
    for arm, cnt in GENERIC_ARM_COUNTS.items():
        for s in free_for_arm[cur:cur + cnt]:
            forced_arm[s] = arm
        cur += cnt

    # 4) footwear -> non-legendary, non-signature slots (one footwear per token)
    # Eligibility is per FOOTWEAR TYPE, not per slot, which is the part the
    # old blanket rule hid. An unpinned slot can take anything (its character
    # is still free). A pinned slot can take regular slippers only if that
    # character is not footwear-excluded, and can take the gorbhouse only if
    # it is one of the six gorbhouse-eligible characters. Allocating gorbhouse
    # without that second test is unsatisfiable and fails the mint outright.
    def wat_ok(slot, wat):
        c = forced_char[slot]
        if c is None:
            return True
        if g.is_wat_excluded(c):
            return False
        if str(wat).lower() == "gorbhouse":
            return g.gets_gorbhouse_overlay(c)
        return True

    free_for_wat = [s for s in avail if s not in is_leg and s not in sig_set]
    random.shuffle(free_for_wat)
    taken = set()
    # rarest first, so the most constrained type picks from the widest pool
    for wat, cnt in sorted(FOOTWEAR_COUNTS.items(), key=lambda kv: kv[1]):
        pool = [s for s in free_for_wat
                if s not in taken and wat_ok(s, wat)]
        if len(pool) < cnt:
            sys.exit(f"footwear {wat!r}: only {len(pool)} eligible slots "
                     f"for {cnt} tokens")
        for s in pool[:cnt]:
            forced_wat[s] = wat
            taken.add(s)

    # 4b) weather -> exact counts on NON-legendary slots. Secret rares are
    #     standalone art with no plate to weather and no protect mask to
    #     hold the effect off them, so they are out too.
    if not args.no_weather:
        wx_free = [s for s in avail if s not in is_leg and s not in is_star]
        if WEATHER_TOTAL > len(wx_free):
            sys.exit(f"WEATHER_COUNTS total {WEATHER_TOTAL} exceeds the "
                     f"{len(wx_free)} non-legendary slots available")
        random.shuffle(wx_free)
        cur = 0
        for wx, cnt in WEATHER_COUNTS.items():
            for s in wx_free[cur:cur + cnt]:
                forced_wx[s] = wx
            cur += cnt

    # 5) stickers -> any composable slot, spread evenly across every sticker
    sticker_files = g.get_files(g.STICKERZ)
    stk_slots = random.sample(avail, min(STICKER_TOTAL, len(avail)))
    for i, s in enumerate(stk_slots):
        forced_stk[s] = sticker_files[i % len(sticker_files)]

    # ---- compose every token ----
    manifest, seen = {}, set()
    for i in range(N):
        if args.render and i and i % 250 == 0:
            print(f"  composed {i}/{N}…", flush=True)
        # secret rare: standalone 1/1, no other traits, guaranteed unique
        if forced_sr[i] is not None:
            srf = forced_sr[i]
            layers, char = g.secret_rare_combination(srf)
            meta = g.extract_metadata(layers, char)
            t = {k: None for k in TRAIT_KEYS}
            t["character"] = char
            t["bg"] = srf
            t["legendary"] = False
            t["secret_rare"] = srf
            t["attributes"] = meta
            manifest[i + 1] = t
            if args.render:
                render(layers, i + 1)
            continue

        leg = forced_bg[i]
        star = leg == g.STARFIELD_BG
        if star:
            leg = None                 # a capped plate, but not a legendary
        fb  = (g.BACKGROUNDZ, g.STARFIELD_BG) if star else (
            (g.BACKGROUNDZ, leg) if leg is not None else None)
        farm = forced_arm[i] if forced_arm[i] is not None else None
        fwat = forced_wat[i] if forced_wat[i] is not None else None
        fstk = forced_stk[i] if forced_stk[i] is not None else None
        exp_arm = expected_arm_name(farm)
        exp_wat = expected_footwear_name(fwat)
        exp_stk = expected_sticker_name(fstk)

        for _attempt in range(4000):
            layers, char = g.generate_random_combination(
                force_bg=fb,
                force_char=forced_char[i],
                force_arm=farm if farm is not None else None,
                force_wat=fwat if fwat is not None else None,
                force_sticker=fstk if fstk is not None else None,
                exclude_chars=PINNED_CHARS,
            )
            if leg is not None and camo(char, leg):
                continue                           # re-roll camouflaging char
            if star and not g.starfield_allowed(char):
                continue          # re-roll onto a character the plate suits

            meta = g.extract_metadata(layers, char)
            md = {a["trait_type"]: a["value"] for a in meta}
            # forced optional traits must materialize EXACTLY (re-roll until the
            # generator could place them on a compatible character)
            if md.get("Arms")     != exp_arm:  continue
            if md.get("Footwear") != exp_wat:  continue
            if md.get("Sticker")  != exp_stk:  continue

            t = traits_of(layers, char)
            if sig(t) in seen:
                continue
            seen.add(sig(t))
            t["legendary"] = leg is not None
            t["starfield"] = star
            if forced_wx[i] is not None:
                # Appended rather than built by extract_metadata(), because
                # weather is not a LAYER -- it is a grade applied to the
                # finished composite, so there is nothing in the layer
                # stack for that function to read.
                t["weather"] = forced_wx[i]
                meta = list(meta) + [{"trait_type": "Weather",
                                      "value": forced_wx[i].title()}]
            meta = _with_trait_count(meta)
            t["attributes"] = meta
            manifest[i + 1] = t
            if args.render:
                render(layers, i + 1, starfield=star)
            break
        else:
            sys.exit(f"token {i+1}: no unique combo for arm={farm} wat={fwat} "
                     f"stk={fstk} leg={leg}")

    # ---- write OpenSea token metadata + manifest ----
    os.makedirs(META_DIR, exist_ok=True)
    for tid, t in manifest.items():
        name = None
        # external_url points at the GUEST ARTIST's own site, and only on the
        # 2 tokens that have one. It is the one standard metadata field for a
        # link, and no other Sweetardio token uses it, so it credits the artist
        # everywhere the token travels without competing with anything.
        ext = None
        if t.get("secret_rare"):
            name = g.secret_rare_token_name(t["secret_rare"])
            ext = g.secret_rare_artist_url(t["secret_rare"])
        # An animation_url ONLY where there is an animation. A static
        # token that claims one shows a broken player on every surface
        # that believes it. TWO tiers animate: a weather state, and the
        # starfield plate. They are allocated mutually exclusive, so a token
        # never has two loops competing for the one field.
        anim = (args.animation.replace("{id}", str(tid))
                if args.animation and (t.get("weather") or t.get("starfield"))
                else None)
        token = g.token_metadata(
            t["attributes"], token_id=tid, image=f"{tid}.png", name=name,
            animation_url=anim, symbol=args.symbol, external_url=ext,
            seller_fee_basis_points=args.royalty_bps)
        with open(os.path.join(META_DIR, f"{tid}.json"), "w") as f:
            json.dump(token, f, indent=2, ensure_ascii=False)
    # compact manifest (drop the embedded attributes to keep it small)
    slim = {}
    for tid, t in manifest.items():
        row = {k: t[k] for k in TRAIT_KEYS + ("legendary",)}
        if t.get("weather"):
            row["weather"] = t["weather"]
        if t.get("starfield"):
            row["starfield"] = True
        if t.get("secret_rare"):
            row["secret_rare"] = t["secret_rare"]
        slim[tid] = row
    with open(MANIFEST_PATH, "w") as f:
        json.dump(slim, f)

    # ---- report ----
    def dist(key):
        return Counter(t[key] for t in manifest.values())

    out = []
    def p(s=""):
        out.append(s)
        print(s)

    p(f"minted {len(manifest)}/{N} unique tokens (seed {args.seed})\n")

    sr_d = {srf: [tid for tid, t in manifest.items()
                  if t.get("secret_rare") == srf] for srf in secrets}
    if not secrets:
        p("SECRET RARES: none — tier retired to traits/secret_rarez_retired.\n"
          "  Every token is a composited character; restoring the folder\n"
          "  restores the tier, but re-run calibrate_rarity.py afterwards\n"
          "  because it moves the composited-token denominator.\n")
    else:
        p(f"SECRET RARES (1/1 standalone, {len(secrets)} total):")
        for srf in secrets:
            ids = sr_d[srf]
            p(f"  {g.trait_name(g.SECRET_RAREZ, srf):20} x{len(ids):<2} "
              f"-> token {ids[0] if ids else '?'}")
        sr_bad = {srf: len(ids) for srf, ids in sr_d.items() if len(ids) != 1}
        p(f"  -> each exactly once? "
          f"{'YES' if not sr_bad else 'NO ' + str(sr_bad)}\n")

    leg_d = {f: sum(1 for t in manifest.values() if t["bg"] == f) for f in legs}
    bad = {f: c for f, c in leg_d.items() if c != args.leg_each}
    p(f"LEGENDARY BACKGROUNDS (target {args.leg_each} each):")
    for f in legs:
        p(f"  {g.trait_name(g.BACKGROUNDZ, f):28} {leg_d[f]}")
    p(f"  -> all exactly {args.leg_each}? {'YES' if not bad else 'NO ' + str(bad)}")
    p(f"  legendary tokens: {sum(leg_d.values())} "
      f"({100*sum(leg_d.values())/N:.1f}%)\n")

    char_d = dist("character")
    if CHARACTER_COUNTS:
        cbad = {c: char_d.get(c, 0) for c, want in CHARACTER_COUNTS.items()
                if char_d.get(c, 0) != want}
        p("RARE CHARACTERS (pinned to exact counts):")
        for c, want in CHARACTER_COUNTS.items():
            p(f"  {g.trait_name(g.CHARACTERZ, c):28} {char_d.get(c, 0)}  "
              f"(target {want})")
        p(f"  -> all exact? {'YES' if not cbad else 'NO ' + str(cbad)}\n")
    # composited tokens only: secret rares are standalone and carry no character
    cast = set(char_table())
    unpinned = {c: n for c, n in char_d.items()
                if c in cast and c not in CHARACTER_COUNTS}
    if unpinned:
        lo, hi = min(unpinned.values()), max(unpinned.values())
        p(f"OTHER CHARACTERS ({len(unpinned)} sharing the rest, "
          f"{lo}-{hi} each)\n")

    wx_d = Counter(t.get("weather") for t in manifest.values()
                   if t.get("weather"))
    if WEATHER_COUNTS and not args.no_weather:
        wbad = {w: wx_d.get(w, 0) for w, want in WEATHER_COUNTS.items()
                if wx_d.get(w, 0) != want}
        total_wx = sum(wx_d.values())
        p(f"WEATHER (animated, {total_wx}/{N} = {100*total_wx/N:.1f}% of "
          f"the supply):")
        for w, want in WEATHER_COUNTS.items():
            c = wx_d.get(w, 0)
            p(f"  {w.title():22} {c:4}  {100*c/N:5.2f}%  (target {want})")
        p(f"  -> all exact? {'YES' if not wbad else 'NO ' + str(wbad)}")
        leg_wx = sum(1 for t in manifest.values()
                     if t.get("weather") and t["legendary"])
        p(f"  on legendary plates: {leg_wx} (must be 0 — weather hides the "
          f"plate that made them rare)\n")
        if leg_wx:
            wbad["legendary_overlap"] = leg_wx

    arm_d = dist("arm")
    armed = sum(c for a, c in arm_d.items() if a is not None)
    p(f"ARMS (armed {armed}/{N} = {100*armed/N:.1f}%, "
      f"empty-handed {100*(N-armed)/N:.1f}%):")
    for a, c in sorted(arm_d.items(), key=lambda kv: (kv[0] is None, kv[1])):
        if a is None:
            continue
        p(f"  {g.trait_name(g.ARMZ, a):22} {c:4}  {100*c/N:5.2f}%")
    p("")

    fw_names = Counter(a["value"] for t in manifest.values()
                       for a in t["attributes"] if a["trait_type"] == "Footwear")
    shod = sum(fw_names.values())
    p(f"FOOTWEAR (worn {shod}/{N} = {100*shod/N:.1f}%):")
    for name, c in fw_names.most_common():
        p(f"  {name:22} {c:4}  {100*c/N:5.2f}%")
    p("")

    stk_names = Counter(a["value"] for t in manifest.values()
                        for a in t["attributes"] if a["trait_type"] == "Sticker")
    stk_total = sum(stk_names.values())
    p(f"STICKERS (present {stk_total}/{N} = {100*stk_total/N:.1f}%, "
      f"{len(stk_names)} distinct)\n")

    p("SKINS:")
    skin_names = Counter(a["value"] for t in manifest.values()
                         for a in t["attributes"] if a["trait_type"] == "Skin")
    for s, c in skin_names.most_common():
        p(f"  {s:18} {c:5}  {100*c/N:5.2f}%")

    # quality: no camouflage, no eye<->bg clash
    cw, ew = g.load_char_blocklist(), g.load_eyez_blocklist()
    camo_v = sum(1 for t in manifest.values()
                 if not t["legendary"] and t["bg"] in cw.get(t["character"], []))
    camo_v += sum(1 for t in manifest.values()
                  if t["legendary"] and camo(t["character"], t["bg"]))
    eye_v = sum(1 for t in manifest.values()
                if t["eye"] in ew.get(t["bg"], []))
    p(f"\nquality: camouflage={camo_v}  eye-clash={eye_v}  "
      f"unique={len(seen)}/{N}  distinct_chars={len(dist('character'))}")

    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(out) + "\n")
    p("\nwrote output/mint_manifest.json")
    p("wrote output/mint/metadata/<id>.json  (OpenSea token metadata)")
    p("wrote output/mint/rarity_report.txt")


if __name__ == "__main__":
    main()
