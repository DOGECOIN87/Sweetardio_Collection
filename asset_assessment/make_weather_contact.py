#!/usr/bin/env python3
"""Contact sheet for the weather states, plus the numbers that judge them.

`dynamic/render.py --sheet` grades ONE token across the eight states, which
answers "what does blizzard look like". It cannot answer the two questions
that actually decide whether a new state ships:

  1. Does it hold across the PLATE FAMILY? background_pop_studies/grade.py
     normalises the plates toward one key, but they still arrive at it from
     very different places, and a state that reads beautifully on a busy
     mid-key plate can do nothing at all on a dark one. So every state is
     rendered down a column of DIFFERENT plates here, not one.

  2. Is it a different TRAIT, or a second copy of one that already exists?
     This is the whole risk in adding to a table whose own docstring puts
     a ceiling on how many ordinary states there can be. Blizzard's
     failure mode is that it reads as snow again; tornado's is that it
     reads as storm. That is not an eyeball judgement -- it is a distance,
     so this measures it.

  3. Does it leave the BACKGROUND readable? The plate is a trait the holder
     chose and cannot switch off, so a state that buries it is taking
     something away rather than adding to it. Every state is scored on how
     much of the plate's own detail and chroma survives, against the
     unweathered mint. verify_sky.py holds the per-state floors; this is
     where the numbers are written down and looked at.

`flooded` is measured here like any other state, but it is not like any
other state: it is the only one that touches the CHARACTER, below its
waterline. What that costs the character is not something a plate-region
measurement can see, so it is not the number to judge that state by --
verify_sky.py checks the part that matters (bit-identical above the line,
water clear of the face) and the sheet is where you look at the rest.

The measurement is mean CIE76 dE over the PLATE REGION ONLY, between every
pair of states on the same plate at the same phase, averaged over plates.
Plate region only because the character is bit-identical in every state by
construction (that is the rule verify_sky.py gates), so including it would
divide every distance by the same constant and flatter every pair.

DISTINCT_DE is the bar, and it is deliberately set ABOVE the closest pair
the collection already ships, because the dusk grade dominates every state
and drags them together. That is tolerable for a pair that has been in the
set from the start and is separated elsewhere in the table; it is not a
standard a NEW state should be allowed to meet. Every run prints the
closest approved pair next to the bar, so the bar can be re-read rather
than trusted.

This is what retired `overcast`: it sat 3.3 from `rain` and 4.8 from
`snow`, closer to both than this bar would let a new state be.

From the repo root:

    python3 asset_assessment/make_weather_contact.py
    python3 asset_assessment/make_weather_contact.py --plates 8
    python3 asset_assessment/make_weather_contact.py --no-sheet   # numbers

Writes dynamic/proof/contact_weather.png and dynamic/proof/WEATHER_DISTINCTNESS.md.
Exits non-zero if a state is not distinct from the one it is most likely
to be confused with.
"""

import argparse
import itertools
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import generator as gen                                    # noqa: E402
from dynamic import sky as skymod                          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROOF = os.path.join(ROOT, "dynamic", "proof")
SHEET = os.path.join(PROOF, "contact_weather.png")
LOG = os.path.join(PROOF, "WEATHER_DISTINCTNESS.md")
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# The six that describe the ordinary sky, and the two that are an event.
# None is a clear sky -- the mint itself, and the reference every other
# state is measured against. There is no 'clear' state to render.
ORDINARY = ["fog", "rain", "snow", "storm"]
SEVERE = ["blizzard", "tornado", "flooded"]

# Which existing state each new one is at risk of duplicating. Being far
# from the average of the table is easy and means nothing; being far from
# your nearest neighbour is the whole question.
CONFUSABLE = {"blizzard": "snow", "tornado": "storm", "flooded": "rain"}

# Mean plate dE below which two states are the same trait wearing two
# names. See the calibration note in the header -- the closest already
# approved pair is reported next to it every run.
DISTINCT_DE = 6.0


