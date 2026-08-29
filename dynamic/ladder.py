#!/usr/bin/env python3
"""Sweep one SKY_STATES parameter and render the candidates side by side.

The repo's habit for a value that can only be picked by eye -- the skin
ball relight, the shadow settings -- is to render a ladder rather than
argue about the number. This does that for the sky grade, and adds the one
measurement the eye is bad at: how much plate detail each candidate costs.

It renders candidates WITHOUT writing them. Nothing here mutates
SKY_STATES on disk; pick a value from the sheet and edit sky.py by hand.

    python3 dynamic/ladder.py --phase night --param sh_amt \\
            --values 0.54 0.42 0.30 0.20 0.10
    python3 dynamic/ladder.py --phase night --param contrast \\
            --values -0.12 -0.06 0.0 0.06
"""

import argparse
import copy
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dynamic import sky as skymod

PROOF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proof")
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def plate_detail(img, plate_mask):
    """High-frequency energy on the PLATE, normalised by plate brightness.

    The normalisation is the whole point. Raw high-frequency energy falls
    at night simply because everything is darker, which would rank every
    dark grade as 'destroying detail'. Dividing by the plate's own mean
    luma separates real softening -- flattening, black lift, a shadow tint
    strong enough to collapse the shadows onto one colour -- from mere
    exposure.
    """
    y = np.asarray(img, dtype=np.float64)[..., :3].mean(-1)
    hi = np.abs(np.diff(y, axis=0))
    m = plate_mask[1:, :]
    if not m.any():
        return 0.0
    return float(hi[m].mean() / max(y[plate_mask].mean(), 1e-6))


def samples():
    out = []
    for i in range(1, 100):
        b = os.path.join(PROOF, f"token_{i}.png")
        m = os.path.join(PROOF, f"token_{i}_mask.png")
        if os.path.exists(b) and os.path.exists(m):
            out.append((i, Image.open(b).convert("RGBA"),
                        Image.open(m).convert("L")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="night", choices=list(skymod.SKY_STATES))
    ap.add_argument("--param", default="sh_amt")
    ap.add_argument("--values", nargs="+", type=float,
                    default=[0.54, 0.42, 0.30, 0.20, 0.10])
    ap.add_argument("--weather", default=None,
                    help="a WEATHER_STATES key; omit for a clear sky, which "
                         "is the absence of a state rather than one of them")
    ap.add_argument("--token", type=int, default=1)
    ap.add_argument("--cell", type=int, default=430)
    args = ap.parse_args()

    toks = samples()
    if not toks:
        sys.exit("no sample tokens; run: python3 dynamic/render.py --tokens 3")
    current = skymod.SKY_STATES[args.phase].get(args.param)
    print(f"phase={args.phase}  param={args.param}  "
          f"current={current}  weather={args.weather}")

    # mint reference, per token
    ref = {}
    for idx, base, mask in toks:
        pm = np.asarray(mask) == 0
        ref[idx] = (plate_detail(base, pm), pm)

    original = copy.deepcopy(skymod.SKY_STATES[args.phase])
    cells, rows = [], []
    try:
        for v in args.values:
            skymod.SKY_STATES[args.phase][args.param] = v
            keeps = []
            for idx, base, mask in toks:
                out = skymod.apply_sky(base, mask, args.phase, args.weather,
                                       seed=idx)
                r0, pm = ref[idx]
                keeps.append(plate_detail(out, pm) / max(r0, 1e-9) * 100.0)
                if idx == args.token:
                    shown = out
            mean = sum(keeps) / len(keeps)
            mark = "  <- current" if current is not None and abs(
                v - current) < 1e-9 else ""
            cells.append((f"{args.param} = {v:g}   detail {mean:.0f}%{mark}",
                          shown))
            rows.append((v, mean, keeps))
            print(f"  {args.param}={v:<7g} plate detail kept "
                  f"{mean:5.1f}%   per-token "
                  + " ".join(f"{k:.0f}%" for k in keeps))
    finally:
        skymod.SKY_STATES[args.phase] = original

    pad, cap, top = 14, 34, 62
    cols = len(cells)
    w = cols * args.cell + pad * (cols + 1)
    h = top + args.cell + cap + pad * 2
    sheet = Image.new("RGB", (w, h), (16, 17, 21))
    draw = ImageDraw.Draw(sheet)
    title = (f"Sweetardio — '{args.phase}' ladder on {args.param}   "
             f"(plate detail kept, vs the mint, mean of {len(toks)} tokens)")
    tf = _font(24)
    for pt in range(24, 11, -1):
        tf = _font(pt)
        if draw.textlength(title, font=tf) <= w - 2 * pad - 4:
            break
    draw.text((pad + 2, 18), title, font=tf, fill=(238, 240, 246))
    for i, (label, img) in enumerate(cells):
        x = pad + i * (args.cell + pad)
        sheet.paste(img.convert("RGB").resize(
            (args.cell, args.cell), Image.Resampling.LANCZOS), (x, top + pad))
        draw.text((x + 2, top + pad + args.cell + 8), label, font=_font(18),
                  fill=(176, 182, 198))
    out = os.path.join(PROOF, f"ladder_{args.phase}_{args.param}.png")
    sheet.save(out)
    print(f"\n{out}")


if __name__ == "__main__":
    main()
