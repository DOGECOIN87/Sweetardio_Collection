# Sweetardio Collection — 4444 Mint Process

This document describes how to generate the complete, drop-ready 4,444-token
collection (images + metadata) for uploading to **launchmynft.io** (or any
ERC-721 / inscriptions launchpad that takes an images folder + a metadata
folder).

The build is **fully deterministic**: the same `--seed` always produces the
exact same 4,444 tokens, so you can regenerate the entire collection on your
own machine and get byte-identical results.

## 1. Requirements

```bash
pip install pillow numpy
```

Python 3.8+ and the repository checked out. Run all commands **from the repo
root**. `numpy` is not optional: `build_mint.py` imports `verify_separation`,
which is numpy-based, so the build fails at import without it. The wider
`asset_assessment/` toolset also wants `scipy`.

## 2. Generate the collection

```bash
python3 asset_assessment/build_mint.py --n 4444 --leg-each 50 --seed 4444 --render
```

This writes everything under `output/` (which is git-ignored — it is a
regenerated artifact, not committed):

| Path | Contents |
|------|----------|
| `output/mint/images/<id>.png`    | 4,444 token images, `1.png` … `4444.png` (1393×1393) |
| `output/mint/metadata/<id>.json` | 4,444 OpenSea-format metadata files, `1.json` … `4444.json` |
| `output/mint_manifest.json`      | compact trait manifest (one row per token) |
| `output/mint/rarity_report.txt`  | full rarity distribution report |

> Rendering is serial and costs roughly **1.5 s and 2.3 MB per token** — about
> **2 hours and 10 GB** for the full 4,444 on a 4-core container. Check the
> free space before starting. Drop `--render` if you only want the metadata +
> report first to review rarity (~20 s), then re-run with `--render` to produce
> the images; the allocation is identical either way, since the render rides
> the same seeded RNG stream.

## 3. Metadata format (launchmynft.io)

Each `<id>.json` is a standard token object:

```json
{
  "name": "Sweetardio Collection #1",
  "description": "Sweetardio Collection — 4,444 hand-crafted sweet degens. ...",
  "image": "1.png",
  "attributes": [
    { "trait_type": "Character",  "value": "Oatmeal Cream Pie" },
    { "trait_type": "Background", "value": "Bubble Trouble" },
    { "trait_type": "Skin",       "value": "Black" },
    { "trait_type": "Eyes",       "value": "Cyborg" },
    { "trait_type": "Mouth",      "value": "Fang" },
    { "trait_type": "Footwear",   "value": "Bunny Slippers" },
    { "trait_type": "Arms",       "value": "Katana" },
    { "trait_type": "Sticker",    "value": "Golden Ticket" }
  ]
}
```

Five trait types are on **every** token — Character, Background, Skin, Eyes,
Mouth. The other three are present only when the token has them, and an absent
trait is **omitted** rather than written as "None":

| trait type | tokens carrying it |
|---|---:|
| Sticker  | 4222 (95.0%) |
| Arms     | 707 (15.9%) |
| Footwear | 533 (12.0%) |

The `image` field is the bare filename (`<id>.png`). launchmynft.io pairs each
JSON with the matching image by name; if your launchpad needs an `ipfs://CID/`
prefix instead, it is added at upload time — no need to change the files.

There is **no secret-rare tier**. Its 23 artworks are retired to
`traits/secret_rarez_retired/`, so every one of the 4,444 tokens is a
composited character and no token carries a `Secret Rarez` attribute. Moving
the folder back to `traits/secret_rarez/` restores the tier, but re-run
`calibrate_rarity.py` afterwards — standalone 1/1s change the composited-token
denominator the draw gains are fitted against.

## 4. Rarity model

The model has **two halves**, and which half a trait belongs to is decided by
whether it is always present.

**Optional traits** — arms, footwear, stickers — plus the legendary plates and
the pinned characters are **slot-allocated to exact counts**: the allocator
picks the token slots up front and composition fills them, so the numbers below
are hit exactly, not approached. Their counts live in the `optional` block of
`traits/rarity_weights.json`, which is the single source of truth —
`generator.py` derives its per-token roll rates from the same numbers, so an
ad-hoc render samples the same collection the mint produces.

**Always-present traits** — eyes, mouths, backgrounds — cannot be slot-allocated,
because they have to compose with the compat blocklists. They are drawn by
weight and *calibrated*: `traits/rarity_weights.json` holds a `target` share
and a solved `gain` per asset, because an asset barred from part of the pool
comes out rarer than its weight says. See section 4.1.

The shipped, per-asset table for both halves is `catalog/RARITY.md`, generated
from the token metadata itself.

