# Task: Fix character sizing, placement, eye/skin & arm alignment, and optimize trait pairing

You are continuing work on the **Sweetardio Collection** NFT generator. The
art is composited by `generator.py` onto a **1393×1393** canvas. Read this whole
brief before touching code — the "Face rule" and "What scaling exists today"
sections explain constraints that several of these fixes depend on.

Develop on branch `claude/happy-mendel-9xaj1n`. Commit and push each fix.

---

## How the compositor works (read first)

- **Layer order** (`generate_random_combination`): background → WAT footwear
  base → before-skinz body → **skin ball** → after-skinz body → eyes → mouth →
  arms → WAT overlay → gorbhouse → sticker → bg overlay.
- **Face rule (critical invariant):** the skin ball, eyes and mouth are drawn at
  **fixed canvas positions**. Every character's PNG has its **face hole drawn
  around the ball center ~(690, 601)**. Measured anchors:
  - Skin ball center ≈ **(690, 601)**, ball W×H ≈ 280×255.
  - Eyes center ≈ **(685, 575)** (slightly above ball center), eye W ≈ 286.
  - `ball_fit()` enlarges *only the skin ball* about its own center just enough
    that the (wider) eyes fit inside it — `BALL_FIT_MARGIN = 0.92`.
- **Vertical placement:** `VERTICAL_OFFSET = 150` is added to character-anchored
  layers **only when footwear-less** and the character is not in
  `NO_OFFSET_CHARS`. On top of that, `CHAR_Y_ADJUST[char]` is a per-character
  trim. **Every character-anchored layer (body, skin, eyes, mouth, arms) shares
  the same `dy`**, so their relative alignment is preserved under vertical moves.
- **What scaling exists today:** ONLY the skin ball is scaled (`fscale`/`fcenter`
  via `scale_about`). **Characters and arms composite at their native baked-in
  size** — there is no per-character or per-arm scale factor yet. Any "make it
  bigger" fix must add one (see Issue 1) or re-export the art.

## Test loop

```
python3 asset_assessment/render_batch_sheet.py        # seed 42, 100 renders
# writes /tmp/batch100_sheet.png + /tmp/batch100_strip_{1..4}.png
python3 asset_assessment/audit_placement.py           # measures bottoms, prints CHAR_Y_ADJUST
```
`render_batch_sheet.py` uses the full production pipeline. Same seed = same trait
picks, so you can A/B a change by re-rendering and diffing the same cells.
Inspect the strips (higher-res) to judge alignment.

---

## Issue 1 — Gummy bears are too small (match ice-cream size & placement)

**Measured (sparkle-proof bbox, native art):**

| character        | W    | H    | bottom |
|------------------|------|------|--------|
| cyan_gummy_bear  | 663  | 870  | 1128   |
| pink_gummy_bear  | 653  | 864  | 1123   |
| purple_gummy_bear| 659  | 870  | 1127   |
| ice creams (avg) | ~780 | ~1070| ~1285+ |

Bears are ~82% of ice-cream footprint → they read as small/floaty. Bring them up
to roughly ice-cream scale (~**1.18–1.25×**).

**Constraint:** scaling a character up moves its face hole unless you scale
**about the face-hole / ball center (690, 601)**. If you scale about the bbox
center the eyes will no longer sit in the hole (this is exactly Issue 3).

**Recommended approach:** add an optional per-character scale to the compositor,
mirroring the existing skin-ball mechanism:
- A `CHAR_SCALE = {"gummy_bear": 1.2, ...}` dict (substring match like
  `CHAR_Y_ADJUST`).
- In the character-layer dicts, set `"fscale"` / `"fcenter"=(690,601)` so
  `scale_about` runs. **Apply the identical scale+center to the skin/eyes/mouth
  for that character too**, otherwise the face hole grows but the ball/eyes don't
  and the face breaks. (Simplest: when a character has a CHAR_SCALE, scale the
  body about (690,601), and leave skin/eyes/mouth fixed only if the hole stays
  centered on the ball — verify per character.)
- `og_gummy_bear` art has decorative sparkles that inflate its raw bbox to
  1013×1303 off-center (cx≈860); use the **largest-connected-component**
  measurement from `audit_placement.py`, don't trust the raw bbox.

After scaling, re-measure bottoms and update `CHAR_Y_ADJUST` so the enlarged
bears still land on the intended ground line.

