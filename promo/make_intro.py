#!/usr/bin/env python3
"""The lineage intro: Milady Maker -> Remilia -> Radbro -> Retardio ->
Gorbagio -> Sweetardio.

The film opens for someone who knows NFTs and has never heard of this
collection, so it does not start with the art -- it starts with the family
tree the art comes out of, and arrives at Sweetardio as the next name on a
list the viewer already recognises.

THE RAIL IS THE ARGUMENT. Each ancestor, once shown, shrinks into a strip
along the bottom and stays there. By the last card the whole lineage is on
screen at once, so "this is the next one" is something the viewer can see
rather than something the film asserts.

ARTWORK IS NEVER INVENTED. Every ancestor is somebody else's work and is
loaded from promo/lineage/ as supplied. A missing file renders an explicit
placeholder card instead -- the video builds either way, and it is obvious
which slots are still empty.

    promo/lineage/1_milady.gif        animated; frames are played
    promo/lineage/2_remilia.png
    promo/lineage/3_radbro.gif
    promo/lineage/4_retardio.png
    promo/lineage/5_gorbagio.png
    promo/lineage/6_sweetardio.mp4    the logo dolly zoom (the payoff)

    python3 promo/make_intro.py --out promo/sweetardio_intro.mp4
"""

import argparse
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_promo import (W, H, FPS, font, tracked, tracked_width,   # noqa: E402
                        encode, Seg, timeline_frames, read_loop)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "promo", "lineage")

# ---- palette, sampled off the Sweetardio logo itself ----
# Black ground, the badge's own hot pink, its brushed steel, its navy. The
# rarity video's plum would have been the wrong reference: this sequence ends
# on the logo, so it should have been travelling toward the logo's colours the
# whole time.
BLACK = (0, 0, 0)
PINK = (205, 27, 108)
PINK_HI = (240, 74, 145)
STEEL = (196, 199, 205)
STEEL_DIM = (108, 112, 122)
NAVY = (28, 45, 91)
INK = (232, 234, 240)

# name, file, headline, one line of copy
#
# COPY IS FOR THE OWNER TO APPROVE. These are other people's projects and the
# lines below are written from general knowledge, not from anything in this
# repo -- every one of them should be read by someone who was there.
LINEAGE = [
    ("Milady Maker", "1_milady.gif", "IT ALL BEGAN WITH",
     "10,000 neochibi PFPs that looked like nothing else on Ethereum,"
     " and changed what a PFP was allowed to be."),
    ("Remilia Corporation", "2_remilia.png", "THEN CAME",
     "The collective behind Milady. Not a drop — a whole aesthetic,"
     " and a network of everything that came after it."),
    ("Radbro", "3_radbro.gif", "THE WEBRING SPREAD",
     "Same lineage, harder edge. Consume. Obey. Conform."),
    ("Retardio", "4_retardio.png", "IT CROSSED CHAINS",
     "The joke went to Solana and went further than anyone expected."),
    ("Gorbagio", "5_gorbagio.png", "AND WENT DIVING",
     "Dumpster Divers. A trash can, a rifle, and a chain of its own."),
]

CLOSER = ("Every one of them a descendant.", "This is the next one.")


# --------------------------------------------------------------- the ground
def make_ground(seed=11):
    """Black, with a faint pink-and-blue star haze — the logo's own backdrop
    rather than a second design invented beside it."""
    im = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    for _ in range(260):
        x, y = rng.randrange(W), rng.randrange(H)
        r = rng.choice([1, 1, 1, 2])
        c = rng.choice([PINK, (70, 110, 220), STEEL, STEEL])
        a = rng.uniform(0.12, 0.55)
        d.ellipse([x - r, y - r, x + r, y + r],
                  fill=tuple(int(c[i] * a) for i in range(3)))
    # two soft neon streaks, low and wide, so the frame is not dead black
    glow = Image.new("RGB", (W, H), BLACK)
    gd = ImageDraw.Draw(glow)
    gd.line([-100, 250, W + 100, 90], fill=(60, 12, 40), width=26)
    gd.line([-100, H - 160, W + 100, H - 30], fill=(14, 26, 62), width=30)
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    return Image.blend(im, Image.blend(im, glow, 0.9), 0.8)


