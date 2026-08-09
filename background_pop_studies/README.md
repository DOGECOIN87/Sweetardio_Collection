# Background Pop Studies

Adaptive, measurement-driven grading of the Sweetardio background plates so
the dessert characters own the colour contrast.

Layout: **`traits/backgroundz/` holds the 34 GRADED plates** the generator
uses (ungraded sources preserved in `traits/backgroundz_originals/`), and
**`traits/backgrounds_pop/` holds the 4 graded Legendary plates** (sources
in `traits/backgrounds_pop_originals/`). Originals are never modified —
every operation is a deterministic, reversible tone/colour transform,
nothing generated or repainted; regrade anytime with the commands below.

## Why this direction (measured, not assumed)

Phase 1 (`asset_assessment/ASSESSMENT.md`, `analyze.py`, `analyze_split.py`):

- Character bodies measure **warm** (mean R−B **+62.3**), **saturated**
  (mean HSV S **0.629**), mid-bright (darkest body L 54.2 brownie, brightest
  L 206.4 marshmallow). 80 % of saturation-weighted body mass sits in hue
  0–60°.
- The vertical-split study showed cone-style characters are dual-tone: warm
  cones (temp +96) under scoop tops that carry the brand palette (cyan
  sherbert top = 58 % Fluorescent-Cyan match; zaffre top violet-band;
  rainbow/pink tops cerise/pink-band). Most of the cast is single-tone; the
  keep-out below is the **union** of every band any character occupies,
  because any character can land on any plate.
- The plates were scattered: L 13–144, S 0.00–0.93, temp −84…+50, edge
  density 5–34; 12 warm plates sat inside the bodies' own hue band.

Therefore the stage is **cool / desaturated / mid-key**, keeping only the
muted slate-navy corridor (~210–265°, Oxford Blue brand territory) plus
neutrals, while characters keep red-orange, cyan, and violet–cerise–pink.

## The engine (`grade.py`)

All parameters are continuous functions of each plate's measured
L / S / busyness (edge density + L std) / temperature — no per-plate
hand-tuning. Per-plate values: `ULTIMATE_GRADE_LOG.md`.

| step | transform | adapts how |
|---|---|---|
| 1 | mid-key power curve toward L\* = 130/255 (midpoint of darkest/brightest body), luma-ratio applied (hue-safe) | exponent `p = clamp((ln L*/ln L)^0.55, 0.55, 1.30)` |
| 2 | gentle smoothstep S-curve on luma | blend `c = max(0.05, 0.32·(1−0.5·contrast)·(1−0.5·busy))` |
| 3 | desaturate toward stage S 0.30 + keep-out squeeze in character bands (warm 0–75°, cyan 172–202°, pink/violet 270–345°, feathered) | global factor `clamp((0.30/S)^0.75, 0.45, 1)`; band squeeze 0.15–0.18 |
| 4 | cool split-tone: shadows → slate-navy `(0.07,0.13,0.27)`, highlights → pale cyan `(0.82,0.90,0.98)` | amount `smoothstep((temp+60)/105)`: warmest plates get max (0.16 sh / 0.10 hl), already-cool plates ≈ 0 |
| 5 | depth blur + local-contrast reduction | gate `busy = smoothstep((edge−11)/9)`; blur ≤ min_side/200 px, detail cut ≤ 0.35 — only ~6 busy plates |
| 6 | navy-tinted vignette + slight bloom | vignette `0.10 + 0.08·smoothstep(L)`; bloom 0.10 |

Special cases (automatic): `Whitehouse_Lawn_Overlay.png` is 1 %-opaque →
tone ops only, no spatial ops; alpha channels are passed through untouched;
the one JPG source is written as PNG.

## Phase 3 — the two gaps grading alone could not close

**1. Twelve plates had never been graded.** `traits/backgroundz` had drifted to
69 plates while the logs covered 50, and a pixel diff against
`backgroundz_originals` showed 14 of the unlogged 19 were graded (just missing
log rows) — but **12 had no original preserved at all**, which is also why they
had never been regraded: they were the only copy. They measured as the sharpest
plates in the set (edge 16–24 against a graded family topping out near 16), and
they looked it: the Liberty coin, the sheet of hundreds and the gravestones
rendered at full contrast with the character sitting flat on top of them.

