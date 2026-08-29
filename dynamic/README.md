# `dynamic/` — the weather pass, baked into 444 tokens

**The weather is not live.** It was designed as a live overlay and it is
not one any more: `build_mint.py` draws a state once, at exact counts, and
`bake_weather.py` renders it into that token's own still and loop. From
then on it is a permanent trait like the arms or the footwear, and the
files never change.

That pivot deleted more than it added. Gone: the Open-Meteo client, the
WMO code table, the locale question, the 30-minute cache, the alert feed,
the "what happens when the API is down" fallback, and the whole worry about
marketplaces caching a sky that has since changed. What is left is a
renderer and 444 files.

    444 of 4,444 (10%) carry weather:
      rain 110 · snow 95 · fog 80 · storm 75 · blizzard 40 · flooded 30 · tornado 14

`solar.py` and the eight sky phases still exist and still work, but they
are no longer on the mint path — everything bakes at one phase (see
`bake_weather.py`, `DEFAULT_PHASE`).

## The rule

> The effect touches the **background plate and nothing else**. Body, skin
> ball, eyes, mouth, arms, footwear, stickers and the paired background
> overlays composite on top exactly as minted, pixel for pixel.

`verify_sky.py` asserts this numerically over every phase × weather ×
sample token, and it is not an approximation — protected pixels come back
**bit-identical**, and alpha is preserved bit-for-bit, the same discipline
`shade_skin_balls.py` and `shade_eyes.py` hold to.

### One exception, and it is checked rather than waived

**`flooded` is the only state that touches the character**, below its
waterline. It has to: water the figure stands *in front of* is a puddle
backdrop, not a flood, and the ask was a character submerged in it. So the
water runs **after** the protect blend, over the finished frame.

Everything about the exception is bounded, and `sky.touches_character()`
makes it a thing code can ask about rather than a name to remember:

- **Above the highest the water can ever reach, the rule still holds
  exactly** — bit-identical protected pixels, and `verify_sky.py` runs that
  check instead of skipping the state. Measured: 335,471 protected pixels
  above the line, unchanged; 176,573 below it, changed on purpose.
- **Alpha is never touched, at any depth.** That is not a taste question —
  the whole cast's face geometry is registered to it.
- **The water stays off the face.** `sky.waterline()` derives its bounds
  from the config rather than declaring them beside it, and the gate fails
  if the water reaches the face hole's underside at 0.52 of the canvas.
  Drowning the one part of the token a holder looks at is not a flood, it
  is a deleted character.

If you need the old guarantee unconditionally — "no state ever alters a
minted pixel" — the way to keep it is to not ship this state, not to
soften it. Half-submerging a character while claiming the art is untouched
would be the worst of both.

## Why it is a grade, not a re-render

A full composite is **~2s and needs all 441MB of `traits/`**, so re-running
`generator.py` per image request is not viable. Instead the pass is a pure
function of the plate region of a *finished* token:

    out = base * protect  +  effect(base) * (1 - protect)

`create_image(..., mask_path=...)` writes the `protect` mask at mint-build
time — the union of every layer except `layers[0]`. It is written there
because that is the only place the silhouette is known for free; recovering
it from the finished PNG would mean segmenting the art. **The masks measure
36KB mean**, so all 4,444 add ~156MB. `build_mint.py --render --masks` is
what actually writes them; without that flag the pass has no input.

Two consequences:

- The grounding shadow and the subject-separation pocket are baked into the
  plate pixels, so they grade **with** the plate. That is correct — they are
  stage, not character.
- Weather particles are drawn into the effect layer, so the same mask puts
  them **behind** the character. There is deliberately no in-front pass.

## The key light does not move

`CLAUDE.md` pins the key to the upper left and all 123 trait assets are
authored to it. A night render that *relit* the scene would take every
character out of register with the cast. So solar altitude drives exposure,
contrast, saturation, split-tone and vignette — **never a new light
direction**. What falls down-and-right (rain lean, vignette weighting)
follows the existing convention rather than fighting it.

## Altitude, not the clock

`solar.py` is the NOAA solar position algorithm: closed form, so the
time-of-day half needs **no API, no key and no rate limit**. Only weather
needs a network call.

