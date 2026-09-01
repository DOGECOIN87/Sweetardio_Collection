#!/usr/bin/env python3
"""The launch film: lineage intro, then what to look for when trading.

Built to the owner's brief (promo/LORE_BRIEF.md), and three of those answers
decide almost everything about it:

  A4  he scores it himself at 140 BPM and wants text MINIMAL. So every cut
      lands on a beat, and there are no metadata panels anywhere -- the
      rarity video's nine-row read-out is the opposite of this instruction.
      Numbers appear alone, big, and briefly.
  B2  rarity rank is misleading, so no rank appears. Only counts and odds.
  B7  nothing is minted yet, so no prices and no floors -- it closes on the
      launch date instead.

THE THESIS IS B4, ANSWERED FROM THE DATA. Every rarity tool scores traits
INDEPENDENTLY and sums them; none of them score a pairing. So the thing the
owner says to look for -- animated, then armed -- is precisely the thing no
ranking will price. 466 tokens are animated and 707 carry an arm, but only
64 are both, and exactly ONE pairs the rarest weather with a weapon.

WHAT IT DOES NOT DO. It shows the art and does not caption it. Several
backgrounds and stickers reference real, living people, and the owner's call
on whether to name them was still open when this was built -- so the film
names none of them. Nothing is hidden: the art appears exactly as minted.
Nothing is amplified either, which is the reversible default. See H1-H3.

    python3 promo/make_film.py --out promo/sweetardio_film.mp4
"""

import argparse
import json
import os
import sys
from types import SimpleNamespace

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g                                          # noqa: E402
import make_intro as mi                                        # noqa: E402
from make_promo import (W, H, FPS, font, tracked, tracked_width,  # noqa: E402
                        encode, Seg, timeline_frames, read_loop)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES = os.path.join(ROOT, "output", "mint", "images")
ANIM = os.path.join(ROOT, "output", "mint", "anim")
MANIFEST = os.path.join(ROOT, "output", "mint_manifest.json")

BLACK, PINK, PINK_HI = mi.BLACK, mi.PINK, mi.PINK_HI
STEEL, INK = mi.STEEL, mi.INK
DIM = (120, 124, 136)

# D1, ANSWERED: "just list the traits". No lore prose and no origin story
# (D3) -- for an audience that already knows NFTs (A1), the honest answer to
# "what is this" is what it is composed of. The roster is also the only place
# in the film where a viewer learns the vocabulary, so it is the one screen
# allowed to carry a list.
ROSTER = [
    ("Characters", 27), ("Backgrounds", 66), ("Skins", 3),
    ("Eyes", 10), ("Mouths", 9), ("Arms", 11),
    ("Footwear", 5), ("Stickers", 23), ("Weather", 7),
]
ROSTER_FOOT = "2 one-of-one artworks, by guest artists"


# ------------------------------------------------------------ plate makers
def art_plate(ground, art, box, caption=None, badge=None):
    """Art, large, on black. At most one short line under it."""
    im = ground.copy()
    d = ImageDraw.Draw(im)
    y = (H - box) // 2 - (34 if caption else 0)
    x = (W - box) // 2
    d.rounded_rectangle([x - 6, y - 6, x + box + 6, y + box + 6],
                        radius=20, outline=(48, 51, 60), width=3)
    im.paste(art.resize((box, box), Image.Resampling.LANCZOS), (x, y))
    if badge:
        f = font(23)
        bw = tracked_width(d, badge, f, 2.4)
        d.rounded_rectangle([x + 20, y + 20, x + 20 + bw + 44, y + 68],
                            radius=24, fill=(10, 5, 14), outline=PINK, width=2)
        tracked(d, (x + 42, y + 32), badge, f, PINK_HI, track=2.4)
    if caption:
        f = font(30)
        d.text(((W - d.textlength(caption, font=f)) / 2, y + box + 30),
               caption, font=f, fill=DIM)
    return im


def stat_plate(ground, big, kicker=None, sub=None, colour=None):
    """One number, alone. Minimal text means the number IS the sentence."""
    im = ground.copy()
    d = ImageDraw.Draw(im)
    y = 380
    if kicker:
        f = font(26)
        w = tracked_width(d, kicker, f, 5.5)
        tracked(d, ((W - w) / 2, y - 78), kicker, f, PINK_HI, track=5.5)
    f = font(168)
    while d.textlength(big, font=f) > W - 220:
        f = font(int(f.size * 0.92))
    d.text(((W - d.textlength(big, font=f)) / 2, y), big, font=f,
           fill=colour or INK)
    if sub:
        fs = font(36, bold=False)
        d.text(((W - d.textlength(sub, font=fs)) / 2, y + int(f.size * 1.16)),
               sub, font=fs, fill=DIM)
    return im


