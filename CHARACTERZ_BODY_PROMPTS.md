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

## 4. Ice cream — the spec and the prompt

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

## 5. Gummy bear — the spec and the prompt

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
