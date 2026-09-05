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
it from the finished PNG would mean segmenting the art. **The masks are
28–60KB each**, so all 4,444 add ~150MB.

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

## Six weather states, not a hundred

Open-Meteo (free, no key, takes lat/lon directly) returns ~100 WMO codes.
Six is the ceiling at which they still read as distinct traits rather than
noise. Call once per *distinct locale* bucketed to ~25km and cache 30 min —
4,444 tokens is a few hundred real cities.

**Fog is the strongest of the six and nearly free**: the mask means the
plate can be hazed while the character is not, which is literal atmospheric
perspective. The character pops forward without a pixel of it changing.

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
| `clear` | none — a clear sky is a still, and costs the plate nothing |
| `overcast` | cloud shadow drifting across the plate |
| `fog` | haze density rolling through, thickening and thinning |
| `rain` | two depth bands falling down-and-right, near band 2x faster |
| `snow` | slow fall with a sideways sway, one cycle per loop |
| `flooded` | standing water: the plate below a waterline becomes its own rippled reflection |
| `storm` | heavy rain, plus a lightning strike and its echo |

**A motionless state is never exported as an animation.** Encoding N
identical frames of a still spends a downscale and a lossy round-trip to
say nothing at all — so `clear` goes out as a lossless PNG at full mint
resolution instead. `verify_sky.py` gates this: a state declaring no motion
must apply **no spatial op**, so it can tone-grade the plate but never
soften or resample it, and at `day` it must return the mint bit-for-bit.

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
per loop, sway uses an integer number of cycles, and the fog field is rolled
by exactly its own width. The rain lean is *derived* from that tile geometry
rather than set by hand, so streaks always point along the direction they
actually travel — on the square canvas that lands at 1/3, down and to the
right, matching the cast-shadow convention.

## Will the loops play on marketplaces and wallets?

Partly, and the format decides it. Solana metadata carries an animated
asset in `animation_url`, with `properties.category` and a mime-typed entry
in `properties.files[]`.

| format | verdict |
|---|---|
| **MP4 (H.264, yuv420p)** | the safest bet, and also the smallest here — 80–261KB against WebP's 300–726KB |
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

## `flooded`, and why it is not just heavy rain

Storm is weather falling. **Flooded is water standing.** Below a waterline
the plate is replaced by a mirror of the plate above it — compressed
(water foreshortens what it reflects), displaced by a travelling sine whose
amplitude grows with depth, and pulled toward a murky green-blue that
thickens further down. The ripple runs a whole number of cycles per loop,
so it wraps like every other motion here.

Because the pass is plate-only, **the flood rises behind the character**:
the figure stands in it rather than being tinted by it. That is the rule
paying off rather than getting in the way.

The waterline lip has to be **wide and weak**. A tight bright line reads as
a scanline across the plate, not as water — the first version was exactly
that. It also rides the same ripple as the reflection, so the waterline is
never a perfect ruler edge.

## Banner quality: supersample, do not grade small

The banner renders each panel at the **full 1393 mint canvas** and
downsamples once at the end. Grading at the 500px panel size instead threw
away 2.8x of linear detail before the codec ever saw it, which is what made
the first cut look soft — the encoder was not the problem.

Output is 3000x1000 (`_2x`, for retina) plus a 1500x500 cut **downsampled
from that same supersampled render** rather than rendered at 1500 directly:
same pixels, visibly cleaner edges. H.264 High profile, yuv420p, CRF 14,
`preset veryslow`.

## The logo is a real asset, not a typeface

The collection already has **two** marks, on two different plates, and
neither existed as a standalone file. `extract_logo.py` cuts both.

- **`red`** (the default) — red script on a silver sign board with a dark
  green *COLLECTION* pill, from `Sweetardio (16).png`. Solid edges, high
  contrast, and it holds up when scaled.
- **`neon`** — pink neon tubing in a shop window, from `Sweetardio.png`.
  Atmospheric, but it is glass and glow: it goes soft at size and needs a
  dark backing to read at all. That is why it is not the default.

The board needs a different cut from the neon. Its *COLLECTION* pill is
dark green, so a brightness key drops it while keeping the plaque around
it — but the plaque is a solid board, so **filling each row between its own
extremes** recovers the pill without keying that colour at all. The wall
behind is dark navy and nearly the pill's luminance, so the key keeps only
the largest connected component first; without that the row fill would run
from a wall tile on one side to the board on the other and swallow the gap.

The neon cut is a different problem entirely:

its key is by **hue, not
brightness**. The sign sits on a light grey mesh, so a luminance key keeps the background,
and a warm gold bokeh flare overlaps its lower left, so a plain chroma key
keeps that too. Gating on the two colours the logo is actually made of —
pink around 295-360°, teal around 150-225° — drops both, while a separate
low-chroma highlight pass picks up the white tube outlines the hue gate
cannot see.

A gamma on the resulting alpha collapses the wide haze. Keeping it made the
mark look like a lit sign over a **dark** panel and like a dirty rectangle
over a bright one — and the banner has both.

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
python3 dynamic/render.py --tokens 3 --sheet      # mint samples + sheets
python3 dynamic/render.py --variety 6             # one token per plate
python3 dynamic/animate.py                        # weather loops (webp)
python3 dynamic/verify_sky.py                     # THE GATE
```

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
