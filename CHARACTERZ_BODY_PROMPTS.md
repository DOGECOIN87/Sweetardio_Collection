# Character Body — AI Generation Prompts

Prompts for regenerating **character body art**, and the measured spec each one
has to hit.

Companion docs: `SKIN_ENHANCE_PROMPTS.md`, `EYEZ_ENHANCE_PROMPTS.md`,
`MOUTHZ_ENHANCE_PROMPTS.md`.

---

## 0. Status

| Family | State |
|---|---|
| Ice creams | **5 regenerated and live** (vanilla, neapolitan, rocky road, cyan sherbert, pink sherbert). The 3 that were not returned — mint choc chip, zaffre sherbert, rainbow sherbert — have been **retired from the trait set** rather than left mismatched. |
| Gummy bears | Prompt below (§5). Current art is fine geometrically; it is the render quality and the socket that need the pass. |

---

## 1. The rule that governs all of this

The compositor **pins the face**. The skin ball, eyes and mouth all land at
fixed canvas coordinates around the ball centre **(690, 601)**, and nothing
moves to follow a body that drifted. So a body is defined by two things:

- where its **face socket** sits relative to its own silhouette, and
- how far its **feet/base** fall **below** the socket.

The second number is the one that decides whether a character stands on the
same floor as the rest of the cast. Everything else is style.

**`CHAR_SCALE` cannot fix the first number.** It scales about a pivot that sits
*inside the face*, so body and face shrink together and the ratio is unchanged.
That is why the ice creams could not be fixed by scaling and needed new art.

## 2. What the ice-cream regeneration actually changed

Worth recording honestly, because the headline number did *not* move:

| | Body W × H | Face down the body | Below the face |
|---|---|---|---|
| Cast (21 non-ice-cream, non-bear) | 700 × 747 | 0.49 | — |
| Ice creams, old art | 787 × 1067 median | 0.33 | 715 |
| Ice creams, new art | 813 × 1092 | **0.344** | **716** |

So the new bodies are the *same proportions* as the old ones, and still need
`CHAR_SCALE["ice_cream"] = 0.74` to put their cone tips on the shared 1111
ground line. The regeneration was still worth it, for reasons the ratio does
not capture:

- The **scoop is much larger** relative to the whole, so at the same 0.74 the
  character reads bigger — which was the complaint.
- The **face hole grew from 179–219px to ~257px**, putting the ice creams in
  the same range as the doughnuts and cookies (230–260px).
- That bigger hole is what makes **skin-under-body** layering work (§3).

## 3. Layer order — skin first, then the ice-cream body

The new bodies are `after_skinz_*`, so the stack is:

```
background → skin ball → ICE CREAM BODY → eyes → mouth → footwear → arms
```

The ball is drawn first and shows through the body's hole; the hole's rim
overlaps the ball and reads as a recess in the scoop. The old art was
`before_skinz_*` — ball drawn *over* the body — which is why the face used to
sit flat on top of the scoop with no socket.

This is the same path the doughnuts and cookies take (`body_after_skin()` in
`generator.py`), so no new mechanism was needed; the `after_skinz_` filename
prefix is the whole switch.

## 4a. Ice cream v2 — the cone is the whole problem

Measured on the delivered art, the scoop is **already correct** and the face is
**already centred in it**. The face-frac of 0.344 comes from one thing:

| | px | share of body |
|---|---:|---:|
| Scoop | 720 tall × 813 wide | 66% |
| Cone | 369 tall | 34% |
| Hole centre, measured down the **scoop** | 375 of 720 | **0.52 — dead centre** |
| Hole centre, measured down the **body** | 375 of 1089 | 0.344 |

So nothing about the scoop or the hole needs to change. **Shorten the cone from
369px to ~120px** — a shallow wafer cup instead of a tall cone — and the
arithmetic does the rest:

| Cone | Body | Face-frac |
|---:|---|---:|
| 369 (today) | 813 × 1089 | 0.344 |
| 160 | 813 × 880 | 0.426 |
| **120** | **813 × 840** | **0.446** |
| 100 | 813 × 820 | 0.457 |

At 120px the body is 813 × 840 — near enough square, and in the same size band
as the cast's 700 × 747 median with the face at 0.446 against the cast's 0.49.
Close enough that **`CHAR_SCALE["ice_cream"]` can be deleted entirely** and the
family runs at native size, which is what makes them read bigger.

