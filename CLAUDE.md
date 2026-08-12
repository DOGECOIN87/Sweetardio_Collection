# Sweetardio Collection — project notes

## Lighting convention

**The light originates from the TOP LEFT.** This is the collection's fixed key
light and every asset must be lit consistently with it:

- Key light from the **upper left**, roughly 45°.
- Cooler, dimmer fill from the lower right.
- Highlights and catchlights land on the **upper-left** face of a form.
- The terminator and the deepest ambient occlusion fall on the **lower-right**
  and outer rim, with a rim light picking that edge back out.
- Cast shadows therefore fall **down and to the right** of the caster.

Anything generated, re-rendered or hand-authored for this collection — skins,
eyes, mouths, characters, arms, footwear, stickers — follows this. An asset lit
from another direction will not sit with the rest of the cast.

Where this is already encoded:

- `SKIN_ENHANCE_PROMPTS.md`, `EYEZ_ENHANCE_PROMPTS.md`,
  `MOUTHZ_ENHANCE_PROMPTS.md` — every prompt specifies the upper-left key.
- `asset_assessment/shade_cyan_skin.py` — documents the measured convention
  ("top-left light, lower-edge falloff") and the limb-luma ratios that prove it
  across the skin balls.

- `SUBJECT_SEPARATION` in `generator.py` — the occlusion band that separates
  the character from the plate is offset **down and right**, for the same
  reason the cast shadow is.

- `GROUND_SHADOW` in `generator.py` — the cast shadow is offset per mode:
  `drop_dx`/`drop_dy` push the floating characters' shadow down and to the
  right at 45°, while the contact pool keeps `dx: 0` because a pool sits under
  its caster whatever the key light is doing.

## Canvas and face rule

- Canvas is **1393 × 1393**, and **every trait asset must be authored at that
  size**. `_render_layer()` silently resizes anything else, which scales the
  art *and moves its origin* — a 1343 sticker landed 40px off from where its
  file said. All 123 trait assets now conform; only `backgroundz` may vary,
  since a plate is re-fit to the frame by design.
  `asset_assessment/audit_art_quality.py` flags any deviation.
- The skin ball, eyes and mouth composite at **fixed canvas positions**; the
  ball centre is ~(690, 601) and every character's face hole is drawn around
  it. Nothing moves to meet a layer that drifted, so footprints and positions
  must be preserved exactly when an asset is re-authored.
- `ball_fit()` sizes every skin ball from the **widest eye**, so eye width is
  load-bearing across the whole collection.
- **The eyes must overlap the face hole's rim.** The eye whites spill past the
  hole edge onto the body — that overlap is the collection's face style, not an
  accident. With the hole registered at 250px and the median eye at 277px, the
  ratio is ~1.11 for every character.

## One face, one size, for the whole cast

**The face assembly — skin ball, eyes, mouth — is the same size on every
character.** It composites at fixed canvas positions around (690, 601) and
does **not** carry `CHAR_SCALE`. Only the **body** scales.

This is the rule that makes every face read the same. When the assembly did
scale with the body, a 0.74 ice cream got a 0.74 face: a 217px ball against
everyone else's 293px, showing through a 190px hole against their 250px. The
cast ran **179–260px rendered, a 1.45× spread**.

The other half of the rule lives in the **art**: because the body still
carries `CHAR_SCALE`, each hole must be authored so that

    file hole width × CHAR_SCALE == FACE_HOLE_WIDTH (250)

so a 0.74 ice cream needs a 338px hole in its file and an unscaled body needs
250px. `asset_assessment/normalize_face_hole.py` warps existing art onto that
circle without moving the body's silhouette, and
`asset_assessment/audit_face_holes.py` checks it. All 27 now render 249–252px,
roundness 0.99–1.01.

Two consequences worth knowing:

- A hole that is too **small** leaks nothing — it just shows a ring of skin
  ball around the face and reads as a shrunken head. Only `audit_face_holes.py`
  catches that. A hole too **big** leaks the background plate, which is
  `verify_face_coverage.py`'s job. You need both.
- `FACE_HOLE_BOTTOM_OVERRIDE` is now **empty and should stay that way**.
  Growing one character's ball is the wrong lever — it is the fallback for art
  that cannot be re-registered, and it costs face size wherever it applies.
  Both entries it once held (nutty_bar 765, gold_waffle 750) died once their
  holes were registered properly.

