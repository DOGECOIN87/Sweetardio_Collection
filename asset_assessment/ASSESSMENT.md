# Sweetardio Asset Assessment — Phase 1

Measured with `asset_assessment/analyze.py` (read-only). Conventions: opaque
pixels only (alpha ≥ 128); luminance L = Rec.709 luma on 0–255; saturation
S = HSV (max−min)/max on 0–1; temperature = mean(R−B) (>0 warm, <0 cool);
pink bias = mean((R+B)/2 − G); busyness = luminance std plus edge density
(mean |∇luma| at 512 px); dominant colours = deterministic seeded 5-means.
Full per-image numbers: `asset_assessment/metrics.csv` / `metrics.json`.

## 1. Inventory

Inventory below is a **current** re-measurement (`analyze.py`); the analysis in
§2–§4 is the original Phase-1 pass and its per-folder figures may differ where
assets have since been added or retired.

| folder | files | role | sizes / modes | mean L | L std | mean S | temp R−B |
|---|---|---|---|---|---|---|---|
| `backgroundz` | 57 | **ACTIVE background plates** (used by `generator.py`), incl. 4 `Legendary_*` | mixed 1393² / 1254² / 1024², RGBA + RGB | 90.5 | 46.7 | 0.325 | −2.5 |
| `backgroundz_originals` | 53 | ungraded sources for `backgroundz` | mixed | 73.6 | 45.9 | 0.469 | −1.8 |
| `backgrounds_pop_originals` | 4 | ungraded sources for the `Legendary_*` plates | 1393² RGBA | 32.9 | 30.2 | 0.506 | −15.6 |
| `characterz` | 33 | **character bodies** (before_/after_skinz) | 1393² RGBA, 23 % opaque | 116.5 | 48.3 | 0.656 | **+58.5** |
| `skinz` | 5 | skin/texture overlays (White, Black, Alien, Gold Foil, Fluorescent Cyan) | 1393² RGBA, 3 % opaque | 118.3 | 30.5 | 0.551 | +25.3 |
| `eyez` | 11 | eyes | 1393² RGBA, 0.6 % opaque | 63.0 | 68.8 | 0.267 | −22.3 |
| `mouthz` | 9 | mouths | 1393² RGBA | 60.7 | 44.6 | 0.166 | +8.6 |
| `armz` | 16 | arms / held items | 1393² RGBA, 5 % opaque | 132.4 | 80.0 | 0.164 | +5.4 |
| `armz_originals` | 3 | ungraded saber sources | 1393² RGBA | 141.1 | 90.2 | 0.416 | −39.2 |
| `saber_parts` | 1 | lightsaber build asset | 1393² RGBA | 99.2 | 66.5 | 0.120 | −6.8 |
| `what_are_thosez` | 11 | footwear base+overlay pairs | 1393² RGBA | 133.5 | 54.6 | 0.376 | +12.3 |
| `stickerz` | 23 | corner stickers | 1343² RGBA, 1 % opaque | 133.6 | 73.4 | 0.295 | +17.5 |
| `secret_rarez` | 26 | 1/1 standalone artworks, never composited | 1393² RGBA | 82.8 | 56.9 | 0.407 | +15.8 |

Layer order (from `generator.py`): backgroundz → footwear base → characterz →
footwear overlay → skinz → eyez → mouthz → armz → stickerz, on a 1393² canvas.
Real character compositing for proofs is therefore feasible.

Two oddballs inside `backgroundz`:
- `Whitehouse_Lawn_Overlay.png` — only **1 % opaque** (it is a foreground
  overlay stored in the plates folder, warm temp +50, edge 34).
- `Sweetardio_114 (29).png` — pure **grayscale** (S = 0.000) with partial alpha.

## 2. What the character bodies actually are (measured, not assumed)

- **Warm.** Mean temp **+62.3**; 24 of 29 bodies are warm. The only cool
  bodies: cyan sherbert (−95), cyan frosted poptart (−40), gummy worm (−51),
  gummy bear (−24).
- **Red-orange hue band.** **80.5 %** of saturation-weighted body mass sits in
  hue 0–60° (chocolate browns, golden doughnut/waffle ambers, pink-red
  sherberts). That is the band the stage must stay out of.
- **Mid-bright, wide range.** Mean L 115.6; darkest real body = brownie bite
  **L 54.2**, brightest = marshmallow **L 206.4**.
- **Saturated.** Mean S **0.629** (colour-bodies typically 0.6–0.9; only
  sugar cube/marshmallow are neutral, S ≈ 0.10–0.16 — those separate by
  luminance, not hue).
- **The 5 brand palette colours are accents, not body mass.** Opaque-pixel
  share within RGB-distance 60 of each palette colour, averaged over bodies:
  Zaffre 0.5 %, Dark Violet 0.5 %, Hollywood Cerise 0.5 %, Fluorescent Cyan
  1.5 % (Oxford Blue "9.6 %" is actually near-black outline/shadow pixels).
  The palette lives in the **eyes** (Cyan/Cerise eyes), **skins**
  (Fluorescent Cyan skin: 37 % of its hue mass in the cyan band), stickers —
  and in the navy plates themselves.

### 2b. Vertical split follow-up (`asset_assessment/analyze_split.py`)