def line_plate(ground, text, size=76, colour=None):
    im = ground.copy()
    d = ImageDraw.Draw(im)
    f = font(size)
    while d.textlength(text, font=f) > W - 240:
        f = font(int(f.size * 0.93))
    d.text(((W - d.textlength(text, font=f)) / 2, (H - f.size) / 2 - 20),
           text, font=f, fill=colour or INK)
    return im


def roster_plate(ground, rows, foot, upto=None):
    """The trait list. Built up a row at a time so it reads as assembling
    rather than as a wall of text arriving at once -- the only concession
    that lets a nine-row list survive a minimal-text brief."""
    im = ground.copy()
    d = ImageDraw.Draw(im)
    fk, fn, fl, ff = font(26), font(46), font(30), font(26, bold=False)
    w = tracked_width(d, "WHAT IS IN ONE", fk, 5.5)
    tracked(d, ((W - w) / 2, 132), "WHAT IS IN ONE", fk, PINK_HI, track=5.5)

    x0, x1 = 620, 1300
    y = 222
    shown = len(rows) if upto is None else upto
    for i, (label, count) in enumerate(rows):
        if i >= shown:
            break
        live = (upto is not None and i == shown - 1)
        d.text((x0, y), f"{count}", font=fn,
               fill=PINK_HI if live else INK)
        d.text((x0 + 92, y + 12), label, font=fl,
               fill=STEEL if live else (132, 136, 148))
        y += 68
    if upto is None or shown >= len(rows):
        d.text(((W - d.textlength(foot, font=ff)) / 2, y + 26), foot,
               font=ff, fill=DIM)
    return im


def launch_plate(ground):
    im = ground.copy()
    d = ImageDraw.Draw(im)
    f1, f2, f3 = font(30), font(104), font(40)
    w = tracked_width(d, "MINT", f1, 6)
    tracked(d, ((W - w) / 2, 352), "MINT", f1, PINK_HI, track=6)
    s = "14 SEPTEMBER 2026"
    d.text(((W - d.textlength(s, font=f2)) / 2, 400), s, font=f2, fill=INK)
    s = "launchmynft.io"
    d.text(((W - d.textlength(s, font=f3)) / 2, 552), s, font=f3, fill=STEEL)
    w = tracked_width(d, "SWEETARDIO COLLECTION", f1, 6)
    tracked(d, ((W - w) / 2, H - 220), "SWEETARDIO COLLECTION", f1, DIM, track=6)
    return im


# The owner picks the hero shots; the film does not. Auto-selection ranks by
# whatever the manifest happens to order by, which is not the same thing as
# "looks good". promo/heroes.json overrides any or all of the four groups:
#
#     {"collection": [1, 98, ...], "animated": [...],
#      "armed": [...], "both": [...]}
#
# Missing or partial is fine -- any group not named falls back to the
# automatic pick, so a half-filled file still builds.
HEROES_PATH = os.path.join(ROOT, "promo", "heroes.json")


def heroes():
    try:
        with open(HEROES_PATH) as f:
            picks = json.load(f)
        print(f"heroes.json: " + ", ".join(
            f"{k} {len(v)}" for k, v in picks.items() if v))
        return picks
    except FileNotFoundError:
        print("no promo/heroes.json — picking automatically")
        return {}
    except Exception as e:
        sys.exit(f"promo/heroes.json is not readable: {e}")


# ------------------------------------------------------------------ build
def token_frames(ground, tid, box, animate=True, caption=None, badge=None):
    """A token as full FRAMES, ready for the timeline.

    Returns composed 1920x1080 plates, not bare artwork: every segment in the
    timeline has to be the same size, because the crossfade blends one into
    the next and PIL will not blend mismatched images.
    """
    art = None
    if animate:
        p = os.path.join(ANIM, f"{tid}.mp4")
        if os.path.exists(p):
            art = read_loop(p, box, limit=26)
    if not art:
        art = [Image.open(os.path.join(IMAGES, f"{tid}.png")).convert("RGB")]
    return [art_plate(ground, a, box, caption=caption, badge=badge)
            for a in art]


