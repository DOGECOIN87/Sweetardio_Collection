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

- `SUBJECT_SEPARATION` in `generator.py` — the occlusion band that separates
  the character from the plate is offset **down and right**, for the same
  reason the cast shadow is.

- `GROUND_SHADOW` in `generator.py` — the cast shadow is offset per mode:
  `drop_dx`/`drop_dy` push the floating characters' shadow down and to the
  right at 45°, while the contact pool keeps `dx: 0` because a pool sits under
  its caster whatever the key light is doing.

## Canvas and face rule

- Canvas is **1393 × 1393**, and **every trait asset must be authored at that
  size**. `_render_layer()` silently resizes anything else, which scales the
  art *and moves its origin* — a 1343 sticker landed 40px off from where its
  file said. All 123 trait assets now conform; only `backgroundz` may vary,
  since a plate is re-fit to the frame by design.
  `asset_assessment/audit_art_quality.py` flags any deviation.
- The skin ball, eyes and mouth composite at **fixed canvas positions**; the
  ball centre is ~(690, 601) and every character's face hole is drawn around
  it. Nothing moves to meet a layer that drifted, so footprints and positions
  must be preserved exactly when an asset is re-authored.
- `ball_fit()` sizes every skin ball from the **widest eye**, so eye width is
  load-bearing across the whole collection.
- **The eyes must overlap the face hole's rim.** The eye whites spill past the
  hole edge onto the body — that overlap is the collection's face style, not an
  accident. With the hole registered at 250px and the median eye at 277px, the
  ratio is ~1.11 for every character.

## One face, one size, for the whole cast

**The face assembly — skin ball, eyes, mouth — is the same size on every
character.** It composites at fixed canvas positions around (690, 601) and
does **not** carry `CHAR_SCALE`. Only the **body** scales.

This is the rule that makes every face read the same. When the assembly did
scale with the body, a 0.74 ice cream got a 0.74 face: a 217px ball against
everyone else's 293px, showing through a 190px hole against their 250px. The
cast ran **179–260px rendered, a 1.45× spread**.

The other half of the rule lives in the **art**: because the body still
carries `CHAR_SCALE`, each hole must be authored so that

    file hole width × CHAR_SCALE == FACE_HOLE_WIDTH (250)

so a 0.74 ice cream needs a 338px hole in its file and an unscaled body needs
250px. `asset_assessment/normalize_face_hole.py` warps existing art onto that
circle without moving the body's silhouette, and
`asset_assessment/audit_face_holes.py` checks it. All 27 now render 249–252px,
roundness 0.99–1.01.

Two consequences worth knowing:

- A hole that is too **small** leaks nothing — it just shows a ring of skin
  ball around the face and reads as a shrunken head. Only `audit_face_holes.py`
  catches that. A hole too **big** leaks the background plate, which is
  `verify_face_coverage.py`'s job. You need both.
- `FACE_HOLE_BOTTOM_OVERRIDE` is now **empty and should stay that way**.
  Growing one character's ball is the wrong lever — it is the fallback for art
  that cannot be re-registered, and it costs face size wherever it applies.
  Both entries it once held (nutty_bar 765, gold_waffle 750) died once their
  holes were registered properly.

New character art is registered by `asset_assessment/register_character.py`,
which scales the art until its hole matches before pinning it to the ball
centre; run `normalize_face_hole.py` afterwards to put the hole exactly on the
cast circle.

## Z-order: the body is always drawn over the skin

**No skin ball is ever painted over a character.** The ball is composited
first and the visible face is whatever shows through the body's face hole —
for every character, with no exceptions. `body_after_skin()` in `generator.py`
returns True unconditionally; the `before_skinz_` / `after_skinz_` filename
prefixes are historical and record only how the art was authored, never how it
is composited.

Two things follow, and both are checked by
`asset_assessment/verify_face_coverage.py`:

- **The ball must reach the hole's rim for every skin × eye pair.** If it
  falls short the gap is neither skin nor body, it is a hole through to the
  background plate — and it appears for only some pairs, because `ball_fit`
  sizes the ball from the widest eye and each ball has its own size and centre.
  The fix is `FACE_HOLE_BOTTOM_OVERRIDE[<char>]`, whose value is in
  **pre-`CHAR_SCALE` file space**, not composited canvas space.
- **Every character therefore needs a real enclosed hole.** All 27 have one.

## The ice cream names describe the art, and did not always

Four of the five ice creams carried the wrong name until 2026-08. Measured by
the dominant hue of the top 45 % of the body (the scoop, above the cone):

| name | art | now |
|---|---|---|
| `cyan_sherbert_ice_cream` | neapolitan stripes (7°) | `neopolitan_ice_cream` |
| `neopolitan_ice_cream` | solid cyan (181°) | `cyan_sherbert_ice_cream` |
| `pink_sherbert_ice_cream` | solid chocolate (16°, V 0.51) | `chocolate_ice_cream` |
| `rocky_road_ice_cream` | solid pink (346°) | `pink_sherbert_ice_cream` |

`rocky_road` is gone as a name: rocky road has marshmallows and nuts in it, and
a plain brown scoop is **chocolate**.

Two things this cost, both worth knowing before renaming anything else here:

- **Per-character values are tuned to the ART, so they move with it.** The four
  were identical everywhere except `CHAR_Y_ADJUST`, where the chocolate body
  measured −18 against the others' −21. That −18 had to follow the body to its
  new name, or the rename silently misplaces two characters by 3px.
