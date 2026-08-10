#!/usr/bin/env python3
"""Solve the draw gains in traits/rarity_weights.json so the REALISED mint
distribution matches the intended one.

The always-present traits -- eyes, mouths, backgrounds -- cannot be
slot-allocated to exact counts the way arms, footwear and stickers are,
because they have to compose with the compat blocklists. They are drawn by
weight instead. But a weight is not a share: an asset that is hard-blocked
from part of the pool comes out rarer than its weight says, and the worse the
blocking the bigger the gap.

That gap was not hypothetical. Before any of this existed, the eye
distribution ran 3.87 % (Blue) to 13.01 % (Smug) -- a 3.4x spread nobody
chose. It correlates perfectly with how much of the plate pool each eye is
barred from:

    Blue     blocked from 42.0 % of plates ->  3.87 %
    Cyborg                  23.2 %          ->  6.05 %
    Cyan                    14.5 %          ->  6.93 %
    Cerise                  10.1 %          ->  7.99 %
    the other six            0 %            -> 12-13 % each

So the fix is not to pick better weights by hand; it is to measure what the
weights actually produce and correct them. This runs the allocator, compares
the realised share of every asset against its target, multiplies each gain by
target/realised, and repeats. It converges in a handful of passes because the
distortion is close to multiplicative.

Allocation without rendering is ~20 s at n=4444, so a full solve is a couple
of minutes.

THE GAINS ARE FITTED TO A SPECIFIC (n, seed). That is deliberate rather than a
limitation: the collection is minted once, from one seed, so calibrating
against the seed that will ship makes the realised distribution the one that
was measured -- within ~0.1 points on every asset. Fitted to seed 4444 and
then measured on an unseen seed, the same gains drift to ~1.6 points, which is
ordinary sampling noise at these counts (2 sigma is about +/-1.1 points for a
16 % trait at n=4421), not a bug in the fit.

So: RE-RUN THIS whenever --n or the mint seed changes, or whenever an asset is
added or retired. Use --seeds to average several allocations per pass instead,
which trades the exactness on one seed for gains that hold across any seed.

Usage (from repo root):
  python3 asset_assessment/calibrate_rarity.py                 # solve + write
  python3 asset_assessment/calibrate_rarity.py --check         # measure only
  python3 asset_assessment/calibrate_rarity.py --check --seed 909090
  python3 asset_assessment/calibrate_rarity.py --seeds 4444,7,99   # robust fit
"""

import argparse
import collections
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g  # noqa: E402

RARITY_PATH = g.RARITY_PATH
MANIFEST = "output/mint_manifest.json"
CATS = {"eyez": ("eye", g.EYEZ),
        "mouthz": ("mouth", g.MOUTHZ),
        "backgroundz": ("bg", g.BACKGROUNDZ)}


def load():
    with open(RARITY_PATH) as f:
        return json.load(f)


def save(doc):
    with open(RARITY_PATH, "w") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")


def run_alloc(n, seed):
    r = subprocess.run(
        [sys.executable, "asset_assessment/build_mint.py",
         "--n", str(n), "--seed", str(seed)],
        capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("build_mint failed:\n" + r.stdout[-3000:] + r.stderr[-3000:])
    with open(MANIFEST) as f:
        return list(json.load(f).values())


def realised(tokens, key):
    """Share of COMPOSITED tokens carrying each asset, in percent. Secret
    rares are standalone 1/1s with no traits, so they are not part of the
    denominator any target is expressed against."""
    vals = [t.get(key) for t in tokens if t.get(key)]
    total = len(vals)
    c = collections.Counter(vals)
    return {k: 100.0 * v / total for k, v in c.items()}, total


def report(doc, tokens):
    ok = True
    for cat, (key, gcat) in CATS.items():
        target = doc.get(cat, {}).get("target", {})
        if not target:
            continue
        got, total = realised(tokens, key)
        print(f"\n== {cat}  (of {total} composited tokens) ==")
        print(f"{'asset':<34}{'target':>9}{'actual':>9}{'delta':>9}")
        for f, tgt in sorted(target.items(), key=lambda kv: kv[1]):
            act = got.get(f, 0.0)
            d = act - tgt
            if abs(d) > 0.6:
                ok = False
            print(f"{g.trait_name(gcat, f)[:34]:<34}"
                  f"{tgt:8.2f}%{act:8.2f}%{d:+8.2f}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4444)
    ap.add_argument("--seed", type=int, default=4444)
    ap.add_argument("--seeds", default=None,
                    help="comma-separated seeds to AVERAGE each pass over; "
                         "trades exactness on one seed for gains that hold "
                         "across any seed")
    ap.add_argument("--iters", type=int, default=6)
    ap.add_argument("--check", action="store_true",
                    help="measure against target and exit, writing nothing")
    ap.add_argument("--tol", type=float, default=0.6,
                    help="stop once every asset is within this many points")
    args = ap.parse_args()

    seeds = ([int(x) for x in args.seeds.split(",")] if args.seeds
             else [args.seed])
    doc = load()
    if args.check:
        report(doc, run_alloc(args.n, seeds[0]))
        return

    def measure_all(key):
        """Mean realised share over every calibration seed."""
        acc = collections.defaultdict(float)
        for tk in seed_tokens:
            got, _ = realised(tk, key)
            for k, v in got.items():
                acc[k] += v / len(seed_tokens)
        return acc

    for it in range(1, args.iters + 1):
        seed_tokens = [run_alloc(args.n, s) for s in seeds]
        worst = 0.0
        for cat, (key, _) in CATS.items():
            target = doc.get(cat, {}).get("target", {})
            if not target:
                continue
            got = measure_all(key)
            gain = doc[cat].setdefault("gain", {})
            for f, tgt in target.items():
                act = got.get(f, 0.0)
                worst = max(worst, abs(act - tgt))
                # multiplicative correction, damped and clamped so one noisy
                # pass cannot send a gain to zero or to the moon
                ratio = tgt / max(act, 0.05)
                ratio = min(max(ratio, 0.25), 4.0)
                new = gain.get(f, 1.0) * (ratio ** 0.75)
                gain[f] = round(min(max(new, 0.01), 100.0), 4)
        save(doc)
        print(f"pass {it}: worst deviation {worst:.2f} points")
        if worst <= args.tol:
            print("converged")
            break

    print("\nfinal (seed %d):" % seeds[0])
    report(doc, run_alloc(args.n, seeds[0]))


if __name__ == "__main__":
    main()
