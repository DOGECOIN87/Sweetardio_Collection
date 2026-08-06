# Mouth Trait — AI Enhancement Prompts

Prompts for re-rendering the nine **Mouthz** assets so they read as dimensional
and glossy instead of flat vector fills — while staying the cartoon mouths the
collection is built on.

Companion sheet: `catalog/mouthz_reference_sheet.png` (all nine, proportions
exact). Companion docs: `SKIN_ENHANCE_PROMPTS.md`, `EYEZ_ENHANCE_PROMPTS.md`.

---

## 1. Read this before generating anything

**Same rule as the eyes: dimensional cartoon, not photoreal.** A flat graphic
face on a photorealistic body is the collection's look. A realistic mouth with
real lips and gums breaks the character and stops matching the rest of the set.
Add gloss, depth and shading *inside* the cartoon shape.

**These are much smaller than the eyes.** The largest is Smoke at 179×114; the
smallest is Flat at **48×7 pixels** — a single stroke. At that size there is
almost no room for detail, and the failure mode is not "not enough realism", it
is a generator elaborating a 7-pixel line into something that reads as mush at
thumbnail size. For the small assets, restraint is the brief.

**Two mechanical constraints:**

1. **Position is fixed and off-centre.** Mouths are pasted at exact canvas
   coordinates, and most sit right of the face centreline (centres range
   x 695–760 against a ball centre near x 690). That offset is intentional
   character, not an error to correct. Nothing else moves to meet a drifted
   layer.
2. **The black keyline carries the read.** Mouths composite over five very
   different skins — near-white Alien, dark chocolate Black, mid-tan White,
   saturated Cyan gel, bright Gold Foil. The heavy dark line is what keeps them
   visible on all five. Do not thin it or soften it into a rendered edge.

Unlike the eyes, mouths have **no compat file and no `ball_fit` coupling** —
`generator.py` never measures them. Colour and width changes are therefore safe
from the pipeline's point of view, and the only real risk is artistic.

**One asset extends past the face.** Smoke reaches to x=850 on the canvas,
beyond the skin ball's right edge — the joint deliberately sticks out past the
cheek. Do not tuck it back in.

---

## 2. Geometry reference (measured)

| # | Mouth | W×H (px) | Centre | File |
|--:|-------|---------:|-------:|------|
| 1 | Awkward Smile | 127 × 44 | (695, 658) | `Awkward_smile.png` |
| 2 | Diamond Grill | 118 × 50 | (699, 662) | `layer-Mouth_Diamond_Grill (1).png` |
| 3 | Fang | 77 × 40 | (709, 661) | `layer-Mouth_Fang (1).png` |
| 4 | Flat | 48 × 7 | (700, 651) | `layer-Mouth_Flat (1).png` |
| 5 | Lollipop | 67 × 60 | (727, 685) | `layer-Mouth_Lollipop (1).png` |
| 6 | Sad | 65 × 22 | (711, 655) | `layer-layer-layer-Mouth_Sad (1).png` |
| 7 | Smirk | 59 × 63 | (715, 672) | `layer-Mouth_Smirk (1).png` |
| 8 | Smoke | 179 × 114 | (760, 678) | `layer-Mouth_Smoke (1).png` |
| 9 | Tasty | 81 × 34 | (711, 662) | `layer-Mouth_Tasty-1.png` |

Canvas 1393 × 1393, transparent everywhere else.

---

## 3. How to run these

Nine assets share one set of rules and differ only in subject, so this doc is a
**master prompt with a slot**. Paste §4, then paste one asset block from §5
where it says `>>> ASSET <<<`. To hand off everything at once, use §6 with the
reference sheet.

Because these are small, attach the asset **and** say what it is — a generator
handed a 48×7 PNG with no context will not reliably work out that it is a
mouth. The asset blocks do that.

---

## 4. Master prompt