- **`char_y_adjust` and `is_wat_excluded` match by SUBSTRING**, so a new name
  can collide with an existing one. `chocolate_ice_cream` sits alongside four
  other `chocolate_*` characters; it was checked in both directions before the
  rename (nothing matched, and `char_y_adjust` takes the longest key anyway).

Renaming also invalidates `char_compat.json` (rebuild it) and therefore the
rarity gains, because a changed blocklist changes the draw — re-run
`calibrate_rarity.py` and regenerate `catalog/RARITY.md`.

### Four other names do not describe their art, and stay anyway

The whole cast was checked by eye against its art in 2026-08 — all 27
characters, 69 plates, 10 eyes, 9 mouths, 11 arms, 5 footwear pairs and 23
stickers. Beyond the ice creams, four names do not match what is in the frame,
and **all four are deliberate and were confirmed as keepers**:
`Coder Chick` (a pastel unicorn wallpaper), `Druski` (a still from his content
that he is not in), `Legendary Tenders` (the word NOTHING over a star field)
and the `Military Brat` arm (two cartoon gloves, no weapon — it is the de-facto
unarmed arm, lifting 3 of 27 figures against the AK15's 18).

They live in `INTENTIONAL` in `asset_assessment/dump_trait_names.py` and are
marked **†** in `catalog/NAMES.md`. **Read that list before "fixing" a name.**
The ice creams needed correcting because the art contradicted the flavour;
these are the owner's naming, which is a different thing.

## Character art is resolved by exact base name

`char_base_name()` in `generator.py` is the one definition of a character's
name. It builds the cast list *and* maps a name back to its art, so the two
cannot disagree. Never match a character to a file by substring: `waffle` is a
substring of `gold_waffle`, which is exactly how the waffle spent a long time
rendering the gold waffle's body (with its own placement tables applied to it,
leaking a 132×31 hole through its face) while `after_skinz_waffle.png` was
never drawn at all.

## The skin balls are lit spheres, not flat discs

The three skins ship **relit** by `asset_assessment/shade_skin_balls.py`:
a mean-preserving Lambert form ramp from the upper-left key, a broad satin
specular plus a small glossy hotspot, a cool bounce on the lower-right limb
and rim occlusion. Before this they were near-uniform matte discs whose entire
luma gradient lived in the outer ~8 % of the radius, which is why a face read
as a sticker — the eye got no form information anywhere the eyes and mouth
actually sit. Measured in-ball luma span went 0.43–0.66 → 1.09–1.65, and the
BR/TL limb ratio 0.51–0.67 → 0.28–0.37 (the old 0.48–0.65 band recorded in
`shade_cyan_skin.py` described the flat art and is superseded).

Two rules hold it together:

- **Alpha is preserved bit-for-bit; only RGB is touched.** `ball_fit()` sizes
  every ball from the widest eye and each face hole is registered against the
  ball's footprint, so a change to the alpha would move the whole cast's face
  geometry. The tool asserts on this.
- **The form ramp is mean-preserving**, so each skin keeps its identity — the
  median colour of all three moved by dE ≈ 2.4, imperceptible.

Originals live in `traits/skinz_originals/` (a *sibling* of `traits/skinz` —
the generator mints every `.png` in a trait folder, so a backup inside it
would mint as a skin). The tool always relights from the backup, so re-running
it is idempotent rather than compounding the pass on itself; `--restore` puts
the originals back and `--ladder` renders candidates without writing.

**Everything on the face casts onto the ball.** Three configs in
`generator.py`, all riding the generic per-layer shadow, which clips to the
foreground so they land on the ball and body but never the plate, and all
offset down-and-right for the top-left key:

- `EYE_SHADOW` — every eye. Without it the eyes were the last thing on the
  face standing off the ball with nothing under them, and at a face zoom they
  read as stickers, the brow-style assets worst of all.
- `MOUTH_PROP_SHADOW` — the joint and the lollipop, which are 3D props.
- `MOUTH_SHADOW` — the other seven, at **lighter** settings.

That last one corrects an earlier rule here which said flat line-art mouths
should get no shadow because it embosses them. Rendered three ways once the
eyes had shadows, that was half right: at the eyes' strength the thin line
mouths *do* emboss, but with nothing at all they float, and conspicuously so
beside eyes that no longer do. **The distinction is strength, not presence.**

## The eyes are registered, then lit as lenses

**Every eye is authored to one size and one baseline.** `register_eyes.py`
puts all ten on width 277–278 (1.11× the 250px hole), centre x within ±0.5 of
the ball's 690, centre y at −29. Before it they ran width 236–288, cx −7…+25.5,
cy −36.5…−16.5 — which left `Beady` visibly slid across the face, and left
`Googly` (236) and `Clueless` (245) *narrower than the hole*, so they never
overlapped its rim. That overlap is the collection's face style.

**Eye width is load-bearing.** `ball_fit()` sizes the ball from the eye's
opaque width, so registering the widths also collapses `ball_fit` to one value
per skin. That is where "one face, one size" already pointed, but it means
**`verify_face_coverage.py` is the gate** on any eye-width change — a smaller
ball on the widest pairing can stop short of a hole rim.

`shade_eyes.py` then lights them, and the useful idea is that the gloss is
**per eyeball, not per face**. A specular taken from the ball's normal lays one
soft sheen across the whole face and never looks wet; each connected blob is
instead fitted as its own convex lens and given a catchlight on its upper-left.
It deliberately does **not** skip dark pixels — an earlier version guarded gloss
away from near-black art to keep brows matte and thereby killed it on every
pupil and iris, which is exactly where wetness lives.

