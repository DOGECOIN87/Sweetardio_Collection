# Sweetardio — Art Quality Review

Measured with `asset_assessment/audit_art_quality.py` plus targeted checks, over
all 33 characters, 3 skins, 11 eyes, 9 mouths, 16 arms, 11 footwear, 23 stickers,
69 background plates and the 23 secret-rare 1/1s — every asset in the
collection.

`ASSESSMENT.md` measures colour and composition for grading decisions. This
asks a narrower question: **is any asset technically substandard, and does the
art hold together as one collection?**

---

## Verdict

The composited art is in good shape. Geometry, lighting and edge quality are
consistent across the cast, and the defects that exist are concentrated in one
place: **background plates**, which is also the highest-impact place to have
them, since the plate fills the entire frame behind every token.

The two worst offenders — the only plates below 1254² — have been rebuilt
(§1a). Nothing outstanding blocks a mint.

---

## 1. Backgrounds are the weak layer — 46% are upscaled

*(The two 1024 plates below have since been fixed — see §1a.)*

| Native size | Plates | At composite |
|-------------|-------:|--------------|
| 1393 × 1393 | 37 | native |
| 1343 × 1343 | 13 | upscaled 1.04× |
| 1254 × 1254 | 19 | upscaled 1.11× |

`_render_layer()` resizes any non-1393 layer up to the canvas, so 32 of 69
plates are still interpolated at render time. At 1.04× that is invisible; at
1.11× it is a slight softening. Neither is worth acting on without better
sources — the 1254 group is the only one that would repay a re-export.

## 1a. The two 1024 plates — fixed

Both were upscaled 1.36× at render time. Neither had a higher-resolution
original in `backgroundz_originals/`, so both were rebuilt through EDSR ×2
super-resolution and resampled down to 1393, which reconstructs detail at 2×
before losing any — materially better than the single Lanczos step the runtime
was doing.

They turned out to be **different problems**, which the original measurement
missed:

- **`Coder_Chick.png`** was genuinely detailed art — embroidered patches on
  woven fabric, measuring **267% of the median plate's detail** at native
  resolution. It was the upscale that hurt it, and the rebuild removes the
  Lanczos ringing. A modest but real gain.
- **`Empty_Fridge.png`** was not "soft by design" as first assumed. It was a
  **degraded copy** — 25% of the median plate's detail, the 4th softest of 69.
  A sharp 1254² source was supplied and is now kept in
  `backgroundz_originals/`. Rebuilt from that, the plate measures **4.9× its
  previous detail** and sits at the collection median instead of near the
  bottom.

Worth recording: the winning candidate measured *lower* gradient energy than a
Lanczos-plus-unsharp alternative (9.87 vs 13.23) while looking clearly better.
Sharpening halos inflate that metric without adding detail, so the choice was
made by eye at 1:1, not by the number.

Because both plates changed appearance, `char_compat.json`, `eyez_compat.json`
and `wat_compat.json` were regenerated — they encode measured dominant colours,
so stale entries would have let a character camouflage into the new, much
brighter fridge. `build_mint` still reports camouflage=0 and eye-clash=0.

## 2. Stickers were authored to the wrong canvas — fixed

22 of 23 stickers were **1343 × 1343** rather than 1393, so every one was
resized at render time. That mattered more than the 1.04× scale suggests:
`_render_layer()` maps 0–1343 onto 0–1393, which moves the origin as well as
scaling the art — a sticker's true position was **40px** from where its own
file placed it. Position was implicitly defined by the resize.

All 22 were normalised by baking that exact resize into the file. Verified by
hashing every sticker's composited output before and after: **23 of 23 are
byte-identical**, so there is no visual change — the sheet did not need
re-rendering. What changed is that position and scale are now explicit in the
art instead of emerging from a runtime resize, and the whole class conforms.

No higher-resolution sticker sources exist, so there was no detail to recover;
this is a hygiene fix, not a quality gain. `Sweetardio_200 (30).png` remains
the softest of the class (0.178 against a 0.317 median) — soft in origin, not
in handling.

Every trait class is now on-spec: 129 assets at 1393² across characterz,
skinz, eyez, mouthz, armz, what_are_thosez, stickerz and secret_rarez.
`backgroundz` is the only class allowed to vary, since a plate is re-fit to the
frame by design.

## 3. Two sabers carry colour under full transparency

`Sweetardio_114 (5).png` (Pink Saber) and `(6).png` (Cyan Saber) have non-zero
RGB in fully transparent pixels — mean 11.9 and 14.6, peaks at 255. The Blue
Saber is cleaner at 7.5.

Harmless under a straight alpha composite, but it is latent: any resampling
mixes those pixels into neighbours. That now happens on **every ice cream and
gummy bear**, whose arms are resampled by `cscale` (0.74 / 0.881). No visible
fringe today; worth cleaning when the sabers are next touched.

## 4. The 1/1s are clean

