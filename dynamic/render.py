#!/usr/bin/env python3
"""Render dynamic-sky variants of a token, and build proof sheets.

Two jobs:

  1. `--tokens N` mints N sample tokens through the normal pipeline, saving
     the base PNG *and* its protect mask, into dynamic/proof/. This is the
     mint-build step, in miniature: build_mint.py would do the same thing
     by passing mask_path= to create_image().

  2. `--sheet` grades those tokens across all eight sky phases and all
     eight weather states and lays the results out as contact sheets, so
     the art direction can be judged on pixels rather than on a parameter
     table.

From the repo root:

    python3 dynamic/render.py --tokens 3 --sheet
    python3 dynamic/render.py --sheet --strength 0.6
"""

import argparse
import datetime
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont

import generator as gen
from dynamic import sky as skymod
from dynamic import solar

PROOF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proof")
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

PHASE_ORDER = ["high_noon", "day", "golden_dawn", "golden_dusk",
               "blue_dawn", "blue_dusk", "twilight", "night"]
# Ordinary states first, then the two severe ones, so a weather sheet
# reads as the tiering it is rather than as eight equal options.
WEATHER_ORDER = ["clear", "overcast", "fog", "rain", "snow", "storm",
                 "blizzard", "tornado"]


def _font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def mint_samples(n, seed):
    """Mint n tokens the normal way, saving base PNG + protect mask."""
    os.makedirs(PROOF_DIR, exist_ok=True)
    random.seed(seed)
    made = []
    for i in range(1, n + 1):
        layers, char = gen.generate_random_combination()
        base = os.path.join(PROOF_DIR, f"token_{i}.png")
        mask = os.path.join(PROOF_DIR, f"token_{i}_mask.png")
        t0 = time.time()
        gen.create_image(layers, base, mask_path=mask)
        print(f"  token {i}: {char} ({time.time() - t0:.2f}s composite)")
        made.append((i, char, base, mask))
    return made


def variety_sheet(n, phases, cell_px, seed, strength):
    """One token per plate, graded at each named phase.

    The grade has to hold across the whole plate FAMILY, not just whichever
    plate the first sample happened to draw. background_pop_studies/grade.py
    already normalises the plates toward one key, but they still arrive at
    it from very different places -- and a phase that reads beautifully on a
    busy mid-key plate can do nothing at all on a dark one.
    """
    os.makedirs(PROOF_DIR, exist_ok=True)
    plates = sorted(gen.get_files(gen.BACKGROUNDZ))
    overlays = set(gen.BG_OVERLAY_PAIRS.values())
    plates = [p for p in plates if p not in overlays]
    random.seed(seed)
    picks = random.sample(plates, min(n, len(plates)))

    made = []
    for i, plate in enumerate(picks, 1):
        layers, char = gen.generate_random_combination(
            force_bg=(gen.BACKGROUNDZ, plate))
        b = os.path.join(PROOF_DIR, f"var_{i}.png")
        m = os.path.join(PROOF_DIR, f"var_{i}_mask.png")
        gen.create_image(layers, b, mask_path=m)
        made.append((os.path.splitext(plate)[0], char,
                     Image.open(b).convert("RGBA"), Image.open(m).convert("L")))
        print(f"  {i}. {char} on {plate}")

    for ph in phases:
        cells = []
        for plate, char, base, mask in made:
            img = skymod.apply_sky(base, mask, ph, "clear",
                                   seed=hash(plate) & 0xffff,
                                   strength=strength)
            cells.append((f"{plate[:26]}", img))
        out = contact_sheet(
            cells, 3, cell_px,
            f"Sweetardio — '{ph.replace('_', ' ')}' across {len(made)} "
            f"different plates",
            os.path.join(PROOF_DIR, f"sheet_variety_{ph}.png"))
        print(out)


def _load(idx):
    base = os.path.join(PROOF_DIR, f"token_{idx}.png")
    mask = os.path.join(PROOF_DIR, f"token_{idx}_mask.png")
    if not (os.path.exists(base) and os.path.exists(mask)):
        return None
    return Image.open(base).convert("RGBA"), Image.open(mask).convert("L")


