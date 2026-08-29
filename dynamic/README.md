# `dynamic/` — time-of-day and weather, on the background only

A **prototype**, not a shipped feature. The renderer works and is verified;
what is not yet decided is where it runs (see *Open decisions*).

## The rule

> The effect touches the **background plate and nothing else**. Body, skin
> ball, eyes, mouth, arms, footwear, stickers and the paired background
> overlays composite on top exactly as minted, pixel for pixel.

`verify_sky.py` asserts this numerically over every phase × weather ×
sample token, and it is not an approximation — protected pixels come back
**bit-identical**, and alpha is preserved bit-for-bit, the same discipline
`shade_skin_balls.py` and `shade_eyes.py` hold to.

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
a name for doing nothing — and worse, something a service might re-encode a
copy of the mint to serve. `weather.py` returns `None` for WMO 0 and 1,
every function in `sky.py` takes `None` where a state name goes, and
`is_identity()` is what tells a service to hand back **the original minted
bytes**.

That is the state most holders are in most of the time, so it must cost the
plate nothing at all — and now it provably does, because there is nothing
there to run.

## Five ordinary states, then two that are an event

Open-Meteo (free, no key, takes lat/lon directly) returns ~100 WMO codes.
`weather.py` collapses them: **five** named states cover the ordinary sky,
past which they stop reading as distinct traits and start reading as noise
— drizzle and light rain are the same trait however different the code is.
Call once per *distinct locale* bucketed to ~25km and cache 30 min — 4,444
tokens is a few hundred real cities.

**`blizzard` and `tornado` sit outside that ceiling on purpose**, because
they are not more of the same. A holder sees `overcast` most weeks of the
year and a blizzard a handful of times, so a state that reads as an EVENT
does not add to the noise the ceiling exists to stop. What they must not do
is arrive by accident, and each is gated on more than a code — in opposite
directions:

- **`blizzard` is not a WMO code.** It is snow *and* wind, which Open-Meteo
  returns as separate fields, so it is derived: heavy snow at 35km/h, any
  snow at the NWS's own 56km/h. The NWS definition proper (56km/h sustained
  plus visibility under 400m for three hours) is a handful of tokens a year
  worldwide — rare enough that nobody would ever see the state.
- **`tornado` is not derivable from Open-Meteo at all.** There is no WMO
  code for one and no field that implies one; 99 is a thunderstorm with
  heavy hail, which is the closest the table gets and is still not a
  tornado. `classify()` never returns it — it comes from a severe-weather
  **alert feed** through `from_alert()`, or it is set by hand for a
  collection-wide event. Reading hail as a tornado would put the rarest
  state in the set on several thousand hailstorms a year.

`fetch()` never raises. A render request is on the critical path of someone
looking at their token, so a slow or broken weather service must cost them
the dynamic layer and not the image. `stable_state(token_id)` gives an
unclaimed token a deterministic sky from its id — off a fixed hash, not
python's `hash()`, which is salted per process and would hand the same
token a different sky on every restart.

## The weather sits in a band; the plate stays readable

