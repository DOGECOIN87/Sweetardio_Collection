# Handover — Sweetardio Collection

Branch: **`claude/random-100-sheet-vpmwgl`** (all work goes here; do not open a
PR unless asked). Last commit at handover: `c5c3992`.

Read `CLAUDE.md` first — it holds the lighting convention, the canvas rule and
the face rule, all of which constrain everything below.

---

## 1. The immediate task — no skin may draw over a character

**The instruction:** *"we need to properly fix the skins/character face holes so
that they appear correctly. I no longer want any of the skins placed over the
character."*

Today 20 of 27 characters already draw **body over skin** — the ball is
composited first and shows through the body's face hole. **7 still draw skin
over body** and must be flipped:

| character | hole width | median eye ÷ hole after the flip |
|---|---:|---:|
| Twinkie | 259 | 1.08 |
| zebra_cake | 224 | 1.25 |
| churro | 211 | 1.32 |
| og_poptart | 210 | 1.33 |
| cyan_frosted_poptart | 204 | 1.37 |
| sugar_cube | 195 | 1.43 |
| chocolate_frosted_poptart | 178 | **1.57** |

All seven have a real enclosed hole, and the skin ball is ~324px wide, so the
ball covers every one of them. What changes is that the visible face becomes the
**hole** rather than the whole ball, so these faces get smaller — the poptarts
most of all. That is the collection's established look (all 27 characters sit at
eye ÷ hole between 1.04 and 1.57), but it is a visible change and worth showing
the user a render before calling it done.

**Where the switch is:** `generator.py`, `body_after_skin(char_name, fname)`
around line 774. It currently returns False for `SKIN_ON_TOP_CHARS` (churro) and
for any file not named `after_skinz_*`. Making it always return True is the whole
change; `SKIN_ON_TOP_CHARS` then has no users and should go with it, and the
docstring and `BODY_OVER_SKIN_CHARS` comments need rewriting rather than leaving
stale.

**Then check, in this order:**

1. **Ball covers every hole.** Composite character + skin alone and count
   transparent pixels enclosed by the result, for every skin × eye pair. There
   is a worked example of this loop in the session history; the shape is:
   render only the `characterz` and `skinz` layers, then
   `ndimage.binary_fill_holes(m) & ~m`. Anything over ~200px is a real leak,
   not antialiasing. Fix a leak with `FACE_HOLE_BOTTOM_OVERRIDE[<char>]`, which
   grows the ball via `ball_fit`'s `need_h`; note the value is in **pre-CHAR_SCALE
   file space**, not composited canvas space — getting that wrong wasted a cycle
   on the Nutty Bar.
2. `python3 asset_assessment/verify_placement.py` — must exit 0.
3. `python3 asset_assessment/build_char_compat.py` — the visible art changes, so
   the dominant-colour tables must be regenerated or camouflage checks go stale.
4. `python3 asset_assessment/build_mint.py --n 400 --seed 7` — camouflage=0,
   eye-clash=0.
5. Render and **look**: `python3 asset_assessment/render_sample_sheet.py`.

---

## 2. What was just finished (context for the above)

Three new tools, all committed:

- **`asset_assessment/audit_edges.py`** — measures halo, stepped edges,
  thresholded alpha, ghost colour, specks and face-hole wobble across all 123
  trait assets. Run it before and after any asset change.
- **`asset_assessment/fix_matte_line.py`** — removes a white outline baked into
  an anti-aliased edge. Applied to 9 characters (3 poptarts and the zebra cake
  measured **100%** of their fringe at clipped 255; the 5 ice creams 26–31%).
- **`asset_assessment/strip_specks.py`** — removes disconnected render debris.
  Applied to 38 assets.
- **`asset_assessment/build_nutty_bar.py`** — the full extraction for the
  regenerated Nutty Bar, kept because it documents the technique: key the
  checkerboard, take the hole as the union of alpha-0 and enclosed checker, fit
  an ellipse to it, mark the boundary band untrusted, bleed, then feather.

`clean_alpha.py` was also run across every class. The skins matter most there —
`ball_fit` resamples them on **every** token.

---

## 3. Remaining backlog from the audit

`python3 asset_assessment/audit_edges.py` currently flags 69 of 123. Not all are
defects; the ones worth working through, in priority order:

