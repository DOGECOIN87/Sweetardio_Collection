# Handover — Sweetardio Collection

Branch: **`claude/handover-md-continuation-djmyoq`** (all work goes here; do not
open a PR unless asked).

Read `CLAUDE.md` first — it holds the lighting convention, the canvas rule, the
face-size rule, the z-order rule and the name-resolution rule, all of which
constrain everything below.

**Environment note:** a fresh container has no `pillow`, `numpy` or `scipy`.
`pip install pillow numpy scipy` before running anything in `asset_assessment/`.

---

## 1. What this session changed

Four things, in order. All are committed and all the checks below pass.

### 1a. No skin draws over a character

*"I no longer want any of the skins placed over the character"*, confirmed as
*"yes I want all character ls to render after skins."*

`body_after_skin()` returns **True unconditionally**. `SKIN_ON_TOP_CHARS`
(churro) and `BODY_OVER_SKIN_CHARS` (gummy bears, nutty bar) are gone — no
per-character z-order exceptions remain, and the `before_skinz_` /
`after_skinz_` prefixes now record only how the art was authored. Seven
characters flipped: Twinkie, zebra_cake, churro, og_poptart,
cyan_frosted_poptart, sugar_cube, chocolate_frosted_poptart.

### 1b. `waffle` was rendering `gold_waffle`'s body

The character-file lookup ended in a substring match, and "waffle" is a
substring of "gold_waffle" — so the waffle was a duplicate of the gold waffle
wearing the waffle's own placement tables (which leaked a 132×31 hole through
its face), and `after_skinz_waffle.png` was never drawn at all. Body art now
resolves by **exact base-name equality** via `generator.char_base_name()`,
which is also what builds the cast list, so the two cannot disagree. The same
name-stripping had existed in five copies; they all delegate to it now.

### 1c. One katana, one knives, and the locked-arm draw fixed

There were five arm files all named "Katana" in the metadata and two named
"Knives" — one per character family, from when each family was a different
size. `CHAR_SCALE` has since brought the cast to one size, so one of each fits
everyone. Kept `Armz_Katana.png` and `Armz_Knives.png` (the two whose fists
actually touch the narrow bodies); the other five are in `traits/armz_originals/`.

`ARMZ_CHAR_LOCK` is now empty. Separately, the arm draw was
`random.choice(all_arm_files)` over *every* arm with the lock override applied
only when the character had a lock of its own, so a character could pick up
someone else's signature weapon — 56 hits per 600 combos. The draw is filtered
by `armz_allowed` first now.

### 1d. Every face is the same size

Two halves, and both were needed.

**The compositor:** the face assembly — skin ball, eyes, mouth — no longer
carries `CHAR_SCALE`. Only the body scales. Previously a 0.74 ice cream got a
0.74 face: a 217px ball against everyone else's 293px, through a 190px hole
against their 250px.

**The art:** every hole is registered so `file hole × CHAR_SCALE == 250`
rendered. `asset_assessment/normalize_face_hole.py` warps art onto that circle
without moving the body silhouette.

The cast went from **179–260px rendered (a 1.45× spread) to 249–252px**,
roundness 0.99–1.01. That also emptied `FACE_HOLE_BOTTOM_OVERRIDE` — both
entries it held died once the holes were registered rather than worked around.

Rendered all three candidate targets before choosing. Normalising at 250 with
a native-size face was the only one that is uniform *at a size that reads*:
holding the current architecture caps the whole cast at the ice creams' 190px,
which shrinks every other face by about 27%.

### 1e. The Nutty Bar was too tall

1139px against a cast median of 771, aspect 2.33 on the narrowest body in the
set. `CHAR_SCALE` cannot fix that — it is a uniform scale, so every value that
brought the height into line left a narrower plank with a smaller face
(rendered the ladder to confirm). The art was squashed vertically to 0.85
about the ball centre: aspect 2.33 → 1.98, matching the Twinkie, keeping the
width and the full-size face. `CHAR_Y_ADJUST` re-derived −118 → −20.