def _detail(rgb8, plate):
    """Brightness-normalised band-pass energy -- the same measure
    verify_sky.py gates on, so the record and the gate cannot disagree."""
    a = rgb8[..., :3].astype(np.float64)
    y = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    img = Image.fromarray(np.clip(y, 0, 255).astype(np.uint8), "L")
    near = np.asarray(img.filter(ImageFilter.GaussianBlur(2.0)),
                      dtype=np.float64)
    far = np.asarray(img.filter(ImageFilter.GaussianBlur(8.0)),
                     dtype=np.float64)
    return float(np.abs(near - far)[plate].mean()
                 / max(float(y[plate].mean()), 1.0))


def _font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


# ----------------------------------------------------------------- colour
#
# CIE76 over sRGB. Plain RGB distance would rank a shift in the dark end of
# a night plate as far smaller than the same visible change at noon, which
# is exactly backwards for judging whether a holder can tell two skies
# apart.
def _to_lab(rgb8):
    c = rgb8.astype(np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = lin[..., 0], lin[..., 1], lin[..., 2]
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda v: np.where(v > 0.008856, np.cbrt(v), 7.787 * v + 16.0 / 116.0)
    fx, fy, fz = f(x), f(y), f(z)
    return np.dstack([116.0 * fy - 16.0, 500.0 * (fx - fy),
                      200.0 * (fy - fz)])


def plate_de(a, b, plate):
    """Mean dE between two renders, over the exposed plate only."""
    d = _to_lab(a[..., :3]) - _to_lab(b[..., :3])
    return float(np.sqrt((d * d).sum(-1))[plate].mean())


def plate_chroma(rgb, plate):
    """Mean sRGB chroma over the exposed plate -- max channel minus min.

    Crude next to a Lab chroma and deliberately so: it is a RATIO against
    the same measure on the mint, so the units cancel and what is left is
    "how much of the background's colour is still there".
    """
    a = rgb[..., :3].astype(np.float64)
    return float((a.max(-1) - a.min(-1))[plate].mean())


# ------------------------------------------------------------------ input
def samples(n, seed):
    """n tokens, each on a DIFFERENT plate, with their protect masks.

    Minted fresh rather than reused from dynamic/proof, because the point
    of the sheet is plate variety and the proof tokens are three arbitrary
    draws that may share a plate.
    """
    plates = sorted(gen.get_files(gen.BACKGROUNDZ))
    overlays = set(gen.BG_OVERLAY_PAIRS.values())
    plates = [p for p in plates if p not in overlays]
    random.seed(seed)
    picks = random.sample(plates, min(n, len(plates)))

    os.makedirs(PROOF, exist_ok=True)
    out = []
    for i, plate in enumerate(picks, 1):
        layers, char = gen.generate_random_combination(
            force_bg=(gen.BACKGROUNDZ, plate))
        b = os.path.join(PROOF, f"wx_{i}.png")
        m = os.path.join(PROOF, f"wx_{i}_mask.png")
        fl = os.path.join(PROOF, f"wx_{i}_float.png")
        gen.create_image(layers, b, mask_path=m, float_mask_path=fl)
        name = os.path.splitext(plate)[0]
        print(f"  {i}. {char} on {name}", flush=True)
        out.append((name, Image.open(b).convert("RGBA"),
                    Image.open(m).convert("L"), i,
                    Image.open(fl).convert("L")))
    return out


# ------------------------------------------------------------------ sheet
def build_sheet(grid, states, labels, cell, phase, path):
    """states down the page, plates across it, with the severe tier ruled off."""
    pad, cap, top, rule = 12, 30, 76, 16
    cols = len(labels)
    rows = len(states)
    extra = rule if any(s in SEVERE for s in states) else 0
    w = cols * cell + pad * (cols + 1)
    h = top + rows * (cell + cap) + pad * (rows + 1) + extra
    sheet = Image.new("RGB", (w, h), (16, 17, 21))
    draw = ImageDraw.Draw(sheet)
    named = [s for s in states if s is not None]
    draw.text((pad + 2, 16),
              f"Sweetardio — {len(named)} weather states across "
              f"{cols} plates  ·  {phase.replace('_', ' ')}",
              font=_font(25), fill=(238, 240, 246))
    draw.text((pad + 2, 47),
              "background only; body, face, arms, footwear and stickers are "
              "bit-identical to the mint in every cell. Top row is the "
              "unweathered plate, for comparison.",
              font=_font(15), fill=(150, 156, 172))

    y = top + pad
    for state in states:
        if state == SEVERE[0] and extra:
            draw.line([(pad, y - pad // 2 - 2), (w - pad, y - pad // 2 - 2)],
                      fill=(64, 68, 82), width=1)
            draw.text((pad + 2, y - pad // 2 + 2), "SEVERE — event states",
                      font=_font(14), fill=(150, 156, 172))
            y += rule
        for c in range(cols):
            x = pad + c * (cell + pad)
            sheet.paste(grid[(state, c)].convert("RGB").resize(
                (cell, cell), Image.Resampling.LANCZOS), (x, y))
        name = state or "no weather — the mint, unchanged"
        draw.text((pad + 2, y + cell + 6),
                  f"{name}   ·   " + "   ".join(l[:22] for l in labels),
                  font=_font(16), fill=(176, 182, 198))
        y += cell + cap + pad
    # This sheet is a committed design record, and at eight rows of graded
    # photographic plates it is the largest file in dynamic/proof (~6MB at
    # the default cell). optimize=True buys only about 2% of that -- the
    # size is the plate content, not the encoder -- so drop --cell if it
    # needs to be smaller, rather than expecting compression to do it.
    sheet.save(path, optimize=True)
    return path


# ------------------------------------------------------------------ table
def distinctness(grid, states, plates):
    """Mean plate dE for every pair of states, averaged over plates."""
    pair = {}
    for a, b in itertools.combinations(states, 2):
        vals = [plate_de(np.asarray(grid[(a, c)]), np.asarray(grid[(b, c)]),
                         plates[c]) for c in range(len(plates))]
        pair[(a, b)] = sum(vals) / len(vals)
    return pair


def get(pair, a, b):
    return pair.get((a, b), pair.get((b, a)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plates", type=int, default=6,
                    help="how many DIFFERENT plates to render each state on")
    ap.add_argument("--phase", default="day",
                    choices=list(skymod.SKY_STATES))
    ap.add_argument("--seed", type=int, default=4444)
    ap.add_argument("--cell", type=int, default=300)
    ap.add_argument("--no-sheet", action="store_true",
                    help="measure only; skip the contact sheet")
    args = ap.parse_args()

    states = [s for s in ORDINARY + SEVERE if s in skymod.WEATHER_STATES]
    print(f"minting {args.plates} tokens on distinct plates")
    toks = samples(args.plates, args.seed)
    labels = [t[0] for t in toks]
    plate_masks = [np.asarray(t[2]) == 0 for t in toks]

    print(f"grading {len(states)} states x {len(toks)} plates at "
          f"{args.phase}")
    grid = {}
    for state in [None] + states:
        for c, (_, base, mask, tid, afl) in enumerate(toks):
            grid[(state, c)] = skymod.apply_sky(base, mask, args.phase,
                                                state, seed=tid, t=0.25,
                                                afloat=afl)
        print(f"  {state or 'no weather (the mint)'}", flush=True)

    # Legibility, measured against THE SAME PHASE WITH NO WEATHER, not
    # against the mint. The weather is what is on trial here; folding in
    # the sky grade would charge `fog` for the fact that dusk is darker
    # than noon and make the number mean two things at once. At `day` the
    # two baselines are the same image anyway, which is why this agrees
    # with verify_sky.py's floors -- those are measured at day.
    legib = {}
    for state in states:
        det, chr_ = [], []
        for c, (_, base, mask, tid) in enumerate(toks):
            plate = np.asarray(mask) == 0
            ref = np.asarray(grid[(None, c)])
            out = np.asarray(grid[(state, c)])
            d0 = _detail(ref, plate)
            det.append(_detail(out, plate) / d0 if d0 else 1.0)
            c0 = plate_chroma(ref, plate)
            chr_.append(plate_chroma(out, plate) / c0 if c0 else 1.0)
        legib[state] = (min(det), min(chr_))

    pair = distinctness(grid, states, plate_masks)

    # Reported, not used as the threshold: the closest pair among the
    # ordinary states, which were approved before these two existed. It is
    # context for DISTINCT_DE, which sits deliberately above it.
    approved = [(get(pair, a, b), a, b)
                for a, b in itertools.combinations(ORDINARY, 2)
                if get(pair, a, b) is not None]
    approved.sort()
    lines = []

    def p(s=""):
        lines.append(s)
        print(s)

    p(f"# Weather distinctness — {args.phase}, {len(toks)} plates")
    p()
    p(f"Mean CIE76 dE over the exposed plate, averaged across "
      f"{len(toks)} different plates.")
    p(f"Seed {args.seed}. Plates: {', '.join(labels)}.")
    p()
    if approved:
        d, a, b = approved[0]
        p(f"Closest ALREADY-APPROVED pair: `{a}` / `{b}` at dE {d:.1f} — "
          f"context, not the bar.")
        p(f"DISTINCT_DE is {DISTINCT_DE:.1f}, set deliberately above it: a "
          f"new state entering a capped")
        p(f"table has to separate harder than a pair that has been in the "
          f"set from the start and")
        p(f"is distinguished elsewhere in the matrix.")
        p()

    p("| state | plate detail kept | plate chroma kept |")
    p("|---|---|---|")
    for state in states:
        d, c = legib[state]
        p(f"| `{state}` | {d * 100:.0f}% | {c * 100:.0f}% |")
    p()
    p(f"Worst of the {len(toks)} plates, against the SAME PHASE WITH NO "
      f"WEATHER — so the number is")
    p("what the weather costs, not what the hour of day costs. The "
      "per-state floors live in")
    p("`verify_sky.py`'s `PLATE_DETAIL_FLOOR`, which fails the build if a "
      "state drifts past its own.")
    p()

    p("| new state | vs | dE | vs whole table (min) | verdict |")
    p("|---|---|---|---|---|")
    failures = []
    for s in SEVERE:
        if s not in states:
            continue
        near = CONFUSABLE.get(s)
        d = get(pair, s, near)
        others = [(get(pair, s, o), o) for o in states if o != s]
        lo, lo_name = min(others)
        ok = d >= DISTINCT_DE and lo >= DISTINCT_DE
        p(f"| `{s}` | `{near}` | {d:.1f} | {lo:.1f} (`{lo_name}`) | "
          f"{'distinct' if ok else 'TOO CLOSE'} |")
        if not ok:
            failures.append(f"{s}: nearest is {lo_name} at dE {lo:.1f}, "
                            f"under DISTINCT_DE {DISTINCT_DE:.1f}")

    p()
    p("Full matrix (dE):")
    p()
    p("| | " + " | ".join(states) + " |")
    p("|" + "---|" * (len(states) + 1))
    for a in states:
        row = []
        for b in states:
            row.append("—" if a == b else f"{get(pair, a, b):.1f}")
        p(f"| **{a}** | " + " | ".join(row) + " |")

    os.makedirs(PROOF, exist_ok=True)
    with open(LOG, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nwrote {os.path.relpath(LOG, ROOT)}")

    if not args.no_sheet:
        path = build_sheet(grid, [None] + states, labels, args.cell,
                           args.phase, SHEET)
        print(f"wrote {os.path.relpath(path, ROOT)}")

    if failures:
        print("\nFAIL — a state is not distinct enough to be its own trait:")
        for f in failures:
            print("  " + f)
        return 1
    print("\nOK — every severe state is distinct from the one it is most "
          "likely to be confused with.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