```
Re-render the attached image as a higher-quality version of the SAME artwork.
It is a single trait layer from a collectible series: a cartoon mouth that gets
composited onto a character's face.

THIS IS NOT A REALISM CONVERSION. The style is a flat graphic cartoon face on
a photorealistic body, and that contrast is the whole look. Keep it a cartoon
mouth. What I want added is dimension WITHIN that cartoon: a sense of a curved
surface, soft gradients instead of dead flat fills, real depth inside any
opening, and a clean glossy finish.

The artwork is SMALL — it is designed to read instantly at thumbnail size.
Restraint beats detail. Do not elaborate it into something busy.

KEEP EXACTLY AS IT IS:
- The outline shape and silhouette.
- The width and height proportion. Do not make it larger, wider, more centred,
  or more symmetrical than it already is.
- The heavy black keyline, at the same weight and full opacity. This artwork
  sits on backgrounds ranging from near-white to near-black and that outline
  is the only thing keeping it readable. Do not thin it, blur it, soften it
  into a shadow, or replace it with a rendered edge.
- The colour of every filled area.
- The expression. This is the character's entire mood.

ADD:
- Depth inside any open area: the inside of a mouth is a cavity, so it should
  darken toward the back with a soft gradient rather than being a flat black
  shape.
- A soft gradient across each filled area so it reads as curved.
- A restrained glossy highlight where a wet or polished surface would catch
  light — key from the upper left.
- Clean soft shading where forms overlap.

DO NOT:
- Do not make it a realistic mouth. No real lips, no gums, no skin, no stubble,
  no philtrum, no chin.
- Do not add a face, a head, a body, or any surrounding character.
- Do not add a background, a surface, a scene, or a cast shadow.
- Do not add glow, bloom, or any halo outside the artwork's outline.
- Do not add text, logos, watermarks, or sparkles.
- Do not add teeth, a tongue, or any element that is not already there.

OUTPUT: the mouth alone, on a fully transparent background, square canvas,
highest resolution available. Crisp anti-aliased edge with no colour fringe.
If you cannot output true transparency, render on a flat, uniform pure green
(#00FF00) field with no shadow, gradient, or spill onto the green.

>>> ASSET <<<
```

---

## 5. Asset blocks

Paste one of these in place of `>>> ASSET <<<`.

**1. Awkward Smile** — `Awkward_smile.png` · 127×44
```
THIS ASSET: a wide, slightly strained cartoon grin — a heavy black outline
enclosing a row of squarish white teeth with visible gaps between them, corners
turned up and pinched. Keep the gaps and the slightly uneven teeth; the
awkwardness is the trait. Give each tooth a subtle gradient and a soft
highlight along its top edge, darken the gaps between them so they read as
spaces rather than black paint, and add depth at the corners of the mouth.
```

**2. Diamond Grill** — `layer-Mouth_Diamond_Grill (1).png` · 118×50
```
THIS ASSET: a wide grin filled with a row of gem-set teeth — small pale
blue-white diamonds in settings, already the most detailed mouth in the set.
Push the gemstone read: crisp faceted highlights, tiny sharp catchlights,
cool internal refraction, and a hint of metal in the settings between stones.
Keep the tooth count, the row layout and the mouth shape exactly. Stay
blue-white — do not tint the stones warm or make them rainbow.
```

**3. Fang** — `layer-Mouth_Fang (1).png` · 77×40
```
THIS ASSET: a small open mouth as a solid black angular shape with a single
white fang hanging from the upper edge, right of centre. Give the black
interior real cavity depth — darkest at the back, slightly lifted at the front
lip — and make the fang read as a glossy pointed tooth with a bright edge
highlight and a soft shadow where it meets the upper lip. Keep it a single
fang and keep the mouth small and closed-ish.
```

**4. Flat** — `layer-Mouth_Flat (1).png` · 48×7
```
THIS ASSET: a short, flat, straight black line — a deadpan mouth. It is 48x7
pixels. That is the entire trait and its blankness is the joke. Do NOT add a
mouth opening, teeth, lips, curvature, or expression. The only change: let the
stroke read as a slightly raised painted line rather than flat ink — a faint
sheen along its upper surface and a very subtle taper at each end. If in doubt,
change less.
```

**5. Lollipop** — `layer-Mouth_Lollipop (1).png` · 67×60
```
THIS ASSET: a lollipop held in the mouth, seen edge-on — a round candy disc on
a thin stick angling down and to the right, currently reading as flat grey.
This one benefits most from real rendering: make the disc a glossy hard candy
with a bright specular highlight, a soft translucent edge where light passes
through, and a visible thickness to the disc. Make the stick a matte paper
tube with a subtle cylinder gradient. Keep the angle, the proportions and the
position of the disc on the stick exactly.
```

**6. Sad** — `layer-layer-layer-Mouth_Sad (1).png` · 65×22
```
THIS ASSET: a small downturned black arc — a simple frown, no opening. Keep it
a single clean arc with the same curve and the same stroke weight. Add only a
faint sheen along the upper surface of the stroke so it reads as a raised
painted line, and a very slight taper at each tip. Do not open it into a mouth,
do not add teeth, and do not deepen the curve.
```

**7. Smirk** — `layer-Mouth_Smirk (1).png` · 59×63
```
THIS ASSET: an asymmetric black brush-stroke smirk — a curve that hooks up
sharply on one side, taller than it is wide. The lopsidedness is the trait; do
not straighten or balance it. Keep the exact curve and stroke weight, and add
only a subtle gloss along the upper surface of the stroke plus a slight taper
at the ends. Do not open it into a mouth and do not add teeth.
```