`LENS_SCALE` sets the strength per asset, because the assets differ in what
they already are: 1.0 for flat cartoon eyes, 0.45 for anime eyes that already
carry a painted catchlight, 0.35 for brows, 0 for `Alien` and `Cyborg`, which
are already rendered as glossy 3D objects.

**Both eye tools preserve alpha bit-for-bit**, for the same reason the skin
tool does. Note the two back up to *different* folders on purpose:
`eyez_originals/` holds the pre-registration art (and the retired `Retardio`),
`eyez_registered/` holds `shade_eyes.py`'s input. Each tool always works from
its own backup so it is idempotent; sharing one would make the shading pass
silently undo the registration.

Retiring an eye means rebuilding `traits/eyez_compat.json`
(`build_eyez_compat.py`), and so does any pass that changes eye colour.

## Face holes: check the rim for a baked matte line

Some character art was cut with a black outline left in the pixels bordering
its face hole. Over the light skin ball it reads as a hard, stepped dark
hairline round the face; over flat green it is unmistakable.
`fix_hole_matte_line.py --report` ranks the cast by it. **All four affected
assets are now fixed** — churro (−59.5), `sugar_cube` (−69.5), `gold_waffle`
(−59.9) and `og_gummy_bear` (−57.7) — and nothing is left above the −40 flag.
Most of the cast always sat within ~10 of its own body, so this was a defect in
four assets, not house style. The residue the report still lists (−39.4
`chocolate_frosted_poptart` down to −23.6 `chocolate_chip_cookie`) is soft
shading around the hole, not a hairline; check it over flat green before
"fixing" anything there.

The repaint band must straddle the boundary — the partly transparent pixels
*inside* the hole carry the line too, and repainting only the outside leaves a
dotted fringe where the solid ring was. Alpha is never touched, which is what
keeps `audit_face_holes.py` and `verify_face_coverage.py` out of it.

`FACE_INSET_SHADOW` in `generator.py` shades the ball where the hole's rim
occludes it, so the face reads as set *into* the recess. It lands exactly on
that rim, so fix the matte line first or the shadow deepens it.

## The gorbhouse is footwear, and must be drawn like footwear

The trash-cans are a `what_are_thosez` base like the bunny/pepe/shiba/monster
slippers, and the art says so: `Gorbhouse_base.png` occupies **y 820..1146**,
the same authored band as Bunny (825..1148) and Cookie Monster (821..1276).
Every footwear layer is therefore composited at `offset=False, dy=0` — its
authored position — and the character standing in it is placed by
`CHAR_Y_ADJUST` alone.

The gorbhouse used to break both halves of that. It had a draw of its own
(`gets_gorbhouse`) *and* a layer of its own, appended anchored to the
CHARACTER (`offset=apply_offset, dy=y_adjust`); and because it never set
`chosen_wat`, `apply_offset = not chosen_wat and …` stayed **True**, so a
character wearing footwear collected the **footwear-LESS** trims —
`VERTICAL_OFFSET` (+150), `FOOTWEARLESS_DY` and `BG_CHAR_EXTRA_Y`. Cans and
body went down 130–190px together, which is why it looked internally coherent
and still wrong: the body bottom landed at **1105–1109**, i.e. **156px BELOW
the can rims**, against 137–139px *above* their floor for every other slipper.
The character sat in the cans up to its middle.

The fix is one line of intent: the gorbhouse roll sets
`chosen_wat = GORBHOUSE_BASE`, and everything else — the base layer, the
overlay layer, `apply_offset`, `extract_metadata`'s Footwear attribute — falls
out of the path that already existed. **Do not give it a layer of its own
again.** If a future asset needs the same treatment, give it a `_base` file
and let `wat_base_name()` find it.

Measured after: all 15 footwear-capable characters bottom out at **943–965**
(22px spread), sinking 123–144px into their slipper, the six gorbhouse
wearers included. Before, those six sat 150px outside that band.

Two things worth knowing:

- **`gold_waffle` is gorbhouse-eligible only by SUBSTRING**, via `"waffle"` in
  `GORBHOUSE_CHARS` — it has no entry of its own. That is the repo's
  recurring failure class (see `char_base_name`), so it is deliberate or it is
  a bug; it renders correctly either way, so it was left alone. Decide it
  before adding another `*_waffle`.
- Drawing the base as well as the overlay adds 6,047 px the overlay lacks, at
  (539,829)–(874,907). Measured across all six wearers, **0** of them are
  visible — the body covers them — so it is a no-op today and correct
  structurally.

## Footwear geometry is measured on the SOLID art, and two assets needed it

Every slipper is composited at `offset=False, dy=0` — its authored position —
and the character is moved to meet it. Two per-footwear tables in
`generator.py` handle the assets that do not fit that on their own, and both
were solved from measurement:

**`WAT_CHAR_LIFT` — raise the CHARACTER (never the footwear).** A slipper's
*silhouette* decides how buried the body looks, not its height. Per-column
tops: the bunny/pepe/shiba/monster taper — only ears, eyes and ankle stubs
reach the asset top, and 90 % of their width starts at y 972–1006. The
gorbhouse is a flat-topped cylinder, 90th-percentile column top y 895. So at
one shared body line the cans cover **37.2 %** of their own mass against
28–30 % for every other slipper, and the body sits **63px below** the point
where the can's bulk begins where every other slipper puts it 17–49px
*above*. Rendered as a ladder (0 / −40 / −70 / −95 / −120), **−70** is where
the black ankle stubs authored into the can art read as short legs and the
body still rests on the lids; −95 and beyond floats it. This is a property of
the SLIPPER, so all six wearers take it identically — it needs no
per-character tuning.