### Exact counts

- **Legendary backgrounds:** each `Legendary_*` plate appears **exactly 50×**
  (4 × 50 = 200). They never appear via the normal random background pick.
- **Arms (707 = 15.9% armed, 84.1% empty-handed):**
  AK15 **20** (rarest) · Blue/Pink/Cyan Saber **25 each** · Dual Uzis **40** ·
  AR47 **55** · Knives **64** · Military Brat **85** · Nerf Blaster **110** ·
  Katana **128** · Cash **130**.
  The katana and knives are **one generic artwork each**, minted across the
  whole cast. They were once six character-locked signature blades at 32 each;
  the counts here preserve what a collector sees, because the metadata only
  ever showed the display name (4 × 32 = 128 "Katana", 2 × 32 = 64 "Knives").
  `SIGNATURE_ARMS` and `generator.ARMZ_CHAR_LOCK` are both empty by design.
- **Footwear (533 = 12.0%):** Shiba **109** · Bunny / Cookie Monster / Pepe
  **108 each** · Gorbhouse **100**.
- **Stickers (4222 = 95.0%):** spread evenly across all 23 sticker assets.
  Stickers are **common** — a bare token is the scarce one.
- **Characters:** 14 of 27 are pinned to exact counts in `CHARACTER_COUNTS`
  (`asset_assessment/build_mint.py`), tiered by how distinctive the body reads:
  4 chase at **60**, 10 uncommon at **130**. The remaining 13 are deliberately
  left unpinned and share the other 2,904 slots (~223 each), because
  legendary-background slots re-roll the character when it camouflages against
  the plate, and a forced character can never satisfy that re-roll. Unpinned
  slots draw from the complement of the pinned set, or a pinned count would be
  only a floor.

  The 13 unpinned land at **181–276**, not a flat 223. That spread is expected:
  the forced footwear and forced arm slots can only be satisfied by characters
  eligible for them, so characters excluded from footwear draw slightly less of
  the remaining supply. Pin a character if you need its count exact.

Every token is a **unique** trait combination, with no background↔character
camouflage and no eye↔background colour clash — the mint report prints
`camouflage=0 eye-clash=0 unique=4444/4444` and those are the numbers to check.

### 4.1 Calibrated traits, and when the gains go stale

The `gain` values in `traits/rarity_weights.json` are **fitted to a specific
(n, seed)** — 4444 / 4444, the same seed section 2 mints with. Re-solve them
with `asset_assessment/calibrate_rarity.py` whenever `--n` or the seed changes,
or whenever **any asset is added or retired**: a changed pool re-randomises
every downstream draw, and a changed blocklist changes the draw directly.

```bash
python3 asset_assessment/calibrate_rarity.py --check     # measure, don't write
python3 asset_assessment/calibrate_rarity.py             # solve + write
python3 asset_assessment/build_rarity_table.py           # refresh catalog/RARITY.md
```

At the mint seed every asset should sit within **±0.6 points** of target, which
is the precision a single seed can resolve — 1σ sampling noise for a 16% trait
at n=4444 is 0.55 points. Do not chase a tighter tolerance; the iteration is
not contractive near the noise floor and will fit noise instead.

## 5. Reproducibility & changing the art

- Re-running with the **same seed** regenerates the identical collection.
- If you add/remove/rename trait assets, re-running the build is **not enough**
  on its own — the allocator reads the current `traits/` folders each time, but
  three things do not follow automatically:
  1. rebuild the compat maps — `build_char_compat.py`, `build_eyez_compat.py`,
     `build_wat_compat.py` (an asset absent from them is never filtered);
  2. re-solve the draw gains — `calibrate_rarity.py` (see 4.1);
  3. regenerate `catalog/RARITY.md` — `build_rarity_table.py`.
- Display names for every asset live in `generator.py` → `TRAIT_NAMES`. Edit
  there to change how a trait reads in metadata, then run
  `verify_trait_names.py`, which fails on a name that no longer resolves.

## 6. Quick upload checklist for launchmynft.io

1. Run `calibrate_rarity.py --check` and confirm nothing exceeds ±0.6.
2. Run the command in step 2 (with `--render`).
3. Confirm the report's last quality line reads
   `camouflage=0  eye-clash=0  unique=4444/4444  distinct_chars=27`.
4. Upload `output/mint/images/` as the **images** folder.
5. Upload `output/mint/metadata/` as the **metadata** folder.
6. Confirm token counts match (4,444 images, 4,444 JSON).
7. Spot-check a few JSONs and the rarity report (`output/mint/rarity_report.txt`).