### 1f. The centred round bodies floated when bare

The seven `CENTERED_CHARS` (cookies, doughnuts, ding dong) skip the standing
drop when they have no footwear and were placed by **body centre** on the
canvas centre. That ties the float to body height, so the SHORTEST bodies hung
highest: ding_dong (639px, the shortest) sat 79px above where the bare
standing cast plants, chocolate_chip_cookie 65px, while the sugar doughnut was
only 20px off. The group also straddled `GROUND_SHADOW`'s 1053 `ground_line`,
so half of it cast a floating drop shadow and half a grounded contact pool.

They are **bottom-aligned onto 1096** now — the standing-bare median — so the
whole cast sits in one 1084-1109 band with a consistent contact shadow.
`verify_placement.py` judges every group on a shared bottom line as a result;
the centre-based rule it used for this group is gone.

### Verification run at handover

| check | result |
|---|---|
| `verify_face_coverage.py` (891 composites) | 0 leaks, all 27 covered on every skin × eye |
| `audit_face_holes.py` | all 27 render 250px, exit 0 |
| `verify_placement.py` | exit 0, 49 cases, 0 flags; centred group all exactly on 1096 |
| `verify_generator_rules.py` | **exit 0** — 0 lock leaks, synthetic lock fires correctly |
| `build_char_compat.py` | rebuilt against the new art |
| `build_mint.py --n 4444 --seed 7` | camouflage=0, eye-clash=0, 4421/4444 unique |
| whole cast rendered | eyeballed, all 27 |

---

## 2. Tooling

New this session:

- **`verify_face_coverage.py`** — composites body + ball for every character ×
  skin × eye and counts transparent pixels *enclosed* by the result. Catches a
  hole too BIG for the ball (background leaking through a face).
- **`audit_face_holes.py`** — checks `file hole × CHAR_SCALE == FACE_HOLE_WIDTH`.
  Catches a hole too SMALL, which leaks nothing and just reads as a shrunken
  head. **You need both; they catch opposite failures.**
- **`normalize_face_hole.py`** — per-angle radial warp that resizes a hole onto
  the cast circle without moving the body's silhouette.
- **`squash_character.py`** — vertical-only scale about the ball centre, for an
  aspect-ratio problem `CHAR_SCALE` cannot touch.

Existing:

- **`audit_edges.py`** — halo, stepped edges, thresholded alpha, ghost colour,
  specks, face-hole wobble across all 123 trait assets.
- **`fix_matte_line.py`** — removes a white outline baked into an edge.
- **`strip_specks.py`** — removes disconnected render debris.
- **`build_nutty_bar.py`** — the regenerated Nutty Bar's extraction, kept
  because it documents the technique.

---

## 3. Remaining backlog from the edge audit

`audit_edges.py` flags 69 of 123. Not all are defects; in priority order:

- **STEPPED (16 assets)** — opaque pixels touching fully-clear ones, i.e. no
  anti-aliasing. Worst: `armz/Arms_Cash.png` 615,
  `what_are_thosez/Gorbhouse_base` 214, `characterz/after_skinz_gold_waffle` 201,
  `characterz/before_skinz_og_gummy_bear` 148. **Look before fixing** — a
  feather changes alpha, which moves `getbbox()`, which can move placement.
- **GHOST (42)** — mostly `what_are_thosez` and `stickerz`, which are never
  resampled, so hygiene rather than a visible defect. Low priority.
- **HALO (23)** — gradient contamination rather than a clipped white line, so
  `fix_matte_line.py` skips them.
  `armz/layer-layer-layer-layer-Military_Brat.png` at +113.8 is the worst.
- **WOBBLE (4)** — was largely a face-hole metric, and every hole is now a
  registered circle, so re-run it before working from the old numbers.

Note the numbers above predate the hole normalisation and the arm retirement.
**Re-run `audit_edges.py` to get a current list.**

