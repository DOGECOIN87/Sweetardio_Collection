#!/usr/bin/env python3
"""Deterministic mint allocator: compose exactly N unique tokens with explicit
rarity targets, on top of generator.py's weighted, compat-aware pipeline.

Rarity model (all counts are EXACT, hit by pre-allocating token slots):

  Backgrounds
    * Legendary_* plates (in traits/backgroundz) are 1/1-style rares: each one
      appears EXACTLY --leg-each times (default 50). 4 x 50 = 200.
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
  a full trait-distribution report (also -> output/mint/rarity_report.txt)
Reproducible by --seed.

Usage (from repo root):
  python3 asset_assessment/build_mint.py [--n 4444] [--leg-each 50] [--seed 4444]
"""

import argparse
import json
import os
import sys
import time
from collections import Counter

sys.path.insert(0, ".")
sys.path.insert(0, "asset_assessment")
import generator as g
from verify_separation import at_risk, plate_stats   # noqa: E402
from build_char_compat import char_table              # noqa: E402

TRAIT_KEYS = ("character", "bg", "skin", "eye", "mouth", "arm", "wat", "sticker")

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
# satisfy, so the 200 legendary slots have to draw from somewhere.
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


# ---- Artist Series: guest-artist plates on hand-picked characters ----
# These are finished 1/1 artworks, not backdrops, so the pairing is CURATED
# rather than drawn: each plate lists exactly as many characters as it has
# tokens, so every one of its tokens is a different character.
#
# Picked by eye off a 27-character contact sheet rendered on each plate
# (asset_assessment/, see the commit that added this), on the one thing that
# decides whether a character reads in front of a busy illustration: tonal
# contrast against that plate.
#
#   Radbro Webring    is dark, cool teal/purple with a black mass at centre,
#                     so the WARM, light and metallic bodies carry. The cyan
#                     bodies and the dark chocolates sink into it.
#   Duhnut Candy Man  is bright cyan over a cream sticker outline, so it is
#                     the exact inverse: the DARK, saturated bodies read and
#                     the creams and whites wash out against it.
#
# Pinned characters are allowed here and are pre-credited against
# CHARACTER_COUNTS below, so a curated appearance costs the character one of
# its pinned tokens rather than adding a 141st.
ARTIST_CHARS = {
    "Artist_Radbro_Webring.png": [
        "gold_waffle", "Twinkie", "churro", "marshmallow", "sugar_cube",
        "glazed_doughnut", "waffle", "rice_crispy_treat", "sugar_doughnut",
        "og_poptart",
    ],
    "Artist_Duhnut_Candy_Man.png": [
        "chocolate_sandwich_cookie", "ding_dong", "chocolate_doughnut",
        "chocolate_ice_cream", "brownie_bite", "chocolate_frosted_poptart",
        "Nutty_Bar", "oatmeal_cream_pie", "chocolate_chip_cookie", "smores",
    ],
}

# Who actually drew each plate. The piece's TITLE is its display name in
# TRAIT_NAMES; this is the person, which is a different string for one of the
# two and would otherwise appear nowhere a collector can see.
#
# Credit lived only in the games repo (src/content/artistRares.ts) and the
# landing-page placard it feeds. That is the half that can change or go away;
# the token metadata is the half that travels to the launchpad, to wallets and
# to every marketplace that indexes the collection, so the credit belongs in
# both. Emily Cartoons' name in particular appeared in no metadata at all —
# her signature is painted into the art and vanishes at thumbnail size.
#
# Minted with the permission of both artists (confirmed by the owner, 2026-08).
ARTIST_CREDIT = {
    "Artist_Radbro_Webring.png": "Radbro Webring",
    "Artist_Duhnut_Candy_Man.png": "Emily Cartoons",
}

# Artist tokens carry NO arm, footwear or sticker. Each plate is a finished
# artwork with its own subject, title lettering and artist signature; a weapon
# across the lettering or a corner sticker over the signature is the one thing
# that reliably ruins it. The character alone is what the curation is for.
ARTIST_BARE = True