**It does not stack with `ARMED_LIFT`.** Both say "this figure must ride N px
higher for clearance", so the figure takes the larger N, not the sum. Summed,
an armed gorbhouse went up 140px and floated clear of the cans on two long
black ankles.

**`WAT_SCALE` / `WAT_SCALE_PIVOT` — resize a footwear asset.** Measured on the
**solid** art (alpha > 200; four of the five carry a baked soft drop shadow,
and any lower threshold reads that as extra sole):

| slipper | one foot w | sole | height |
|---|---|---|---|
| Cookie Monster | 327 | 1168 | 345 |
| Pepe | 287 | 1147 | 329 |
| Shiba | 286 | 1142 | 309 |
| Gorbhouse | 282 | 1144 | 323 |
| Bunny | 256 | 1147 | 321 |

The Cookie Monster was ~14 % wider than the cast mean and its sole sat 23px
below a 1142–1147 line the other four agree on — so its wearers stood on a
lower floor than everyone else, contact shadow and all. **0.88** puts one
foot at 287: *exactly* Pepe's, the largest of the other four rather than
smaller than them.

**Solve the pivot against the real render path, not by algebra on the bbox.**
`scale_about` resamples, so the threshold that defines "sole" moves under it:
the pivot the algebra gives (y 728) measured back as sole 1114–1129, 30px
high. y 985 is the value that measures back as 1145. Re-solve it if the scale
ever changes.

Every file of a pair — base and overlay(s) — must take the same scale and
pivot, or the front piece slides off the back one. `_wat_layer()` is the one
place that builds a footwear layer, for that reason.

## An armed figure rides 70px higher, as one piece

`ARMED_LIFT` in `generator.py` raises the WHOLE figure — body, skin ball, eyes,
mouth, footwear, and the arm — whenever a weapon is held and that weapon
overhangs the body's base. 18 of the 27 qualify with a rifle; the ones whose
arm already sits inside their own footprint (the ice creams, churro, Nutty Bar,
Twinkie) are untouched.

The reason it is applied to `y_adjust` before any layer is built, rather than
to the arm, is the whole point. **Four earlier attempts moved the arm relative
to the body and all four were reverted**: anchoring it to a fraction of body
height, to a fixed distance above the base, to the cast-median base, and a
one-sided overhang clamp. Every one of them either rode the gun up over the
eyes on the squat bodies — the face is pinned at a fixed canvas position while
bodies are not — or destroyed the sabers' blade-down pose, because a bounding
box cannot tell a weapon that hangs low by design from one that hangs low by
accident.

Moving body and arm together cannot cause either failure, since it changes no
relationship inside the figure. Verified: across 27 characters × 11 arms, every
part moves by exactly the same 70px, and the highest body top is y=132, well
clear of the frame.

`ARM_SCALE_PIVOT (694, 1040)` is a **scaling** pivot, not a hand line — y=1040
falls outside most of the arm art (Cash spans 625–908, the sabers 122–1302). It
cannot be used to anchor position. A real per-arm fix needs a hand marker
authored into the art, not a formula over a bbox.

When the lift is not enough for **one** character, the sanctioned lever is
`ARM_CHAR_DY` (per character) and `ARM_CHAR_ARM_DY` (per character × arm, and
it wins). These move the arm relative to the body — the thing the five formulas
were reverted for — and they are allowed only because each value is **authored
by eye against that one character's face**, never derived across the cast.

`ding_dong` is the only entry: a 636px round body whose arm centre sat at
92.2 % of body height against a cast band of 67–88 %. It takes −40, except

- **Dual Uzis −55.** They hang lowest of any arm and were still at 95.6 % after
  −40. The owner's rule: *−55 is only suitable for dual uzis.*
- **Cash 0.** The fists hold notes fanned *upward* at chest height, so it was
  never low; −40 put 489px of banknote across the eyes (0px at dy 0).

That split is the point: one number per character cannot fit arms that differ
in pose, so any new entry needs the whole 11-arm strip rendered and looked at.
With these values 0 of 11 weapons touch `ding_dong`'s eyes.

### The gummy bear has arms of its own, and only the sabers argue with them

`og_gummy_bear` is the one character whose BODY ART carries arms — two
~6,700px lobes at x 396..451 and x 922..977, y 751..911, tips at (429, 839)
and (944, 839). Every armz asset lays gloved hands over that, and the pairing
reads right only when the added glove lands **on** the bear's own arm.
Measured, right glove vs that right-arm tip:

| arm | offset | reads as |
|---|---|---|
| Knives | dx +3, dy −18 | its hand |
| Military Brat | dx −1, dy −55 | its hand |
| Cash | dx +57, dy +16 | its hand |
| Dual Uzis | dx +128, dy −86 | in front of the torso |
| AK15 | dx +244, dy +22 | in front of the torso |
| **the 3 sabers** | **dx −59, dy +263** | a hand floating above an orphaned arm |

The saber is the only **asymmetric** pose in the set: it holds its hands
187px apart vertically where every other two-handed arm keeps them within
0–93px. So its LEFT glove lands on the bear's left arm (dx +5, dy +75) and
reads fine, while the right rides up by the head and strands the right arm
below it. That is the artefact, and it is visible at thumbnail size.

