#!/usr/bin/env python3
"""The launch film: where it came from, what is in it, and what it all means.

THE FILM IS ABOUT THE ART, NOT THE RARITY. Three cuts in a row led with
counts and odds and the owner's note each time was to push the other way,
the last one flatly: "I don't want the focus to be the rarity. I want the
lore explained. The art/stickers explained." So the counts are gone --
no odds, no "1 in N", no scarcity ladder. What is left is what each thing
IS and why it is in there.

EVERYTHING STATED HERE CAME FROM THE OWNER (promo/LORE_BRIEF.md). Nothing
about the lore is inferred, because the repo cannot know it: the name is
Retardio + sweets, the empty gloves are a military brat's own joke, the
Starfield is a Nyan Cat homage, Drained The Swamp is what it sounds like,
and the four legendary plates honour people from the Gorbagana period --
deliberately uncredited, because he asked that the public work it out.

THE STICKERS ARE THE HEART OF IT. All 23 are named pop-culture references
and the owner identified every one. That is the section a viewer actually
enjoys, and it was missing entirely from the first cut.

TWO ARE SHOWN WITHOUT NAMING WHAT THEY REFERENCE. Both point at real,
living people, and whether to name them on screen (H1-H3) is a question
the owner has not answered. The art appears exactly as minted; only the
caption is withheld, which is the reversible half.

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

# Sticker -> what it references. Every one identified BY THE OWNER; none of
# it is guesswork. Two are deliberately left uncaptioned -- they point at
# real living people and that call (H1-H3) is still his to make.
STICKER_REF = {
    "Golden Ticket": "Willy Wonka",
    "Marshmallow Man": "Ghostbusters",
    "Box of Chocolates": "Forrest Gump",
    "Calvin Candie": "Django Unchained",
    "Zombieland Twinkie": "Zombieland",
    "Mr Owl": "the Tootsie Pop ad",
    "Hunny Pot": "Winnie the Pooh",
    "Peppermint Butler": "Adventure Time",
    "Rare Candy": "Pokémon",
    "Candy Land": "the board game",
    "Dude Sweet": "Dude, Where's My Car?",
    "American Pie": "the film",
    "Sweet Tooth": "Twisted Metal",
    "Robot Chicken Gummy Bear": "Robot Chicken",
    "Candy Shop": "50 Cent",
    "The Meme is the Tech": "the crypto line",
    "Straight Outta Gulag": "Straight Outta Compton",
    "Benson": "Regular Show",
    "The Bunny": "an old VeggieTales episode",
    "Opengotchi": "an open-source project",
}
HELD = {"Caroline Ellison", "Pwease Lollipop"}   # real people; art only

# Background themes.
#
# THE LABELLED CARDS USE PLATES WITH NO IDENTIFIABLE REAL FACES, and that is
# a deliberate line rather than squeamishness. Several plates are photographs
# of living politicians; putting those under a pink banner reading CONSPIRACY
# and the line "they think something is out there" is not showing the art, it
# is captioning real people with a claim about them. That is the H1-H3
# question the owner has not answered yet, and it is the half that cannot be
# taken back once posted.
#
# Those plates are NOT hidden -- they still appear behind tokens elsewhere in
# the film, exactly as minted. Only the editorial grouping is withheld. To put
# them back, add the stems here; nothing else needs to change.
THEMES = [
    ("CONSPIRACY", "They think something is out there.",
     ["Abduction", "Clouds", "Drained_The_Swamp", "Starfield"]),
    ("CRYPTO", "The rooms they grew up in.",
     ["Bored_Apes", "RIP_Gorbagana", "Emblem", "Swolex"]),
    ("THE MUNCHIES", "Three in the morning, every time.",
     ["Empty_Fridge", "Midnight_Snack (1)", "Baked", "Toasted"]),
    ("CANDY WORLD", "And sometimes it is just very sweet.",
     ["Sweet_Shop", "Choco_Falls", "Candy_Tundra", "Goo_Lagoon"]),
]

# Details that carry a joke, each one the owner's own.
DETAILS = [
    ("The empty gloves are the joke.",
     "He was a military brat. The figure is only pretending to hold one."),
    ("The alien face is not a colourway.",
     "It is the rarest face in the set, and it turns up where you would "
     "expect it to."),
    ("The starfield is a Nyan Cat homage.",
     "The cat was erased from the original. The rainbow was put back."),
]


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


def sticker_one(fname):
    """One sticker's art, cropped to its own ink and set on the ground."""
    p = os.path.join(g.TRAITS_DIR, g.STICKERZ, fname)
    if not os.path.exists(p):
        return None
    im = Image.open(p).convert("RGBA")
    bb = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bb:
        im = im.crop(bb)
    side = max(im.size)
    c = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    c.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    return Image.alpha_composite(
        Image.new("RGBA", c.size, (6, 4, 10, 255)), c).convert("RGB")


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


def sticker_card(ground, art, name, ref):
    """One sticker, large, with what it references named under it.

    This is the section the owner asked for twice. A grid of 23 thumbnails
    says "there are 23 stickers"; it does not say that the owl is the Tootsie
    Pop ad. Naming each one is the whole point.
    """
    box = 560
    im = ground.copy()
    d = ImageDraw.Draw(im)
    x, y = (W - box) // 2, 190
    im.paste(art.resize((box, box), Image.Resampling.LANCZOS), (x, y))
    f = font(54)
    d.text(((W - d.textlength(name, font=f)) / 2, y + box + 40), name,
           font=f, fill=INK)
    if ref:
        fr = font(32, bold=False)
        t = ref if ref.startswith(("the ", "an ", "a ")) else ref
        d.text(((W - d.textlength(t, font=fr)) / 2, y + box + 108), t,
               font=fr, fill=PINK_HI)
    return im