**The background is a trait the holder chose and cannot switch off**, so a
state that buries it is taking something away rather than adding to it.
Fog, blizzard and the tornado were all first written as full-frame grades
and all three failed that test — measured against the same sky with no
weather, fog left **24%** of the plate's own detail and **41%** of its
chroma, blizzard 40%/22%, the tornado 57%/**14%**, across the whole frame.

The fix is not a weaker effect, it is a **placed** one:

- **Fog rolls along the ground.** `band` gates its haze *and* its diffusion
  to a bank in the lower half, whose top edge undulates and rolls. Denser
  than it was where it actually sits, and the sky above it is untouched.
- **Blizzard settles.** The whiteout is banded the same way, and `accum`
  lays a drift along the bottom eighth with an undulating surface. The
  driven snow is the event; the drift is the evidence it has been going a
  while, which is what separates a blizzard from heavy snow at a glance.
- **The tornado stopped darkening the sky to be seen.** It used to crush
  the whole plate so a pale funnel would read against it. Now the funnel
  carries itself — an opaque column with a **lit rim** on its upper-left
  flank — so it separates by local contrast on a bright plate and a dark
  one alike, and the supercell grade can stay light.

| | detail kept | chroma kept | | detail | chroma |
|---|---|---|---|---|---|
| fog | 24% | 41% | → | **45%** | **63%** |
| blizzard | 40% | 22% | → | **66%** | **43%** |
| tornado | 57% | 14% | → | **82%** | **35%** |

`verify_sky.py` holds a `PLATE_DETAIL_FLOOR` per state and fails if one
drifts past its own. It is checked at **`day` and `night`**, because every
hazing state gets steadily worse as the sky darkens — lerping an
already-dark plate toward a bright haze crushes its relative contrast far
harder than doing the same to a bright one. Measured across all eight
phases the fall is monotonic (fog 43%→23%, blizzard 50%→31%, tornado
68%→48%), so night is the binding case.

**Fog is nearly free and always was**: the mask means the plate can be
hazed while the character is not, which is literal atmospheric
perspective. The character pops forward without a pixel of it changing.
`blizzard` is the same trick at the other end of the scale — the plate goes
toward white while the character does not move a pixel.

**The tornado is the one state that is a shape rather than a field.** Every
other weather changes the whole plate uniformly; a funnel is an object
standing in it, which is why it reads as the rarest thing in the set. Three
things follow, and none of them are optional:

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
| `overcast` | cloud shadow drifting across the plate |
| `fog` | a ground bank whose top edge rolls; the sky above stays sharp |
| `rain` | two depth bands falling down-and-right, near band 2x faster |
| `snow` | slow fall with a sideways sway, one cycle per loop |
| `storm` | heavy rain, plus a lightning strike and its echo |
| `blizzard` | driven snow over a whiteout band, on settled drifts |
| `tornado` | the funnel snakes once, its banding climbs three times, the debris orbits twice and more blows past |

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

Three things hold regardless of format:

- **`image` must stay a still PNG.** Every grid, thumbnail, search result
  and notification uses `image`. Animation only ever plays in the detail
  view, often only on hover or click.
- **Caching is the real ceiling, not playback.** Marketplaces cache media
  hard, and Solana has no ERC-4906-style "metadata changed" event to nudge
  them. A loop showing *live* weather will show whatever the weather was
  when they cached it. Live state belongs on your own site; a marketplace
  gets a good-looking snapshot.
- **Test one token before committing 4,444.** Support differs per surface
  and changes without notice; this table is a starting point, not a
  guarantee.

## Locale is a property of the token

The holder's location is **not knowable** from a render request — it arrives
from a marketplace's servers, not from the holder. So locale is claimed:
holder signs in, picks a city, and it **resets on transfer** so the next
owner claims it themselves. Unclaimed tokens should derive a stable
pseudo-locale from the token id rather than defaulting to one place, so the
collection always has tokens in every sky.

If locale is freely settable, rare skies can be farmed. Lock it at first
claim until transfer, or one change per 30 days.

## Usage

```bash
pip install pillow numpy scipy

python3 dynamic/solar.py                          # one instant, six cities
python3 dynamic/weather.py                        # the WMO table + gates
python3 dynamic/weather.py --lat 51.51 --lon -0.13 # one live locale
python3 dynamic/render.py --tokens 3 --sheet      # mint samples + sheets
python3 dynamic/render.py --variety 6             # one token per plate
python3 dynamic/animate.py                        # weather loops (mp4/webp)
python3 dynamic/verify_sky.py                     # THE GATE

python3 asset_assessment/make_weather_contact.py  # the approval sheet
python3 asset_assessment/build_mint.py --render --masks   # mint + masks
```

`make_weather_contact.py` is what decides whether a *new* state ships.
`render.py --sheet` grades one token, which cannot answer either question
that matters: does the state hold across the plate **family**, and is it a
new trait or a second copy of one the set already has. So it renders every
state down a column of different plates and measures mean plate dE between
every pair, and exits non-zero if a state is not distinct from the one it
is most likely to be confused with. Current numbers, at dusk over 6 plates:
`blizzard`/`snow` **44.8**, `tornado`/`storm` **19.3**, against a bar of
6.0 — which sits deliberately above the closest already-approved pair
(`overcast`/`rain`, 3.3 at dusk, because the dusk grade dominates both).

**`build_mint.py --masks` is not optional if this ships.** `create_image()`
has taken `mask_path=` since the prototype landed and the mint did not pass
it, which left the pass with no input at collection scale. The masks
measure 36KB mean, ~156MB across 4,444.

`dynamic/proof/sheet_*.png` are committed as the design record; the
`token_*` / `var_*` inputs are regenerated artifacts and are git-ignored.

## Open decisions

1. **Solana has no `baseURI`.** Each NFT carries its own `uri` string in its
   Metaplex Token Metadata account, so this must be decided **before mint**
   or retrofitted with one update transaction per token (4,444 of them).
   Keep `isMutable: true` either way — it is the escape hatch.
2. **Canonical or alternate view?** Recommended: `image` stays the static
   minted render (marketplaces cache it happily, rarity tools keep working)
   and the live view is additional. `animation_url` is the standard slot for
   it, but wallet/marketplace support for HTML there varies and needs
   testing on Phantom, Magic Eden and Tensor before it is relied on.
3. **Dynamic state in `attributes`?** A value that changes hourly will be
   indexed by rarity tools as though it were permanent. Safest is to leave
   the seven canonical traits untouched and expose sky/weather elsewhere.
4. Whether the night grade's brightness gap is a bug or the look — see
   `sheet_variety_night.png`. Across the plate family it reads as a
   deliberate spotlight; on busy mid-key plates it reads flatter.
5. **How the two severe states are sourced in production.** `blizzard`
   falls out of Open-Meteo for free. `tornado` does not: it needs an
   alerts feed, and the free ones are national — `api.weather.gov` covers
   the US and much of the world publishes nothing comparable. So either
   the state is US-skewed by accident of data coverage, or it becomes an
   owner-triggered collection-wide event, or a token can hold it as a
   claimed one-off. `stable_state()`'s mix currently gives it ~1% for
   unclaimed tokens, which is a placeholder, not a decision.