`ARM_CHAR_ARM_DY` takes **+100** for the three sabers on the bear — the only
positive entry in the table, because it pushes an arm DOWN rather than
lifting it. That is as far as the pose can go and stay in frame: the blade
spans y 84..1263 at rest and 184..1363 at +100 (>128 alpha), against a 1393
canvas, and at +130 it clips. Coverage of the bear's own arms goes 32 % →
64 %.

**It does not remove the artefact, it reduces it** — the arm tip still shows
past the hilt, and the owner chose this over the alternatives knowing that.
Two things were rejected: blocking the pairing (costs 3 of 297
character × arm combinations and, because a changed draw re-randomises
everything downstream, a rarity re-solve), and a bear body authored without
its own arms for the armed case (the real fix, and the art does not exist —
a naive alpha cut of the arm lobes leaves an edge with no rim light and the
arm's interior gloss sliced through, which is fine at token size and
obviously wrong at 3×).

The blade runs OFF the frame at both values — it touches the left and right
edges before and after — so no floating blade stub is introduced. Check that
if the value ever moves.

## The starfield is the ultra-rare tier, and the one ANIMATED plate

`Starfield.png` is **10 of 4444 — 0.225 %, 1 in 444 — the rarest COMPOSITED
trait in the collection**. Next rarest is Tornado at 14 (0.32 %); a legendary
plate is 50 (1.13 %). Only the 1/1 secret rares beat it, at 1 of 4444 each,
and those are not composited traits at all — they are whole tokens.

The cap only holds because the plate is kept out of the weighted draw
entirely. `is_allocator_only_bg()` in `generator.py` covers the `Legendary_*`
plates and this one, and `generate_random_combination` filters on it before
weighting — a plate sitting in the pool at weight 1.0 alongside ~70 others
would mint on roughly 1 token in 70, not 10 in 4444. `STARFIELD_COUNT` in
`build_mint.py` is then the only way one exists.

It is **generated, not photographed**: `dynamic/starfield.py` rebuilds it from
`Nyan_Blank.gif`, so its source of truth is reproducible rather than merely
restorable. That is why it is NOT in `traits/backgroundz_originals` — and
because `grade.py` grades everything in that folder with no skip list, it also
carries an explicit `GENERATED` skip there. Running the family grader over a
flat authored field would put a vignette, a bloom and a depth blur on a colour
that is meant to be exactly one value.

The field is **Oxford Blue `#002147`**, not the GIF's own `#00008B`. The plate
family is graded cool, desaturated and mid-key; `#00008B` is the one saturated
primary in the set (L\* 21.6, chroma 79) and reads as a swatch beside them,
where Oxford Blue (L\* 15.5, chroma 32) reads as deep space. Because the field
went DOWN in luma, the sparkles gain contrast rather than lose it.
`from_gif()` **cleans then recolours**, in that order — cleaning leaves exactly
two colours so the swap is a substitution, and recolouring first would strand
the Nyan-removal residue as visible specks.

### What it composes with

- **Characters: `STARFIELD_CHARS`, 14 of 27, matched EXACTLY** (`waffle` and
  `gold_waffle` are both on it and a substring test cannot tell them apart).
  The plate is flat, so `build_char_compat.py`'s camouflage test degenerates —
  there is one colour to clash with. The list is cut on measured mean CIE76 dE
  between the composited body and the field: the cast runs 38.1 (chocolate
  sandwich cookie) to 103.9 (Twinkie), and the natural break is ~75, below
  which sit the dark chocolate bodies (mean L\* 22–40) that read as
  silhouettes. Nothing is *illegible* anywhere on that range, so this is an
  appearance cut, not a legibility one.
- **Weather: mutually exclusive.** Not squeamishness about rain in space —
  both tiers own `animation_url`, and a token carrying each would have two
  loops and one field to put them in.
- **Legendary plates: mutually exclusive**, one rare plate per token.
- **Stickers: allowed, deliberately.** They allocate from every composable
  slot, legendary included. All 10 drew one.

### The loop is written at MINT time, not in a bake pass

`bake_weather.py` can work from a finished PNG plus its protect mask because a
weather state is a grade laid *over* the token. The starfield's **plate
moves**, and the grounding shadow and the subject-separation pocket are
painted onto the plate *before* the character goes down — so a frame built by
swapping the plate under a finished PNG loses both and the character floats.
(`starfield.behind()` does exactly that and is labelled a proof path.)

So `build_mint.py --render --animation` calls `starfield.loop_layers()`, which
re-composites the whole stack once per plate frame. 10 tokens x 12 frames is
120 composites at ~1s each; the 444 weather tokens would have been 16,000,
which is why the weather bake had to be a grade and this one does not.

### On the flat field, the halo is the SHADOW

Measured on a Twinkie over the plate, as % of plate pixels deviating from the
flat field: both stages on 4.1 %, shadow only 4.0 %, separation only 0.6 %,
neither 0.6 %. `SUBJECT_SEPARATION` contributes essentially nothing, exactly
as its own rule predicts — its strength is measured from a band-pass, and a
flat field has no business to detect. The visible pool under a floating
character is `GROUND_SHADOW`, and **the owner chose to keep it.**

### It did not move the rarity gains

Adding it changed `char_compat.json`'s weights (all 27 entries — the grader
measures against every plate in the folder, capped ones included, which is how
the `Legendary_*` plates are already treated) but changed **nothing** in
`eyez_compat.json` beyond adding the plate's own entry: no existing plate's
blocklist or weight moved. The eyez entry blocks Blue and Cyan on it, which
costs those eyes nothing at all, because the plate is not in the weighted pool.