They are now copied into `traits/backgroundz_originals/` **first** (so the
operation is reversible like every other plate) and then graded with `--only`,
logged to `PHASE3_GRADE_LOG.md`. The approved 50 were not touched — see the
non-determinism note at the end of `ULTIMATE_GRADE_LOG.md`.

**2. A plate can only be graded as a whole; the pocket the character stands in
is a composite-time problem.** Grading does not know where the body will land,
so a plate that is quiet at the frame and busy dead-centre still competes with
the body in front of it. `generator.SUBJECT_SEPARATION` adds a silhouette-driven
pass in `create_image()` (see `_subject_separation`), between the character
build and the grounding shadow:

- a **wide** recession field — the silhouette blurred to 170px and gained so it
  is at full strength on the silhouette's edge — inside which the plate is
  defocused, desaturated and dimmed;
- a **tight** occlusion band hugging the silhouette, offset down and right
  because the key light comes from the top left (`CLAUDE.md`).

Its strength is **adaptive**, measured per token on the annulus of plate the
character does not cover, because a fixed amplitude is wrong in both
directions — rendered as a ladder, `Toasted` still lost to its own marshmallows
at the setting that already smudged `Celestial` into a grey cloud.

The competition metric is a **band-pass**, `|blur(8) − blur(40)|`. The first
metric tried was plain gradient energy at 4px, which ranked `Celestial` the
7th busiest plate in the collection because it was reading the plate's film
grain — grain is not what the eye compares a doughnut against. Band-passed,
`Celestial` drops to 2.6 (second quietest, and the pass correctly leaves it
alone) while `Toasted` rises to 17.4. Ramp: off at 2.5, full at 14.0.

The background overlays in `BG_OVERLAY_PAIRS` are composited *after* the
character and are deliberately untouched — they are foreground, not stage.
Cost is +0.16s per token (1.15s → 1.31s). Set `SUBJECT_SEPARATION = None` to
disable.

## Results

- Plate family converges: mean L 13–144 → 33–136 (std 33→24), mean S
  0.00–0.93 → 0.06–0.67 (std 0.24→0.16), temp −84…+50 → −68…+32.
- Cast-wide stress test (`asset_assessment/verify_separation.py`, 49 cast
  entries × every plate): weak-separation pairings **73 → 15** across the full
  69-plate set after Phase 3 (was 37 → 15 over the 34 plates graded at the
  time). Remaining ones
  are borderline dark-pixel HSV artifacts dominated by the documented gummy
  worm tradeoff (its body lives in the stage corridor; saturation contrast
  carries it — see `samples/verify_Sweetardio_115_1.png`).
- Proofs in `samples/`: `final_*` Original-vs-Graded side-by-sides with real
  composited characters (darkest / brightest / busiest / warmest plates +
  the two palette-collision cases), `verify_*` single-tone worst cases,
  `final_cohesion_3x3.png` cohesion grid.

## Regenerate

```bash
pip install pillow numpy
python3 background_pop_studies/grade.py            # backgroundz_originals -> backgroundz + log
python3 background_pop_studies/grade.py --src traits/backgrounds_pop_originals \
        --dst traits/backgrounds_pop --log background_pop_studies/LEGENDARY_GRADE_LOG.md
python3 background_pop_studies/make_proofs.py --final    # proof pairs + 3x3 grid
python3 background_pop_studies/make_proofs.py --verify   # single-tone worst cases
python3 asset_assessment/analyze.py                # re-measure everything
python3 asset_assessment/verify_separation.py      # cast-wide separation check
```

`grade.py --only <substr>...` grades a subset; `--src/--dst/--log` override
paths. Everything is deterministic — same inputs, same bytes out.

**Note:** `generator.py` reads `traits/backgroundz` (graded; falls back to
`traits/backgroundz_originals` with a warning if the folder is ever empty). Eye↔background pairing is governed by `traits/eyez_compat.json`
(anti-clash, built by `asset_assessment/build_eyez_compat.py`); delete the
file or rebuild with `--mode match` to change the rule. Curated showcase:
`python3 background_pop_studies/make_showcase.py` → `showcase/`.
