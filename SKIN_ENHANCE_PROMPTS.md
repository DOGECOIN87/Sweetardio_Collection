# Skin Trait — AI Enhancement Prompts

Paste-ready prompts for re-rendering each of the five **Skinz** assets in an AI
image generator (ChatGPT / GPT Image) so they read as photoreal 3D — real form
shadow, occlusion, rim light and micro-surface — instead of flat painted balls.

**One skin per prompt. Attach that skin's original PNG with the prompt.**

---

## 1. What a "skin" actually is (why the prompts are shaped this way)

The skin is the **face ball**. It is not a background element and it is never
seen whole and unobstructed:

- It sits in the **face hole** of the character body on a 1393×1393 canvas.
- The pipeline **enlarges it 1.08–1.16×** at composite time (`ball_fit()` in
  `generator.py`) so it always covers the deepest face hole and is wide enough
  for the widest eyes.
- **Eyes and mouth are composited on top of it** at fixed canvas positions.
  Eyes are up to **288px wide**, centred about **30px above** the ball's
  centre — nearly as wide as the ball itself.

So after compositing, only about this much of the ball is actually visible:

| Region | Visible | What it must carry |
|--------|---------|--------------------|
| Band above the eyes | ~50 px | the form turning away toward the top, ambient occlusion into the face hole |
| Left / right margins | ~10–17 px each | the terminator and the rim light — this is where "3D" is won |
| Lower third (around the mouth) | ~110 px | the bottom of the sphere falling into shadow, contact darkening |
| Dead centre / upper middle | **hidden** | covered by the eyes — do not put the money detail here |

That single fact drives every prompt below: **the modelling has to live at the
rim, the top band and the lower third.** A gorgeous specular hotspot in the
middle of the ball is wasted — the eyes cover it, and a bright blown-out patch
there fights the eye art it shows through.

---

## 2. Geometry reference (measured from the current assets)

Every enhanced skin has to land back on the same canvas footprint or the face
will not line up with the eyes and the character's face hole.

| Skin file | Ball W×H (px) | Ball centre (x, y) | Composite upscale |
|-----------|--------------:|-------------------:|------------------:|
| `layer-layer-layer-Skin_White (2).png` | 276 × 253 | (691, 598) | 1.134× |
| `layer-Skin_Black (3).png` | 281 × 257 | (691, 599) | 1.114× |
| `layer-Skin_Fluorescent_Cyan (2).png` | 281 × 244 | (690, 598) | 1.114× |
| `layer-Skin_Alien (2).png` | 269 × 248 | (689, 605) | 1.164× |
| `layer-Skin_Gold_Foil (1).png` | 292 × 258 | (690, 603) | 1.078× |

Canvas is **1393 × 1393, fully transparent** outside the ball.

---

## 3. How to run these

1. Open a **fresh chat per skin** — mixing them makes the model blend materials.
2. Attach **only** that skin's original PNG.
3. Paste the prompt for that skin verbatim.
4. Check the result against the acceptance list in §5 before keeping it.
5. If it drifts (wrong shape, added face, new object), reply with the **retry
   line** in §6 rather than re-rolling blind.

The generator will most likely hand back a 1024×1024 image, not 1393×1393, and
transparency is unreliable in the chat UI — that is expected and handled: each
prompt includes a flat-green fallback, and the asset gets re-cut and re-centred
to the numbers in §2 locally afterward.

---

## 4. The prompts

### 4.1 — White (warm cream / vanilla fondant)

```
Re-render the attached image as a photorealistic 3D asset. It is a single
trait layer from a 3D-rendered collectible series: a rounded "face ball" that
gets composited into a hole in a character's body.

Keep it the SAME object — same shape, same silhouette, same colour identity.
This is a quality upgrade, not a redesign. Someone comparing before and after
must see the same ball, rendered properly.

MATERIAL: warm cream-beige confectionery — soft matte fondant or marzipan.
Base tone #C9A176. Light-side tone around #DAB68B, shadow side around #B68E63,
deepest occluded bottom edge around #6A4C2E. Give it gentle subsurface warmth
so light bleeds slightly under the surface at the rim, plus a very fine
powdered-sugar micro-grain across the form. Semi-matte: a soft broad sheen,
never a glossy plastic highlight.

FORM AND LIGHT:
- Read as a slightly flattened sphere / domed disc, not a flat circle.
- One soft key light from the upper left at about 45 degrees, with a cooler,
  dimmer fill from the lower right.
- A soft terminator where the form turns away, real ambient occlusion
  darkening the lower and outer rim, and a subtle warm rim light catching the
  lower-right edge to separate the ball from what sits behind it.
- The strongest modelling must be at the RIM, the TOP BAND and the LOWER
  THIRD of the ball. Keep the upper-middle area smooth, evenly lit and free of
  any blown-out specular hotspot or busy texture.

DO NOT:
- Do not add eyes, a mouth, a nose, eyebrows, or any face. It must stay a
  featureless ball — the face is composited on top later.
- Do not add a background, backdrop, surface, table, or scene.
- Do not add a cast shadow or drop shadow.
- Do not add glow, bloom, or any halo outside the ball's outline.
- Do not add text, logos, watermarks, or sparkles.
- Do not change the hue family — it must stay warm cream-beige.
- Do not change the outline shape or the width-to-height proportion.

OUTPUT: the ball alone, centred, on a fully transparent background, square
canvas, highest resolution available. Crisp anti-aliased edge with no fringe
or matte line. If you cannot output true transparency, render it on a flat,
uniform pure green (#00FF00) field with absolutely no shadow, gradient, or
colour spill onto the green.
```