Side Eye — the eye this file already flags as the sensitive one — reads
**+1.12 / +0.87** at seeds 4444 / 909090 against the **+0.31 / +1.70** recorded
before the plate existed. Same band, tighter spread. Re-solving to chase that
would be fitting noise on one seed, which `calibrate_rarity.py`'s docstring
warns against explicitly, so **the gains were left alone**. Backgrounds stayed
within ±0.42.

## The 1/1 secret rares are the rarest tier, and composite with NOTHING

`traits/secret_rarez/` holds finished full-canvas artworks that mint as a whole
token with no character, plate, skin, eyes or mouth over them. Each is **1 of
4444 — 0.0225 %, ten times rarer than the Starfield** and fifty times rarer
than a legendary plate.

The tier holds two guest-artist pieces: **Duhnut Candy Man** (#1, by Emily
Cartoons) and **Radbro Webring** (#2, by Radbro Webring). The 23 in-house
pieces of the original tier stay retired in `traits/secret_rarez_retired/`.

**The mechanism already existed — do not build a new one.** `build_mint.py`
step 0 gives each a fixed slot and excludes it from every other pool;
`generator.secret_rare_combination()` makes the art the sole layer.
Restoring the tier is *only* dropping files into the folder:

- **The `Secret_` prefix is required** — `is_secret_rare()` matches on it.
- **Numbering is `secret_rare_number()`, which indexes SORTED FILENAMES.**
  D sorts before R, hence #1 Duhnut and #2 Radbro. Adding or renaming a piece
  renumbers the set, which is why restoring a retired piece would not give it
  back its old number.
- **There is deliberately no `TRAIT_NAMES[SECRET_RAREZ]` block.** Names fall
  back from the filenames, and `_fallback_display_name()` strips the `Secret_`
  tier marker. Adding a block would take that strip path out of service — it
  is exactly how the tier shipped "Secret Rarez #1 — Secret Milk Dunk" until
  `33dbdff`, because every secret rare had an explicit name until there were
  none at all.

### Use the UNGRADED art, and store it at 1393

The pieces existed on an unmerged branch in **two** versions, and the graded
one is the wrong one. `background_pop_studies/grade.py` normalises a plate
cool / desaturated / mid-key so a *character* reads in front of it; nothing
stands in front of a 1/1, so that grade only mutes an artist's own colour.
Measured on the Radbro piece, grading lifted the blacks (mean RGB 44 → 77) and
cut the saturation (std 68.4 → 56.4).

The art is 1200×1200 and the canvas is 1393. Stored at 1393 it is
**bit-identical** to what `_render_layer()`'s silent resize would produce, so
it changes no output — it just stops `audit_art_quality.py` flagging a SIZE
deviation, and stops the origin quietly moving if the art is ever re-authored.

**The top-left lighting convention does not apply to this tier.** Every other
asset is lit to sit with the cast; a 1/1 composites with nothing, so it keeps
the artist's own light. `audit_art_quality.py` reads UL/LR as `nan` on both
(they are fully opaque) and flags neither.

### The guest artists are credited on-chain

`SECRET_RARE_ARTISTS` in `generator.py` maps a piece to `(artist, url)`, and
`extract_metadata()` adds an `Artist` attribute; `build_mint.py` puts the URL
in the token's `external_url`. Only 2 of 4444 carry either, so Artist is a
rarity signal as well as a credit.

It lives in `generator.py`, not `build_mint.py`, because the credit is a
property of the ARTWORK — every path that builds a secret rare's metadata goes
through `extract_metadata()` and so cannot drop it. **A missing entry is
legitimate and must never be fatal**: the 23 retired pieces are in-house art
with no guest to credit.

It matters unevenly. "Radbro Webring" is both the piece and the artist, so
that one carried the name by accident; Emily Cartoons appeared in no metadata
at all — her signature is painted into the art and vanishes at thumbnail size.
The same two links are the site's own attribution, in the `Sweetarded-Games`
repo at `src/content/artistRares.ts`. Minted with both artists' permission
(confirmed by the owner, 2026-08).

### DO NOT resurrect the old Artist Series

The unmerged branch `claude/rarity-collection-generation-3j2o6v` made these
**plates at 10 each** with curated character pairings, `is_artist_bg()`,
`is_quota_bg()` and an `ARTIST_BARE` rule. That is the opposite of standalone
1/1s. Take only the ART from that branch — its `is_quota_bg` idea already
exists on main, in better form, as `generator.is_allocator_only_bg()`.

### It did not move the rarity gains either

Same finding as the starfield, and for the same reason. Adding the two drops
the composited pool 4444 → 4442 and re-randomises every downstream draw.
Measured before and after on **three** seeds (4444 / 909090 / 7), the eyes'
mean absolute deviation went 0.45 → 0.55 points and the **worst single reading
improved**, 1.44 (Cerise at seed 7) → 1.12. Side Eye — the eye this file
already flags as the sensitive one — read 1.12 / 0.87 / 0.71 before and
0.70 / 1.12 / 0.72 after: the same band, and it moves in *both* directions
across seeds, which is what noise looks like rather than a systematic shift.
All of it sits inside the ±0.6 the calibration can resolve (1σ for a 16 %
trait at this supply is 0.55 points), so **the gains were left alone.**
Re-solving to chase it would be fitting noise on one seed, which
`calibrate_rarity.py`'s docstring warns against explicitly.

Skins are **not** calibrated at all — they draw on raw weights (7 / 37 / 56 in
`skin_weights.json`), so their shares move more freely: Alien read 7.47 %
before and 6.62 % after, both within ~1.2σ of target. That is not a regression
and there is no knob for it.

**Two denominators had been sized against 4444 and are now honest.**
`calibrate_rarity.realised()` excluded secret rares by falsiness, which worked
for every category except backgroundz — `build_mint.py` stores the artwork's
own filename in the token's `bg` slot, so that one category counted them and
reported 4444 against eyez's 4442 (and let two artwork filenames into the
background counter as if they were plates). It now skips them explicitly.
`build_rarity_table.py` hard-coded "**4444 tokens, all composited**" in its
header; that line is now written from the metadata.