New character art is registered by `asset_assessment/register_character.py`,
which scales the art until its hole matches before pinning it to the ball
centre; run `normalize_face_hole.py` afterwards to put the hole exactly on the
cast circle.

## Z-order: the body is always drawn over the skin

**No skin ball is ever painted over a character.** The ball is composited
first and the visible face is whatever shows through the body's face hole —
for every character, with no exceptions. `body_after_skin()` in `generator.py`
returns True unconditionally; the `before_skinz_` / `after_skinz_` filename
prefixes are historical and record only how the art was authored, never how it
is composited.

Two things follow, and both are checked by
`asset_assessment/verify_face_coverage.py`:

- **The ball must reach the hole's rim for every skin × eye pair.** If it
  falls short the gap is neither skin nor body, it is a hole through to the
  background plate — and it appears for only some pairs, because `ball_fit`
  sizes the ball from the widest eye and each ball has its own size and centre.
  The fix is `FACE_HOLE_BOTTOM_OVERRIDE[<char>]`, whose value is in
  **pre-`CHAR_SCALE` file space**, not composited canvas space.
- **Every character therefore needs a real enclosed hole.** All 27 have one.

## The ice cream names describe the art, and did not always

Four of the five ice creams carried the wrong name until 2026-08. Measured by
the dominant hue of the top 45 % of the body (the scoop, above the cone):

| name | art | now |
|---|---|---|
| `cyan_sherbert_ice_cream` | neapolitan stripes (7°) | `neopolitan_ice_cream` |
| `neopolitan_ice_cream` | solid cyan (181°) | `cyan_sherbert_ice_cream` |
| `pink_sherbert_ice_cream` | solid chocolate (16°, V 0.51) | `chocolate_ice_cream` |
| `rocky_road_ice_cream` | solid pink (346°) | `pink_sherbert_ice_cream` |

`rocky_road` is gone as a name: rocky road has marshmallows and nuts in it, and
a plain brown scoop is **chocolate**.

Two things this cost, both worth knowing before renaming anything else here:

- **Per-character values are tuned to the ART, so they move with it.** The four
  were identical everywhere except `CHAR_Y_ADJUST`, where the chocolate body
  measured −18 against the others' −21. That −18 had to follow the body to its
  new name, or the rename silently misplaces two characters by 3px.
- **`char_y_adjust` and `is_wat_excluded` match by SUBSTRING**, so a new name
  can collide with an existing one. `chocolate_ice_cream` sits alongside four
  other `chocolate_*` characters; it was checked in both directions before the
  rename (nothing matched, and `char_y_adjust` takes the longest key anyway).

Renaming also invalidates `char_compat.json` (rebuild it) and therefore the
rarity gains, because a changed blocklist changes the draw — re-run
`calibrate_rarity.py` and regenerate `catalog/RARITY.md`.

## Character art is resolved by exact base name

`char_base_name()` in `generator.py` is the one definition of a character's
name. It builds the cast list *and* maps a name back to its art, so the two
cannot disagree. Never match a character to a file by substring: `waffle` is a
substring of `gold_waffle`, which is exactly how the waffle spent a long time
rendering the gold waffle's body (with its own placement tables applied to it,
leaking a 132×31 hole through its face) while `after_skinz_waffle.png` was
never drawn at all.

## The skin balls are lit spheres, not flat discs

The three skins ship **relit** by `asset_assessment/shade_skin_balls.py`:
a mean-preserving Lambert form ramp from the upper-left key, a broad satin
specular plus a small glossy hotspot, a cool bounce on the lower-right limb
and rim occlusion. Before this they were near-uniform matte discs whose entire
luma gradient lived in the outer ~8 % of the radius, which is why a face read
as a sticker — the eye got no form information anywhere the eyes and mouth
actually sit. Measured in-ball luma span went 0.43–0.66 → 1.09–1.65, and the
BR/TL limb ratio 0.51–0.67 → 0.28–0.37 (the old 0.48–0.65 band recorded in
`shade_cyan_skin.py` described the flat art and is superseded).

Two rules hold it together:

- **Alpha is preserved bit-for-bit; only RGB is touched.** `ball_fit()` sizes
  every ball from the widest eye and each face hole is registered against the
  ball's footprint, so a change to the alpha would move the whole cast's face
  geometry. The tool asserts on this.