---

## 4. The three backlog bugs — all now fixed

1. **Locked arms landed on the wrong characters** (56 hits per 600 combos).
   Fixed in §1c; `verify_generator_rules.py` exits 0.
2. **`gummy_worm` was a dead trait.** Its `TRAIT_NAMES` entry is gone, and the
   arm locked to it — which could therefore never be drawn — became the cast's
   single generic `Armz_Katana.png`.
3. **Footwear never minted.** Not a bug: `--n 400` was running quotas sized for
   4444, and signature-arm slots were excluded from the footwear pool. At
   `--n 4444` footwear mints 533 (12.0%), and `SIGNATURE_ARMS` is now empty.

---

## 5. Standing conventions worth not re-deriving

- **Light comes from the top left.** Cast shadows fall down and to the right.
- **Canvas is 1393 × 1393** for every trait asset; only `backgroundz` may vary.
- **The body always draws over the skin ball.** No per-character exceptions,
  and the filename prefixes do not control it.
- **Character art resolves by exact base name**, never by substring —
  `generator.char_base_name()` is the single definition.
- **One face, one size.** Ball, eyes and mouth do NOT carry `CHAR_SCALE`; only
  the body scales. Every hole is authored so
  `file hole × CHAR_SCALE == FACE_HOLE_WIDTH` (250).
- **The compositor pins the face** at ~(690, 601). Nothing moves to follow a
  body that drifted, so new art is registered by its **face hole**, not its
  bbox — `register_character.py`, then `normalize_face_hole.py`.
- **`FACE_HOLE_BOTTOM_OVERRIDE` is empty and should stay that way.** Growing
  one character's ball is the fallback for art that cannot be re-registered,
  and it costs face size wherever it applies.
- **`CHAR_SCALE` cannot change where the face sits on a body,** and it cannot
  change a body's proportions either — it is a uniform scale. Use
  `squash_character.py` for an aspect-ratio problem.

## 6. Decisions already made — do not reopen

- **All characters render after the skins.** Asked for, implemented, rendered,
  confirmed.
- **All face holes are the same size**, at 250px rendered, with the face
  assembly at native size. Three options were rendered; the user picked this
  one ("I liked opt 1 the best").
- **The ice creams' bodies ship as delivered** at `CHAR_SCALE` 0.74. Note their
  *faces* are no longer scaled with them — that is §1d, not a reopening of the
  body decision.
- **Gummy bears: OG only.** Cyan, pink and purple are retired to
  `characterz_originals/`.
- **Mint choc chip, zaffre and rainbow sherbert are retired.** Cast is 27.
- **The Nutty Bar's hole is not extended downward** — asked for, seen, reversed.
  (Its *body* was squashed in §1e, which is a different change.)

## 7. A note on method

Several metrics in this repo lied convincingly before being corrected, and the
corrections are documented in `asset_assessment/ART_QUALITY_REVIEW.md` under
"Methodology notes — two checks that lied". The pattern repeats: group-median
tests cannot catch a whole group being wrong; limb-luma conflates albedo with
shading; gradient energy rewards sharpening halos; `SOFT` tracks smooth
subjects; nearest-neighbour zoom fabricates aliasing; a raw ghost mean cannot
tell a correct bleed from junk. **Render it and look before reporting a finding
as real** — that step caught every one of them.

Three more from this session, all caught the same way:

- The waffle's face leak was real, but the obvious fix (add a hole override)
  would have papered over a character rendering the wrong art entirely. **Chase
  a finding to its cause before treating the symptom.**
- The first hole-normalisation pass left hairline cracks radiating from every
  hole — a half-pixel discontinuity in the warp field at the cardinal angles,
  invisible in the summary numbers (which said every hole was on target) and
  obvious the moment the art was zoomed. Circular median + box filter on the
  radius field fixed it.
- "Footwear never mints" looked like a bug in the allocator for a whole
  session. It was a tool run below its design size.