### 4.2 — Black (dark milk chocolate)

```
Re-render the attached image as a photorealistic 3D asset. It is a single
trait layer from a 3D-rendered collectible series: a rounded "face ball" that
gets composited into a hole in a character's body.

Keep it the SAME object — same shape, same silhouette, same colour identity.
This is a quality upgrade, not a redesign. Someone comparing before and after
must see the same ball, rendered properly.

MATERIAL: rich dark milk chocolate, tempered and freshly moulded. Base tone
#553C2B. Light-side tone around #5D4332, shadow side around #4A3323, deepest
occluded bottom edge around #2D1D11. Semi-matte cocoa surface with a faint
satin sheen — the low, wide sheen of set chocolate, not wet gloss. Add
believable micro-detail: fine cocoa pitting and a barely-there mould texture,
subtle enough that it reads as surface quality rather than noise.

FORM AND LIGHT:
- Read as a slightly flattened sphere / domed disc, not a flat circle.
- One soft key light from the upper left at about 45 degrees, with a cooler,
  dimmer fill from the lower right.
- A soft terminator where the form turns away, real ambient occlusion
  darkening the lower and outer rim, and a warm rim light catching the
  lower-right edge so the dark ball still separates from a dark background.
- The strongest modelling must be at the RIM, the TOP BAND and the LOWER
  THIRD of the ball. Keep the upper-middle area smooth, evenly lit and free of
  any blown-out specular hotspot or busy texture.
- Do not let the shadow side crush to pure black — hold detail and colour in
  the darks so the form still reads.

DO NOT:
- Do not add eyes, a mouth, a nose, eyebrows, or any face. It must stay a
  featureless ball — the face is composited on top later.
- Do not add a background, backdrop, surface, table, or scene.
- Do not add a cast shadow or drop shadow.
- Do not add glow, bloom, or any halo outside the ball's outline.
- Do not add text, logos, watermarks, or sparkles.
- Do not change the hue family — it must stay warm dark chocolate brown, not
  neutral grey or black.
- Do not change the outline shape or the width-to-height proportion.

OUTPUT: the ball alone, centred, on a fully transparent background, square
canvas, highest resolution available. Crisp anti-aliased edge with no fringe
or matte line. If you cannot output true transparency, render it on a flat,
uniform pure green (#00FF00) field with absolutely no shadow, gradient, or
colour spill onto the green.
```

### 4.3 — Alien (cool grey-blue matte)

```
Re-render the attached image as a photorealistic 3D asset. It is a single
trait layer from a 3D-rendered collectible series: a rounded "face ball" that
gets composited into a hole in a character's body.

Keep it the SAME object — same shape, same silhouette, same colour identity.
This is a quality upgrade, not a redesign. Someone comparing before and after
must see the same ball, rendered properly.

MATERIAL: cool grey-blue, smooth matte silicone or soft vinyl — the surface of
a high-end designer toy. Base tone #A8B0B6. Light-side tone around #B2B8BF,
shadow side around #9BA1A6, deepest occluded bottom edge around #646A6E. Give
it a faint waxy sheen and a whisper of translucency at the rim, so the very
edge picks up a slightly lighter, warmer glow where light passes through the
thin part of the form. Surface should be almost flawless with only the
faintest micro-texture.

FORM AND LIGHT:
- Read as a slightly flattened sphere / domed disc, not a flat circle.
- One soft key light from the upper left at about 45 degrees, with a cooler,
  dimmer fill from the lower right.
- A soft, wide terminator suited to a matte surface, real ambient occlusion
  darkening the lower and outer rim, and a clean rim light along the
  lower-right edge.
- The strongest modelling must be at the RIM, the TOP BAND and the LOWER
  THIRD of the ball. Keep the upper-middle area smooth, evenly lit and free of
  any blown-out specular hotspot or busy texture.

DO NOT:
- Do not add eyes, a mouth, a nose, eyebrows, or any face. It must stay a
  featureless ball — the face is composited on top later.
- Do not add a background, backdrop, surface, table, or scene.
- Do not add a cast shadow or drop shadow.
- Do not add glow, bloom, or any halo outside the ball's outline.
- Do not add text, logos, watermarks, or sparkles.
- Do not change the hue family — it must stay cool desaturated grey-blue, and
  must not drift green, purple, or toward chrome.
- Do not make it metallic or reflective.
- Do not change the outline shape or the width-to-height proportion.

OUTPUT: the ball alone, centred, on a fully transparent background, square
canvas, highest resolution available. Crisp anti-aliased edge with no fringe
or matte line. If you cannot output true transparency, render it on a flat,
uniform pure green (#00FF00) field with absolutely no shadow, gradient, or
colour spill onto the green.
```