- **The form ramp is mean-preserving**, so each skin keeps its identity — the
  median colour of all three moved by dE ≈ 2.4, imperceptible.

Originals live in `traits/skinz_originals/` (a *sibling* of `traits/skinz` —
the generator mints every `.png` in a trait folder, so a backup inside it
would mint as a skin). The tool always relights from the backup, so re-running
it is idempotent rather than compounding the pass on itself; `--restore` puts
the originals back and `--ladder` renders candidates without writing.

**Everything on the face casts onto the ball.** Three configs in
`generator.py`, all riding the generic per-layer shadow, which clips to the
foreground so they land on the ball and body but never the plate, and all
offset down-and-right for the top-left key:

- `EYE_SHADOW` — every eye. Without it the eyes were the last thing on the
  face standing off the ball with nothing under them, and at a face zoom they
  read as stickers, the brow-style assets worst of all.
- `MOUTH_PROP_SHADOW` — the joint and the lollipop, which are 3D props.
- `MOUTH_SHADOW` — the other seven, at **lighter** settings.

That last one corrects an earlier rule here which said flat line-art mouths
should get no shadow because it embosses them. Rendered three ways once the
eyes had shadows, that was half right: at the eyes' strength the thin line
mouths *do* emboss, but with nothing at all they float, and conspicuously so
beside eyes that no longer do. **The distinction is strength, not presence.**

## The eyes are registered, then lit as lenses

**Every eye is authored to one size and one baseline.** `register_eyes.py`
puts all ten on width 277–278 (1.11× the 250px hole), centre x within ±0.5 of
the ball's 690, centre y at −29. Before it they ran width 236–288, cx −7…+25.5,
cy −36.5…−16.5 — which left `Beady` visibly slid across the face, and left
`Googly` (236) and `Clueless` (245) *narrower than the hole*, so they never
overlapped its rim. That overlap is the collection's face style.

**Eye width is load-bearing.** `ball_fit()` sizes the ball from the eye's
opaque width, so registering the widths also collapses `ball_fit` to one value
per skin. That is where "one face, one size" already pointed, but it means
**`verify_face_coverage.py` is the gate** on any eye-width change — a smaller
ball on the widest pairing can stop short of a hole rim.

`shade_eyes.py` then lights them, and the useful idea is that the gloss is
**per eyeball, not per face**. A specular taken from the ball's normal lays one
soft sheen across the whole face and never looks wet; each connected blob is
instead fitted as its own convex lens and given a catchlight on its upper-left.
It deliberately does **not** skip dark pixels — an earlier version guarded gloss
away from near-black art to keep brows matte and thereby killed it on every
pupil and iris, which is exactly where wetness lives.

`LENS_SCALE` sets the strength per asset, because the assets differ in what
they already are: 1.0 for flat cartoon eyes, 0.45 for anime eyes that already
carry a painted catchlight, 0.35 for brows, 0 for `Alien` and `Cyborg`, which
are already rendered as glossy 3D objects.

**Both eye tools preserve alpha bit-for-bit**, for the same reason the skin
tool does. Note the two back up to *different* folders on purpose:
`eyez_originals/` holds the pre-registration art (and the retired `Retardio`),
`eyez_registered/` holds `shade_eyes.py`'s input. Each tool always works from
its own backup so it is idempotent; sharing one would make the shading pass
silently undo the registration.

Retiring an eye means rebuilding `traits/eyez_compat.json`
(`build_eyez_compat.py`), and so does any pass that changes eye colour.

## Face holes: check the rim for a baked matte line

Some character art was cut with a black outline left in the pixels bordering
its face hole. Over the light skin ball it reads as a hard, stepped dark
hairline round the face; over flat green it is unmistakable.
`fix_hole_matte_line.py --report` ranks the cast by it. **All four affected
assets are now fixed** — churro (−59.5), `sugar_cube` (−69.5), `gold_waffle`
(−59.9) and `og_gummy_bear` (−57.7) — and nothing is left above the −40 flag.
Most of the cast always sat within ~10 of its own body, so this was a defect in
four assets, not house style. The residue the report still lists (−39.4
`chocolate_frosted_poptart` down to −23.6 `chocolate_chip_cookie`) is soft
shading around the hole, not a hairline; check it over flat green before
"fixing" anything there.

The repaint band must straddle the boundary — the partly transparent pixels
*inside* the hole carry the line too, and repainting only the outside leaves a
dotted fringe where the solid ring was. Alpha is never touched, which is what
keeps `audit_face_holes.py` and `verify_face_coverage.py` out of it.

