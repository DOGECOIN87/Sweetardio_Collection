# Trait Catalog

Reference contact sheets for every asset trait class in the collection. One
sheet per class, with each asset labeled by filename. Transparent traits are
cropped to their content and shown on a neutral gray; full background plates
are shown whole.

Regenerate after adding/removing assets with
`asset_assessment/render_traitsheet.py <sheet>` (see that file's docstring
for the full list of sheet keys).

| Sheet | Class | Items |
|-------|-------|------:|
| `traitsheet_backgroundz.png` | Backgroundz (plates + overlays) | 66 |
| `traitsheet_backgroundz_all.png` | Backgroundz — all, incl. Legendary | 70 |
| `traitsheet_backgroundz_legendary.png` | Backgroundz — Legendary | 4 |
| `traitsheet_characterz.png` | Characterz | 33 |
| `traitsheet_skinz.png` | Skinz | 3 |
| `traitsheet_eyez.png` | Eyez | 11 |
| `traitsheet_mouthz.png` | Mouthz | 9 |
| `traitsheet_armz.png` | Armz | 16 |
| `traitsheet_what_are_thosez.png` | What_are_thosez (footwear) | 11 |
| `traitsheet_stickerz.png` | Stickerz | 23 |
| `traitsheet_secret_rarez.png` | Secret Rarez (1/1s) | 23 |

## Reference sheets (AI enhancement hand-off)

`skinz_reference_sheet.png`, `eyez_reference_sheet.png` and
`mouthz_reference_sheet.png` are the hand-off sheets for AI face-trait
enhancement: every asset drawn at its **native pixel size** on a common grid, so
the real size differences and proportions survive — unlike the `traitsheet_*`
sheets, which scale each asset to fill its tile. Each cell is labeled with the
asset's true pixel size and its canvas centre.

```bash
python3 asset_assessment/render_ref_sheet.py skinz
python3 asset_assessment/render_ref_sheet.py eyez
python3 asset_assessment/render_ref_sheet.py mouthz
```

Sheets that come out under ~1024px on the long side are scaled up to fill it,
since that is the resolution an image model actually sees; labels always state
true native size.

| Sheet | Class | Items | Shown |
|-------|-------|------:|-------|
| `skinz_reference_sheet.png` | Skins | 3 | 1.03× |
| `eyez_reference_sheet.png` | Eyes | 11 | 1:1 |
| `mouthz_reference_sheet.png` | Mouths | 9 | 1.48× |

See `SKIN_ENHANCE_PROMPTS.md`, `EYEZ_ENHANCE_PROMPTS.md` and
`MOUTHZ_ENHANCE_PROMPTS.md` for the prompts they accompany, and
`asset_assessment/register_trait.py` for putting results back on the canvas.

## Sample batch sheet

`sample_batch_100.png` is an inspection sheet: 100 random tokens straight off
the production pipeline, 10×10 at 700px per cell, each cell captioned with its
index and character. The seed used is stamped in the bottom-right corner —
current sheet is **seed 323037840**.

```bash
python3 asset_assessment/render_sample_sheet.py                   # fresh 100
python3 asset_assessment/render_sample_sheet.py --seed 323037840  # re-render this one
```

The run prints a manifest listing every trait of every cell, so anything that
looks off on the sheet can be traced to the traits behind it. Full-size token
PNGs are written to `output/sample_batch/` (git-ignored).
