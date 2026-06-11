# Background Pop Studies

Adaptive, measurement-driven grading of the 34 active background plates in
`traits/backgroundz/` so the dessert characters own the colour contrast.
Output: `traits/backgroundz_pop/` (gitignored — ~95 MB of regenerable
full-res PNGs; regenerate with one command below). Originals are never
modified. Every operation is a deterministic, reversible tone/colour
transform — nothing generated or repainted.

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

## Results

- Plate family converges: mean L 13–144 → 33–136 (std 33→24), mean S
  0.00–0.93 → 0.06–0.67 (std 0.24→0.16), temp −84…+50 → −68…+32.
- Cast-wide stress test (`asset_assessment/verify_separation.py`, 49 cast
  entries × 34 plates): weak-separation pairings **37 → 15**, remaining ones
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
python3 background_pop_studies/grade.py            # 34 plates -> traits/backgroundz_pop/ + log
python3 background_pop_studies/make_proofs.py --final    # proof pairs + 3x3 grid
python3 background_pop_studies/make_proofs.py --verify   # single-tone worst cases
python3 asset_assessment/analyze.py                # re-measure everything
python3 asset_assessment/verify_separation.py      # cast-wide separation check
```

`grade.py --only <substr>...` grades a subset; `--src/--dst/--log` override
paths. Everything is deterministic — same inputs, same bytes out.
