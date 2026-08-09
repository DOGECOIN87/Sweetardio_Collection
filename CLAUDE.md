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

**Mouth props cast onto the skin.** `MOUTH_PROP_SHADOW` in `generator.py`
gives the joint and the lollipop a shadow via the generic per-layer shadow,
which clips to the foreground so it lands on the ball and body but never the
plate. Only those two are listed: the other seven mouths are flat line art
painted onto the face, and a shadow embosses them.

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
`fix_hole_matte_line.py --report` ranks the cast by it. The churro is fixed;
**`sugar_cube` (−69.5), `gold_waffle` (−59.9) and `og_gummy_bear` (−57.7) still
carry it.** Most of the cast sits within ~10 of its own body, so this is a
defect in four assets, not house style.

The repaint band must straddle the boundary — the partly transparent pixels
*inside* the hole carry the line too, and repainting only the outside leaves a
dotted fringe where the solid ring was. Alpha is never touched, which is what
keeps `audit_face_holes.py` and `verify_face_coverage.py` out of it.

`FACE_INSET_SHADOW` in `generator.py` shades the ball where the hole's rim
occludes it, so the face reads as set *into* the recess. It lands exactly on
that rim, so fix the matte line first or the shadow deepens it.

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