## The flood is the one state that reaches the character, and the sticker floats on it

`flooded` is the only weather state that touches protected pixels — everything
else grades the plate behind the character and gives every masked pixel back
bit-identical. Below the waterline the flood refracts, mirrors, tints and
darkens the composited frame, character and all.

**Every sticker in the collection is authored at y 1114..1338, and the
waterline sits at y 836.** So all 23 are fully under water, and until this was
fixed the flood repainted them: measured on the Golden Ticket, the gold
(187, 176, 141) came back (74, 98, 99) — a murky teal, unreadable as gold, and
individual sticker pixels moved by up to **223 of 255**. At thumbnail size the
piece was a smudge.

The fix is a **second mask**. `create_image(float_mask_path=...)` writes the
corner sticker ALONE, and `sky.apply_sky(..., afloat=...)` rests it on the
water instead of sinking it. The sticker core now comes back **bit-identical
to the mint** (max delta 0).

Four things worth knowing:

- **It is a separate file, not a second channel of the protect mask.** Every
  existing consumer opens that one with `.convert("L")`, which on a
  multi-channel image returns a luma MIX and would silently corrupt the
  protect mask itself.
- **The float mask is the sticker only, not `_is_top()`'s union.** A paired
  background overlay is part of the plate's own scene and must keep drowning
  with it.
- **Exempting the sticker is not enough on its own** — a piece the water
  neither wets nor acknowledges reads as a decal pasted over the flood. Three
  cues are painted INTO the water first, so they are themselves refracted and
  tinted by the depth ramp: a contact shadow, a meniscus climbing the edge,
  and the piece's own reflection.
- **The reflection mirrors PER COLUMN about each column's lowest lit pixel**,
  not about one global bottom row. Stickers are authored tilted, and a single
  mirror line detaches the reflection from the high side and drops a second,
  readable copy of the art into the water. It is also sampled *through* the
  existing refraction and blurred in CONTENT, not just in weight — softening
  the weight alone feathers the edges of a still-legible upside-down mirror.
  Settings came off a rendered ladder (fade/strength/blur 0.026/0.34/5,
  0.014/0.30/7, **0.009/0.26/9**, 0.006/0.22/11); past ~13px of fade it stays
  legible upside down.

That the sticker sits low in frame is not a contradiction. The surface recedes
from the viewer, so something floating near the bottom edge is simply close to
the camera — which is where flood debris sits in a photograph.

Empty float mask is a no-op, and every non-submerging state ignores it
entirely (verified identical across all six). `verify_sky.py` passes it, so
the gate tests the shipping path rather than a render nobody gets.

## The blizzard plate-detail floor is measured as a RATIO, and that is wrong

**Not yet fixed — it changes the owner's quality bar and needs their call.**

`verify_sky.py` scores a state as `detail_with_weather / detail_without`, and
floors that ratio. Fitted to the blizzard on ten proof tokens, what it
actually does is:

    detail_after = 0.0173 + 0.271 x detail_before

Blizzard keeps 27 % of the plate's own detail and **adds** a fixed ~0.017 of
its own — the snow is itself high-frequency texture the band-pass counts. So
the ratio is `0.0173/base + 0.271`: a function of the PLATE, not of the
weather. Same blizzard, same physics, scored across plates: 96 % at base
0.025, 62 % at 0.05, 44 % at 0.10, **37 %** at 0.18.

It fails plates that are doing well and passes plates that are gone:

- Token 10 fails at 36 % kept while retaining **0.0635** absolute detail —
  nearly 3x more than token 5, which passes at 91 % with 0.0222.
- Across ten tokens, plate business correlates **−0.87** with the gate's score
  and **+0.99** with the detail that actually survives. It ranks backwards.
- A plate flattened to a single colour — nothing to preserve, so everything
  measured is snow — scores **376 % "kept"** against a 41 % floor.

The fix is to floor on absolute retained detail. **Stickers cannot help
here**: the sticker is inside the protect mask and `plate_detail` measures
only `mask < 128`, so sticker pixels are excluded by construction, and the
float-mask work above left token 10's blizzard reading unchanged at 36 %.

## Backgrounds are a two-stage problem