All **23 secret rares** pass every check: 1393 × 1393 RGBA, fully opaque,
no ghost colour, no stray specks. These mint standalone and are the most
valuable tokens in the set, so it is worth stating plainly — there is nothing
to fix here.

Two were flagged `SOFT` (`Secret_Milk_Dunk`, `Secret_Unicorn_Twinkie`) and both
are false. Rendered at 1:1 the Oreo embossing and the Twinkie's crumb texture
are crisp; the metric is depressed by large flat areas in their compositions —
a black ground and a bokeh backdrop respectively. Same failure mode the `SOFT`
flag showed elsewhere: it tracks how much of the frame is smooth, not how much
real detail the art carries.

## 5. Background softness is deliberate, with one to watch

Beyond resolution, 25 plates flag `SOFT` — but backgrounds are *supposed* to be
soft, defocused so the character reads on top of them. The class spans a huge
range of real detail (0.82 to 31.1 gradient energy, median 4.19), which is what
you would expect from a deliberate depth-of-field treatment.

The three softest were checked individually: `Flavor_Explosion` (atmospheric
blur behind a silhouette), `Sugar` (shallow-DOF product shot, sharp at the top
of frame) and `Graham` (a plain cracker-texture backdrop). All three are native
1393² with no sharper source, and all read as intentional. None shows the tell
that gave `Empty_Fridge` away — soft art *with* a sharp original sitting
unused.

`Graham` at 0.82 is the softest real plate in the collection, five times below
the median. Not a defect, but the one to revisit first if the backdrops are
ever re-graded.

---

## What is verified clean

- **Lighting.** Zero of 33 characters violate the top-left key light. Skins
  measure 1.32–1.61 upper-left / lower-right limb luma — correctly keyed. (See
  the methodology note below: this only became a trustworthy result after the
  check was gated on albedo uniformity.)
- **Face-hole edges.** 27 of 33 characters have perfectly anti-aliased face
  holes. The remaining 6 carry 21–89 hard-stepped pixels each — Nutty Bar is
  the worst at 89, out of roughly 800 boundary pixels. Negligible.
- **Canvas hygiene.** All 129 trait assets are exactly 1393 × 1393 RGBA across
  every class. Only `backgroundz` varies, by design.
- **Transparency.** No ghost colour anywhere except the two sabers above.
- **Geometry.** Placement, scale and face-hole alignment verified separately by
  `verify_placement.py` — 33 characters, 55 placement cases, zero issues.

---

## Methodology notes — two checks that lied

Recorded because both would have produced confident, wrong findings.

**The lighting check flagged 7 characters, all false.** A limb-luma comparison
measures albedo and shading together. Neopolitan, Rocky Road and Zaffre all
have a *dark scoop on a light cone*, so their upper-left limb reads dark no
matter where the key light is. Rendering all seven confirmed every one is
correctly lit. The check is now gated on `albedo_uniform()` and reports n/a
rather than a flag on multi-coloured art — after which zero characters fail.

**A "hard aliased edge" on ding_dong was an artifact of my own zoom.** Viewing
the face hole at 4× with NEAREST turns any 1px anti-aliased curve into visible
stair-steps. Measured properly, ding_dong's hole is 100% anti-aliased with zero
hard-stepped pixels.

**Two flags remain unresolved rather than reported as defects.** `WIDE-EDGE`
(25 assets) conflates intended soft art — saber glow, fur slippers, ice-cream
drips — with a sloppy matte, and an attempt to separate the two scored an
unflagged control *worse* than the flagged assets. `SOFT` (7 assets) turned out
to track smooth *subjects* — marshmallow, ding dong, zebra-cake icing,
chocolate glaze, white glove fists — not low-resolution art. Neither is
reportable as a defect on current evidence.

---

## Art-direction observations

Not defects — judgement calls worth having an opinion on.

- **The face is the least-finished layer.** Eyes and mouths are flat vector
  fills sitting on photorealistic bodies. That contrast is the collection's
  identity and should not be traded away, but the face art carries less craft
  than everything under it. This is exactly what `EYEZ_ENHANCE_PROMPTS.md` and
  `MOUTHZ_ENHANCE_PROMPTS.md` exist to address, and the trial run showed the
  treatment works.
- **Ice cream and gummy-bear faces are now ~26% smaller** than the rest of the
  cast, a consequence of the accepted `CHAR_SCALE` fix. Deliberate, but it is
  the one place the collection's uniform face size no longer holds.
- **Two cookies still sit high.** chocolate_chip_cookie −40px and
  chocolate_sandwich_cookie −55px from canvas centre, the same issue the
  doughnuts had. Pending a decision, tracked in `verify_placement.py`.

---

## Reproducing

```bash
python3 asset_assessment/audit_art_quality.py                 # every class
python3 asset_assessment/audit_art_quality.py characterz armz # selected
python3 asset_assessment/verify_placement.py                  # geometry
```
