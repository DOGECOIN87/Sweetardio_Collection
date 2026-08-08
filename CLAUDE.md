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
  file said. All 129 trait assets now conform; only `backgroundz` may vary,
  since a plate is re-fit to the frame by design.
  `asset_assessment/audit_art_quality.py` flags any deviation.
- The skin ball, eyes and mouth composite at **fixed canvas positions**; the
  ball centre is ~(690, 601) and every character's face hole is drawn around
  it. Nothing moves to meet a layer that drifted, so footprints and positions
  must be preserved exactly when an asset is re-authored.
- `ball_fit()` sizes every skin ball from the **widest eye**, so eye width is
  load-bearing across the whole collection.
- **The eyes must overlap the face hole's rim.** All 30 characters have the
  median eye (279px) wider than their face hole — ratios 1.04 to 1.57, median
  1.13 — so the eye whites spill past the hole edge onto the body. That overlap
  is the collection's face style, not an accident.

  It is fixed by the **art**, because `eye width ÷ hole width` survives every
  transform downstream: `ball_fit` scales only the ball, and `CHAR_SCALE` scales
  body, ball, eyes and mouth together. A body whose hole comes back wider than
  ~270px cannot be corrected in `generator.py` — the eyes will float inside it
  with a ring of skin ball showing.

  So new character art is registered to a **hole width of 248px** (the cast
  median) by `asset_assessment/register_character.py`, which scales the art
  until the hole matches before pinning it to the ball centre. Sizing the hole
  correctly also removes any need for a `FACE_HOLE_BOTTOM_OVERRIDE`: a
  cast-sized hole is one the standard ball already covers.

## Verification tools

```bash
python3 asset_assessment/verify_placement.py    # where characters actually land
python3 asset_assessment/audit_placement.py     # what CHAR_Y_ADJUST should be
python3 asset_assessment/render_sample_sheet.py # N random tokens, full pipeline
```

`verify_placement.py` exits non-zero if any character is off its group, drifts
horizontally off the face column, or has a face hole away from the ball centre.