def build(args):
    beat = 60.0 / args.bpm
    with open(MANIFEST) as f:
        man = {int(k): v for k, v in json.load(f).items()}
    have = sorted(int(f[:-4]) for f in os.listdir(IMAGES) if f.endswith(".png"))
    ground = mi.make_ground()

    def animated(t):
        return bool(man[t].get("starfield") or man[t].get("weather"))

    def armed(t):
        # The Military Brat holds NOTHING -- the figure is miming, which is
        # the owner's own joke. Counting it as armed would overstate the
        # thing this whole section is about by 12 %.
        a = str(man[t].get("arm") or "")
        return bool(a) and "Military_Brat" not in a

    n = len(man)
    n_anim = sum(1 for t in man if animated(t))
    n_arm = sum(1 for t in man if armed(t))
    n_both = sum(1 for t in man if animated(t) and armed(t))
    star_arm = sorted(t for t in man if man[t].get("starfield") and armed(t))
    the_one = next(t for t in man
                   if man[t].get("weather") == "tornado" and armed(t))

    picks = heroes()

    def pick(group, auto, want):
        """The owner's list for a group, else the automatic one. Only ids that
        were actually rendered survive -- a pick the mint has not drawn yet
        would otherwise crash the build at encode time."""
        ids = [int(t) for t in picks.get(group, []) if int(t) in have]
        missing = [t for t in picks.get(group, []) if int(t) not in have]
        if missing:
            print(f"  {group}: not rendered, skipped — "
                  + ", ".join(f"#{t}" for t in missing))
        return (ids or auto)[:want]

    seg = []
    def S(plates, beats, loop_fps=13):
        seg.append(Seg(plates, beats * beat, loop_fps=loop_fps))

    # ---- 1. the lineage intro, as approved ----
    seg.extend(mi.build(SimpleNamespace(
        box=560, hold=8 * beat, gif_fps=12, max_frames=60, logo_frames=200)))

    # ---- 2. what it is: the roster (D1) ----
    S(stat_plate(ground, "4,444", kicker="SWEETARDIO COLLECTION"), 5)
    for i in range(1, len(ROSTER) + 1):        # one row per beat, assembling
        S(roster_plate(ground, ROSTER, ROSTER_FOOT, upto=i), 1)
    S(roster_plate(ground, ROSTER, ROSTER_FOOT), 7)
    faces = pick("collection",
                 [t for t in have if not animated(t)
                  and not man[t].get("secret_rare")], 8)
    for t in faces:
        S(token_frames(ground, t, args.box, animate=False), 2)

    # ---- 3. the thesis (B4) ----
    S(line_plate(ground, "Rarity tools rank traits.", size=68, colour=DIM), 6)
    S(line_plate(ground, "This one rewards combinations.", size=68), 8)

    # ---- 4. what to look for (B1) ----
    S(stat_plate(ground, "1", kicker="WHAT TO LOOK FOR",
                 sub="Is it animated?"), 6)
    for t in pick("animated", [t for t in have if animated(t)], 6):
        S(token_frames(ground, t, args.box), 2)
    S(stat_plate(ground, f"{n_anim}", kicker="ANIMATED",
                 sub=f"of {n:,}  ·  1 in {round(n / n_anim)}"), 5)

    S(stat_plate(ground, "2", kicker="WHAT TO LOOK FOR",
                 sub="Is it armed?"), 6)
    for t in pick("armed",
                  [t for t in have if armed(t) and not animated(t)], 6):
        S(token_frames(ground, t, args.box, animate=False), 2)
    S(stat_plate(ground, f"{n_arm}", kicker="ARMED",
                 sub=f"of {n:,}  ·  1 in {round(n / n_arm)}"), 5)

    # ---- 5. the grails (B6) ----
    S(line_plate(ground, "Both?", size=92), 5)
    for t in pick("both",
                  [t for t in have if animated(t) and armed(t)], 4):
        S(token_frames(ground, t, args.box), 3)
    S(stat_plate(ground, f"{n_both}", kicker="ANIMATED AND ARMED",
                 sub=f"of {n:,}  ·  1 in {round(n / n_both)}",
                 colour=PINK_HI), 6)

    S(line_plate(ground, "On the rarest plate in the collection.", size=54,
                 colour=DIM), 5)
    for t in [t for t in star_arm if t in have]:
        S(token_frames(ground, t, args.box, animate=True), 3)
    S(stat_plate(ground, f"{len(star_arm)}", kicker="STARFIELD AND ARMED",
                 sub=f"of {n:,}  ·  1 in {round(n / len(star_arm)):,}",
                 colour=PINK_HI), 6)

    # ---- 6. the one ----
    S(line_plate(ground, "And one of them holds a weapon in a tornado.",
                 size=52, colour=DIM), 6)
    S(token_frames(ground, the_one, args.box + 60), 10)
    S(stat_plate(ground, "1", kicker="OF 4,444", sub="There is only one.",
                 colour=PINK_HI), 8)

    # ---- 7. the close ----
    S(launch_plate(ground), 12)

    total = sum(x.dur for x in seg)
    print(f"\n{len(seg)} segments, {total:.1f}s ({total/60:.2f} min), "
          f"{total/beat:.0f} beats at {args.bpm:g} BPM")
    return seg


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="promo/sweetardio_film.mp4")
    ap.add_argument("--bpm", type=float, default=140.0)
    ap.add_argument("--box", type=int, default=760, help="token art size")
    args = ap.parse_args()
    segs = build(args)
    print("encoding...")
    n = encode(timeline_frames(segs, xf=0.24), args.out)
    print(f"wrote {args.out}  {n} frames, {n / FPS:.1f}s, "
          f"{os.path.getsize(args.out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