def _with_artist_credit(meta, plate):
    """Insert the Artist attribute directly after Background, so the credit
    reads next to the piece it belongs to rather than at the end of the list.

    Only the 20 Artist Series tokens carry it, which is also why it doubles as
    a rarity signal: a marketplace shows Artist as a trait held by 20 of 4444.
    """
    artist = ARTIST_CREDIT.get(plate)
    if not artist:
        sys.exit(f"{plate}: no ARTIST_CREDIT entry — an Artist Series plate "
                 f"must name the person who drew it")
    out = []
    for a in meta:
        out.append(a)
        if a["trait_type"] == "Background":
            out.append({"trait_type": "Artist", "value": artist})
    return out


def _render_one(job):
    """Composite one token. Module-level so multiprocessing can pickle it.

    Takes (layers, out_path) and consumes NO randomness — that is the property
    that lets the render fan out across processes without changing a pixel of
    the output. Trait selection has already happened, on the single seeded
    stream, by the time a job reaches here.
    """
    layers, out_path = job
    g.create_image(layers, out_path)
    return out_path


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
    ap.add_argument("--leg-each", type=int, default=50)
    ap.add_argument("--artist-each", type=int, default=10,
                    help="tokens per Artist Series plate (exact)")
    ap.add_argument("--format", choices=("webp", "png"), default="webp",
                    help="token image format. webp (default) is ~9x smaller "
                         "than png at visually-lossless quality — a 4444 mint "
                         "is ~1.1 GB instead of ~9.8 GB. png is the lossless "
                         "escape hatch; the build is deterministic either way, "
                         "so the seed is the archival master, not the files.")
    ap.add_argument("--jobs", type=int, default=0,
                    help="render processes (default: all cores). Rendering is "
                         "RNG-free, so this changes speed only, never output.")
    ap.add_argument("--seed", type=int, default=4444)
    ap.add_argument("--render", action="store_true",
                    help="also render every token PNG to output/mint/images/")
    args = ap.parse_args()
    random.seed(args.seed)

    img_dir = "output/mint/images"
    if args.render:
        os.makedirs(img_dir, exist_ok=True)

    bg_dir = os.path.join(g.TRAITS_DIR, g.BACKGROUNDZ)
    legs = sorted(f for f in os.listdir(bg_dir)
                  if f.endswith(".png") and g.is_legendary_bg(f))
    leg_total = len(legs) * args.leg_each
    if leg_total > args.n:
        sys.exit(f"{len(legs)} legendaries x {args.leg_each} = {leg_total} "
                 f"exceeds n={args.n}")

    arts = sorted(f for f in os.listdir(bg_dir)
                  if f.endswith(".png") and g.is_artist_bg(f))
    art_total = len(arts) * args.artist_each
    if leg_total + art_total > args.n:
        sys.exit(f"{len(arts)} artist plates x {args.artist_each} = {art_total} "
                 f"plus {leg_total} legendary exceeds n={args.n}")

    # 1/1 secret rares: one standalone token each, never composited
    # Secret rares are RETIRED: traits/secret_rarez is gone, its 23 assets
    # moved to traits/secret_rarez_retired. Restoring the folder restores the
    # tier -- nothing else here is conditional on them. A missing directory is
    # the normal case now, not an error.
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

    # 1a) Artist Series -> exact quota each, on the curated character list.
    #     Both the plate AND the character are forced, so unlike a legendary
    #     slot there is nothing here to re-roll: the pairing is the point.
    art_picks = []
    for plate in arts:
        chars = ARTIST_CHARS.get(plate)
        if not chars:
            sys.exit(f"{plate}: no ARTIST_CHARS entry — every Artist_ plate "
                     f"needs a curated character list")
        for i in range(args.artist_each):
            art_picks.append((plate, chars[i % len(chars)]))
    art_pool = [s for s in avail if s not in is_leg]
    art_slots = random.sample(art_pool, len(art_picks))
    random.shuffle(art_picks)
    for s, (plate, ch) in zip(art_slots, art_picks):
        forced_bg[s] = plate
        forced_char[s] = ch
    is_art = set(art_slots)

    # 1b) rare characters -> exact counts on NON-legendary slots. Legendary
    #     slots re-roll the character when it camouflages against the plate,
    #     which a forced character could never satisfy, so they are excluded.
    #     Artist slots already carry a forced character and are excluded too,
    #     but any pinned character they used is PRE-CREDITED here so its total
    #     still lands exactly on its CHARACTER_COUNTS target.
    art_credit = Counter(forced_char[s] for s in art_slots)
    char_free = [s for s in avail if s not in is_leg and s not in is_art]
    random.shuffle(char_free)
    char_need = {c: max(0, cnt - art_credit.get(c, 0))
                 for c, cnt in CHARACTER_COUNTS.items()}
    char_total = sum(char_need.values())
    if char_total > len(char_free):
        sys.exit(f"CHARACTER_COUNTS total {char_total} exceeds the "
                 f"{len(char_free)} non-legendary slots available")
    cur = 0
    for cname, cnt in char_need.items():
        for s in char_free[cur:cur + cnt]:
            forced_char[s] = cname
        cur += cnt
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

    # 3) generic arms -> any composable slot without an arm yet.
    #    Artist slots are held back (ARTIST_BARE): a weapon lands across the
    #    plate's title lettering, which is the artist's own signature on the
    #    piece. Arms still hit their exact counts — holding back 20 of 4444
    #    leaves far more free slots than the 707 armed tokens need.
    free_for_arm = [s for s in avail if forced_arm[s] is None
                    and not (ARTIST_BARE and s in is_art)]
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

    free_for_wat = [s for s in avail if s not in is_leg and s not in sig_set
                    and not (ARTIST_BARE and s in is_art)]
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

    # 5) stickers -> any composable slot, spread evenly across every sticker.
    #    Artist slots are held back for the same reason as arms: the corner
    #    sticker sits exactly where these two plates carry their signature.
    stk_pool = [s for s in avail if not (ARTIST_BARE and s in is_art)]
    sticker_files = g.get_files(g.STICKERZ)
    stk_slots = random.sample(stk_pool, min(STICKER_TOTAL, len(stk_pool)))
    for i, s in enumerate(stk_slots):
        forced_stk[s] = sticker_files[i % len(sticker_files)]

    # ---- compose every token ----
    # Layer lists are COLLECTED here and rendered afterwards, possibly in
    # parallel. Trait selection is the only RNG consumer, so keeping it in this
    # one serial loop keeps the stream — and therefore the whole mint — exactly
    # as deterministic as it was when rendering happened inline.
    manifest, seen = {}, set()
    render_jobs = []
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
                render_jobs.append((layers, os.path.join(img_dir, f"{i + 1}.{args.format}")))
            continue

        leg = forced_bg[i]
        fb  = (g.BACKGROUNDZ, leg) if leg is not None else None
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
            # Camouflage re-roll applies to LEGENDARY slots only. An artist
            # slot forces its character as well as its plate, so there is
            # nothing left to re-roll — the pairing was picked by eye, which
            # is a stricter filter than the camo measure anyway. Testing it
            # here would also KeyError, since leg_stats covers only the
            # legendaries.
            if leg is not None and i not in is_art and camo(char, leg):
                continue                           # re-roll camouflaging char

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
            t["legendary"] = leg is not None and i not in is_art
            t["artist"] = i in is_art
            if i in is_art:
                meta = _with_artist_credit(meta, leg)
            t["attributes"] = meta
            manifest[i + 1] = t
            if args.render:
                render_jobs.append((layers, os.path.join(img_dir, f"{i + 1}.{args.format}")))
            break
        else:
            sys.exit(f"token {i+1}: no unique combo for arm={farm} wat={fwat} "
                     f"stk={fstk} leg={leg}")

    # ---- render pass ----
    # create_image() is a pure function of its layer list: it consumes no RNG,
    # so tokens can be composited in any order, in any number of processes,
    # and come out byte-identical. Compositing is ~870 ms of the ~1250 ms per
    # token (big gaussians over a 1393x1393 canvas for the separation pocket
    # and the shadows) with WebP encode the other ~380 ms, and all of it ran on
    # ONE core of four.
    if render_jobs:
        jobs = args.jobs or (os.cpu_count() or 1)
        print(f"rendering {len(render_jobs)} tokens on {jobs} process(es)…",
              flush=True)
        t0 = time.time()
        if jobs > 1:
            import multiprocessing as mp
            with mp.Pool(jobs) as pool:
                for k, _ in enumerate(
                        pool.imap_unordered(_render_one, render_jobs, chunksize=8), 1):
                    if k % 250 == 0:
                        el = time.time() - t0
                        print(f"  rendered {k}/{len(render_jobs)}… "
                              f"({el/k:.2f}s/token, ~{(len(render_jobs)-k)*el/k/60:.0f} min left)",
                              flush=True)
        else:
            for k, job in enumerate(render_jobs, 1):
                _render_one(job)
                if k % 250 == 0:
                    print(f"  rendered {k}/{len(render_jobs)}…", flush=True)
        el = time.time() - t0
        print(f"rendered {len(render_jobs)} tokens in {el/60:.1f} min "
              f"({el/len(render_jobs):.2f}s/token)")

    # ---- write OpenSea token metadata + manifest ----
    os.makedirs("output/mint/metadata", exist_ok=True)
    for tid, t in manifest.items():
        name = None
        if t.get("secret_rare"):
            name = g.secret_rare_token_name(t["secret_rare"])
        token = g.token_metadata(t["attributes"], token_id=tid,
                                 image=f"{tid}.{args.format}", name=name)
        with open(f"output/mint/metadata/{tid}.json", "w") as f:
            json.dump(token, f, indent=2, ensure_ascii=False)
    # compact manifest (drop the embedded attributes to keep it small)
    slim = {}
    for tid, t in manifest.items():
        row = {k: t[k] for k in TRAIT_KEYS + ("legendary",)}
        if t.get("secret_rare"):
            row["secret_rare"] = t["secret_rare"]
        slim[tid] = row
    with open("output/mint_manifest.json", "w") as f:
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

    if arts:
        art_d = {f: sum(1 for t in manifest.values() if t["bg"] == f) for f in arts}
        art_bad = {f: c for f, c in art_d.items() if c != args.artist_each}
        p(f"ARTIST SERIES (target {args.artist_each} each, curated pairings, "
          f"no arm/footwear/sticker):")
        for f in arts:
            pairs = [t["character"] for t in manifest.values() if t["bg"] == f]
            p(f"  {g.trait_name(g.BACKGROUNDZ, f):28} {art_d[f]}")
            for c in sorted(set(pairs)):
                p(f"      {c}")
        p(f"  -> all exactly {args.artist_each}? "
          f"{'YES' if not art_bad else 'NO ' + str(art_bad)}")
        art_extra = [t for t in manifest.values() if t.get("artist")
                     and (t["arm"] or t["wat"] or t["sticker"])]
        p(f"  -> all bare? {'YES' if not art_extra else 'NO (%d)' % len(art_extra)}")
        p(f"  artist tokens: {sum(art_d.values())} "
          f"({100*sum(art_d.values())/N:.1f}%)\n")

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

    with open("output/mint/rarity_report.txt", "w") as f:
        f.write("\n".join(out) + "\n")
    p("\nwrote output/mint_manifest.json")
    p("wrote output/mint/metadata/<id>.json  (OpenSea token metadata)")
    p("wrote output/mint/rarity_report.txt")


if __name__ == "__main__":
    main()
