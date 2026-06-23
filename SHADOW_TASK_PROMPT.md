# NEXT TASK — Character grounding / drop shadows (Sweetardio generator)

Handoff brief for the next assistant. Goal: make every character read as
sitting *in* its scene by adding a soft, configurable shadow. This is a pure
compositing addition — no change to trait selection.

## Repo & where to work
- Sweetardio NFT generator. The compositor is **`generator.py`**;
  measurement/render tools are in **`asset_assessment/`**.
- Develop on branch **`claude/happy-mendel-9xaj1n`**, commit with clear
  messages, push to that branch, then **merge `--no-ff` into `main` and push
  main** (keep them in sync). **No PR** unless asked. Pushes go to
  **github.com** (the local git proxy is read-only). The owner sometimes edits
  `main` directly (asset updates) — **`git fetch origin main` and fast-forward
  before assuming you're ahead.**

## How the compositor works (read `generator.py` first)
- `generate_random_combination()` returns an ordered list of **layer dicts**;
  `create_image(layers, out)` composites them onto a **1393×1393 RGBA** canvas.
- Layer order (bottom→top): background plate → [WAT footwear base] →
  before-skinz body → **skin ball** → after-skinz body → eyes → mouth →
  [WAT/gorbhouse overlay] → arms → **corner sticker** → [paired bg overlay].
- Per-layer keys: `path`, `offset` (bool; +150 footwear-less drop), `dy`
  (per-char trim), `fscale`/`fcenter` (ball_fit), `cscale`/`ccenter` (per-char
  scale about **(690,601)**), `ascale`/`acenter` (per-arm scale), `shadow`
  (existing ball shadow).
- `create_image` per layer: resize → `fscale` → `cscale` → `ascale` →
  `dy`/`offset` translate → [existing `SKIN_SHADOW`] → `alpha_composite`; it
  builds `fg_mask` = union of all non-bg layer alphas.

## The problem (what's missing)
Characters are composited straight onto the plate with **no shadow**, so they
look pasted-on instead of sitting in the scene. Add a soft shadow that anchors
each character to its background. Highest-impact polish in the collection.

## Existing hook — read it, then go BEYOND it
`SKIN_SHADOW = None` plus a branch in `create_image` blurs a layer's alpha,
offsets it, and **clips it to `fg_mask`** ("never falls on the background").
That's a face-ball shadow meant to fall on the **body** — the *opposite* of
grounding. The grounding shadow must fall **on the background**, behind the
character. Do **not** reuse that fg clip.

## Goal
A configurable soft shadow cast by the character's silhouette **onto the bg,
above the plate and below the character**, so the character sits on top of its
own shadow. One config dict (like the repo's other config), `None` disables.
Tunables: `blur`, `opacity`, `dx`, `dy` (+down), and a `mode` (`ground` =
squashed contact pool at the base; `drop` = offset+blur full silhouette;
`auto` = pick per character).

## Required refactor of `create_image`
Layers draw sequentially, so the silhouette isn't known when the bg is drawn.
Move to a 3-stage composite:
1. Composite the **background** plate(s).
2. Build the **character composite** on a separate transparent canvas — all
   character-anchored layers (body, skin, eyes, mouth, arms, and
   footwear/gorbhouse base where present), with identical per-layer transforms.
   Exclude the bg, the **corner sticker**, and the **paired bg overlay**.
3. Derive the shadow from that composite's alpha → black RGBA whose alpha =
   `blur(offset(squash?(silhouette))) * opacity`; composite onto the bg
   **without clipping to fg**.
4. Composite the character composite.
5. Composite the **sticker** + **paired bg overlay** on top (as today).

Recommend deriving the silhouette from the **body+skin** mass (optionally
excluding arms) so a katana doesn't throw a shadow spike — make it
configurable.

## Measured context & constraints
- Pivot / ball center **(690,601)**. Ground band ~**1084–1109**; NO_OFFSET
  "churro line" **1111**; ice-cream/bear cone line **1290**.
- **Grounded** characters (ice creams, bears, churro, footwear/gorbhouse
  wearers): seat a contact **pool** at the lowest opaque row of the foreground.
- **Centered/portrait** characters (`CENTERED_CHARS` = cookies,
  oatmeal_cream_pie, gummy_worm, footwear-less doughnuts) **float by design** —
  a ground pool looks wrong; give them a soft **drop** shadow or none. Branch
  `mode` on grounded vs `is_centered`+footwear-less.
- Characters **with footwear/gorbhouse** already have a base; seat the shadow
  under the *base*, not the body.
- **Preserve everything**: WAT/gorbhouse exclusivity, `ARMZ_CHAR_LOCK`,
  `NO_OFFSET_CHARS`, `CENTERED_CHARS`, `GORBHOUSE_CHANCE`, char↔bg
  camouflage + pairing tables (`traits/char_compat.json`),
  `traits/skin_weights.json`, and the **4444 mint allocator**
  (`asset_assessment/build_mint.py`, `force_bg` path). The shadow is **pure
  compositing** — `generate_random_combination`'s layer list is unchanged; all
  work is in `create_image`. Keep it deterministic (no unseeded randomness) and
  cheap (≈one extra blur+composite per token, so a 4444 render stays
  reasonable).

## Workflow — measure, don't guess
- After each change: `python3 asset_assessment/render_batch_sheet.py` (seed 42,
  100 renders) and eyeball `/tmp/batch100_strip_{1..4}.png`. Also render
  specific cases at full res: grounded ice-cream/bear, centered cookie, a
  footwear character, a gorbhouse doughnut — confirm the shadow seats correctly
  and never shows **through/above** the character.
- `python3 asset_assessment/verify_generator_rules.py` → must stay
  **0 violations / 0 unresolved**.
- `python3 asset_assessment/audit_placement.py` → must stay **0 hole flags**.
- Show the owner a **before/after** (shadow off vs on) for ~8 diverse
  characters before committing.

## Definition of done
Every character reads as sitting in its scene — grounded ones with a soft
contact pool at the base, portrait ones with a subtle drop shadow (or none) —
nothing showing through/above the subject, all driven by one tunable config
dict, before/after approved by the owner, and synced to `main`.