def contact_sheet(cells, cols, cell_px, title, out_path):
    """cells = [(label, PIL image)]; laid out on a dark card with captions."""
    pad, cap, top = 14, 34, 62
    rows = (len(cells) + cols - 1) // cols
    w = cols * cell_px + pad * (cols + 1)
    h = top + rows * (cell_px + cap) + pad * (rows + 1)
    sheet = Image.new("RGB", (w, h), (16, 17, 21))
    draw = ImageDraw.Draw(sheet)
    # Shrink the title until it fits the sheet rather than letting it run off
    # the right edge -- these sheets exist to be READ.
    tf = _font(26)
    for pt in range(26, 11, -1):
        tf = _font(pt)
        if draw.textlength(title, font=tf) <= w - 2 * pad - 4:
            break
    draw.text((pad + 2, 18), title, font=tf, fill=(238, 240, 246))

    for i, (label, img) in enumerate(cells):
        r, c = divmod(i, cols)
        x = pad + c * (cell_px + pad)
        y = top + pad + r * (cell_px + cap + pad)
        sheet.paste(img.convert("RGB").resize(
            (cell_px, cell_px), Image.Resampling.LANCZOS), (x, y))
        draw.text((x + 2, y + cell_px + 8), label, font=_font(19),
                  fill=(176, 182, 198))
    sheet.save(out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens", type=int, default=0,
                    help="mint this many fresh sample tokens first")
    ap.add_argument("--seed", type=int, default=4444)
    ap.add_argument("--sheet", action="store_true",
                    help="build the phase and weather proof sheets")
    ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--cell", type=int, default=420)
    ap.add_argument("--variety", type=int, default=0,
                    help="mint N tokens on N DIFFERENT plates and sheet them")
    ap.add_argument("--variety-phases", nargs="*",
                    default=["golden_dusk", "night"])
    ap.add_argument("--token", type=int, default=1,
                    help="which minted sample to grade for the sheets")
    args = ap.parse_args()

    if args.tokens:
        print(f"minting {args.tokens} sample tokens -> {PROOF_DIR}")
        mint_samples(args.tokens, args.seed)

    if args.variety:
        print(f"minting {args.variety} tokens on distinct plates")
        variety_sheet(args.variety, args.variety_phases, args.cell,
                      args.seed, args.strength)

    if not args.sheet:
        return

    tok = _load(args.token)
    if tok is None:
        sys.exit("no sample tokens; run with --tokens 3 first")
    base, mask = tok
    tid = args.token
    suffix = "" if tid == 1 else f"_t{tid}"

    # --- sheet 1: all eight sky phases, clear weather -------------------
    cells, t0 = [], time.time()
    for ph in PHASE_ORDER:
        img = skymod.apply_sky(base, mask, ph, "clear", seed=tid,
                               strength=args.strength)
        tag = "  (canonical mint)" if ph == "day" else ""
        cells.append((ph.replace("_", " ") + tag, img))
    per = (time.time() - t0) / len(PHASE_ORDER)
    p1 = contact_sheet(cells, 4, args.cell,
                       "Sweetardio — time of day  (background only; "
                       "every other trait is bit-identical to the mint)",
                       os.path.join(PROOF_DIR, f"sheet_phases{suffix}.png"))
    print(f"{p1}   [{per * 1000:.0f} ms per render]")

    # --- sheet 2: weather, at dusk where it reads most clearly ----------
    cells = []
    for wx in WEATHER_ORDER:
        img = skymod.apply_sky(base, mask, "blue_dusk", wx, seed=tid,
                               strength=args.strength)
        cells.append((f"blue dusk + {wx}", img))
    p2 = contact_sheet(cells, 4, args.cell,
                       "Sweetardio — weather  (particles fall BEHIND the "
                       "character; fog hazes the plate, not the figure)",
                       os.path.join(PROOF_DIR, f"sheet_weather{suffix}.png"))
    print(p2)

    # --- sheet 3: the same hour, six cities ----------------------------
    now = datetime.datetime(2026, 8, 21, 18, 0,
                            tzinfo=datetime.timezone.utc)
    cities = [("Reykjavik", 64.15, -21.94), ("London", 51.51, -0.13),
              ("New York", 40.71, -74.01), ("Singapore", 1.35, 103.82),
              ("Tokyo", 35.68, 139.65), ("Sydney", -33.87, 151.21)]
    cells = []
    for name, la, lo in cities:
        ph, alt = solar.sun_phase(la, lo, now)
        img = skymod.apply_sky(base, mask, ph, "clear", seed=tid,
                               strength=args.strength)
        cells.append((f"{name} — {ph.replace('_', ' ')} ({alt:+.0f}°)", img))
    p3 = contact_sheet(cells, 3, args.cell,
                       f"Sweetardio — one token, one instant "
                       f"({now:%d %b %Y %H:%M} UTC), six holders",
                       os.path.join(PROOF_DIR, f"sheet_cities{suffix}.png"))
    print(p3)


if __name__ == "__main__":
    main()
