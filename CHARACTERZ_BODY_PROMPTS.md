# Character Body — AI Generation Prompt (Ice Creams)

A prompt for generating **replacement ice-cream body art**, and the measured
spec it has to hit.

Companion docs: `SKIN_ENHANCE_PROMPTS.md`, `EYEZ_ENHANCE_PROMPTS.md`,
`MOUTHZ_ENHANCE_PROMPTS.md`.

---

## 1. Why the art has to change (it cannot be fixed by scaling)

The ice creams read wrong for one measurable reason: **the face sits too high
on the body**, because the cone is long relative to the scoop.

| | Body W × H | Face position down the body |
|---|---|---|
| Cast (29 non-ice-cream characters) | 675 × 759 median | **0.49** — face at mid-body |
| Ice creams, as authored | 787 × 1067 median | **0.33** — face a third down |

Scaling cannot correct this. `CHAR_SCALE` scales about the ball centre, which
sits inside the face, so the body and the face shrink together and **the ratio
is mathematically unchanged** — 0.33 before, 0.33 after. Shrinking to 0.74 only
traded size away to buy a shorter cone below the face; the face still sits a
third of the way down.

So the two things that were in tension — "faces centred" and "not too small" —
are only in tension *because of the art*. A body with a bigger scoop and a
shorter cone gets both at native scale, with no `CHAR_SCALE` at all.

## 2. The spec the new art must hit

Non-negotiable, because the compositor pins the face:

- **Canvas 1393 × 1393**, transparent PNG, RGBA.
- **Face socket centred at (690, 601)** — the ball centre. Every other face
  layer is pinned there and nothing moves to follow a body that drifted.
- **Socket ~200px across** (current ice creams run 178–218px). The skin ball
  covers it at ~312–325px after `ball_fit`, so anything up to ~260px is safe;
  larger and a rim of background shows around the face.
- Ice creams are **`before_skinz`**: the ball is drawn *over* the body, so the
  face is a **recess/socket in the scoop**, not a hole cut through to nothing.

Target proportions, derived from the cast:

- **Body ~760 wide × ~800 tall** (cast median is 675 × 759; the ice cream may
  run slightly larger as a hero silhouette, but not 1067 tall).
- **Face at ~0.48 of body height from the top** — so with the socket pinned at
  y=601, the body top lands near **y=217** and the cone tip near **y=1017**.
- That means roughly **55% scoop, 45% cone** by height. The current art is
  closer to 35/65, which is what puts the face up in the corner.

## 3. The prompt

Attach the existing flavour's art as a style reference, paste this, then paste
one flavour block from §4.

```
Generate a single character body for a 3D-rendered collectible series. It is
one layer of a composited NFT: a photorealistic ice cream that will have a
cartoon face composited into a socket in its scoop.

STYLE: photorealistic 3D confectionery product render, the look of a premium
food photograph — real material, real subsurface, real micro-texture. Not
illustration, not clay, not cel-shaded. It must sit beside photoreal cookies,
doughnuts and waffles as if shot in the same studio.

PROPORTIONS — this is the point of the regeneration:
- A GENEROUS, ROUND scoop and a SHORT, STUBBY cone. Roughly 55% scoop to 45%
  cone by height. Chunky and characterful, not a tall elegant cone.
- The whole character should read as compact and wide-ish, about as tall as it
  is wide plus a little — not a tall thin column.
- The face socket must sit at about the MIDDLE of the body's height, not up in
  the scoop. This is the single most important requirement.

THE FACE SOCKET:
- A clean circular recess set into the front of the scoop, centred
  horizontally and sitting at mid-height of the whole character.
- Smooth, evenly lit inside, slightly darker than the surrounding scoop so it
  reads as a recess. A separate face layer is composited over it later.
- No eyes, no mouth, no facial features of any kind. The socket is empty.

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
colour fringe, no matte line. If you cannot output true transparency, render
on a flat pure green (#00FF00) field with no shadow, gradient or spill.

>>> FLAVOUR <<<
```

## 4. Flavour blocks

Paste one in place of `>>> FLAVOUR <<<`. Colours are the current art's.

**Vanilla** — `before_skinz_vanilla_ice_cream.png`
```
FLAVOUR: classic vanilla. A pale cream scoop with a soft matte surface and
fine flecks of vanilla bean, sitting in a golden waffle cone with a crisp
lattice pattern. A gentle melt drip over the cone's rim.
```

**Neapolitan** — `before_skinz_neopolitan_ice_cream.png`
```
FLAVOUR: neapolitan. One scoop split into three vertical bands — chocolate,
vanilla and strawberry — meeting cleanly, in a golden waffle cone. Keep the
three-band split clearly readable at thumbnail size.
```

**Rocky Road** — `before_skinz_rocky_road_ice_cream.png`
```
FLAVOUR: rocky road. A dark chocolate scoop studded with mini marshmallows and
chocolate chunks breaking the surface, in a golden waffle cone. Keep the
inclusions chunky and few rather than dense and busy.
```

**Mint Choc Chip** — `before_skinz_mint_chocolate_chip_ice_cream.png`
```
FLAVOUR: mint choc chip. A pale green scoop with dark chocolate shards through
it, in a golden waffle cone. Keep the green soft and creamy, not neon.
```

**Cyan Sherbert** — `before_skinz_cyan_sherbert_ice_cream.png`
```
FLAVOUR: cyan sherbert. A vivid cyan scoop with the slightly icy, granular
surface of sherbert rather than the smooth fat of ice cream, with a thick
cyan melt drip over a golden waffle cone.
```

**Pink Sherbert** — `before_skinz_pink_sherbert_ice_cream.png`
```
FLAVOUR: pink sherbert. A hot pink scoop with an icy granular sherbert
surface and a thick pink melt drip over a golden waffle cone.
```

**Zaffre Sherbert** — `before_skinz_zaffre_sherbert_ice_cream.png`
```
FLAVOUR: zaffre sherbert. A deep violet-blue scoop with an icy granular
sherbert surface and a thick purple melt drip over a golden waffle cone.
```

**Rainbow Sherbert** — `before_skinz_rainbow_sherbert_ice_cream.png`
```
FLAVOUR: rainbow sherbert. One scoop swirled from pink, cyan and purple
sherbert in soft folded bands, with a multi-coloured melt drip over a golden
waffle cone. Keep the three colours distinct rather than blended to mud.
```

## 5. Accepting a result

- [ ] **Face socket at mid-height**, not up in the scoop. This is the whole point.
- [ ] **Short stubby cone**, roughly 45% of the body height.
- [ ] **No facial features** in the socket.
- [ ] **Lit from the upper left**, terminator lower-right.
- [ ] **Photoreal**, matching the cookies and doughnuts.
- [ ] **Clean transparent edge**, no baked shadow, no halo.

## 6. Getting it into the pipeline

The generator will return the character at an arbitrary size and position.
`register_trait.py` handles skins, eyes and mouths but **not characters** —
a character needs its face socket landed on (690, 601), which is a different
registration. Bring the result back and it can be placed and re-measured with
`audit_placement.py` and `verify_placement.py`.

Once the new bodies are in, **delete the ice-cream entry from `CHAR_SCALE`** in
`generator.py`. The whole point of the new proportions is that they work at
native scale, so the 0.74 workaround should go with them, and `CHAR_Y_ADJUST`
should be re-derived scale-aware by `audit_placement.py`.