def load_art(fname, box):
    """An ancestor's artwork, letterboxed into `box` on its own. Returns a
    list of frames (one for a still, many for a GIF), or None if absent."""
    path = os.path.join(ART, fname)
    if not os.path.exists(path):
        return None
    if fname.lower().endswith(".mp4"):
        return read_loop(path, box, limit=200)
    im = Image.open(path)
    frames = []
    try:
        while True:
            f = im.convert("RGBA")
            bg = Image.new("RGBA", f.size, (0, 0, 0, 0))
            frames.append(Image.alpha_composite(bg, f).convert("RGB"))
            im.seek(im.tell() + 1)
    except EOFError:
        pass
    out = []
    for f in frames:
        s = min(box / f.width, box / f.height)
        r = f.resize((max(1, int(f.width * s)), max(1, int(f.height * s))),
                     Image.Resampling.LANCZOS)
        c = Image.new("RGB", (box, box), BLACK)
        c.paste(r, ((box - r.width) // 2, (box - r.height) // 2))
        out.append(c)
    return out or None


def placeholder(name, box):
    """An honest empty slot. Better than a stand-in: nobody can mistake this
    for the artwork, and it says exactly which file is missing."""
    im = Image.new("RGB", (box, box), (10, 10, 12))
    d = ImageDraw.Draw(im)
    for i in range(0, box, 22):                       # dashed frame
        d.line([i, 0, min(i + 12, box), 0], fill=STEEL_DIM, width=3)
        d.line([i, box - 2, min(i + 12, box), box - 2], fill=STEEL_DIM, width=3)
        d.line([0, i, 0, min(i + 12, box)], fill=STEEL_DIM, width=3)
        d.line([box - 2, i, box - 2, min(i + 12, box)], fill=STEEL_DIM, width=3)
    f1, f2 = font(30), font(19)
    d.text(((box - d.textlength(name, font=f1)) / 2, box / 2 - 40), name,
           font=f1, fill=STEEL_DIM)
    s = "artwork pending"
    d.text(((box - d.textlength(s, font=f2)) / 2, box / 2 + 8), s,
           font=f2, fill=(84, 88, 98))
    return im


# ------------------------------------------------------------- the lineage
RAIL_Y = H - 132


def draw_rail(im, thumbs, active):
    """The ancestors shown so far, in order, along the bottom.

    Grows by one each card, so the family tree assembles in front of the
    viewer instead of being asserted at the end.
    """
    if not thumbs:
        return
    d = ImageDraw.Draw(im)
    size, gap = 92, 44
    total = len(thumbs) * size + (len(thumbs) - 1) * gap
    x = (W - total) // 2
    cy = RAIL_Y + size // 2
    f = font(15)
    for i, (name, th) in enumerate(thumbs):
        on = (i == active)
        if i:                                          # the connecting line
            d.line([x - gap + 6, cy, x - 6, cy], fill=(52, 55, 64), width=2)
        col = PINK if on else (60, 63, 72)
        d.rounded_rectangle([x - 4, RAIL_Y - 4, x + size + 4, RAIL_Y + size + 4],
                            radius=10, outline=col, width=3 if on else 2)
        t = th.resize((size, size), Image.Resampling.LANCZOS)
        if not on:                                     # past steps recede
            t = Image.blend(Image.new("RGB", t.size, BLACK), t, 0.44)
        im.paste(t, (x, RAIL_Y))
        w = tracked_width(d, name.upper(), f, 1.4)
        tracked(d, (x + (size - w) / 2, RAIL_Y + size + 14), name.upper(), f,
                STEEL if on else (78, 82, 92), track=1.4)
        x += size + gap


def card(ground, art, name, kicker, line, thumbs, active):
    """One ancestor: artwork above, name, one line, and the rail beneath."""
    im = ground.copy()
    d = ImageDraw.Draw(im)

    box = art.width
    ax, ay = (W - box) // 2, 108
    d.rounded_rectangle([ax - 7, ay - 7, ax + box + 7, ay + box + 7],
                        radius=16, outline=(46, 49, 58), width=3)
    im.paste(art, (ax, ay))

    y = ay + box + 34
    fk = font(21)
    kw = tracked_width(d, kicker, fk, 5.0)
    tracked(d, ((W - kw) / 2, y), kicker, fk, PINK_HI, track=5.0)

    y += 38
    fn = font(66)
    while d.textlength(name, font=fn) > W - 320:
        fn = font(int(fn.size * 0.92))
    d.text(((W - d.textlength(name, font=fn)) / 2, y), name, font=fn, fill=INK)

    y += int(fn.size * 1.18)
    fl = font(27, bold=False)
    for part in wrap(d, line, fl, 1180):
        d.text(((W - d.textlength(part, font=fl)) / 2, y), part,
               font=fl, fill=(158, 163, 176))
        y += 38

    draw_rail(im, thumbs, active)
    return im


def wrap(d, text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for word in words:
        t = (cur + " " + word).strip()
        if d.textlength(t, font=fnt) > width and cur:
            lines.append(cur)
            cur = word
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def closer_plate(ground, thumbs):
    im = ground.copy()
    d = ImageDraw.Draw(im)
    f1 = font(52, bold=False)
    f2 = font(78)
    y = 340
    d.text(((W - d.textlength(CLOSER[0], font=f1)) / 2, y), CLOSER[0],
           font=f1, fill=(150, 155, 168))
    y += 96
    d.text(((W - d.textlength(CLOSER[1], font=f2)) / 2, y), CLOSER[1],
           font=f2, fill=INK)
    draw_rail(im, thumbs, -1)
    return im


def build(args):
    ground = make_ground()
    box = args.box
    seg, thumbs = [], []

    for name, fname, kicker, line in LINEAGE:
        frames = load_art(fname, box)
        if frames is None:
            print(f"  MISSING promo/lineage/{fname} — placeholder for {name}")
            frames = [placeholder(name, box)]
        else:
            print(f"  {name:22s} {fname}  {len(frames)} frame(s)")
        thumbs.append((name.split()[0], frames[0]))
        plates = [card(ground, f, name, kicker, line, thumbs, len(thumbs) - 1)
                  for f in frames[:args.max_frames]]
        seg.append(Seg(plates, args.hold, loop_fps=args.gif_fps))

    seg.append(Seg(closer_plate(ground, thumbs), 3.4))

    # the payoff: the logo's own dolly zoom, letterboxed onto the black ground
    logo = os.path.join(ART, "6_sweetardio.mp4")
    if os.path.exists(logo):
        frames = read_loop(logo, 0, limit=args.logo_frames, native=True)
        plates = []
        for f in frames or []:
            s = min(W / f.width, H / f.height)
            r = f.resize((int(f.width * s), int(f.height * s)),
                         Image.Resampling.LANCZOS)
            c = ground.copy()
            c.paste(r, ((W - r.width) // 2, (H - r.height) // 2))
            plates.append(c)
        if plates:
            print(f"  Sweetardio logo         {len(plates)} frames")
            seg.append(Seg(plates, len(plates) / 24.0, loop_fps=24))
    else:
        print("  MISSING promo/lineage/6_sweetardio.mp4 — no payoff shot")

    total = sum(x.dur for x in seg)
    print(f"{len(seg)} segments, {total:.1f}s")
    return seg


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="promo/sweetardio_intro.mp4")
    ap.add_argument("--hold", type=float, default=4.0,
                    help="seconds per ancestor")
    ap.add_argument("--box", type=int, default=560,
                    help="artwork size on the card")
    ap.add_argument("--gif-fps", type=float, default=12,
                    help="playback rate for an animated ancestor")
    ap.add_argument("--max-frames", type=int, default=60)
    ap.add_argument("--logo-frames", type=int, default=200)
    args = ap.parse_args()

    segs = build(args)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    print("encoding...")
    n = encode(timeline_frames(segs, xf=0.4), args.out)
    print(f"wrote {args.out}  {n} frames, {n / FPS:.1f}s, "
          f"{os.path.getsize(args.out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
