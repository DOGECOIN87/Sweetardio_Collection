#!/usr/bin/env python3
"""Bake the 444 animated weather tokens: a weathered still and its loop.

The weather is no longer live. build_mint.py draws it once, at exact
counts, and it is a permanent trait of the token from then on -- so it is
rendered once here, into files, and never computed again.

Two things come out per token:

  images/<id>.png    the weathered still, at the full 1393 mint canvas.
                     This REPLACES the clear render, because the still is
                     what every grid, thumbnail, search result and push
                     notification shows -- a token whose trait says Tornado
                     and whose thumbnail is a clear sky has the trait
                     invisible exactly where most people will look.
  anim/<id>.mp4      the seamless loop, for animation_url.

IT ALWAYS RENDERS FROM THE CLEAR ORIGINAL, never from its own output. The
first run moves the clear render to images_clear/ and works from there
forever after, so re-running is idempotent rather than compounding a
second flood on top of the first. That is the same discipline
shade_skin_balls.py and shade_eyes.py hold to, for the same reason: a pass
that reads its own output is one interrupted run away from silently
double-applying.

Needs the mint rendered WITH masks first -- the protect mask is what holds
the effect off the character, and there is no way to recover it from a
finished PNG:

    python3 asset_assessment/build_mint.py --render --masks \\
            --animation '{id}.mp4'
    python3 asset_assessment/bake_weather.py

    python3 asset_assessment/bake_weather.py --limit 8      # a proof run
    python3 asset_assessment/bake_weather.py --force        # re-bake all

Resumable: a token whose loop already exists is skipped, so an interrupted
run costs only the token it was on.
"""

import argparse
import json
import os
import shutil
import sys
import time

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dynamic import sky as skymod                        # noqa: E402
from dynamic.animate import write_mp4                    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MINT = os.path.join(ROOT, "output", "mint")
MANIFEST = os.path.join(ROOT, "output", "mint_manifest.json")

IMAGES = os.path.join(MINT, "images")
CLEAR = os.path.join(MINT, "images_clear")
MASKS = os.path.join(MINT, "masks")
# The sticker-only mask, written beside the protect mask by build_mint.py
# --masks. Optional: a run whose mint predates it simply floats nothing.
FLOATS = os.path.join(MINT, "float_masks")
ANIM = os.path.join(MINT, "anim")

# `day` is the identity grade: the exact light the other 4,000 tokens are
# minted at. So a weather token differs from the rest of the collection by
# WEATHER ONLY, which is the whole trait. It was briefly baked at blue
# dusk, which made the animated tier a different hour as well -- a change
# to everybody's art that nobody asked for.
DEFAULT_PHASE = "day"