**8. Smoke** — `layer-Mouth_Smoke (1).png` · 179×114
```
THIS ASSET: a rolled joint held at an angle in the mouth, with a lit glowing
ember at the tip and thin wisps of smoke rising from it. The largest and most
photographic mouth in the set. Push it: visible paper texture and a slight
twist at the tip, a genuinely hot ember with a bright core falling off to
darker ash at the edges, a faint warm light spill onto the paper nearest the
ember, and soft translucent smoke wisps that thin out as they rise. Keep the
angle, the length and the smoke path exactly. This asset deliberately extends
past the edge of the face — keep it that long, do not shorten or re-angle it
to fit.
```

**9. Tasty** — `layer-Mouth_Tasty-1.png` · 81×34
```
THIS ASSET: a black mouth line with a bright magenta-pink tongue lolling out
below it, to the right. Make the tongue read as a wet, soft, fleshy cartoon
tongue: a gradient from deeper pink at the base to brighter at the tip, a
glossy highlight along its upper surface, a soft central crease, and a shadow
where it tucks under the black mouth line. Keep the tongue the same pink, the
same size and on the same side.
```

---

## 6. All nine at once

Attach `catalog/mouthz_reference_sheet.png` and paste §4 with this in the
`>>> ASSET <<<` slot. Ask for one image per mouth — a returned grid gives back
tiny crops of assets that are already small.

```
THE ASSETS: the attached sheet shows nine cartoon mouths with their true pixel
sizes labeled — some are very small and must stay simple. Work through them
ONE AT A TIME and return each as its own separate, full-size image. Do not
return a grid or contact sheet.

 1. Awkward Smile — wide strained grin, squarish white teeth with gaps; keep the gaps
 2. Diamond Grill — grin of gem-set teeth; push the faceted gemstone read, stay blue-white
 3. Fang         — small black open mouth with one white fang; give the cavity depth
 4. Flat         — a 48x7 flat black line, deadpan; add a sheen and NOTHING else
 5. Lollipop     — candy disc on a stick, edge-on; glossy hard candy, matte paper stick
 6. Sad          — small downturned arc; keep it a single clean stroke
 7. Smirk        — asymmetric hooked brush stroke; keep it lopsided
 8. Smoke        — lit joint with ember and smoke wisps; keep its full length past the face
 9. Tasty        — black mouth line with a magenta tongue; make the tongue wet and soft

Restraint matters more than detail here — several of these are under 80px wide
and must still read instantly at thumbnail size.

Start with number 1.
```

---

## 7. Acceptance checklist

- [ ] **Still a cartoon.** No real lips, gums, skin, or chin. It belongs on the
      same character as before.
- [ ] **Keyline intact.** The black outline is as heavy and opaque as the
      original. Check against a dark skin, not just on white.
- [ ] **Same silhouette and size.** Overlay on the original at 50% opacity —
      the outer edges track.
- [ ] **Expression unchanged.** A smirk still smirks, Flat is still flat, Sad
      still turns down.
- [ ] **Nothing invented.** No teeth, tongue, or elements that were not there.
- [ ] **Smoke kept its length**, still reaching past the edge of the face.
- [ ] **Clean edge.** No baked shadow, outer glow, or backdrop colour in the
      anti-aliased pixels.
- [ ] **Reads at thumbnail size.** Zoom to 10%: still instantly legible. This
      is the one the small mouths fail.

## 8. Retry lines

- **Over-elaborated a small asset:** `Too much detail for the size. This is a
  <48x7 px> mark that must read instantly at thumbnail size. Simplify back to
  the original shape and add only a subtle sheen.`
- **Went photoreal:** `Too realistic. Go back to a flat cartoon mouth — no real
  lips, gums, or skin. Keep the graphic shape and the heavy black outline; add
  only gloss, gradient, and interior depth.`
- **Outline weakened:** `Restore the heavy black outline at its original weight
  and full opacity. It must stay a solid graphic keyline.`
- **Invented features:** `Remove the added <teeth / tongue / lips>. Include only
  what is in the attached image.`
- **Shape drifted:** `The outline must match the attached image exactly — same
  width, same height, same asymmetry. Do not centre or balance it.`

## 9. Getting the result back in

```bash
python3 asset_assessment/register_trait.py enhanced.png "layer-Mouth_Fang (1).png" \
    --preview /tmp/fang_ab.png
```

The class is inferred from the filename. It keys out the backdrop, despills,
crops, and pastes the art onto a 1393×1393 canvas at the original footprint and
position. Mouths have no `ball_fit` coupling, so the run reports footprint and
position drift only. Add `--replace` to write into `traits/mouthz/`.

Keep the filename identical — `TRAIT_NAMES` in `generator.py` maps it to the
display name in token metadata, so renaming changes what the token says.
Then verify in a real render:

```bash
python3 asset_assessment/render_sample_sheet.py --n 25 --cols 5 --cell 500 \
    --out /tmp/mouth_check.png
```

Check the small mouths at sheet scale, not zoomed in — the failure mode is
detail that dissolves into mush at thumbnail size.