### 4.4 — Fluorescent Cyan (translucent blue gel)

```
Re-render the attached image as a photorealistic 3D asset. It is a single
trait layer from a 3D-rendered collectible series: a rounded "face ball" that
gets composited into a hole in a character's body.

Keep it the SAME object — same shape, same silhouette, same colour identity.
This is a quality upgrade, not a redesign. Someone comparing before and after
must see the same ball, rendered properly.

MATERIAL: translucent blue gel — a gummy-candy / jelly ball with real
subsurface scattering, light passing through the body of the material and
glowing out of the shadow side. Core tone #006489, deeper toward #01536E at
the occluded bottom edge. Keep the existing soft bright highlight in the UPPER
LEFT around #C7E3EF and keep it exactly there. Preserve the small trapped air
bubbles suspended inside the gel and make them read as genuinely internal —
refracting, at varying depths, slightly out of focus the deeper they sit —
rather than as dots painted on the surface. Wet, glossy exterior.

FORM AND LIGHT:
- Read as a slightly flattened sphere / domed disc, not a flat circle.
- One soft key light from the upper left at about 45 degrees, with a cooler,
  dimmer fill from the lower right.
- The bottom rim should glow with transmitted light rather than going flatly
  dark — that internal bounce is what sells gel.
- Crisp caustic-style brightening where light exits the lower-right rim, plus
  real ambient occlusion where the form meets its own edge.
- The strongest modelling must be at the RIM, the TOP BAND and the LOWER
  THIRD of the ball. Keep the upper-middle area readable and free of busy
  texture.

DO NOT:
- Do not add a second specular hotspot in the middle or upper-middle of the
  ball — one highlight only, in the upper left, exactly where it already is.
- Do not add eyes, a mouth, a nose, eyebrows, or any face. It must stay a
  featureless ball — the face is composited on top later.
- Do not add a background, backdrop, surface, table, or scene.
- Do not add a cast shadow or drop shadow.
- Do not add glow, bloom, or any halo outside the ball's outline.
- Do not add text, logos, watermarks, or sparkles.
- Do not change the hue family — it must stay saturated cyan-blue and must not
  drift teal-green or navy.
- Do not change the outline shape or the width-to-height proportion.

OUTPUT: the ball alone, centred, on a fully transparent background, square
canvas, highest resolution available. Crisp anti-aliased edge with no fringe
or matte line. If you cannot output true transparency, render it on a flat,
uniform pure magenta (#FF00FF) field with absolutely no shadow, gradient, or
colour spill onto the magenta.
```

> Cyan uses a **magenta** key field, not green — a green backdrop contaminates
> the translucent blue edge and the bubbles pick it up.

### 4.5 — Gold Foil (crumpled foil, legendary)

