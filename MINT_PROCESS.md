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
pip install pillow
```

Python 3.8+ and the repository checked out. Run all commands **from the repo
root**.

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

> Rendering all 4,444 images takes a while (tens of minutes depending on the
> machine). Drop `--render` if you only want the metadata + report first to
> review rarity, then re-run with `--render` to produce the images.

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
    { "trait_type": "Arms",       "value": "Oatmeal Pie Katana" },
    { "trait_type": "Sticker",    "value": "Crying Tomato" }
  ]
}
```

The `image` field is the bare filename (`<id>.png`). launchmynft.io pairs each
JSON with the matching image by name; if your launchpad needs an `ipfs://CID/`
prefix instead, it is added at upload time — no need to change the files.

**Secret-rare 1/1 tokens** carry a single distinguishing attribute and a
special name, e.g.:

```json
{
  "name": "Sweetardio Collection #343 — Milk Dunk (1 of 1)",
  "description": "...",
  "image": "343.png",
  "attributes": [ { "trait_type": "1 of 1", "value": "Milk Dunk" } ]
}
```

## 4. Rarity model (exact counts)

All counts are hit exactly by pre-allocating token slots before composition.

- **Secret rares (1/1):** the 9 finished artworks in `traits/secret_rarez/`
  are minted **exactly once each** as standalone tokens — never composited with
  any other trait.
- **Legendary backgrounds:** each `Legendary_*` plate appears **exactly 50×**
  (13 × 50 = 650). They never appear via the normal random background pick.
- **Arms (~16% armed, ~84% empty-handed):**
  AK15 / Golden AK **20** (rarest) · Blue/Pink/Cyan Saber **25 each** ·
  Dual Uzis **40** · AR47 **55** · Military Brat **85** · Nerf Blaster **110** ·
  Cash **130** · 6 character-locked signature katanas **32 each**.
- **Footwear (~12%):** Gorbhouse / Cookie Monster / Bunny / Pepe / Shiba.
- **Stickers (~18%):** spread evenly across every sticker asset.

Every composited token is a **unique** trait combination, with no
background↔character camouflage and no eye↔background colour clash.

## 5. Reproducibility & changing the art

- Re-running with the **same seed** regenerates the identical collection.
- If you add/remove/rename trait assets, re-run the build — the allocator reads
  the current `traits/` folders each time.
- Display names for every asset live in `generator.py` → `TRAIT_NAMES`. Edit
  there to change how a trait reads in metadata.

## 6. Quick upload checklist for launchmynft.io

1. Run the command in step 2 (with `--render`).
2. Upload `output/mint/images/` as the **images** folder.
3. Upload `output/mint/metadata/` as the **metadata** folder.
4. Confirm token counts match (4,444 images, 4,444 JSON).
5. Spot-check a few JSONs and the rarity report (`output/mint/rarity_report.txt`).
