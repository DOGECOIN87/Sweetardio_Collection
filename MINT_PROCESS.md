# Sweetardio Collection — 4,444 Mint Process

How to generate the complete, drop-ready collection: 4,444 images, 4,444
metadata files, and the 466 animation loops that go with them.

The build is **deterministic**. The same `--seed` over the same `traits/`
produces the same 4,444 tokens, so the collection can be regenerated from a
clean checkout and come out the same.

> **Run this on your own machine, not in a container session.** The full
> build is ~4 hours and ~12 GB (see [§7](#7-what-it-costs)); `output/` is
> git-ignored, so anything produced in an ephemeral session is lost with it.

---

## 1. Requirements

```bash
pip install pillow numpy scipy imageio-ffmpeg
```

Python 3.8+, the repository checked out, and **all of `traits/` present**
(458 MB). Run every command **from the repo root**.

`imageio-ffmpeg` is only needed for `--animation`; without it the mint stops
when it reaches the first animated token rather than silently skipping it.

---

## 2. Clean up the previous mint FIRST

**A mint never writes into another mint's output.** Every path is keyed by
token id, so a re-run overwrites what it produces and leaves everything else
untouched. That is silent, and it is wrong in both directions:

- a smaller `--n` leaves the tail of the last run sitting beside the new one;
- any change to the tier allocation — a retired plate, a moved count, new art
  — leaves the previous run's **animations pointing at stills that have been
  replaced underneath them**.

Every individual file still validates. The folder holds two collections.

`build_mint.py` now refuses to start against a dirty `output/` and tells you
what it found. Clear it deliberately:

```bash
# keep the old run if you might want it — it is not in git
mv output ../sweetardio_output_$(date +%Y%m%d)

# ...or let the mint clear it for you
python3 asset_assessment/build_mint.py --fresh ...
```

`--fresh` deletes `images/`, `metadata/`, `masks/`, `float_masks/`, `anim/`,
`images_clear/`, the manifest and the rarity report. It is never the default:
deleting a finished 12 GB render on a typo is not a recoverable mistake.

**Nothing outside `output/` is a build artifact.** In particular do **not**
clear these — every one of them is an input or a record something still
reads:

| Path | Why it stays |
|---|---|
| `traits/*_originals/`, `*_registered/`, `*_prespeckle/` | the pre-pass backups every relighting/cleaning tool re-derives from; deleting them makes those passes non-idempotent |
| `traits/backgroundz_originals/` | read at mint time by `BACKGROUNDZ_FALLBACK`, and the only ungraded source `grade.py` can regrade from |
| `traits/*_retired/` | retired art, kept so a restore is possible; `backgroundz_retired/` also keeps a plate from silently reappearing at the next regrade |
| `catalog/`, `dynamic/proof/sheet_*.png` | the committed design record |
| `ULTIMATE_GRADE_LOG.md` | the only record of what each plate was graded with — the engine is not bit-identical across numpy/Pillow versions |

Safe to delete anywhere, any time: `__pycache__/`, and the git-ignored
regenerated proofs (`dynamic/proof/token_*.png`, `var_*.png`, `wx_*.png`).

---

## 3. Generate

Two passes, on purpose. The first composes and renders everything; the second
rewrites the 444 weather tokens. Keeping them apart makes the expensive pass
restartable — an interrupted bake costs one token, not the whole mint.

### Pass 1 — compose, render, and write the starfield loops

```bash
python3 asset_assessment/build_mint.py \
    --n 4444 --leg-each 30 --seed 4444 --fresh \
    --render --masks \
    --animation '{id}.mp4' --symbol SWEET --royalty-bps 500
```

| Flag | Why you need it |
|---|---|
| `--render` | without it you get metadata only — useful for reviewing rarity in ~30 s before committing to the 3-hour render |
| `--masks` | writes the protect + float masks. **Pass 2 cannot run without them**, and they are only obtainable here: the silhouette is known for free during the composite and would otherwise have to be segmented back out of a finished PNG |
| `--animation` | writes `animation_url` **and** the Metaplex `properties` block. Without it the 466 animated tokens carry loops that display on no surface at all |
| `--symbol`, `--royalty-bps` | no defaults on purpose — royalties and payout addresses are a business decision, not a rendering one |

The starfield tier's loops are written **here**, not in pass 2, because it is
the only animated tier whose *plate moves*: its frames have to be
re-composited rather than graded over a finished still.

### Pass 2 — bake the weather

```bash
python3 asset_assessment/bake_weather.py
```

Rewrites the still and writes the loop for the 444 tokens that drew a weather
state. It moves the clear render to `output/mint/images_clear/` on first run
and reads from there afterwards, so re-running cannot stack a second flood on
the first.

### What lands where

| Path | Contents |
|---|---|
| `output/mint/images/<id>.png` | 4,444 stills, 1393×1393 |
| `output/mint/metadata/<id>.json` | 4,444 token metadata files |
| `output/mint/anim/<id>.mp4` | 466 loops (444 weather + 22 starfield) |
| `output/mint/masks/`, `float_masks/` | pass-2 input; not uploaded |
| `output/mint/images_clear/` | pre-weather stills; not uploaded |
| `output/mint_manifest.json` | compact trait manifest, one row per token |
| `output/mint/rarity_report.txt` | full distribution report |

---

## 4. Verify before uploading

```bash
python3 asset_assessment/verify_mint.py --expect-images --expect-anim --expect-masks
python3 asset_assessment/verify_media.py --dir output/mint/anim --metadata output/mint/metadata/1.json
```

`verify_mint.py` is the gate on the finished output, and it is the one that
catches a **mispaired** collection — token 3,207's picture beside token
3,207's traits where one of the two came from a different run. It checks:

- ids 1..N, each with exactly one image and one metadata file, **no orphan in
  either folder**;
- every `image` field names the file that is actually there;
- `animation_url` on exactly the animated tokens, pointing at a file that
  exists, with the `properties` block Solana needs;
- attributes agree with the manifest, and `Trait Count` counts the attributes
  beside it;
- every designed count minted exactly — legendary, starfield, weather, arms,
  footwear, secret rares, pinned characters;
- every image opens at the mint canvas (a truncated write is a valid filename).

It does **not** check that a token's picture shows the traits it claims —
that needs a re-render. It proves the bookkeeping, which is the half that
fails silently.

`verify_media.py` proves the MP4s are streams a hardware decoder will take
(profile, level, `yuv420p`, faststart) and that each loop still wraps after
encoding. Neither proves a marketplace *plays* them — only one real token on
Phantom / Magic Eden / Tensor can. What they buy is that when it fails there,
the file and the JSON are not the reason.

The art-side gates are separate and should already be green:

```bash
python3 asset_assessment/verify_placement.py
python3 asset_assessment/verify_face_coverage.py
python3 asset_assessment/audit_face_holes.py
python3 asset_assessment/verify_generator_rules.py
python3 asset_assessment/verify_trait_names.py
python3 dynamic/starfield.py --verify
python3 dynamic/verify_sky.py
```

---

## 5. Metadata format

A composited token:

```json
{
  "name": "Sweetardio Collection #1",
  "symbol": "SWEET",
  "description": "Sweetardio Collection — 4,444 hand-crafted sweet degens. ...",
  "seller_fee_basis_points": 500,
  "image": "1.png",
  "attributes": [
    { "trait_type": "Character",   "value": "Chocolate Chip Cookie" },
    { "trait_type": "Background",  "value": "The Miami Mall Incident" },
    { "trait_type": "Plate Tier",  "value": "Uncommon" },
    { "trait_type": "Skin",        "value": "White" },
    { "trait_type": "Eyes",        "value": "Googly" },
    { "trait_type": "Mouth",       "value": "Diamond Grill" },
    { "trait_type": "Footwear",    "value": "Pepe Slippers" },
    { "trait_type": "Arms",        "value": "Katana" },
    { "trait_type": "Sticker",     "value": "Golden Ticket" },
    { "trait_type": "Trait Count", "value": 9 }
  ]
}
```

`image` is the bare filename; the launchpad pairs JSON to image by name, and
an `ipfs://CID/` prefix is added at upload time.

**An animated token** (weather or starfield) additionally carries:

```json
  "animation_url": "1.mp4",
  "properties": {
    "files": [
      { "uri": "1.png", "type": "image/png" },
      { "uri": "1.mp4", "type": "video/mp4" }
    ],
    "category": "video"
  }
```

`image` stays a **still** even then. Every grid, thumbnail, search result and
notification uses it; animation only ever plays in a detail view.

**The two 1/1 secret rares** compose with nothing, so they carry no trait
slots — one `Secret Rarez` attribute, an `Artist` attribute, and an
`external_url` pointing at that artist's own site:

```json
{
  "name": "Secret Rarez #2 — Radbro Webring",
  "external_url": "...",
  "attributes": [
    { "trait_type": "Secret Rarez", "value": "#2 Radbro Webring" },
    { "trait_type": "Artist",       "value": "Radbro Webring" }
  ]
}
```

Display names for every asset live in `generator.py` → `TRAIT_NAMES`.
`verify_trait_names.py` is the gate on them.

---

## 6. Rarity model (exact counts at n=4444, seed 4444)

Every count below is **hit exactly** by pre-allocating token slots before
composition — they are targets, not outcomes, so a number that comes out
wrong means something is broken rather than unlucky.

**Backgrounds** — 64 plates share the supply on a monotone ladder, every
weighted plate pinned so no tier overlaps the next:

| Tier | Plates | Each | Share |
|---|---:|---:|---|
| Ultra (Starfield) | 1 | 22 | 0.50 % |
| Legendary | 4 | 30 | 0.68 % |
| Scarce | 8 | 41–48 | 0.92–1.08 % |
| Uncommon | 17 | 55–67 | 1.24–1.51 % |
| Standard | 34 | 77–91 | 1.73–2.05 % |

**Secret rares (1/1)** — the two guest-artist pieces, one token each
(0.0225 %), never composited with anything.

**Weather** — 444 (10 %), animated, and mutually exclusive with the
starfield: rain 110 · snow 95 · fog 80 · storm 75 · blizzard 40 · flooded 30
· tornado 14. Kept off legendary plates.

**Arms** — 707 armed (15.9 %): AK15 20 · Pink/Blue/Cyan Saber 25 each · Dual
Uzis 40 · AR47 55 · Knives 64 · Military Brat 85 · Nerf Blaster 110 · Katana
128 · Cash 130.

**Footwear** — 533 worn (12.0 %): Shiba 109 · Pepe 108 · Bunny 108 · Cookie
Monster 108 · Gorbhouse 100.

**Stickers** — 4,222 (95 %); a bare token is the rare case.

**Characters** — four chase at 60 each, ten uncommon at 130, the remaining
thirteen unpinned and sharing the rest (~222 each).

**Trait Count** — 5 to 9, measured at seed 4444: **5** 135 (3.04 %) · **6**
2,892 (65.11 %) · **7** 1,238 (27.87 %) · **8** 170 (3.83 %) · **9** 7
(0.16 %). Both tails are rarer than a legendary plate, and neither was
discoverable before this attribute existed: "carries no arm, no footwear and
no sticker" is an *absence*, and no marketplace can filter on one.

Every composited token is a **unique** trait combination, with no
character↔background camouflage and no eye↔background colour clash.

Counts live in `traits/rarity_weights.json` (arms, footwear, stickers, plate
targets) and in `build_mint.py` (`CHARACTER_COUNTS`, `WEATHER_COUNTS`,
`STARFIELD_COUNT`, `--leg-each`). **Changing any of them re-randomises every
downstream draw**, so the whole collection must be re-rendered — and the
rarity gains must be re-solved with `calibrate_rarity.py`. See CLAUDE.md,
"Re-solving is REQUIRED whenever the allocation moves".

---

## 7. What it costs

Measured on this repo, single-threaded, by rendering a real 166-token slice
and baking all seven weather states from it — not estimated.

| | |
|---|---|
| Metadata only (no `--render`) | **~30 s** |
| Pass 1, 4,444 tokens | **~3 h** at ~2.5 s per composite |
| Starfield loops (22 × 12 frames) | ~11 min, inside pass 1 |
| Pass 2, weather bake (444 tokens) | **~64 min** at 8.7 s per token |
| **Total wall time** | **~4 h** |

| Folder | Per file | Total |
|---|---|---|
| `output/mint/images/` | 2.44 MB | **10.8 GB** |
| `output/mint/images_clear/` | 2.46 MB | 1.1 GB (the 444 pre-weather stills) |
| `output/mint/masks/` + `float_masks/` | 31 KB | 136 MB |
| `output/mint/anim/` | 237 KB | 110 MB (466 loops) |
| `output/mint/metadata/` | ~1 KB | 5 MB |
| **Total** | | **~12.2 GB** |

A PNG's size tracks how busy its plate is — a flat starfield compresses to
~0.8 MB against ~2.9 MB for a heavily graded plate, so the mean moves if the
plate mix ever changes.

Render the metadata first, read `rarity_report.txt`, and only then commit to
the render.

---

## 8. Upload checklist

1. `output/` cleared or moved aside (§2).
2. Pass 1 and pass 2 both finished without error (§3).
3. `verify_mint.py --expect-images --expect-anim --expect-masks` → **OK**.
4. `verify_media.py --dir output/mint/anim` → **OK**.
5. Upload `output/mint/images/` as the images folder — 4,444 PNGs.
6. Upload `output/mint/metadata/` as the metadata folder — 4,444 JSONs.
7. Upload `output/mint/anim/` alongside them — 466 MP4s, named to match the
   `animation_url` values.
8. Do **not** upload `masks/`, `float_masks/` or `images_clear/` — they are
   build inputs.
9. Spot-check one animated token end to end on a real marketplace before
   committing the drop. Nothing offline can prove playback.