Per-character top-half vs bottom-half of the opaque bounding box, confirming
that whole-image means hide structure in the cone-style characters:

- **Cone-style bottoms (10 ice cream/churro/twinkie files): uniformly warm
  cones** — L 99.9, S 0.81, temp **+95.9**, 87 % of hue mass in red-orange.
- **Cone-style tops (scoops) carry the brand palette**: cyan sherbert top is
  86 % cyan-band / **58 % within Fluorescent-Cyan distance** (temp −192);
  zaffre sherbert top is 100 % violet-band (20 % Dark-Violet match); rainbow
  top matches Cerise (17 %); pink sherbert top is 100 % pink-band; mint top
  is 90 % yellow-green. Other scoops stay warm (vanilla, rocky road,
  neopolitan, churro, twinkie).
- Aggregate scoop-top hue mass: R 27 / O 18 / **C 12 / V 12 / P 15** % —
  so characters occupy the warm band **plus** the cyan (~183°) and
  violet–cerise–pink (~283–345°) accent bands.
- Non-cone bodies are warm top and bottom (temp +63 / +57).

**Consequence:** the stage keep-out cannot be just the 0–60° warm band. The
graded stage also gets an extra saturation squeeze in cyan 172–202° and
pink/violet 276–336°, leaving the stage only the **muted slate-navy corridor
(~210–265°, Oxford Blue territory) plus neutrals** — the one region no
character occupies in mass. (Known tradeoff: the gummy worm body sits in the
240–270° blue band; it still separates by saturation — body S 0.76 vs stage
≤ ~0.30 — and luminance.)

## 3. How varied are the active background plates (n = 34)

| metric | min | p25 | median | p75 | max |
|---|---|---|---|---|---|
| mean L | 13.2 | 43.9 | 59.1 | 88.8 | 144.3 |
| L std | 16.5 | 36.3 | 44.1 | 51.7 | 77.0 |
| mean S | 0.000 | 0.33 | 0.50 | 0.62 | 0.93 |
| temp R−B | −84.0 | −29.4 | +1.2 | +18.9 | +50.2 |
| edge density | 5.2 | 7.0 | 8.9 | 12.6 | 34.2 |

- Already navy-leaning overall: 33 % of saturation-weighted hue mass in
  210–240° (cyan-blue), and 47 % of pixels within distance 60 of Oxford Blue.
- **But**: 12 plates are warm (temp > +5), including dessert-texture macros
  (cookie canyon, Oreo, doughnut shop, golden bedroom) that occupy the
  bodies' exact brown/gold band; 9 plates have S ≥ 0.6, rivalling body
  saturation; brightness is scattered over a 10× range (L 13 → 144).
- Extremes (full plates): darkest `Sweetardio_114 (10)` L 13.2 · brightest
  `Sweetardio_11317` L 144.3 · busiest `Sweetardio_114` edge 18.0 / L std 51.5
  · warmest `Sweetardio_11325` temp +43.5.

## 4. Recommended grading direction (Phase 2 — awaiting confirmation)

Bodies are **warm, saturated, mid-bright** ⇒ per the figure-ground logic the
stage should be **cool, desaturated, mid-key** — which also happens to be the
brand's Oxford-Blue world the navy plates already live in:

1. **Desaturate** every plate toward mean S ≈ **0.30** (≈ half of body 0.63,
   below every colour body), continuous factor with a floor so nothing goes
   fully gray; plus an extra saturation squeeze inside the three
   character-owned hue bands (warm 0–75°, cyan 172–202°, pink/violet
   276–336° — see §2b) so the stage never competes where bodies or their
   palette scoop-tops live.
2. **Mid-key normalization**: equal-headroom target = midpoint(darkest body
   54, brightest body 206) ≈ **L 130**; plates move *partially* toward it via
   a clamped power curve (no clipping), so crushed-dark plates lift and the
   family converges to a mid-dark band while keeping identity.
3. **Cool split-tone** (opposite of the bodies' +62 warm bias): shadows →
   slate-navy (Oxford Blue family), highlights → pale cool cyan. Amount is a
   smoothstep of plate temperature: warmest dessert plates (+30…+50) get the
   strongest cooling, already-blue plates (−50…−84) are barely touched.
4. **Gentle smoothstep S-curve**, strength reduced on plates that are already
   high-contrast/busy (continuous in L std and edge density).
5. **Depth blur + local-contrast reduction only on busy plates**
   (edge density ≳ 11 — about 6 plates), strength continuous.
6. **Cool-navy-tinted vignette + subtle bloom** on every plate for stage
   cohesion.

Everything is a deterministic, parameter-logged tone/colour transform;
originals untouched; output to a separate folder. Scope: the 34 plates in
`traits/backgroundz/` only (the Legendary `backgrounds_pop/` plates are
measured above but excluded unless requested). The legacy `background/`
folder referenced by this pass was pruned in 2026-07; it was never read by
the generator.

**Alternative rejected:** a warm/neutral-dark stage would sit inside the
80 % red-orange body band and is contraindicated by the measurements.

Sample proof (engine run on the darkest, brightest, busiest and warmest
plates, plus the two palette-collision cases — cyan scoop on the bluest
plate, cerise scoop on the magenta plate — with real composited characters):
`background_pop_studies/samples/phase1_*.png`.