Worth being straight about the ceiling: a scoop-on-a-cone cannot reach 0.49
while it still has a cone. With the hole centred in the scoop, face-frac =
(S/2)/(S+C), so 0.49 needs the cone to be ~4% of the scoop — i.e. no cone at
all. 0.45 with a shallow cup is the honest target, and it sits between the
doughnuts (0.49, because a ring's hole is its centre) and the gummy bears
(0.384), both of which read fine.

### The v3 prompts — standalone, one per flavour

Fully assembled: no reference image, no placeholder to fill in, nothing to
paste together. One block per flavour, copy and run.

Every proportion is stated as a fraction of total height, because "shallow cup"
as prose was not enough — the generator kept drawing a normal cone. The word
"cone" is gone from the flavour text for the same reason.

**Vanilla** — replaces `after_skinz_vanilla_ice_cream.png`

```
Create a single 3D-rendered ice cream character on a transparent background.
It is one layer of a composited collectible artwork: a photorealistic ice cream
with a round hole punched through its scoop, into which a cartoon face is
composited later.

THE FLAVOUR is classic vanilla — a pale cream scoop with a soft matte surface and fine
flecks of vanilla bean, in a shallow golden waffle cup, with a gentle melt drip
over the rim.

BUILD IT TO THESE PROPORTIONS. They are the point of the image, and they are
NOT the usual ice-cream proportions — read them literally:

- Take the character's total height as 100%.
- The SCOOP is the top 86% of that height.
- The WAFFLE CUP is only the bottom 14%. It is a shallow, flat-bottomed wafer
  bowl that the scoop sits down into — the height of a tuna tin. It must NOT be
  a cone. It must NOT be a tall cup. If it looks like a normal ice cream cone,
  it is wrong.
- The finished character is about as TALL as it is WIDE — roughly square in its
  bounding box, dominated by one huge round scoop.
- The hole therefore lands near the MIDDLE of the total height, about 45% down
  from the crown of the scoop. That is the test: the distance from the top of
  the scoop down to the hole's centre, and the distance from the hole's centre
  down to the bottom of the cup, should be close to equal.

THE SCOOP: one single generous, round, dome-shaped scoop, as wide as the whole
character, with a soft irregular lower edge where it overhangs the cup.

THE HOLE: a clean circular hole punched right THROUGH the front of the scoop,
fully transparent inside, centred horizontally and centred in the scoop's own
height. Its diameter is about ONE THIRD of the character's width. Give it a
visible inner wall so it reads as a real opening bored through solid material,
lit consistently with the rest of the scoop. No eyes, no mouth, no facial
features of any kind — the hole is empty.

STYLE: photorealistic 3D confectionery product render — the look of a premium
food photograph, with real material, real subsurface and real micro-texture.
Not illustration, not clay, not cel-shaded. It has to sit beside photoreal
cookies, doughnuts and waffles as if shot in the same studio. The cup carries a
crisp golden waffle lattice.

LIGHTING: one soft key light from the UPPER LEFT at about 45 degrees, with a
cooler, dimmer fill from the lower right. Highlights on the upper-left of the
scoop; the terminator and the deepest occlusion on the lower-right and under
the cup's rim.

DO NOT: do not draw a cone, the base is a shallow bowl. Do not add a
background, surface, table or scene — the character floats alone. Do not add a
cast shadow or drop shadow. Do not add a face, eyes or a mouth. Do not add
sprinkles, spoons, cherries, text or logos. Do not add glow, bloom or a halo
outside the silhouette.

OUTPUT: the character alone, centred, on a fully transparent background, square
canvas, highest resolution available. Crisp anti-aliased edge, no colour
fringe, no matte line. Deliver the PNG file itself, with real alpha — not a
screenshot or a preview of it.
```

**Neapolitan** — replaces `after_skinz_neopolitan_ice_cream.png`

```
Create a single 3D-rendered ice cream character on a transparent background.
It is one layer of a composited collectible artwork: a photorealistic ice cream
with a round hole punched through its scoop, into which a cartoon face is
composited later.

THE FLAVOUR is neapolitan — one scoop split into three vertical bands, chocolate, vanilla
and strawberry, meeting cleanly, in a shallow golden waffle cup. Keep the
three-band split clearly readable at thumbnail size.

BUILD IT TO THESE PROPORTIONS. They are the point of the image, and they are
NOT the usual ice-cream proportions — read them literally:

- Take the character's total height as 100%.
- The SCOOP is the top 86% of that height.
- The WAFFLE CUP is only the bottom 14%. It is a shallow, flat-bottomed wafer
  bowl that the scoop sits down into — the height of a tuna tin. It must NOT be
  a cone. It must NOT be a tall cup. If it looks like a normal ice cream cone,
  it is wrong.
- The finished character is about as TALL as it is WIDE — roughly square in its
  bounding box, dominated by one huge round scoop.
- The hole therefore lands near the MIDDLE of the total height, about 45% down
  from the crown of the scoop. That is the test: the distance from the top of
  the scoop down to the hole's centre, and the distance from the hole's centre
  down to the bottom of the cup, should be close to equal.

THE SCOOP: one single generous, round, dome-shaped scoop, as wide as the whole
character, with a soft irregular lower edge where it overhangs the cup.

THE HOLE: a clean circular hole punched right THROUGH the front of the scoop,
fully transparent inside, centred horizontally and centred in the scoop's own
height. Its diameter is about ONE THIRD of the character's width. Give it a
visible inner wall so it reads as a real opening bored through solid material,
lit consistently with the rest of the scoop. No eyes, no mouth, no facial
features of any kind — the hole is empty.

STYLE: photorealistic 3D confectionery product render — the look of a premium
food photograph, with real material, real subsurface and real micro-texture.
Not illustration, not clay, not cel-shaded. It has to sit beside photoreal
cookies, doughnuts and waffles as if shot in the same studio. The cup carries a
crisp golden waffle lattice.

LIGHTING: one soft key light from the UPPER LEFT at about 45 degrees, with a
cooler, dimmer fill from the lower right. Highlights on the upper-left of the
scoop; the terminator and the deepest occlusion on the lower-right and under
the cup's rim.

DO NOT: do not draw a cone, the base is a shallow bowl. Do not add a
background, surface, table or scene — the character floats alone. Do not add a
cast shadow or drop shadow. Do not add a face, eyes or a mouth. Do not add
sprinkles, spoons, cherries, text or logos. Do not add glow, bloom or a halo
outside the silhouette.

OUTPUT: the character alone, centred, on a fully transparent background, square
canvas, highest resolution available. Crisp anti-aliased edge, no colour
fringe, no matte line. Deliver the PNG file itself, with real alpha — not a
screenshot or a preview of it.
```

**Rocky Road** — replaces `after_skinz_rocky_road_ice_cream.png`

```
Create a single 3D-rendered ice cream character on a transparent background.
It is one layer of a composited collectible artwork: a photorealistic ice cream
with a round hole punched through its scoop, into which a cartoon face is
composited later.

THE FLAVOUR is rocky road — a dark chocolate scoop studded with mini marshmallows and
chocolate chunks breaking the surface, in a shallow golden waffle cup. Keep the
inclusions chunky and few rather than dense and busy.

BUILD IT TO THESE PROPORTIONS. They are the point of the image, and they are
NOT the usual ice-cream proportions — read them literally:

- Take the character's total height as 100%.
- The SCOOP is the top 86% of that height.
- The WAFFLE CUP is only the bottom 14%. It is a shallow, flat-bottomed wafer
  bowl that the scoop sits down into — the height of a tuna tin. It must NOT be
  a cone. It must NOT be a tall cup. If it looks like a normal ice cream cone,
  it is wrong.
- The finished character is about as TALL as it is WIDE — roughly square in its
  bounding box, dominated by one huge round scoop.
- The hole therefore lands near the MIDDLE of the total height, about 45% down
  from the crown of the scoop. That is the test: the distance from the top of
  the scoop down to the hole's centre, and the distance from the hole's centre
  down to the bottom of the cup, should be close to equal.

THE SCOOP: one single generous, round, dome-shaped scoop, as wide as the whole
character, with a soft irregular lower edge where it overhangs the cup.

THE HOLE: a clean circular hole punched right THROUGH the front of the scoop,
fully transparent inside, centred horizontally and centred in the scoop's own
height. Its diameter is about ONE THIRD of the character's width. Give it a
visible inner wall so it reads as a real opening bored through solid material,
lit consistently with the rest of the scoop. No eyes, no mouth, no facial
features of any kind — the hole is empty.

STYLE: photorealistic 3D confectionery product render — the look of a premium
food photograph, with real material, real subsurface and real micro-texture.
Not illustration, not clay, not cel-shaded. It has to sit beside photoreal
cookies, doughnuts and waffles as if shot in the same studio. The cup carries a
crisp golden waffle lattice.

LIGHTING: one soft key light from the UPPER LEFT at about 45 degrees, with a
cooler, dimmer fill from the lower right. Highlights on the upper-left of the
scoop; the terminator and the deepest occlusion on the lower-right and under
the cup's rim.

DO NOT: do not draw a cone, the base is a shallow bowl. Do not add a
background, surface, table or scene — the character floats alone. Do not add a
cast shadow or drop shadow. Do not add a face, eyes or a mouth. Do not add
sprinkles, spoons, cherries, text or logos. Do not add glow, bloom or a halo
outside the silhouette.

OUTPUT: the character alone, centred, on a fully transparent background, square
canvas, highest resolution available. Crisp anti-aliased edge, no colour
fringe, no matte line. Deliver the PNG file itself, with real alpha — not a
screenshot or a preview of it.
```

**Cyan Sherbert** — replaces `after_skinz_cyan_sherbert_ice_cream.png`

```
Create a single 3D-rendered ice cream character on a transparent background.
It is one layer of a composited collectible artwork: a photorealistic ice cream
with a round hole punched through its scoop, into which a cartoon face is
composited later.

THE FLAVOUR is cyan sherbert — a vivid cyan scoop with the slightly icy, granular surface of
sherbert rather than the smooth fat of ice cream, with a thick cyan melt drip
over a shallow golden waffle cup.

BUILD IT TO THESE PROPORTIONS. They are the point of the image, and they are
NOT the usual ice-cream proportions — read them literally:

- Take the character's total height as 100%.
- The SCOOP is the top 86% of that height.
- The WAFFLE CUP is only the bottom 14%. It is a shallow, flat-bottomed wafer
  bowl that the scoop sits down into — the height of a tuna tin. It must NOT be
  a cone. It must NOT be a tall cup. If it looks like a normal ice cream cone,
  it is wrong.
- The finished character is about as TALL as it is WIDE — roughly square in its
  bounding box, dominated by one huge round scoop.
- The hole therefore lands near the MIDDLE of the total height, about 45% down
  from the crown of the scoop. That is the test: the distance from the top of
  the scoop down to the hole's centre, and the distance from the hole's centre
  down to the bottom of the cup, should be close to equal.

THE SCOOP: one single generous, round, dome-shaped scoop, as wide as the whole
character, with a soft irregular lower edge where it overhangs the cup.

THE HOLE: a clean circular hole punched right THROUGH the front of the scoop,
fully transparent inside, centred horizontally and centred in the scoop's own
height. Its diameter is about ONE THIRD of the character's width. Give it a
visible inner wall so it reads as a real opening bored through solid material,
lit consistently with the rest of the scoop. No eyes, no mouth, no facial
features of any kind — the hole is empty.

STYLE: photorealistic 3D confectionery product render — the look of a premium
food photograph, with real material, real subsurface and real micro-texture.
Not illustration, not clay, not cel-shaded. It has to sit beside photoreal
cookies, doughnuts and waffles as if shot in the same studio. The cup carries a
crisp golden waffle lattice.

LIGHTING: one soft key light from the UPPER LEFT at about 45 degrees, with a
cooler, dimmer fill from the lower right. Highlights on the upper-left of the
scoop; the terminator and the deepest occlusion on the lower-right and under
the cup's rim.

DO NOT: do not draw a cone, the base is a shallow bowl. Do not add a
background, surface, table or scene — the character floats alone. Do not add a
cast shadow or drop shadow. Do not add a face, eyes or a mouth. Do not add
sprinkles, spoons, cherries, text or logos. Do not add glow, bloom or a halo
outside the silhouette.

OUTPUT: the character alone, centred, on a fully transparent background, square
canvas, highest resolution available. Crisp anti-aliased edge, no colour
fringe, no matte line. Deliver the PNG file itself, with real alpha — not a
screenshot or a preview of it.
```

**Pink Sherbert** — replaces `after_skinz_pink_sherbert_ice_cream.png`

```
Create a single 3D-rendered ice cream character on a transparent background.
It is one layer of a composited collectible artwork: a photorealistic ice cream
with a round hole punched through its scoop, into which a cartoon face is
composited later.

THE FLAVOUR is pink sherbert — a hot pink scoop with an icy granular sherbert surface and a
thick pink melt drip over a shallow golden waffle cup.

BUILD IT TO THESE PROPORTIONS. They are the point of the image, and they are
NOT the usual ice-cream proportions — read them literally:

- Take the character's total height as 100%.
- The SCOOP is the top 86% of that height.
- The WAFFLE CUP is only the bottom 14%. It is a shallow, flat-bottomed wafer
  bowl that the scoop sits down into — the height of a tuna tin. It must NOT be
  a cone. It must NOT be a tall cup. If it looks like a normal ice cream cone,
  it is wrong.
- The finished character is about as TALL as it is WIDE — roughly square in its
  bounding box, dominated by one huge round scoop.
- The hole therefore lands near the MIDDLE of the total height, about 45% down
  from the crown of the scoop. That is the test: the distance from the top of
  the scoop down to the hole's centre, and the distance from the hole's centre
  down to the bottom of the cup, should be close to equal.

THE SCOOP: one single generous, round, dome-shaped scoop, as wide as the whole
character, with a soft irregular lower edge where it overhangs the cup.

THE HOLE: a clean circular hole punched right THROUGH the front of the scoop,
fully transparent inside, centred horizontally and centred in the scoop's own
height. Its diameter is about ONE THIRD of the character's width. Give it a
visible inner wall so it reads as a real opening bored through solid material,
lit consistently with the rest of the scoop. No eyes, no mouth, no facial
features of any kind — the hole is empty.

STYLE: photorealistic 3D confectionery product render — the look of a premium
food photograph, with real material, real subsurface and real micro-texture.
Not illustration, not clay, not cel-shaded. It has to sit beside photoreal
cookies, doughnuts and waffles as if shot in the same studio. The cup carries a
crisp golden waffle lattice.

LIGHTING: one soft key light from the UPPER LEFT at about 45 degrees, with a
cooler, dimmer fill from the lower right. Highlights on the upper-left of the
scoop; the terminator and the deepest occlusion on the lower-right and under
the cup's rim.

DO NOT: do not draw a cone, the base is a shallow bowl. Do not add a
background, surface, table or scene — the character floats alone. Do not add a
cast shadow or drop shadow. Do not add a face, eyes or a mouth. Do not add
sprinkles, spoons, cherries, text or logos. Do not add glow, bloom or a halo
outside the silhouette.

OUTPUT: the character alone, centred, on a fully transparent background, square
canvas, highest resolution available. Crisp anti-aliased edge, no colour
fringe, no matte line. Deliver the PNG file itself, with real alpha — not a
screenshot or a preview of it.
```

### The v2 prompt — edit an existing body

Attach **the current art for that flavour** as the reference — this is a
targeted edit, not a fresh generation, and everything above the cone should
survive it.

```
Edit this ice cream character. Keep the scoop EXACTLY as it is — same shape,
same size, same surface, same colour, same lighting, and the same round hole
punched through it in the same place. Change one thing only:

REPLACE THE TALL CONE WITH A SHALLOW WAFER CUP.

- The cone is currently about a third of the character's total height. It
  should be about an EIGHTH — a squat, flat-bottomed wafer cup that the scoop
  sits down into, not a cone the scoop perches on top of.
- Keep the golden waffle lattice texture and the same width where the scoop
  meets it. Just remove almost all of its height.
- Result: the finished character should be about as tall as it is wide, and the
  hole should end up close to the middle of its total height instead of a third
  of the way down. That is the entire point of this edit.

Keep everything else identical:
- Same key light from the UPPER LEFT at about 45 degrees, cooler fill from the
  lower right, deepest occlusion lower-right and under the cup's rim.
- The hole stays a real hole, punched right THROUGH the scoop, fully
  transparent inside, with its inner wall lit to match. No eyes, no mouth, no
  facial features.
- No background, no surface, no table, no cast shadow, no drop shadow.
- No sprinkles, spoons, cherries, text or logos.
- Photorealistic 3D confectionery render throughout — it has to sit beside
  photoreal cookies and doughnuts as if shot in the same studio.

OUTPUT: the character alone, centred, on a fully transparent background,
square canvas, highest resolution available. Crisp anti-aliased edge, no
colour fringe, no matte line. Deliver the PNG file itself, with real alpha —
not a screenshot or a preview of it.
```

Apply either prompt to all five: vanilla, neapolitan, rocky road, cyan
sherbert, pink sherbert. Then re-register (§7), **delete the `ice_cream` entry
from `CHAR_SCALE`**, and re-derive `CHAR_Y_ADJUST` — every one of those five
values is tuned to the current 1089px body and will be wrong for an 840px one.

### If neither prompt lands

This edit does not actually need a generator. The cup's width is unchanged by
shortening it, so compressing the straight lattice barrel vertically while
leaving the rounded base at native height joins at exactly its own width — no
seam, no correction. `scratchpad/shorten_cone.py` in the working session did
this and measured 812 x 850 at face-frac 0.442 (barrel 285px -> 45px). The cost
is honest and visible at 1:1: the waffle diamonds flatten by the same factor,
which reads as a foreshortened bowl rather than a defect, but it is not free.
Generated art is better if the generator will produce it.

## 4. Ice cream v1 — the spec and the prompt

Non-negotiable, because the compositor pins the face:

- **Canvas 1393 × 1393**, transparent PNG, RGBA.
- **Face hole centred at (690, 601)**, **~255px across**. The skin ball covers
  ~312–325px after `ball_fit`, so 255 leaves a ~30px rim of scoop over the ball
  on each side — that rim is what sells the recess. Above ~290px the ball stops
  covering and background shows through.
- A **through hole**, not a painted-on recess: the body is drawn over the ball.
- **~815 wide × ~1090 tall**, face at **~0.345** of body height.

### The prompt

Attach the existing flavour's art as a style reference, paste this, then paste
one flavour block.

```
Generate a single character body for a 3D-rendered collectible series. It is
one layer of a composited NFT: a photorealistic ice cream with a round hole
punched through its scoop, into which a cartoon face is composited later.

STYLE: photorealistic 3D confectionery product render, the look of a premium
food photograph — real material, real subsurface, real micro-texture. Not
illustration, not clay, not cel-shaded. It must sit beside photoreal cookies,
doughnuts and waffles as if shot in the same studio.

PROPORTIONS:
- A GENEROUS, ROUND scoop and a SHORT, STUBBY waffle cup of a cone. Chunky and
  characterful, not a tall elegant cone.
- The hole sits at the centre of the scoop, and the scoop dominates the body.

THE FACE HOLE:
- A clean circular hole punched right THROUGH the front of the scoop, centred
  horizontally, with fully transparent pixels inside it.
- Give the hole a visible inner wall / bevel so it reads as a real opening in a
  solid material, lit consistently with the rest of the scoop.
- No eyes, no mouth, no facial features of any kind. The hole is empty.

LIGHTING: one soft key light from the UPPER LEFT at about 45 degrees, with a
cooler, dimmer fill from the lower right. Highlights on the upper-left of the
scoop; the terminator and the deepest occlusion on the lower-right and under
the cone's rim. This is the collection's fixed key light.

DO NOT:
- Do not add a background, surface, table, or scene. The character floats alone.
- Do not add a cast shadow or drop shadow.
- Do not add a face, eyes, or a mouth.
- Do not add sprinkles, wafers, spoons, cherries, text or logos unless the
  flavour block below asks for them.
- Do not make the cone long or tapered to a fine point — short and stubby.
- Do not add glow, bloom, or a halo outside the silhouette.

OUTPUT: the character alone, centred, on a fully transparent background,
square canvas, highest resolution available. Crisp anti-aliased edge, no
colour fringe, no matte line. Deliver the PNG file itself, with real alpha —
not a screenshot or a preview of it.

>>> FLAVOUR <<<
```

### Flavour blocks

**Vanilla**
```
FLAVOUR: classic vanilla. A pale cream scoop with a soft matte surface and
fine flecks of vanilla bean, sitting in a golden waffle cone with a crisp
lattice pattern. A gentle melt drip over the cone's rim.
```

**Neapolitan**
```
FLAVOUR: neapolitan. One scoop split into three vertical bands — chocolate,
vanilla and strawberry — meeting cleanly, in a golden waffle cone. Keep the
three-band split clearly readable at thumbnail size.
```

**Rocky Road**
```
FLAVOUR: rocky road. A dark chocolate scoop studded with mini marshmallows and
chocolate chunks breaking the surface, in a golden waffle cone. Keep the
inclusions chunky and few rather than dense and busy.
```

**Cyan Sherbert**
```
FLAVOUR: cyan sherbert. A vivid cyan scoop with the slightly icy, granular
surface of sherbert rather than the smooth fat of ice cream, with a thick
cyan melt drip over a golden waffle cone.
```

**Pink Sherbert**
```
FLAVOUR: pink sherbert. A hot pink scoop with an icy granular sherbert
surface and a thick pink melt drip over a golden waffle cone.
```

## 5a. Gummy bear v2 — the same problem, in the legs

The bears have the ice creams' defect in a milder form, and the four are
strikingly consistent about it:

| | Body | Aspect | Hole | Above hole | Below hole | Face-frac |
|---|---|---:|---:|---:|---:|---:|
| Cyan | 664 × 871 | 1.31 | 233 | 335 | 535 | 0.384 |
| OG | 663 × 888 | 1.34 | 237 | 341 | 546 | 0.384 |
| Pink | 655 × 866 | 1.32 | 235 | 333 | 532 | 0.384 |
| Purple | 661 × 871 | 1.32 | 234 | 335 | 532 | 0.384 |
| **Cast median** | **700 × 747** | **1.07** | — | 366 | 381 | **0.490** |

Everything **above** the hole is already right — 336px of head and ears against
the cast's 366. What is wrong is below it: 535px of torso and legs against the
cast's 381, which makes the bear an elongated 1.32 where the cast is a compact
1.07, and drops the face to 0.384.

Take ~23% out of the body below the hole and widen slightly:

| Below-hole | Body | Aspect | Face-frac |
|---:|---|---:|---:|
| 535 (today) | 660 × 872 | 1.32 | 0.384 |
| 444 | 700 × 780 | 1.11 | 0.431 |
| **411** | **700 × 747** | **1.07** | **0.450** |
| 384 | 700 × 720 | 1.03 | 0.467 |

At 700 × 747 the bear *is* the cast median, so **`CHAR_SCALE["gummy_bear"] =
0.881` can be deleted** — and since the bears currently render at 582px wide,
dropping the scale while widening the art takes them to 700px, a 20% gain.

The ceiling here is taste rather than arithmetic: 0.49 is reachable at 686px
tall, but that is a perfectly square bear and reads squashed. 0.45 keeps the
gummy-bear silhouette.

### The v2 prompt

Attach **the current art for that colour** as the reference — a targeted edit,
not a fresh generation.

```
Edit this gummy bear character. Keep the head, the ears, and the round hole
punched through it EXACTLY as they are — same shape, same size, same surface,
same colour, same lighting, same hole in the same place. Change one thing only:

MAKE THE BODY BELOW THE HOLE SHORTER AND THE WHOLE BEAR SLIGHTLY WIDER.

- The torso and legs below the hole are too long: the bear currently stands
  about a third taller than it is wide. It should be barely taller than it is
  wide — squat and chunky, the proportions of a real gummy bear.
- Take roughly a quarter of the height out of everything BELOW the hole. Shorten
  the torso, and make the legs stubbier and more tucked. Do not shrink the head
  or the ears, and do not move or resize the hole.
- Widen the whole bear by a few percent so it reads solid rather than slim.
- Result: the hole should end up close to the middle of the character's total
  height instead of a third of the way down. That is the entire point of this
  edit.

Keep everything else identical:
- Translucent gelatin with real subsurface scattering, slightly tacky glossy
  surface, fine condensation beading, a few tiny internal bubbles. Not opaque,
  not plastic.
- Same key light from the UPPER LEFT at about 45 degrees, cooler fill from the
  lower right, deepest occlusion under the arms, between the legs and along the
  lower-right rim.
- The hole stays a real hole, punched right THROUGH the body, fully transparent
  inside, with its inner wall lighter and more saturated where the candy is
  thin. No eyes, no mouth, no muzzle, no nose.
- No background, no surface, no table, no cast shadow, no drop shadow.
- No sugar coating, wrappers, text or logos.

OUTPUT: the character alone, centred, on a fully transparent background,
square canvas, highest resolution available. Crisp anti-aliased edge, no
colour fringe, no matte line. Deliver the PNG file itself, with real alpha —
not a screenshot or a preview of it.
```

Apply it to all four: OG, cyan, pink, purple. Then re-register (§7), **delete
the `gummy_bear` entry from `CHAR_SCALE`**, and re-derive `CHAR_Y_ADJUST` — the
four current values (32/43/47/50) are tuned to an 872px body at 0.881 and will
all be wrong for a 747px body at native scale.

Note the bears are already `BODY_OVER_SKIN_CHARS`, so the skin draws first and
shows through the hole exactly as it does now. No layering change.

## 5. Gummy bear v1 — the spec and the prompt

The bears' **proportions are already right** — unlike the ice creams, there is
nothing to fix in the geometry. What a regeneration buys is render quality, a
consistent family, and a socket rim to match the new ice creams.

Measured, current art:

| | Body W × H | Hole | Face down the body |
|---|---|---|---|
| All four bears | ~660 × 875 | 233–237px at (694, 594) | 0.384 |

They run at `CHAR_SCALE["gummy_bear"] = 0.881` to put their feet on the same
1111 line as the ice-cream cone tips.

**Spec for new art — authored to work at native scale, no `CHAR_SCALE`:**

- **Canvas 1393 × 1393**, transparent PNG, RGBA.
- **Face hole centred at (690, 601)**, **~240px across** — same family as the
  ice creams and doughnuts.
- **~625 wide × ~825 tall**, which with the hole pinned puts the **top of the
  ears near y = 285** and the **soles of the feet near y = 1110**.
- A **through hole**, and the body draws over the ball (`BODY_OVER_SKIN_CHARS`
  already lists `gummy_bear`, so no filename change is needed).

### The prompt

Attach the existing bear's art as a style reference, paste this, then paste one
colour block.

```
Generate a single character body for a 3D-rendered collectible series. It is
one layer of a composited NFT: a photorealistic gummy bear with a round hole
punched through its torso, into which a cartoon face is composited later.

STYLE: photorealistic 3D candy render — translucent gelatin with real
subsurface scattering, so light entering the upper left glows through the mass
and comes out warmer and deeper on the lower right. A slightly tacky, softly
glossy surface with fine condensation beading and a few tiny internal bubbles.
Not illustration, not plastic, not cel-shaded. It must sit beside photoreal
cookies, doughnuts and ice creams as if shot in the same studio.

PROPORTIONS:
- The classic squat gummy-bear silhouette: rounded head with two small ear
  buttons, no neck, stubby arms held against the sides, short splayed legs,
  seated-forward stance, front-on and symmetrical.
- Chunky and compact, noticeably taller than it is wide but not elongated.

THE FACE HOLE:
- A clean circular hole punched right THROUGH the body, centred horizontally,
  sitting where the head meets the chest — a little above the middle of the
  body's height, with fully transparent pixels inside it.
- Give the hole a visible inner wall so it reads as a real opening bored
  through translucent candy: the gelatin should be lighter and more saturated
  where it is thin around the rim, exactly as real gummy does.
- No eyes, no mouth, no facial features of any kind. The hole is empty.

LIGHTING: one soft key light from the UPPER LEFT at about 45 degrees, with a
cooler, dimmer fill from the lower right. Specular highlights on the
upper-left of the head, ears, shoulders and knees; the deepest occlusion under
the arms, between the legs and along the lower-right rim, with a rim light
picking that edge back out. This is the collection's fixed key light.

DO NOT:
- Do not add a background, surface, table, or scene. The character floats alone.
- Do not add a cast shadow or drop shadow.
- Do not add a face, eyes, a mouth, a muzzle or a nose.
- Do not add sugar coating, wrappers, text or logos.
- Do not make it opaque — the translucency is the whole material.
- Do not add glow, bloom, or a halo outside the silhouette.

OUTPUT: the character alone, centred, on a fully transparent background,
square canvas, highest resolution available. Crisp anti-aliased edge, no
colour fringe, no matte line. Deliver the PNG file itself, with real alpha —
not a screenshot or a preview of it.

>>> COLOUR <<<
```

### Colour blocks

**OG Gummy Bear**
```
COLOUR: a multi-colour gradient bear — hot pink through the head and
shoulders, blending through violet in the middle to cyan at the feet. Keep the
transitions smooth and the whole thing candy-bright.
```

**Cyan Gummy Bear**
```
COLOUR: a single vivid cyan gummy, evenly coloured through the whole body, with
strong light transmission so the thin parts (ears, arms, feet) glow brighter
than the mass.
```

**Pink Gummy Bear**
```
COLOUR: a single hot pink gummy, evenly coloured through the whole body, with
strong light transmission so the thin parts (ears, arms, feet) glow brighter
than the mass.
```

**Purple Gummy Bear**
```
COLOUR: a single deep violet-purple gummy, evenly coloured through the whole
body, with strong light transmission so the thin parts glow brighter than the
mass and keep the purple from going muddy.
```

## 6. Accepting a result

- [ ] **A real PNG with real alpha.** Ask again if what comes back is a JPEG or
      a screenshot — see §7, this cost real quality on the ice creams.
- [ ] **Hole is genuinely transparent**, roughly the specified diameter, with a
      visible inner wall.
- [ ] **No facial features** in the hole.
- [ ] **Lit from the upper left**, terminator lower-right.
- [ ] **Photoreal**, matching the cookies and doughnuts.
- [ ] **Clean transparent edge**, no baked shadow, no halo.

## 7. Getting it into the pipeline

`register_trait.py` handles skins, eyes and mouths but **not characters** — a
character needs its face hole landed on (690, 601), which is a different
registration. The ice-cream pass used a one-off script that keys the image,
resizes to 1393², and translates the hole centre onto the ball centre; the same
script covers bears with a new filename map.

Then:

```bash
python3 asset_assessment/build_char_compat.py    # dominant colours changed
python3 asset_assessment/verify_placement.py     # geometry, exits non-zero
python3 asset_assessment/audit_art_quality.py characterz
python3 asset_assessment/build_mint.py --n 400 --seed 7
```

`CHAR_Y_ADJUST` is the per-character trim onto the shared 1111 line and will
need re-deriving for any body whose height changed.

**Insist on the PNG.** The five ice creams came back as JPEGs of the
generator's *preview*, with the transparency already flattened onto a grey/white
checkerboard and then JPEG-compressed. That is recoverable — the checker is
achromatic and two-valued, so a connected key plus an un-premultiply against the
checker level lifts it cleanly — but it costs the true anti-aliased alpha and
bakes compression noise into the edge. The art in the repo today carries that
loss. If sharper sources ever arrive, re-registering them is a ten-minute job.
