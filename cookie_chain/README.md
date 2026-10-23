# Cookie Chain Edition — build

The 444-token Cookie Chain Edition is built from this repository: the main
collection's compositor (`generator.py`) and figure art (`traits/characterz`,
`skinz`, `eyez`, `mouthz`, `what_are_thosez`, `armz`), plus the edition's own
assets in `cookie_chain/assets/`. The finished images and metadata live in the
`sweetardio-cookie-chain-edition` repository.

```bash
pip install pillow numpy scipy
python3 cookie_chain/prepare_assets.py                 # stickers + plaque
python3 cookie_chain/prepare_footwear.py               # footwear outlines
python3 cookie_chain/build_cookie_chain.py plan        # pool -> score -> select (~50 min)
python3 cookie_chain/build_cookie_chain.py sheet       # 50-token approval sheet
python3 cookie_chain/build_cookie_chain.py render  --out ../sweetardio-cookie-chain-edition
python3 cookie_chain/build_cookie_chain.py validate --out ../sweetardio-cookie-chain-edition
```

`plan.json` is the record of the edition: the exact layer stack of every
token. `sheet` and `render` only read it, so what was approved on the sheet is
what ships. Scratch output (thumbs, pool, sheets) goes to `cookie_chain/work/`.
`plan --reuse` re-selects from the scored pool without
re-rendering it.

## Assets

| folder | what |
|---|---|
| `assets/backgroundz/` | 19 Cookie Chain plates + 5 one-of-one Legendary plates |
| `assets/stickerz/` | 22 die-cut stickers, built by `prepare_assets.py` |
| `assets/sticker_sources/` | the source art they are built from |
| `assets/what_are_thosez/` | the five footwear sets with re-cut outlines, built by `prepare_footwear.py` |
| `assets/armz/` | Cookboy Handheld, Printer |
| `assets/branding/` | the Cookie Chain Edition plaque (built from `plaque_source.png`) |

The main collection's eleven arms are read from `traits/armz`. Nothing here is
written into `traits/`, so the main mint cannot pick any of it up.

## What changed from the previous release

- **Stickers rebuilt as die-cuts.** The old outline was a square max-filter
  grown over the raw alpha, so it traced every defect in it — Out of Order's
  dotted grey halo, Shorts Doggo's ragged fur line, a dark matte ring inside
  the white on Real as a Doughnut and Candy Shop, Cookiebox's ~0.94-alpha
  interior. Now: debris dropped, a solid core with one anti-aliased edge,
  edge colour taken from the art rather than the matte, one Euclidean
  (round-cornered) white border built at 4x, a soft cast shadow down-right
  (the collection's top-left key light), and every sticker sized by die-cut
  AREA so badges, characters and wordmarks carry the same weight. Each output
  is asserted to be one piece.
- **Footwear outlines re-cut** (`prepare_footwear.py`): baked shadows off
  both Cookie Monster files (~52k px each) and the Bunny overlay, the
  chewed Bunny outline and the ragged Pepe / Gorbhouse / Shiba edges
  smoothed at 4x, the 3-4px baked dark or light ring recoloured from inside
  the slipper, and each base trimmed to its overlay so no darker crescent
  peeks out. Sole lines (`alpha > 200`) held within 2px. Edition-only:
  `traits/what_are_thosez` is untouched.
- **Plaque re-cut** with an anti-aliased pill mask fitted to the source's rim;
  the old one was a binary-alpha rounded rectangle that kept a ring of the
  source's glow backdrop at both ends.
- **Figures scaled to the frame.** The whole figure is scaled about the ground
  line by `FIGURE_SCALE` 0.88, with up to a further 7% off the bulkiest bodies
  (`BIG_BODY_SCALE`, from measured rendered area). The bare cast went from
  18.6–28.3% of the canvas (1.52x spread) to 14.4–19.1% (1.33x).
- **Thirteen arms**: the main collection's eleven join Cookboy Handheld and
  Printer.
- **Five one-of-one Legendary plates**: Nightly, Mattrick (the alien plate),
  Shubbi, Tenders, and Opengotchi from the main collection. Simplex is already
  in the edition as "Cookboy Legendary".
- **Edge fix in the compositor path.** `generator.scale_about()` pastes a layer
  with itself as the mask, which squares the alpha of anti-aliased edge
  pixels and darkens them. The edition replaces it (in `cc_common.setup()`)
  with a composite; main-collection renders are unchanged.

## Trait design (exact counts)

| trait | design |
|---|---|
| Character | 4 chase x 6, 10 uncommon x 13, 13 common x 22–23 (the main collection's ladder) |
| Background | 5 one-of-one Legendary, 9 scarce x 16, 3 uncommon x 24, 7 standard x 31–32 |
| Arms | 122 armed: Cookboy Handheld 22, Printer 22, Cash 12, Katana 11, Nerf Blaster 10, Military Brat 9, Knives 8, AR-47 7, Dual Uzis 6, three sabers x 4, AK-15 3 |
| Footwear | 100 shod: Bunny 22, Shiba 22, Pepe 20, Cookie Monster 18, Gorbhouse 18 |
| Sticker | every token, 20–21 each; Nightly Legendary carries Nightly Wallet |
| Skin / Eyes / Mouth | main collection targets, ±15% / ±25% for curation |
| Rarity | Mythic Chase = the 5 one-of-one plates; Legendary Chase 17 / Rare 66 / Uncommon 134 / Core 222 by rank of statistical rarity |

Within those counts the 444 are the highest total-scoring set from the
candidate pool (a 0/1 MILP), scored on the rendered image: colour contrast
across the figure's outline (the worst fifth, and the mean), the face against
its body, how busy the plate is just outside the figure, and any overlap with
the sticker or plaque. No character x plate pairing appears more than twice.