def source_for(tid):
    """The CLEAR render for a token, moved aside on first bake.

    Returns None if the mint has not been rendered for this token.
    """
    clear = os.path.join(CLEAR, f"{tid}.png")
    if os.path.exists(clear):
        return clear
    live = os.path.join(IMAGES, f"{tid}.png")
    if not os.path.exists(live):
        return None
    os.makedirs(CLEAR, exist_ok=True)
    shutil.move(live, clear)
    return clear


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default=DEFAULT_PHASE,
                    choices=list(skymod.SKY_STATES))
    ap.add_argument("--frames", type=int, default=36)
    ap.add_argument("--size", type=int, default=512,
                    help="loop resolution; the STILL is always full canvas")
    ap.add_argument("--ms", type=int, default=55)
    ap.add_argument("--limit", type=int, default=0,
                    help="bake only the first N, for a proof run")
    ap.add_argument("--only", nargs="*", type=int, default=None)
    ap.add_argument("--force", action="store_true",
                    help="re-bake tokens whose loop already exists")
    args = ap.parse_args()

    if not os.path.exists(MANIFEST):
        sys.exit("no output/mint_manifest.json; run build_mint.py first")
    manifest = json.load(open(MANIFEST))

    todo = [(int(t), v["weather"]) for t, v in manifest.items()
            if v.get("weather")]
    todo.sort()
    if args.only:
        keep = set(args.only)
        todo = [(t, w) for t, w in todo if t in keep]
    if args.limit:
        todo = todo[:args.limit]
    if not todo:
        sys.exit("no weather tokens in the manifest — was it minted with "
                 "--no-weather?")

    os.makedirs(ANIM, exist_ok=True)
    os.makedirs(IMAGES, exist_ok=True)
    fps = 1000.0 / args.ms
    print(f"baking {len(todo)} weather tokens at {args.phase}  "
          f"still {'full canvas'}, loop {args.size}px x {args.frames}f")

    done = skipped = 0
    missing = []
    t_start = time.time()
    for tid, state in todo:
        out_mp4 = os.path.join(ANIM, f"{tid}.mp4")
        if os.path.exists(out_mp4) and not args.force:
            skipped += 1
            continue
        src = source_for(tid)
        mask_path = os.path.join(MASKS, f"{tid}.png")
        if src is None or not os.path.exists(mask_path):
            missing.append(tid)
            continue

        base = Image.open(src).convert("RGBA")
        mask = Image.open(mask_path).convert("L")
        float_path = os.path.join(FLOATS, f"{tid}.png")
        afloat = (Image.open(float_path).convert("L")
                  if os.path.exists(float_path) else None)

        # The still: full mint canvas, frame 0 of the loop, so the image a
        # marketplace caches is literally where the animation starts.
        still = skymod.apply_sky(base, mask, args.phase, state,
                                 seed=tid, t=0.0, afloat=afloat)
        still.save(os.path.join(IMAGES, f"{tid}.png"), optimize=True)

        # The loop: one graded plate, N cheap frames -- the whole reason
        # this is affordable at 444 tokens.
        sm = base.resize((args.size, args.size), Image.Resampling.LANCZOS)
        mk = mask.resize((args.size, args.size), Image.Resampling.LANCZOS)
        # Resized HERE rather than inside frame(): the loop calls frame()
        # once per frame, and re-resampling the float mask 24 times a token
        # over 444 tokens is 10k LANCZOS passes for one unchanging image.
        fk = (afloat.resize((args.size, args.size), Image.Resampling.LANCZOS)
              if afloat is not None else None)
        static = skymod.grade_static(sm, args.phase, state)
        frames = [skymod.frame(static, mk, t=i / args.frames, seed=tid,
                               afloat=fk)
                  for i in range(args.frames)]
        if write_mp4(frames, out_mp4, fps) is None:
            sys.exit("no ffmpeg — pip install imageio-ffmpeg")

        done += 1
        if done % 25 == 0 or done == 1:
            rate = (time.time() - t_start) / done
            left = (len(todo) - skipped - done) * rate
            print(f"  {done}/{len(todo) - skipped}  {rate:.1f}s/token  "
                  f"~{left / 60:.0f} min left", flush=True)

    dt = time.time() - t_start
    print(f"\nbaked {done}, skipped {skipped} already done, in "
          f"{dt / 60:.1f} min"
          + (f"  ({dt / done:.1f}s/token)" if done else ""))
    if missing:
        print(f"\n{len(missing)} token(s) had no render or no mask: "
              f"{missing[:10]}{'…' if len(missing) > 10 else ''}")
        print("  the mint must be rendered WITH masks:")
        print("  python3 asset_assessment/build_mint.py --render --masks")
        return 1
    print(f"  stills  -> {os.path.relpath(IMAGES, ROOT)}/<id>.png "
          f"(clear originals kept in {os.path.relpath(CLEAR, ROOT)}/)")
    print(f"  loops   -> {os.path.relpath(ANIM, ROOT)}/<id>.mp4")
    print("\nnow check them: python3 asset_assessment/verify_media.py "
          f"--dir {os.path.relpath(ANIM, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