`FACE_INSET_SHADOW` in `generator.py` shades the ball where the hole's rim
occludes it, so the face reads as set *into* the recess. It lands exactly on
that rim, so fix the matte line first or the shadow deepens it.

## An armed figure rides 70px higher, as one piece

`ARMED_LIFT` in `generator.py` raises the WHOLE figure — body, skin ball, eyes,
mouth, footwear, and the arm — whenever a weapon is held and that weapon
overhangs the body's base. 18 of the 27 qualify with a rifle; the ones whose
arm already sits inside their own footprint (the ice creams, churro, Nutty Bar,
Twinkie) are untouched.

The reason it is applied to `y_adjust` before any layer is built, rather than
to the arm, is the whole point. **Four earlier attempts moved the arm relative
to the body and all four were reverted**: anchoring it to a fraction of body
height, to a fixed distance above the base, to the cast-median base, and a
one-sided overhang clamp. Every one of them either rode the gun up over the
eyes on the squat bodies — the face is pinned at a fixed canvas position while
bodies are not — or destroyed the sabers' blade-down pose, because a bounding
box cannot tell a weapon that hangs low by design from one that hangs low by
accident.

Moving body and arm together cannot cause either failure, since it changes no
relationship inside the figure. Verified: across 27 characters × 11 arms, every
part moves by exactly the same 70px, and the highest body top is y=132, well
clear of the frame.

`ARM_SCALE_PIVOT (694, 1040)` is a **scaling** pivot, not a hand line — y=1040
falls outside most of the arm art (Cash spans 625–908, the sabers 122–1302). It
cannot be used to anchor position. A real per-arm fix needs a hand marker
authored into the art, not a formula over a bbox.

## Backgrounds are a two-stage problem

The plates are graded as a family by `background_pop_studies/grade.py`
(cool / desaturated / mid-key, out of the characters' hue bands), and every
plate in `traits/backgroundz` must have its ungraded source preserved in
`traits/backgroundz_originals` — **copy it there before you touch it**, or it
can never be regraded. Twelve plates were the only copy of themselves for a
whole phase, which is exactly why they stayed ungraded and razor-sharp.

Grading is global, so it cannot know where the body lands.
`SUBJECT_SEPARATION` in `generator.py` closes that half at composite time,
opening a defocused / desaturated / dimmed pocket in the plate around the
silhouette plus a tight occlusion band on its edge. Its strength is measured
per token from a **band-pass** (`|blur(8) − blur(40)|`) on the ring of plate
the character does not cover — a plain high-pass reads film grain and ranks
smooth plates as busy. Never make it a fixed amplitude: the setting a busy
plate needs turns a quiet one into a grey cloud.

## Verification tools

```bash
python3 asset_assessment/verify_placement.py      # where characters actually land
python3 asset_assessment/verify_face_coverage.py  # does the ball cover every hole
python3 asset_assessment/audit_face_holes.py      # is every hole the cast size
python3 asset_assessment/verify_generator_rules.py # footwear + locked-arm rules
python3 asset_assessment/audit_placement.py       # what CHAR_Y_ADJUST should be
python3 asset_assessment/render_sample_sheet.py   # N random tokens, full pipeline
python3 asset_assessment/register_eyes.py --report        # eye size + baseline
python3 asset_assessment/fix_hole_matte_line.py --report  # dark rings on hole rims
```

`verify_placement.py` exits non-zero if any character is off its group, drifts
horizontally off the face column, or has a face hole away from the ball centre.

`verify_face_coverage.py` exits non-zero if any character × skin × eye leaves
transparent pixels enclosed by body + ball — i.e. background showing through a
face. It is the check that has to pass before any character art, `CHAR_SCALE`
or `FACE_HOLE_BOTTOM_OVERRIDE` change is called done.

`audit_face_holes.py` is its complement: it exits non-zero if any hole renders
off `FACE_HOLE_WIDTH`. Run both — they catch opposite failures.

`verify_generator_rules.py` covers the footwear exclusions and the
character-locked arms. Its lock audit includes a **synthetic** lock, so it
still tests the rule while `ARMZ_CHAR_LOCK` is empty.

The environment needs `pillow`, `numpy` and `scipy` (`pip install pillow numpy
scipy`); a bare container has none of them.
