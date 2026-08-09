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
- **The eyes must overlap the face hole's rim.** All 27 characters have the
  median eye (277px) wider than their face hole — ratios 1.06 to 1.54, median
  1.11 — so the eye whites spill past the hole edge onto the body. That overlap
  is the collection's face style, not an accident.

  It is fixed by the **art**, because `eye width ÷ hole width` survives every
  transform downstream: `ball_fit` scales only the ball, and `CHAR_SCALE` scales
  body, ball, eyes and mouth together. A body whose hole comes back wider than
  ~270px cannot be corrected in `generator.py` — the eyes will float inside it
  with a ring of skin ball showing.

  So new character art is registered to a **hole width of 248px** (the cast
  median; the 27 holes measure 180–261, median 250) by
  `asset_assessment/register_character.py`, which scales the art until the hole
  matches before pinning it to the ball centre. Sizing the hole correctly also
  removes any need for a `FACE_HOLE_BOTTOM_OVERRIDE`: a cast-sized hole is one
  the standard ball already covers.

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

## Verification tools

```bash
python3 asset_assessment/verify_placement.py      # where characters actually land
python3 asset_assessment/verify_face_coverage.py  # does the ball cover every hole
python3 asset_assessment/audit_placement.py       # what CHAR_Y_ADJUST should be
python3 asset_assessment/render_sample_sheet.py   # N random tokens, full pipeline
```

`verify_placement.py` exits non-zero if any character is off its group, drifts
horizontally off the face column, or has a face hole away from the ball centre.

`verify_face_coverage.py` exits non-zero if any character × skin × eye leaves
transparent pixels enclosed by body + ball — i.e. background showing through a
face. It is the check that has to pass before any character art, `CHAR_SCALE`
or `FACE_HOLE_BOTTOM_OVERRIDE` change is called done.

The environment needs `pillow`, `numpy` and `scipy` (`pip install pillow numpy
scipy`); a bare container has none of them.