```
Re-render the attached image as a photorealistic 3D asset. It is a single
trait layer from a 3D-rendered collectible series: a rounded "face ball" that
gets composited into a hole in a character's body. This is the rarest variant
in the set, so it should be the most impressive render of the group.

Keep it the SAME object — same shape, same silhouette, same colour identity.
This is a quality upgrade, not a redesign. Someone comparing before and after
must see the same ball, rendered properly.

MATERIAL: crumpled gold foil wrapped tightly over a ball, like the foil on a
premium chocolate truffle. Bright specular highlights around #FCE194, mid
tones around #AE7416, deep creases and occluded folds around #5B3600 to
#623501. Real metal: anisotropic, sharp specular breakup that follows the
crease lines, warm golden bounce light filling the shallow folds, tiny bright
catch-lights where two facets meet at an edge. The foil should look thin and
pressed — you can feel the sphere underneath it.

FORM AND LIGHT:
- Read as a slightly flattened sphere / domed disc, not a flat circle.
- One soft key light from the upper left at about 45 degrees, with a cooler,
  dimmer fill from the lower right.
- Real ambient occlusion in the depth of every crease and along the lower and
  outer rim, and a bright rim catch along the lower-right edge.
- Keep the crease pattern in roughly the same layout and density as the
  attached original — refine and deepen it, do not re-scatter it.
- Concentrate the finest crease detail and the brightest facet hits at the
  RIM, the TOP BAND and the LOWER THIRD. Keep the upper-middle area calmer,
  with larger, smoother foil facets and no single blown-out white hotspot.

DO NOT:
- Do not add eyes, a mouth, a nose, eyebrows, or any face. It must stay a
  featureless ball — the face is composited on top later.
- Do not add a background, backdrop, surface, table, or scene.
- Do not add a cast shadow or drop shadow.
- Do not add glow, bloom, lens flare, or any halo outside the ball's outline.
- Do not add text, logos, watermarks, or sparkle overlays.
- Do not change the hue family — warm yellow gold, not rose gold, brass,
  bronze, or silver.
- Do not turn the crumpled foil into smooth polished metal.
- Do not change the outline shape or the width-to-height proportion.

OUTPUT: the ball alone, centred, on a fully transparent background, square
canvas, highest resolution available. Crisp anti-aliased edge with no fringe
or matte line. If you cannot output true transparency, render it on a flat,
uniform pure green (#00FF00) field with absolutely no shadow, gradient, or
colour spill onto the green.
```

---

## 5. Acceptance checklist

Reject and retry if any of these fail:

- [ ] **No face.** No eyes, mouth, brows, or implied features anywhere on it.
- [ ] **Same silhouette.** Outline matches the original; the ball has not
      become rounder, taller, or narrower. Lay it over the original at 50%
      opacity — the edges should track.
- [ ] **Same colour identity.** Still reads as the trait its metadata name
      claims (White / Black / Alien / Fluorescent Cyan / Gold Foil).
- [ ] **Clean edge.** No baked drop shadow, no outer glow, no dark matte
      fringe, no leftover backdrop colour in the anti-aliased pixels — any of
      these show as a visible ring inside the character's face hole.
- [ ] **Upper-middle is calm.** No blown-out highlight or busy texture where
      the eyes land, ~30px above centre and up to 288px wide.
- [ ] **Rim does the work.** Terminator, occlusion and rim light are legible in
      the outer 15px, because that ring is most of what the viewer will see.
- [ ] **Not flat.** Held at thumbnail size it reads as a sphere with a light
      source, not a coloured circle.

---

## 6. Retry lines

Append to the original prompt when an output misses:

- **Wrong shape:** `The outline must match the attached image exactly — same
  width, same height, same proportion. Overlay it on the original: the edges
  must line up.`
- **Added a face:** `Remove all facial features. This layer is a blank
  featureless ball; the eyes and mouth are separate layers added later.`
- **Went flat:** `Increase the sense of three-dimensional form: deepen the
  shadow side, strengthen the ambient occlusion at the lower and outer rim,
  and add a rim light on the lower-right edge. It must read as a sphere, not a
  disc.`
- **Hotspot in the middle:** `Move the specular highlight off the centre. Keep
  the middle of the ball evenly lit — the brightest values belong at the upper
  rim and the lower-right rim.`
- **Background survived:** `Output the ball alone with a fully transparent
  background — no backdrop, no surface, no shadow.`
- **Colour drifted:** `Return to the original colour: <base hex from §2 table
  for that skin>. Do not shift the hue.`

---

## 7. Getting the result back into the pipeline

The generator's output will not be canvas-ready. Before it can replace a file
in `traits/skinz/`:

1. **Key out the backdrop** if the green/magenta fallback was used, and clean
   the anti-aliased edge so no backdrop colour survives in the fringe.
2. **Auto-crop to the opaque bounds**, then **resize and paste onto a
   1393×1393 transparent canvas** so the ball's width, height and centre match
   its row in the §2 table. The centre position matters more than anything
   else — the eyes and mouth are drawn at fixed canvas coordinates and will not
   move to meet a ball that has drifted.
3. **Keep the filename identical.** `traits/skin_weights.json` matches rarity
   by case-insensitive substring of the filename, and `TRAIT_NAMES` in
   `generator.py` maps the filename to the display name in token metadata.
   Renaming a skin silently changes its rarity and its metadata value.
4. **Verify before committing:**
   ```bash
   python3 asset_assessment/render_sample_sheet.py --n 25 --cols 5 --cell 500 \
       --out /tmp/skin_check.png
   ```
   Check the faces across characters — especially an `after_skinz` body like
   `brownie_bite` or `rice_crispy_treat`, whose face hole is deepest and will
   expose any gap, halo, or off-centre ball immediately.