The plates are graded as a family by `background_pop_studies/grade.py`
(cool / desaturated / mid-key, out of the characters' hue bands), and every
plate in `traits/backgroundz` must have its ungraded source preserved in
`traits/backgroundz_originals` — **copy it there before you touch it**, or it
can never be regraded. Twelve plates were the only copy of themselves for a
whole phase, which is exactly why they stayed ungraded and razor-sharp.

Grading is global, so it cannot know where the body lands.
`SUBJECT_SEPARATION` in `generator.py` closes that half at composite time,
opening a defocused / desaturated / dimmed pocket in the plate around the
silhouette plus a tight occlusion band on its edge. Its strength is measured
per token from a **band-pass** (`|blur(8) − blur(40)|`) on the ring of plate
the character does not cover — a plain high-pass reads film grain and ranks
smooth plates as busy. Never make it a fixed amplitude: the setting a busy
plate needs turns a quiet one into a grey cloud.

### Adding a plate

The source goes to `traits/backgroundz_originals/` **first**, then
`grade.py --only <name>` writes the graded copy into `traits/backgroundz/`.
Four things follow, and none of them are optional:

- **`--only` REWRITES `ULTIMATE_GRADE_LOG.md` with just that plate**, dropping
  every other row. Keep the new row, restore the log, and merge it back in —
  the file is the record of what every approved plate was graded with, and the
  engine is not bit-identical across numpy/Pillow versions, so the other rows
  cannot simply be regenerated.
- Add the filename to `TRAIT_NAMES[BACKGROUNDZ]` in `generator.py`, or the
  metadata falls back to the filename.
- Rebuild **both** compat maps — `build_char_compat.py` (camouflage blocks)
  and `build_eyez_compat.py` (colour-clash blocks). A plate absent from them is
  simply never filtered.
- Run `verify_separation.py`; the plate should be at 0 at-risk pairings.

A plate with no entry in `rarity_weights.json`'s `backgroundz.target` draws at
gain 1.0 alongside the other unpinned plates. That is cheap for the plates
(worst pinned deviation measured 0.18 → 0.36, inside the ±0.6 the calibration
can resolve) but **it is not free for the eyes**: a new plate re-randomises
every downstream draw, and if the plate colour-clashes with an eye it also
removes that eye from part of the pool. `Swolex` blocks Blue and Cerise,
and Side Eye rose ~0.6 points on average across three seeds.

Measure both before deciding, on **more than one seed** —
`calibrate_rarity.py --check --seed N`. Side Eye already read +0.31 / +1.70 /
+1.25 at seeds 4444 / 909090 / 7 *before* this plate existed, because the
gains are fitted to seed 4444 alone. A single-seed reading cannot tell a new
plate's effect from that fit.

Most recent: `Room.png`, `Clouds.png`, `The_Board.png` and a replacement
`Swolex.png` (2026-08).

### Removing a plate

The inverse, and the folder it goes to is not optional. `grade.py` grades
**everything** in `traits/backgroundz_originals` into `traits/backgroundz`
with no skip list, so a retired plate whose source stays there silently
reappears at the next full regrade. Move the ungraded source to
`traits/backgroundz_retired/` (see its README), delete the graded copy, drop
the `TRAIT_NAMES` entry, rebuild **all three** compat maps, and re-solve
`calibrate_rarity.py` — its docstring is explicit that the gains are void
whenever an asset is added or retired.

Keep the plate's row in `ULTIMATE_GRADE_LOG.md`. It is the only record of the
parameters it was graded with, and the engine cannot reproduce them exactly on
a newer numpy/Pillow, so the row is what makes a restore possible.

Two other things point at plates by filename and will not be caught by any
gate: `catalog/character_showcase/pairings.json` pins one plate per character,
and `background_pop_studies/make_proofs.py` names plates in its proof list.
Seven retirements broke four showcase pairings and one proof.

## Verification tools

```bash
python3 asset_assessment/verify_placement.py      # where characters actually land
python3 asset_assessment/verify_face_coverage.py  # does the ball cover every hole
python3 asset_assessment/audit_face_holes.py      # is every hole the cast size
python3 asset_assessment/verify_generator_rules.py # footwear + locked-arm rules
python3 asset_assessment/audit_placement.py       # what CHAR_Y_ADJUST should be
python3 asset_assessment/render_sample_sheet.py   # N random tokens, full pipeline
python3 asset_assessment/register_eyes.py --report        # eye size + baseline
python3 asset_assessment/fix_hole_matte_line.py --report  # dark rings on hole rims
python3 asset_assessment/verify_trait_names.py    # do the names still resolve
```

`verify_trait_names.py` is the gate on the *names*: it fails on a `TRAIT_NAMES`
entry whose asset is gone (the rename bug that left four ice creams misnamed),
an asset with no entry, two assets in a class sharing a display name, and a
`CHAR_Y_ADJUST` / `EXCLUDE_WAT_CHARS` key that matches no character or is
shadowed by a longer one. Run it after any rename. It cannot tell you a name
*describes* its art badly — only looking at the art does that, which is why
`catalog/NAMES.md` and the `traitsheet_*` sheets exist side by side.

`verify_placement.py` exits non-zero if any character is off its group, drifts
horizontally off the face column, or has a face hole away from the ball centre.

`verify_face_coverage.py` exits non-zero if any character × skin × eye leaves
transparent pixels enclosed by body + ball — i.e. background showing through a
face. It is the check that has to pass before any character art, `CHAR_SCALE`
or `FACE_HOLE_BOTTOM_OVERRIDE` change is called done.

`audit_face_holes.py` is its complement: it exits non-zero if any hole renders
off `FACE_HOLE_WIDTH`. Run both — they catch opposite failures.

`verify_generator_rules.py` covers the footwear exclusions and the
character-locked arms. Its lock audit includes a **synthetic** lock, so it
still tests the rule while `ARMZ_CHAR_LOCK` is empty.

The environment needs `pillow`, `numpy` and `scipy` (`pip install pillow numpy
scipy`); a bare container has none of them.
