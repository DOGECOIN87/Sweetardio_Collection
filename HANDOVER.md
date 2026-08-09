# Handover — Sweetardio Collection

Branch: **`claude/handover-md-continuation-djmyoq`** (all work goes here; do not
open a PR unless asked).

Read `CLAUDE.md` first — it holds the lighting convention, the canvas rule, the
face rule, the z-order rule and the name-resolution rule, all of which
constrain everything below.

**Environment note:** a fresh container has no `pillow`, `numpy` or `scipy`.
`pip install pillow numpy scipy` before running anything in `asset_assessment/`.

---

## 1. Done — no skin draws over a character any more

The instruction was: *"we need to properly fix the skins/character face holes so
that they appear correctly. I no longer want any of the skins placed over the
character."* Confirmed again in session: *"yes I want all character ls to render
after skins."*

`body_after_skin()` in `generator.py` now returns **True unconditionally**.
`SKIN_ON_TOP_CHARS` (churro) and `BODY_OVER_SKIN_CHARS` (gummy bears, nutty
bar) are gone — there is no longer any per-character exception, and the
`before_skinz_` / `after_skinz_` filename prefixes now record only how the art
was authored. All 27 characters composite skin-first, body-over.

Seven characters flipped: Twinkie, zebra_cake, churro, og_poptart,
cyan_frosted_poptart, sugar_cube, chocolate_frosted_poptart. Their visible face
shrank from the whole ball to the hole — most on chocolate_frosted_poptart
(eye ÷ hole 1.54). Rendered side by side before/after and it reads as the rest
of the cast does.

**Two bugs fell out of the checks, both fixed:**

1. **`waffle` was rendering `gold_waffle`'s body.** The character-file lookup
   ended in a substring match (`char_name in f and "after_skinz" in f`), and
   "waffle" is a substring of "gold_waffle" — which matched on the *first*
   pattern, so `after_skinz_waffle.png` was never drawn by anything. The waffle
   was effectively a duplicate of the gold waffle wearing the waffle's own
   `CHAR_SCALE` / `CHAR_Y_ADJUST` / `face_hole_bottom`, and the mismatched hole
   override leaked a 132×31 hole through its face on 663px of the White skin ×
   Googly eyes pair. Body art is now resolved by **exact base-name equality**
   through the new `generator.char_base_name()`, which is also what builds the
   cast list, so the two cannot disagree. Every one of the 27 files is now used
   by exactly one character, and none is shared.
2. The same stripping logic existed in **five** copies (generator plus four
   tools). They all delegate to `char_base_name()` now.

That second fix removed the leak at its root, so **no new
`FACE_HOLE_BOTTOM_OVERRIDE` was needed** — the existing gold_waffle 750 /
nutty_bar 765 entries are unchanged.

### Verification run at handover

| check | result |
|---|---|
| `verify_face_coverage.py` (new — 891 composites) | 0 leaks, all 27 covered on every skin × eye |
| `verify_placement.py` | exit 0, 49 placement cases, 0 flags |
| `build_char_compat.py` | rebuilt; output byte-identical (it already read the correct waffle art) |
| `build_mint.py --n 400 --seed 7` | camouflage=0, eye-clash=0 |
| `render_sample_sheet.py` | rendered and eyeballed — faces inset, eyes overlapping the rim, no background through a face |
| `verify_generator_rules.py` | still **exit 1** — the pre-existing locked-arms bug in §4, unchanged. Layer resolution is now 0 failures. |

`asset_assessment/verify_face_coverage.py` is new: it composites body + ball for
every character × skin × eye and counts transparent pixels *enclosed* by the
result (`binary_fill_holes(m) & ~m`). Under ~200px is rim anti-aliasing;
hundreds-to-thousands is a real leak with a bbox you can point at. Run it after
any change to character art, `CHAR_SCALE`, or the hole overrides.

---

## 2. Tooling that exists (context)