- **STEPPED (16 assets)** — opaque pixels touching fully-clear ones, i.e. no
  anti-aliasing. Worst: `armz/Arms_Cash.png` 615, `what_are_thosez/Gorbhouse_base`
  214, `characterz/after_skinz_gold_waffle` 201,
  `characterz/before_skinz_og_gummy_bear` 148. **Look before fixing** — a
  feather changes alpha, which moves `getbbox()`, which can move placement.
- **GHOST (42)** — mostly `what_are_thosez` and `stickerz`, which are never
  resampled, so this is hygiene rather than a visible defect. Low priority.
- **HALO (23)** — the remaining ones are gradient contamination rather than a
  clipped white line, so `fix_matte_line.py` skips them (its threshold is 20%
  clipped-white fringe). `armz/layer-layer-layer-layer-Military_Brat.png` at
  +113.8 is the worst and should be looked at directly.
- **WOBBLE (4)** — `sugar_cube` 5.1 is the only large one, and it is probably a
  **false positive**: the metric fits an ellipse, and a sugar cube's hole may be
  a rounded square. Verify by eye before touching it.

---

## 4. Two pre-existing bugs, both flagged to the user, neither fixed

Both are the user's call because both change output across the whole collection.

1. **Locked arms land on the wrong characters.** `verify_generator_rules.py`
   **exits 1** and has for a long time: 56 hits per 600 combos. In
   `generate_random_combination()`, `arm = random.choice(all_arm_files)` draws
   from *every* arm including character-locked ones, and the `locked_arms`
   override only fires when the character has a lock of its own. So a glazed
   doughnut can end up holding `Armz_Gummy_Bear_Knives.png`. One-line fix — draw
   from arms allowed for the character — but it reshuffles the arm draw for
   every token in the collection.
2. **`gummy_worm` is a dead trait.** `TRAIT_NAMES` carries it with no art, and
   `Armz_Gummy_worms_katana.png` is locked to it, so that arm can never be
   selected. 28 name entries against 27 character files.

---

## 5. Standing conventions worth not re-deriving

- **Light comes from the top left.** Cast shadows fall down and to the right.
- **Canvas is 1393 × 1393** for every trait asset; only `backgroundz` may vary.
- **The compositor pins the face.** Skin ball, eyes and mouth land at fixed
  coordinates around **(690, 601)**. Nothing moves to follow a body that drifted,
  so new character art is registered by its **face hole**, not its bbox —
  `asset_assessment/register_character.py`, which also scales the art until the
  hole is 248px (the cast median).
- **Eyes overlap the hole rim.** All 27 characters have the median eye (279px)
  wider than their hole. `eye ÷ hole` is fixed by the art and survives every
  transform — `ball_fit` scales only the ball, `CHAR_SCALE` scales body, ball,
  eyes and mouth together. It cannot be corrected in `generator.py`.
- **`CHAR_SCALE` cannot change where the face sits on a body.** It scales about
  a pivot inside the face, so the ratio is unchanged. This came up repeatedly.

## 6. Decisions already made — do not reopen

- **The ice creams ship as delivered.** Face at 0.344 of body height,
  `CHAR_SCALE["ice_cream"] = 0.74`. The measurement and the prompts that would
  change it are kept in `CHARACTERZ_BODY_PROMPTS.md` §4a as reference, marked
  closed.
- **Gummy bears: OG only.** Cyan, pink and purple are retired to
  `characterz_originals/`. Three regenerated candidates were measured and
  rejected; the analysis is in the session history, the prompts in §5a.
- **Mint choc chip, zaffre and rainbow sherbert are retired.** Cast is 27.
- **The Nutty Bar's hole is not extended downward** — the user asked for it,
  saw it, and reversed the decision.

## 7. A note on method

Several metrics in this repo lied convincingly before being corrected, and the
corrections are documented in `asset_assessment/ART_QUALITY_REVIEW.md` under
"Methodology notes — two checks that lied". The pattern repeats: group-median
tests cannot catch a whole group being wrong; limb-luma conflates albedo with
shading; gradient energy rewards sharpening halos; `SOFT` tracks smooth
subjects; nearest-neighbour zoom fabricates aliasing; a raw ghost mean cannot
tell a correct bleed from junk. **Render it and look before reporting a finding
as real** — that step caught every one of them.