18:00 is a different sky in Reykjavik and Singapore, and a different sky in
June and December. −6° is blue hour everywhere, always. That is why the
phase bands are the standard astronomical twilight definitions and not a
table of sunset times.

Dawn and dusk sit at the **same** altitude, so they are split on the sign of
dAlt/dt. It is the most visible distinction in the grade table — morning
light is rose and paler, evening light amber and deeper.

## `day` is deliberately the identity grade

It is the grade the plates were approved at in `ULTIMATE_GRADE_LOG.md`, and
it covers most of every holder's waking hours. The dynamic layer should read
as a reward for checking in at dusk, not as a filter permanently laid over
the owner's art.

It is also the most-requested state, so it short-circuits: **3ms**, versus
~550ms for a grade that actually runs. Two identities do most of the rest of
the saving — a *scalar* exposure applied as a luma ratio is just a scalar
multiply, and saturation-about-luma is luma-preserving, so the split-tone
reuses that luma instead of recomputing it.

## There is no `clear` state

A clear sky is the **absence of weather**, not a weather worth grading. The
minted token already *is* the clear-sky render, so a `clear` state would be
a name for doing nothing. Every function in `sky.py` takes `None` where a
state name goes, and `is_identity()` returns True for it.

Under the baked model this is simply the other 4,000 tokens: they are
minted, they are stills, and nothing in `dynamic/` ever touches them.

## Four ordinary states, then three that are an event

**Four** named states cover the ordinary sky. That was the ceiling when the
states had to be derived from ~100 WMO codes, and it survives the pivot for
the same reason it was set: past four they stop reading as distinct traits
and start reading as noise. As a rarity tier it also happens to be the
right shape — the ordinary states take 360 of the 444 and the event states
take 84.

**`overcast` was the fifth and is retired.** It was the weakest state in
the table by every measure taken here: dE 3.3 from `rain` and 4.8 from
`snow` on the plate, closer to both than `DISTINCT_DE` would let a *new*
state be. And what it drew was a mild grey grade with a drifting shadow —
a filter over the art rather than weather happening in it. Every state
that survived puts something **in** the frame: a fog bank, falling
particles, a drift, a funnel, a waterline. A cloudy sky puts nothing
there, and it is what most of the world has most of the time, so it was
also the state most likely to sit permanently over a holder's plate for
nothing. WMO 2 and 3 map to `None` now, alongside the clear codes — the
honest mapping for a sky the art has nothing to draw for is the same as
for a sky with nothing in it.

**`blizzard` and `tornado` sit outside that ceiling on purpose**, because
they are not more of the same. A holder sees `rain` most weeks of the year
and a blizzard a handful of times, so a state that reads as an EVENT does
not add to the noise the ceiling exists to stop. What they must not do
is arrive by accident, and each is gated on more than a code — in opposite
directions:

- **The severe three are not more weather, they are an event.** When the
  states were derived from a live feed this mattered because `blizzard`
  needed snow *and* wind, and `tornado` and `flooded` had no WMO code at
  all — flooding is a consequence of rain over hours, terrain and drainage,
  not a reading of the sky at an instant. None of that is a problem any
  more: the states are **allocated**, not derived. `WEATHER_COUNTS` in
  `build_mint.py` decides how many of each exist, and being un-derivable
  from a weather API is no longer a reason for a state not to exist.


**Fog is nearly free and always was**: the mask means the plate can be
hazed while the character is not, which is literal atmospheric
perspective. The character pops forward without a pixel of it changing.
`blizzard` is the same trick at the other end of the scale — the plate goes
toward white while the character does not move a pixel.

**The tornado is the one state that is a shape rather than a field.** Every
other weather changes the whole plate uniformly; a funnel is an object
standing in it, which is why it reads as the rarest thing in the set. Three
things follow, and none of them are optional:

- It is **lit at 45° from the upper left**, like everything else in the
  collection. Two components: the cylinder turning away from the light
  across its width, and the light coming from *above* down its length.
  With only the first it was lit from due left — correct in x, flat in y,
  and measurably brighter at the bottom than the top. Measured over the
  trunk it now grades 0.71 upper-left → 0.55 lower-right, and the rim
  fades toward the tip where the light rakes past rather than catching it.
  (It was briefly lit from the *right*: the polarity was written when the
  funnel's tint was dark and did not follow when the tint went pale.)
- It is **placed off the face column**. The character composites at a fixed
  canvas position around x=690 of 1393 and the mask puts the whole effect
  behind it, so a centred funnel is a tornado you cannot see. It is seeded
  to the left or right edge, and `verify_sky.py` measures what fraction
  actually survives the mask rather than trusting the arithmetic (worst 81%
  over 3 tokens × 12 seeds, floor 60%).
- It needs **two tints, not one**. The column is condensation and is *paler*
  than the supercell grade behind it, which is what keeps it visible from
  high noon to night — a dark funnel vanishes into a dark sky the moment the
  sun goes down. Its debris is dirt and is darker than everything. Share one
  tint and the debris turns into pale bubbles floating beside the trunk.
- Its debris is sized as a **fraction of the canvas**, like the funnel it
  orbits. Absolute pixel sizes come out 2.7× oversized in the 512px loops
  everyone actually watches, and the grit starts reading as boulders.

Particles are stylised, not photoreal — the cast is flat cartoon over lit
spheres, and photoreal rain in front of a Twinkie reads as a compositing
error. They are seeded by token id, so a token's rain always falls the same
way: it is *that token's* weather, not a new random field every refresh.

## Weather animates; the grade does not

`animate.py` renders each weather state as a seamless loop. The structural
point is that **almost none of the cost moves**: the tone grade, the haze
and the diffusion are identical in every frame, so a loop is ONE graded
plate plus N cheap frames — measured at ~40ms once, then ~35ms per frame at
512px.

That is also the production path. A live view does not need a video: it
needs the single graded still plus a particle pass in a canvas, which is
what makes an `animation_url` page small enough to be worth shipping. The
exported loops run 160–460KB at 512px.

Every motion loops **seamlessly**, and `verify_sky.py` gates it — the frame
at t=1 must be bit-identical to the frame at t=0. A jump at the wrap is the
one thing that makes an ambient effect look cheap, and it is invisible in a
filmstrip; only a numeric check catches it.

| state | motion |
|---|---|
| `fog` | a ground bank whose top edge rolls; the sky above stays sharp |
| `rain` | two depth bands falling down-and-right, near band 2x faster |
| `snow` | slow fall with a sideways sway, one cycle per loop |
| `storm` | heavy rain, plus a lightning strike and its echo |
| `blizzard` | driven snow over a whiteout band, on settled drifts |
| `tornado` | the funnel snakes once, its banding climbs three times, the debris orbits twice and more blows past |
| `flooded` | the surface rolls and the refraction wobbles beneath it |

**A motionless state is never exported as an animation.** Encoding N
identical frames of a still spends a downscale and a lossy round-trip to
say nothing at all. Since a clear sky became `None` rather than a state,
**every named state moves**, and `verify_sky.py` gates it from both sides:
no weather must apply no spatial op and must return the mint bit-for-bit at
`day`, and a named state that did not move would be a state for doing
nothing — which is exactly what `clear` was.

The same rule belongs in the service: check `is_identity()` FIRST and serve
the **original minted bytes** rather than re-encoding them. The dynamic
layer must not cost image quality in the state where it is doing nothing —
and that is the state most holders are in most of the time.

Worth knowing: the dark phases *do* soften the plate's micro-contrast
(measured 54% of the mint's brightness-normalised detail at `night`), but
that is the **sky grade** — deliberate flattening, black lift and a strong
shadow tint — and nothing to do with the weather trait. `SKY_STATES` is
where to dial it if it goes too far.

The loops are built on a torus: particles travel a **whole number of tiles**
per loop, sway uses an integer number of cycles, the fog field is rolled by
exactly its own width, and the funnel's sway, banding, orbit and rise are
all integer cycles. The streak lean is *derived* from that tile geometry
rather than set by hand, so streaks always point along the direction they
actually travel — rain's `(1, 3)` lands at 1/3, steeply down and to the
right, and the blizzard's `(3, 1)` at 3, a shallow drive the same way. Both
match the cast-shadow convention rather than fighting it; wind blowing the
other way would fight the key light.

## Will the loops play on marketplaces and wallets?

Partly, and the format decides it. Solana metadata carries an animated
asset in `animation_url`, with `properties.category` and a mime-typed entry
in `properties.files[]`.

| format | verdict |
|---|---|
| **MP4 (H.264, yuv420p)** | the safest bet, and also the smallest here — 80–400KB against WebP's 300–987KB |
| animated WebP | plays in every browser, but marketplace *image pipelines* commonly re-encode and flatten it to frame 1 |
| GIF | universally supported and the worst-looking: 256 colours band these graded plates, and it came out at ~6MB a loop |
| HTML | richest, least supported — wallets sandbox or refuse it |

`write_mp4()` pins yuv420p and even dimensions deliberately. A stream in
yuv444p or with an odd dimension is what a hardware decoder or a phone
refuses, and it fails as a **black frame** rather than as an error.

`asset_assessment/verify_media.py` now checks that from the bytes, and the
exports come back: **H.264 Main profile, level 2.2, yuv420p, 512×512,
faststart (`moov` before `mdat`) on all seven**. Main profile is what makes
the pixel format provable without decoding anything — `chroma_format_idc`
only exists in the SPS for the *High* profiles, so Baseline/Main/Extended
infer 4:2:0 by definition. Level 2.2 is far under the 4.0 where hardware
support starts thinning.

It also decodes each loop and checks the **encoded** wrap, which
`verify_sky.py` cannot: that one proves the *source* frames at t=0 and t=1
are bit-identical, but the encoder is lossy and could still put a visible
step at the loop point. Measured, the wrap is 1.1–11.3 /255 depending on
the state and always in proportion to the motion around it.

**None of that proves a marketplace plays them.** Support differs per
surface and changes without notice; the only honest test is one real token
on Phantom, Magic Eden and Tensor. What the checks buy is that when it
fails there, the file and the JSON are not the reason.

Three things hold regardless of format:

- **`image` must stay a still PNG.** Every grid, thumbnail, search result
  and notification uses `image`. Animation only ever plays in the detail
  view, often only on hover or click. `verify_media.py` fails a metadata
  file whose `image` points at an mp4.
- **The bare `animation_url` is not enough on Solana.** It needs the
  Metaplex `properties` block beside it — `files[]` typed by mime, and
  `category: "video"` — because surfaces differ in which they read.
  `token_metadata(animation_url=...)` builds both together for that
  reason. Worth knowing: `category` is **not** a typed field of the
  Metaplex standard. It rides the `JsonMetadata` type's open index
  signature — convention the marketplaces read, not schema.
- **Caching is the real ceiling, not playback.** Marketplaces cache media
  hard, and Solana has no ERC-4906-style "metadata changed" event to nudge
  them. A loop showing *live* weather will show whatever the weather was
  when they cached it. Live state belongs on your own site; a marketplace
  gets a good-looking snapshot.
- **Test one token before committing 4,444.** Support differs per surface
  and changes without notice; this table is a starting point, not a
  guarantee.

## Locale was a property of the token, and is not one any more

The old design needed a locale per token and could not get one honestly —
a render request arrives from a marketplace's servers, not from a holder —
so it was going to be *claimed*, reset on transfer, and rate-limited so
rare skies could not be farmed.

None of that survives. The weather is drawn at mint, by the allocator, at
exact counts nobody can influence. **Rare skies cannot be farmed because
there is nothing to farm**: a tornado is 14 of 4,444 and it was decided
before anyone owned anything.

## Usage

```bash
pip install pillow numpy scipy

python3 dynamic/solar.py                          # one instant, six cities
python3 dynamic/render.py --tokens 3 --sheet      # mint samples + sheets
python3 dynamic/render.py --variety 6             # one token per plate
python3 dynamic/animate.py                        # weather loops (mp4/webp)
python3 dynamic/verify_sky.py                     # THE GATE

python3 asset_assessment/make_weather_contact.py  # the approval sheet
python3 asset_assessment/verify_media.py          # will the loops PLAY

# the mint, in two passes
python3 asset_assessment/build_mint.py --render --masks \
        --animation '{id}.mp4' --symbol SWEET --royalty-bps 500
python3 asset_assessment/bake_weather.py          # the 444 stills + loops
```

**Two passes on purpose.** `build_mint.py` composes and renders all 4,444
plus their protect masks; `bake_weather.py` then rewrites the still and
writes the loop for the 444 that drew a state. Separating them keeps the
expensive pass restartable — an interrupted bake costs one token, not the
whole mint — and keeps the weather render off the critical path of a mint
that has nothing to do with it.

`bake_weather.py` never reads its own output: the clear render is moved to
`images_clear/` on first bake and every later run starts from there, so
re-running cannot put a second flood on top of the first. Same discipline
as `shade_skin_balls.py`, for the same reason.

`--animation` is what closes the gap between a correct render and a holder
seeing it move. Without it the mint emits `name`, `description`, `image`
and `attributes` and nothing else — no `animation_url`, no `properties` —
so the loops would have displayed **nowhere**, on any surface, however
good the files were. `--symbol` and `--royalty-bps` have no defaults on
purpose: royalties and payout addresses are the owner's decision.

`make_weather_contact.py` is what decides whether a *new* state ships.
Note that its distinctness number is measured over the **plate region
only**, which understates `flooded` badly — the biggest thing that state
changes is the character, and the character is exactly what that
measurement excludes. It scores dE 11.7 against `rain` on the plate alone
and is unmistakable on the sheet.
`render.py --sheet` grades one token, which cannot answer either question
that matters: does the state hold across the plate **family**, and is it a
new trait or a second copy of one the set already has. So it renders every
state down a column of different plates and measures mean plate dE between
every pair, and exits non-zero if a state is not distinct from the one it
is most likely to be confused with. Current numbers, at dusk over 6 plates:
`blizzard`/`snow` **44.8**, `tornado`/`storm` **19.3**, against a bar of
6.0 — which sits deliberately above the closest already-approved pair
(the tightest surviving pair at dusk, where the grade dominates them all).

**`build_mint.py --masks` is not optional if this ships.** `create_image()`
has taken `mask_path=` since the prototype landed and the mint did not pass
it, which left the pass with no input at collection scale. The masks
measure 36KB mean, ~156MB across 4,444.

`dynamic/proof/sheet_*.png` are committed as the design record; the
`token_*` / `var_*` inputs are regenerated artifacts and are git-ignored.

## What the pivot settled, and what is still open

Three of the four things this file used to list as undecided were
consequences of the weather being live. They are not questions any more:

- **Canonical or alternate view?** Settled. `image` is the *weathered*
  still at the full 1393 canvas and `animation_url` is the loop. The still
  had to carry the weather: a token whose trait says Tornado and whose
  thumbnail is a clear sky has its rarest attribute invisible in every
  grid, search result and notification.
- **Weather in `attributes`?** Settled, and reversed. The old answer was
  no — "a value that changes hourly will be indexed by rarity tools as
  though it were permanent". It *is* permanent now, so it belongs in
  `attributes` and in the rarity table, next to the arms.
- **How the severe states are sourced.** Gone. They are allocated at exact
  counts, not derived from a feed, so `tornado` is not US-skewed by which
  countries publish an alerts API — it is 14 tokens because
  `WEATHER_COUNTS` says 14.

Still open:

1. **One phase for all 444, or a second random axis?** Everything bakes at
   `blue_dusk` — the phase every proof sheet and contact sheet was judged
   at. Rolling the phase per token would multiply the variety and add a
   second rarity dimension, at the cost of doubling how many distinct
   looks a buyer has to learn and making the weather itself harder to read
   at a glance. `bake_weather.py --phase` changes it globally; making it
   per-token is a small change and a real design decision.
2. **`isMutable`.** Solana has no `baseURI` — each NFT carries its own
   `uri`, so the metadata must be right **before** mint or retrofitted one
   transaction per token. Nothing about a baked token changes after mint,
   which is an argument for locking it; keeping it mutable is still the
   only escape hatch if a URI ever has to move.
3. Whether the night grade's brightness gap is a bug or the look — see
   `sheet_variety_night.png`. Across the plate family it reads as a
   deliberate spotlight; on busy mid-key plates it reads flatter. Only
   matters if the phase is ever rolled per token.
