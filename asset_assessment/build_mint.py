#!/usr/bin/env python3
"""Deterministic mint allocator: compose exactly N unique tokens with explicit
rarity targets, on top of generator.py's weighted, compat-aware pipeline.

Rarity model (all counts are EXACT, hit by pre-allocating token slots):

  Backgrounds
    * Legendary_* plates (in traits/backgroundz) are 1/1-style rares: each one
      appears EXACTLY --leg-each times (default 50). 13 x 50 = 650.
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
GENERIC_ARM_COUNTS = {
    AK15:                                       20,    # Golden AK (mythic)
    SABERS[0]:                                  25,    # Blue Saber
    SABERS[1]:                                  25,    # Pink Saber
    SABERS[2]:                                  25,    # Cyan Saber
    "Sweetardio_115 (11).png":                  40,    # Dual Uzis
    "layer-layer-layer-layer-AR47.png":         55,    # AR47
    "layer-layer-layer-layer-Military_Brat.png":85,    # Military Brat
    "layer-layer-layer-layer-Nerf_Blaster.png": 110,   # Nerf Blaster
    "Arms_Cash.png":                            130,   # Cash
}
# character-locked signature weapons (only minted onto their owner). The dead
# gummy-worm katana is intentionally excluded (no gummy_worm character exists).
SIGNATURE_ARMS = {
    "Armz_Gummy_Bear_Knives.png":              32,
    "Armz_Katana_for_ice_cream_character.png": 32,
    "Armz_Marshmallow_knives.png":             32,
    "Armz_Oatmeal_Pie_Katana.png":             32,
    "Armz_Twinkie_Katana.png":                 32,
    "Armz_choc_cookie_katana.png":             32,
}

# ---- footwear rarity (base name as returned by wat_base_name, or "gorbhouse")
FOOTWEAR_COUNTS = {
    "gorbhouse":                100,
    "Cookie_Monster_Slippers":  108,
    "layer-Bunny_Slippers":     108,
    "layer-Pepe":               108,
    "layer-Shiba":              109,
}

STICKER_TOTAL = 800   # ~18%, spread evenly across all sticker assets


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
    if not wat:
        return None
    return "Gorbhouse" if str(wat).lower() == "gorbhouse" \
        else g.trait_name(g.WHAT_ARE_THOSEZ, wat)


def expected_sticker_name(sticker_file):
    return g.trait_name(g.STICKERZ, sticker_file) if sticker_file else None


def main():
    import random
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4444)
    ap.add_argument("--leg-each", type=int, default=50)
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

    # 1/1 secret rares: one standalone token each, never composited
    sr_dir = os.path.join(g.TRAITS_DIR, g.SECRET_RAREZ)
    secrets = sorted(f for f in os.listdir(sr_dir)
                     if f.endswith(".png") and g.is_secret_rare(f))

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

    # 2) signature arms -> NON-legendary slots (owner-locked, footwear-free)
    nonleg = [s for s in avail if s not in is_leg]
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
    free_for_wat = [s for s in avail
                    if s not in is_leg and s not in sig_set]
    random.shuffle(free_for_wat)
    cur = 0
    for wat, cnt in FOOTWEAR_COUNTS.items():
        for s in free_for_wat[cur:cur + cnt]:
            forced_wat[s] = wat
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
                g.create_image(layers, os.path.join(img_dir, f"{i + 1}.png"))
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
                force_arm=farm if farm is not None else None,
                force_wat=fwat if fwat is not None else None,
                force_sticker=fstk if fstk is not None else None,
            )
            if leg is not None and camo(char, leg):
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
            t["legendary"] = leg is not None
            t["attributes"] = meta
            manifest[i + 1] = t
            if args.render:
                g.create_image(layers, os.path.join(img_dir, f"{i + 1}.png"))
            break
        else:
            sys.exit(f"token {i+1}: no unique combo for arm={farm} wat={fwat} "
                     f"stk={fstk} leg={leg}")

    # ---- write OpenSea token metadata + manifest ----
    os.makedirs("output/mint/metadata", exist_ok=True)
    for tid, t in manifest.items():
        name = None
        if t.get("secret_rare"):
            name = g.secret_rare_token_name(t["secret_rare"])
        token = g.token_metadata(t["attributes"], token_id=tid,
                                 image=f"{tid}.png", name=name)
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
    p(f"SECRET RARES (1/1 standalone, {len(secrets)} total):")
    for srf in secrets:
        ids = sr_d[srf]
        p(f"  {g.trait_name(g.SECRET_RAREZ, srf):20} x{len(ids):<2} "
          f"-> token {ids[0] if ids else '?'}")
    sr_bad = {srf: len(ids) for srf, ids in sr_d.items() if len(ids) != 1}
    p(f"  -> each exactly once? {'YES' if not sr_bad else 'NO ' + str(sr_bad)}\n")

    leg_d = {f: sum(1 for t in manifest.values() if t["bg"] == f) for f in legs}
    bad = {f: c for f, c in leg_d.items() if c != args.leg_each}
    p(f"LEGENDARY BACKGROUNDS (target {args.leg_each} each):")
    for f in legs:
        p(f"  {g.trait_name(g.BACKGROUNDZ, f):28} {leg_d[f]}")
    p(f"  -> all exactly {args.leg_each}? {'YES' if not bad else 'NO ' + str(bad)}")
    p(f"  legendary tokens: {sum(leg_d.values())} "
      f"({100*sum(leg_d.values())/N:.1f}%)\n")

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
