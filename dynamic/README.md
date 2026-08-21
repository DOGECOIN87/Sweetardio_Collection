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
