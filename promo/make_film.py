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
    # Optically centred, not top-aligned: the block is kicker + number + sub,
    # so the number sits below the frame's middle and the whole group reads
    # centred. Set flush at the old 380 it left a third of the frame empty
    # underneath, which on a phone reads as a mistake.
    y = 452
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
    y = 246
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


def sticker_plate(ground, arts, upto=None, headline=None):
    """The 23 stickers as a set.

    They are the flattest trait in the collection -- 184 of each, 4.14 % --
    so rarity is the wrong story for them. Completion is the right one, and
    a grid filling in one sticker at a time says that without a sentence.
    """
    im = ground.copy()
    d = ImageDraw.Draw(im)
    fk = font(26)
    w = tracked_width(d, "STICKERS", fk, 5.5)
    tracked(d, ((W - w) / 2, 152), "STICKERS", fk, PINK_HI, track=5.5)
    cols, cell, gap = 8, 150, 26
    rows = (len(arts) + cols - 1) // cols
    x0 = (W - (cols * cell + (cols - 1) * gap)) // 2
    y0 = 244
    shown = len(arts) if upto is None else upto
    for i, a in enumerate(arts):
        x = x0 + (i % cols) * (cell + gap)
        y = y0 + (i // cols) * (cell + gap)
        if i < shown:
            im.paste(a.resize((cell, cell), Image.Resampling.LANCZOS), (x, y))
        else:
            d.rounded_rectangle([x, y, x + cell, y + cell], radius=12,
                                outline=(38, 40, 48), width=2)
    if headline:
        f = font(34)
        d.text(((W - d.textlength(headline, font=f)) / 2,
                y0 + rows * (cell + gap) + 26), headline, font=f, fill=DIM)
    return im


def sticker_arts(limit=23):
    """The sticker art itself, cropped to its own ink and set on black."""
    out = []
    for f in sorted(g.get_files(g.STICKERZ))[:limit]:
        p = os.path.join(g.TRAITS_DIR, g.STICKERZ, f)
        im = Image.open(p).convert("RGBA")
        bb = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        if bb:
            im = im.crop(bb)
        side = max(im.size)
        c = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        c.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
        out.append(Image.alpha_composite(
            Image.new("RGBA", c.size, (10, 8, 14, 255)), c).convert("RGB"))
    return out


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
READS_PATH = os.path.join(ROOT, "promo", "read_scores.json")


def read_scores():
    """How well each token READS, measured — see tools/score_reads.py.

    Ranking by manifest order put cluttered tokens on screen: a saber, a pair
    of slippers and a busy plate all competing, which is what the owner
    rejected. The score is the opposite property -- silhouette contrast
    against the plate ring, a quiet background, and a sensible fill -- so
    sorting by it picks the bold, legible ones the reference cut showed.
    """
    try:
        with open(READS_PATH) as f:
            return {int(k): v["read"] for k, v in json.load(f).items()}
    except Exception:
        return {}


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


CLIPS = os.path.join(ROOT, "promo", "clips")


def clip_frames(ground, name, box, caption=None, limit=30):
    """A loop the owner supplied directly, e.g. his own flooded Twinkie.

    Preferred over anything picked here when it exists: he cut it, and it is
    the reference he gave for what the art should look like on screen.
    """
    p = os.path.join(CLIPS, name)
    if not os.path.exists(p):
        return None
    fr = read_loop(p, box, limit=limit)
    if not fr:
        return None
    return [art_plate(ground, a, box, caption=caption) for a in fr]


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

    reads = read_scores()

    def pick(group, auto, want):
        """The owner's list for a group, else the best-READING ones.

        Only ids that were actually rendered survive -- a pick the mint has
        not drawn yet would otherwise crash the build at encode time.
        """
        ids = [int(t) for t in picks.get(group, []) if int(t) in have]
        missing = [t for t in picks.get(group, []) if int(t) not in have]
        if missing:
            print(f"  {group}: not rendered, skipped — "
                  + ", ".join(f"#{t}" for t in missing))
        if ids:
            return ids[:want]
        auto = sorted(auto, key=lambda t: -reads.get(t, 0))
        if reads:
            print(f"  {group}: best-reading — "
                  + ", ".join(f"#{t} {reads.get(t, 0):.2f}" for t in auto[:want]))
        return auto[:want]

    seg = []
    def S(plates, beats, loop_fps=13):
        seg.append(Seg(plates, beats * beat, loop_fps=loop_fps))

    # ---- 1. the lineage intro, as approved ----
    seg.extend(mi.build(SimpleNamespace(
        box=560, hold=8 * beat, gif_fps=12, max_frames=60, logo_frames=200)))

    # ---- 2. what it is: the roster (D1) ----
    S(stat_plate(ground, "4,444", kicker="SWEETARDIO COLLECTION"), 5)
    for i in range(1, len(ROSTER) + 1):
        S(roster_plate(ground, ROSTER, ROSTER_FOOT, upto=i), 1)
    S(roster_plate(ground, ROSTER, ROSTER_FOOT), 6)

    # ---- 3. THE ART. Held long, and given most of the running time.
    #
    # The first cut was a rarity deck with pictures between the numbers. The
    # owner's note was the reverse -- more artwork, less rarity -- so the
    # stat cards are down from eight to three and every token now holds for
    # four beats instead of two. The numbers that survive are the ones a
    # buyer cannot get from looking.
    for t in pick("collection",
                  [t for t in have if not animated(t)
                   and not man[t].get("secret_rare")], 12):
        S(token_frames(ground, t, args.box, animate=False), 4)

    # ---- 4. weather: ALL SEVEN, each with its own loop ----
    wx_counts = {}
    for t in man:
        if man[t].get("weather"):
            wx_counts[man[t]["weather"]] = wx_counts.get(man[t]["weather"], 0) + 1
    S(line_plate(ground, "Seven of them carry weather.", size=62), 6)
    for state in ("rain", "snow", "fog", "storm", "blizzard", "flooded",
                  "tornado"):
        cap = f"{state.title()}  ·  {wx_counts.get(state, 0)} of 4,444"
        plates = None
        if state == "flooded":                 # the owner's own cut
            plates = clip_frames(ground, "flooded_twinkie.mp4", args.box, cap)
        if plates is None:
            cands = [t for t in have if man[t].get("weather") == state
                     and os.path.exists(os.path.join(ANIM, f"{t}.mp4"))]
            cands.sort(key=lambda t: -reads.get(t, 0))
            if not cands:
                print(f"  weather {state}: NO LOOP RENDERED — skipped")
                continue
            plates = token_frames(ground, cands[0], args.box, caption=cap)
        S(plates, 6)

    # ---- 5. the animated plate ----
    S(line_plate(ground, "One of them moves.", size=66), 5)
    for t in pick("animated",
                  [t for t in have if man[t].get("starfield")], 5):
        S(token_frames(ground, t, args.box), 4)
    S(stat_plate(ground, f"{n_anim}", kicker="ANIMATED",
                 sub=f"of {n:,}  ·  1 in {round(n / n_anim)}"), 5)

    # ---- 6. the stickers, a SET rather than a rarity ----
    arts = sticker_arts()
    S(sticker_plate(ground, arts, upto=0), 2)
    for i in range(4, len(arts) + 1, 4):
        S(sticker_plate(ground, arts, upto=i), 1)
    S(sticker_plate(ground, arts,
                    headline="184 of each. A set inside the set."), 7)

    # ---- 7. armed, and the one ----
    S(line_plate(ground, "Most of them are armed.", size=62), 5)
    for t in pick("armed",
                  [t for t in have if armed(t) and not animated(t)], 6):
        S(token_frames(ground, t, args.box, animate=False), 4)
    for t in pick("both",
                  [t for t in have if animated(t) and armed(t)], 3):
        S(token_frames(ground, t, args.box), 4)

    S(line_plate(ground, "One is armed, animated, and in a tornado.",
                 size=52, colour=DIM), 5)
    S(token_frames(ground, the_one, args.box + 60), 10)
    S(stat_plate(ground, "1", kicker="OF 4,444", sub="There is only one.",
                 colour=PINK_HI), 7)

    # ---- 8. the close ----
    S(launch_plate(ground), 12)

    total = sum(x.dur for x in seg)
    print(f"\n{len(seg)} segments, {total:.1f}s ({total/60:.2f} min), "
          f"{total/beat:.0f} beats at {args.bpm:g} BPM")
    return seg


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="promo/sweetardio_film.mp4")
    ap.add_argument("--bpm", type=float, default=132.0,
                    help="MEASURED off the supplied track, not assumed. "
                         "UK_Drill_Pascal_Bounce is 132.00 exactly — comb "
                         "energy 1.61 there against 0.13 at 140")
    ap.add_argument("--audio", default=None, help="track to mux in")
    ap.add_argument("--audio-start", type=float, default=0.3300,
                    help="the track's first beat; the cut starts there so "
                         "frame 0 is a downbeat")
    ap.add_argument("--box", type=int, default=760, help="token art size")
    args = ap.parse_args()
    segs = build(args)
    print("encoding...")
    n = encode(timeline_frames(segs, xf=0.24), args.out,
               audio=args.audio, audio_offset=args.audio_start)
    print(f"wrote {args.out}  {n} frames, {n / FPS:.1f}s, "
          f"{os.path.getsize(args.out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