def theme_card(ground, plates, title, line):
    """A background theme: four plates at once, so the family reads."""
    im = ground.copy()
    d = ImageDraw.Draw(im)
    fk = font(30)
    w = tracked_width(d, title, fk, 6)
    tracked(d, ((W - w) / 2, 116), title, fk, PINK_HI, track=6)
    cell, gap = 380, 30
    n = len(plates)
    x0 = (W - (n * cell + (n - 1) * gap)) // 2
    for i, pl in enumerate(plates):
        x = x0 + i * (cell + gap)
        im.paste(pl.resize((cell, cell), Image.Resampling.LANCZOS), (x, 200))
        d.rounded_rectangle([x - 3, 197, x + cell + 3, 200 + cell + 3],
                            radius=12, outline=(52, 55, 64), width=2)
    f = font(42, bold=False)
    d.text(((W - d.textlength(line, font=f)) / 2, 200 + cell + 56), line,
           font=f, fill=STEEL)
    return im


def detail_card(ground, headline, line):
    im = ground.copy()
    d = ImageDraw.Draw(im)
    f1 = font(62)
    while d.textlength(headline, font=f1) > W - 260:
        f1 = font(int(f1.size * 0.93))
    d.text(((W - d.textlength(headline, font=f1)) / 2, 430), headline,
           font=f1, fill=INK)
    f2 = font(34, bold=False)
    y = 430 + int(f1.size * 1.45)
    for part in wrap_text(d, line, f2, 1250):
        d.text(((W - d.textlength(part, font=f2)) / 2, y), part,
               font=f2, fill=DIM)
        y += 48
    return im


def wrap_text(d, text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) > width and cur:
            lines.append(cur); cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def plate_art(stem):
    """A background plate straight from traits/, for the theme cards."""
    p = os.path.join(g.TRAITS_DIR, g.BACKGROUNDZ, stem + ".png")
    if not os.path.exists(p):
        return None
    return Image.open(p).convert("RGB")


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

    # ---- 2. the name (C2, the owner's own) ----
    S(detail_card(ground, "Swee-tardio.",
                  "Sweets, and Retardio. The name says where it came from."), 7)

    # ---- 3. what is in one (D1: "just list the traits") ----
    for i in range(1, len(ROSTER) + 1):
        S(roster_plate(ground, ROSTER, ROSTER_FOOT, upto=i), 1)
    S(roster_plate(ground, ROSTER, ROSTER_FOOT), 6)

    # ---- 4. the cast ----
    for t in pick("collection",
                  [t for t in have if not animated(t)
                   and not man[t].get("secret_rare")], 8):
        S(token_frames(ground, t, args.box, animate=False), 4)

    # ---- 5. THE BACKGROUNDS, EXPLAINED ----
    S(detail_card(ground, "Every one of them is somewhere.",
                  "66 backgrounds, and they are not wallpaper."), 6)
    for title, line, stems in THEMES:
        plates = [pl for pl in (plate_art(x) for x in stems) if pl is not None]
        if len(plates) < 2:
            print(f"  theme {title}: only {len(plates)} plates found — skipped")
            continue
        S(theme_card(ground, plates[:4], title, line), 8)

    # ---- 6. THE STICKERS, EXPLAINED ----
    S(detail_card(ground, "Then there are the stickers.",
                  "23 of them. Every one is a reference."), 6)
    for f in sorted(g.get_files(g.STICKERZ)):
        name = g.trait_name(g.STICKERZ, f)
        art = sticker_one(f)
        if art is None:
            continue
        ref = None if name in HELD else STICKER_REF.get(name)
        S(sticker_card(ground, art, name, ref), 3)
    arts = sticker_arts()
    S(sticker_plate(ground, arts, headline="Collect all 23."), 8)

    # ---- 7. the details that carry a joke ----
    for headline, line in DETAILS:
        S(detail_card(ground, headline, line), 7)

    # ---- 8. the tributes, deliberately uncredited ----
    S(detail_card(ground, "Four backgrounds honour people.",
                  "From the Gorbagana days. They are not named on purpose — "
                  "work it out."), 8)
    legs = [pl for pl in (plate_art(x) for x in
            ("Legendary_Just_Aliens", "Legendary_Opengotchi",
             "Legendary_Simplex", "Legendary_Tenders")) if pl is not None]
    if len(legs) >= 2:
        S(theme_card(ground, legs[:4], "LEGENDARY", "You know who you are."), 8)

    # ---- 9. the animated tier, as ART not as a statistic ----
    S(detail_card(ground, "Some of them move.",
                  "Seven kinds of weather, and one plate that never stops."), 6)
    for state in ("rain", "snow", "fog", "storm", "blizzard", "flooded",
                  "tornado"):
        plates = None
        if state == "flooded":
            plates = clip_frames(ground, "flooded_twinkie.mp4", args.box,
                                 state.title())
        if plates is None:
            cands = [t for t in have if man[t].get("weather") == state
                     and os.path.exists(os.path.join(ANIM, f"{t}.mp4"))]
            cands.sort(key=lambda t: -reads.get(t, 0))
            if not cands:
                continue
            plates = token_frames(ground, cands[0], args.box,
                                  caption=state.title())
        S(plates, 5)
    for t in pick("animated",
                  [t for t in have if man[t].get("starfield")], 3):
        S(token_frames(ground, t, args.box), 4)

    # ---- 10. the close ----
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