- **`asset_assessment/verify_face_coverage.py`** — the coverage check above.
- **`asset_assessment/audit_edges.py`** — halo, stepped edges, thresholded
  alpha, ghost colour, specks, face-hole wobble across all 123 trait assets.
  Run before and after any asset change.
- **`asset_assessment/fix_matte_line.py`** — removes a white outline baked into
  an anti-aliased edge. Applied to 9 characters.
- **`asset_assessment/strip_specks.py`** — removes disconnected render debris.
  Applied to 38 assets.
- **`asset_assessment/build_nutty_bar.py`** — the full extraction for the
  regenerated Nutty Bar, kept because it documents the technique.

`clean_alpha.py` was also run across every class. The skins matter most there —
`ball_fit` resamples them on **every** token.

---

## 3. Remaining backlog from the audit

`python3 asset_assessment/audit_edges.py` flags 69 of 123. Not all are defects;
the ones worth working through, in priority order:

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

## 4. Three pre-existing bugs, all flagged to the user, none fixed

All three are the user's call because each changes output across the whole
collection.

1. **Locked arms land on the wrong characters.** `verify_generator_rules.py`
   **exits 1**: 56 hits per 600 combos. In `generate_random_combination()`,
   `arm = random.choice(all_arm_files)` draws from *every* arm including
   character-locked ones, and the `locked_arms` override only fires when the
   character has a lock of its own. So a glazed doughnut can end up holding
   `Armz_Gummy_Bear_Knives.png`. One-line fix — draw from arms allowed for the
   character — but it reshuffles the arm draw for every token in the collection.
2. **`gummy_worm` is a dead trait.** `TRAIT_NAMES` carries it with no art, and
   `Armz_Gummy_worms_katana.png` is locked to it, so that arm can never be
   selected (0 appearances in 600 combos, confirmed). 28 name entries against
   27 character files.
3. **No token in a mint wears footwear.** `build_mint.py --n 400 --seed 7`
   reports `FOOTWEAR (worn 0/400 = 0.0%)`, and it did so before any of this
   session's changes too — so a whole trait class (11 assets) never ships.
   Worth deciding whether that is the intended rarity or a bug in the mint
   allocator's optional-slot handling.

---

## 5. Standing conventions worth not re-deriving

- **Light comes from the top left.** Cast shadows fall down and to the right.
- **Canvas is 1393 × 1393** for every trait asset; only `backgroundz` may vary.
- **The body always draws over the skin ball.** See `CLAUDE.md`; there are no
  per-character exceptions left, and the filename prefixes do not control it.
- **Character art resolves by exact base name**, never by substring —
  `generator.char_base_name()` is the single definition.
- **The compositor pins the face.** Skin ball, eyes and mouth land at fixed
  coordinates around **(690, 601)**. Nothing moves to follow a body that
  drifted, so new character art is registered by its **face hole**, not its
  bbox — `asset_assessment/register_character.py`, which scales the art until
  the hole is 248px (the cast median; the 27 holes measure 180–261, median 250).
- **Eyes overlap the hole rim.** All 27 characters have the median eye (277px)
  wider than their hole — ratios 1.06 to 1.54, median 1.11. `eye ÷ hole` is
  fixed by the art and survives every transform: `ball_fit` scales only the
  ball, `CHAR_SCALE` scales body, ball, eyes and mouth together. It cannot be
  corrected in `generator.py`.
- **`CHAR_SCALE` cannot change where the face sits on a body.** It scales about
  a pivot inside the face, so the ratio is unchanged. This came up repeatedly.

## 6. Decisions already made — do not reopen

- **All characters render after the skins.** Asked for, implemented, rendered
  and confirmed in session.
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

The waffle bug in §1 is the newest entry in that pattern, from the other
direction: the leak metric was right, but the obvious fix (add a hole override)
would have papered over a character rendering the wrong art entirely. Chase a
finding to its cause before treating the symptom.