## Issue 2 — Some smaller characters sit too low on the canvas

Smaller/standing characters drop too far when footwear-less. Owners want them to
look planted, not sunk. Use `audit_placement.py` to measure each character's
standing bottom and tune `CHAR_Y_ADJUST` (negative = up). Targets already
encoded in that tool: offset-eligible standing bottom → 957 (→1107 with the
+150 drop, inside the approved 1084–1109 band); `NO_OFFSET_CHARS` → 1111.
Cross-check against `BG_CHAR_EXTRA_Y` (background-specific extra drop) so you
don't double-count. Re-render seed 42 and confirm the small characters in the
strips sit on/near the ground band.

## Issue 3 — Eyes don't line up on top of the skin ball

Symptom: for some characters/skins the eyes float off the skin ball. Because
eyes and ball are at fixed anchors, misalignment means **that character's face
hole is not centered on (690, 601)**, or a specific skin ball's center drifts
(measured skin centers range cy 597–604; eyes cy ≈ 575).

To fix:
- Run a measurement pass: for each character PNG, find the face-hole center
  (enclosed transparent region nearest (690,601)); `audit_placement.py` already
  locates this and **flags holes that drift > 40px** (`HOLE_TOL`). Start with the
  flagged ones.
- Preferred fix is to **re-center the offending art's hole** on (690,601). If you
  cannot edit art, add a per-character face-anchor nudge that shifts the
  skin+eyes+mouth together to the hole center for that character (must move all
  three identically to preserve the eye-in-ball relationship).
- Verify eye width vs scaled ball: `ball_fit` should already guarantee the ball
  is ≥ eyes/0.92; confirm no character ends up with eyes wider than its ball.

## Issue 4 — Arms misalign on larger vs smaller characters

Arms composite at native size with the character's shared `dy`, so a single arm
PNG sits at one fixed height regardless of how tall the character is. On tall
characters (ice cream) vs short ones (bears) the same arms attach at the wrong
spot. Once Issue 1 changes bear scale, this gets worse unless arms track it.

To fix:
- If you add `CHAR_SCALE` (Issue 1), **scale the arm layer by the same factor
  about the same center** so the arms grow with the body.
- Add a per-character (or per-character-class) **arm vertical anchor** so arms
  attach at the body's hand line. Measure the intended hand Y per character class
  (bears vs ice creams vs standing) and offset the arm layer's `dy` accordingly —
  but keep it separate from the face `dy` so you don't move the eyes.
- Check the locked arms specifically (katanas/knives) on their characters
  (twinkie, gummy_bear, gummy_worm, ice_cream, marshmallow, oatmeal_cream_pie,
  chocolate_chip_cookie) plus generic arms on a tall vs short character.

## Issue 5 — Only pair the most visually appealing combinations

Optimize the generator so random output favors on-palette, attractive combos
rather than any-with-any. Build this as **data-driven compatibility tables**, the
same pattern already used by `traits/eyez_compat.json` (loaded via
`load_eyez_blocklist()`), so it's tunable without code edits. Suggested scope:
- **Color-palette harmony:** define the collection palette, then weight or block
  skin×background, eyes×background, sticker×background pairings that clash. A
  `asset_assessment/build_*_compat.py` builder (mirroring `build_eyez_compat.py`)
  that measures dominant colors and emits a JSON blocklist/weight map is the
  right shape.
- **Weighted selection:** extend the existing `random.choices` weighting (already
  used for skins) to other categories so rare/ugly combos are down-weighted, not
  hard-banned, preserving variety.
- **Keep existing rules intact:** WAT footwear exclusivity, gorbhouse exclusivity
  (no double footwear), `ARMZ_CHAR_LOCK`, `NO_OFFSET_CHARS`, `BG_OVERLAY_PAIRS`.
- Document any new JSON in a builder script header and regenerate it there, so
  the rules are reproducible, not hand-edited.

---

## Guardrails

- Don't break the **face rule**: skin/eyes/mouth share placement; any scale or
  nudge to one of them must apply identically to the others for that character.
- Re-run `render_batch_sheet.py` (seed 42) after **every** change and eyeball the
  strips before committing. Use `audit_placement.py` for numbers, not guesses.
- Preserve reproducibility: keep `sorted()` on file lists and seeded `random`.
- Commit each fix separately with a clear message; push to
  `claude/happy-mendel-9xaj1n`. Do **not** open a PR unless asked.
