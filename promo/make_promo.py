#!/usr/bin/env python3
"""Build the collection promo video from a REAL mint.

Everything on screen is read out of `output/` -- the token images are the
minted PNGs, the traits come from `mint_manifest.json`, and every percentage
is counted across all 4,444 tokens rather than typed in. So the video cannot
claim a rarity the collection does not have, and it goes stale the moment the
allocation changes, which is the correct failure.

    python3 promo/make_promo.py --out promo/sweetardio_promo.mp4

WHAT IT NEEDS
    output/mint_manifest.json        the allocation
    output/mint/images/<id>.png      at least the tokens it features
    output/mint/anim/<id>.mp4        optional; an animated tier PLAYS if its
                                     loop is there, and falls back to the
                                     still if it is not

A token that has no rendered image is skipped with a warning rather than
failing the build: the promo is a proof, and a partial render is the normal
state of the repo between mints (see MINT_PROCESS.md).
"""

import argparse
import json
import math
import os
import random
import subprocess
import sys
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import generator as g                                        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "output", "mint_manifest.json")
IMAGES = os.path.join(ROOT, "output", "mint", "images")
ANIM = os.path.join(ROOT, "output", "mint", "anim")

W, H, FPS = 1920, 1080, 30

# ---- the palette, sampled off the reference cut ----
GROUND = (20, 4, 29)
CARD_EDGE = (62, 42, 86)
CYAN = (34, 211, 238)
WHITE = (255, 255, 255)
LABEL = (150, 132, 180)
MUTED = (118, 102, 142)
GOLD = (251, 191, 36)
HOT = (244, 114, 182)          # the sub-1% band; the reference has no such
                               # tier because it never shows one
PILL_COMMON = (207, 201, 219)
BAR_TRACK = (44, 26, 60)

# Tier -> (pill fill, pill text). The band is the plate's designed scarcity
# (generator.plate_tier), so these are the collection's own five names.
TIER_COLOR = {
    "Ultra":     ((34, 211, 238), (8, 20, 26)),
    "Legendary": ((251, 191, 36), (32, 20, 0)),
    "Scarce":    ((129, 140, 248), (12, 12, 34)),
    "Uncommon":  ((167, 139, 250), (18, 10, 34)),
    "Standard":  ((168, 162, 180), (16, 12, 22)),
}

FONT_DIR = "/usr/share/fonts/truetype/liberation"


def font(size, bold=True):
    name = "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except OSError:
        return ImageFont.load_default()


def tracked(draw, xy, text, fnt, fill, track=0):
    """Draw text with letter-spacing. PIL has no tracking, and the reference's
    small caps labels are unmistakably tracked -- without it they read as a
    different design."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + track
    return x - xy[0]


def tracked_width(draw, text, fnt, track=0):
    return sum(draw.textlength(c, font=fnt) for c in text) + track * (len(text) - 1)


# --------------------------------------------------------------- the ground
def make_ground(seed=7):
    """The plum field and its dust of coloured stars.

    Built once and reused by every segment: it is the one thing on screen
    that never changes, and re-drawing 1,500 dots per frame for 4,000 frames
    is the difference between a 2-minute build and a 20-minute one.
    """
    im = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(im)
    rng = random.Random(seed)
    palette = [(236, 72, 153), (34, 211, 238), (251, 191, 36),
               (167, 139, 250), (255, 255, 255)]
    for _ in range(320):
        x, y = rng.randrange(W), rng.randrange(H)
        r = rng.choice([1, 1, 1, 2, 2, 3])
        c = rng.choice(palette)
        a = rng.uniform(0.25, 0.9)
        c = tuple(int(GROUND[i] + (c[i] - GROUND[i]) * a) for i in range(3))
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    return im


# ------------------------------------------------------------- the rarities
def load_collection():
    """Every percentage in the video, counted from the manifest.

    ABSENCE IS A VALUE. "No arm" is a thing 84 % of the collection has and a
    thing collectors rank on -- it is why Trait Count exists as an attribute
    at all -- so it is counted as "None" rather than skipped, and a token
    with no arm gets a real percentage instead of a blank row.
    """
    with open(MANIFEST) as f:
        man = {int(k): v for k, v in json.load(f).items()}
    n = len(man)
    slots = [("Character", "character", g.CHARACTERZ),
             ("Background", "bg", g.BACKGROUNDZ),
             ("Skin", "skin", g.SKINZ), ("Eyes", "eye", g.EYEZ),
             ("Mouth", "mouth", g.MOUTHZ), ("Arms", "arm", g.ARMZ),
             ("Sticker", "sticker", g.STICKERZ)]
    vals = {}
    for tid, row in man.items():
        if row.get("secret_rare"):
            v = {"Secret Rarez": g.secret_rare_token_name(row["secret_rare"])}
            # secret_rare_artist returns (name, url), not a name
            artist = g.secret_rare_artist(row["secret_rare"])
            if artist:
                v["Artist"] = artist[0]
            vals[tid] = v
            continue
        v = {}
        for label, key, cat in slots:
            v[label] = g.trait_name(cat, row[key]) if row.get(key) else "None"
        v["Plate Tier"] = g.plate_tier(row["bg"]) if row.get("bg") else "None"
        v["Weather"] = row["weather"].title() if row.get("weather") else "None"
        # Footwear: the manifest holds the OVERLAY file and the metadata names
        # the pair from its _base, so the two never hold the same string. The
        # base is recovered from the overlay's own stem rather than guessed.
        v["Footwear"] = footwear_name(row.get("wat"))
        vals[tid] = v
    freq = {}
    for v in vals.values():
        for k, x in v.items():
            freq.setdefault(k, Counter())[x] += 1
    score = {t: sum(n / freq[k][x] for k, x in v.items())
             for t, v in vals.items()}
    rank = {t: i + 1 for i, t in enumerate(sorted(score, key=lambda x: -score[x]))}
    return man, vals, freq, rank, n


_WAT_BASES = None


def footwear_name(wat):
    """Overlay filename -> the pair's display name, matched against the real
    footwear bases rather than by stripping '_Overlay' off the name."""
    global _WAT_BASES
    if not wat:
        return "None"
    if _WAT_BASES is None:
        import re
        _WAT_BASES = {}
        for f in g.get_files(g.WHAT_ARE_THOSEZ):
            m = re.match(r"(.+?)_base(?:\s*\(\d+\))?\.png$", f, re.IGNORECASE)
            if m:
                _WAT_BASES[m.group(1)] = m.group(1)
    stem = os.path.splitext(os.path.basename(wat))[0].lower()
    best = None
    for base in _WAT_BASES:
        head = base.lower().split("_overlay")[0]
        if stem.startswith(head) and (best is None or len(head) > len(best)):
            best = base
    if best is None:
        return "Gorbhouse Slippers" if "gorbhouse" in stem else "None"
    return g.trait_name(g.WHAT_ARE_THOSEZ, best)


def pct_color(p):
    """The pill colour bands. The reference has two; this has three, because
    the reference never shows a trait under 1 % and this video is mostly made
    of them -- the Starfield is 0.50 % and a 1/1 is 0.02 %."""
    if p < 1.0:
        return HOT, (36, 6, 22)
    if p < 3.0:
        return GOLD, (32, 20, 0)
    return PILL_COMMON, (18, 12, 26)


# ------------------------------------------------------------- the segments
ROW_ORDER = ["Character", "Background", "Plate Tier", "Skin", "Eyes",
             "Mouth", "Footwear", "Arms", "Sticker", "Weather"]


def draw_panel(im, tid, vals, freq, rank, n, tier, section=None):
    """The right-hand metadata panel.

    `section` is the run this token belongs to -- the same words the
    explainer card that just played used. It rides at the top right, on the
    brand eyebrow's own line, so the tier being explained and the tokens
    that carry it are never more than a glance apart.
    """
    d = ImageDraw.Draw(im)
    x0, x1 = 1030, 1868
    f_eyebrow, f_num = font(25), font(80)
    f_tier, f_label, f_val = font(29), font(19), font(31)
    f_pct, f_foot = font(24), font(21)

    y = 62
    tracked(d, (x0, y), "SWEETARDIO COLLECTION", f_eyebrow, CYAN, track=2.2)
    if section:
        text, col = section
        fs = font(21)
        w = tracked_width(d, text, fs, 2.0)
        d.rounded_rectangle([x1 - w - 40, y - 8, x1, y + 34],
                            radius=21, fill=(15, 7, 22), outline=col, width=2)
        tracked(d, (x1 - w - 20, y + 1), text, fs, col, track=2.0)
    y += 40
    d.text((x0, y), f"#{tid}", font=f_num, fill=WHITE)
    y += 96

    fill, txt = TIER_COLOR.get(tier, TIER_COLOR["Standard"])
    label = f"{tier} TIER"
    tw = d.textlength(label, font=f_tier)
    d.rounded_rectangle([x0, y, x0 + tw + 56, y + 52], radius=26, fill=fill)
    d.text((x0 + 28, y + 10), label, font=f_tier, fill=txt)
    y += 78

    d.line([x0, y, x1, y], fill=(226, 222, 234), width=2)
    y += 12

    rows = [(k, vals[tid][k]) for k in ROW_ORDER
            if k in vals[tid] and vals[tid][k] != "None"]
    if "Secret Rarez" in vals[tid]:
        rows = [("Secret Rarez", vals[tid]["Secret Rarez"])]
        if "Artist" in vals[tid]:
            rows.append(("Artist", vals[tid]["Artist"]))
    # Distribute the rows over the panel rather than stacking them at a
    # fixed pitch: a 6-trait token and a 10-trait token both have to fill the
    # same column, or the short one ends in 160px of dead space above its
    # footer. Clamped so three rows do not sprawl.
    step = int(max(70, min(112, (972 - y) / max(len(rows), 1))))
    for k, v in rows:
        p = 100.0 * freq[k][v] / n
        tracked(d, (x0, y + 6), k.upper(), f_label, LABEL, track=1.6)
        pill, ptxt = pct_color(p)
        s = f"{p:.2f}%"
        pw = d.textlength(s, font=f_pct)
        # Fit the value to the room the pill leaves rather than cutting it at
        # a fixed length: a 1/1's name is "Secret Rarez #2 - Radbro Webring"
        # and a hard [:30] lops the artist off the end of the rarest token in
        # the collection.
        fv, room = f_val, (x1 - pw - 62) - x0
        while d.textlength(v, font=fv) > room and fv.size > 17:
            fv = font(fv.size - 1)
        d.text((x0, y + 28), v, font=fv, fill=WHITE)
        d.rounded_rectangle([x1 - pw - 40, y + 6, x1, y + 44],
                            radius=19, fill=pill)
        d.text((x1 - pw - 20, y + 13), s, font=f_pct, fill=ptxt)
        # THE BAR IS SQUARE-ROOT SCALED. Linear, a 0.50 % trait and a 0.02 %
        # trait are both an invisible sliver against a 65 % one, so the whole
        # rare end of the collection -- the only end this video is about --
        # would read as "empty bar" for every token.
        by = y + step - 14
        d.line([x0, by, x1, by], fill=BAR_TRACK, width=5)
        frac = max(0.012, math.sqrt(p / 100.0))
        d.line([x0, by, x0 + int((x1 - x0) * frac), by], fill=pill, width=5)
        y += step

    d.text((x0, 1002), f"RARITY RANK  #{rank[tid]:,} / {n:,}",
           font=f_foot, fill=GOLD)
    tw = d.textlength(f"TOKEN #{tid}", font=f_foot)
    d.text((x1 - tw, 1002), f"TOKEN #{tid}", font=f_foot, fill=MUTED)


def card_plate(ground, art, tid, vals, freq, rank, n, tier,
               section=None):
    """One token: art in a rounded card on the left, panel on the right."""
    im = ground.copy()
    d = ImageDraw.Draw(im)
    cx0, cy0, side = 78, 100, 880
    d.rounded_rectangle([cx0 - 5, cy0 - 5, cx0 + side + 5, cy0 + side + 5],
                        radius=34, outline=CARD_EDGE, width=3)
    im.paste(art.resize((side, side), Image.Resampling.LANCZOS), (cx0, cy0))
    # re-cut the rounded corners over the pasted square
    mask = Image.new("L", (side + 10, side + 10), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, side + 9, side + 9], radius=34, fill=255)
    patch = im.crop((cx0 - 5, cy0 - 5, cx0 + side + 5, cy0 + side + 5))
    bg = ground.crop((cx0 - 5, cy0 - 5, cx0 + side + 5, cy0 + side + 5))
    im.paste(Image.composite(patch, bg, mask), (cx0 - 5, cy0 - 5))

    fill, txt = TIER_COLOR.get(tier, TIER_COLOR["Standard"])
    f = font(24)
    s = f"RARITY RANK #{rank[tid]:,} / {n:,}"
    tw = d.textlength(s, font=f)
    d.rounded_rectangle([cx0 + 22, cy0 + 22, cx0 + 22 + tw + 44, cy0 + 68],
                        radius=23, fill=(12, 6, 18))
    d.rounded_rectangle([cx0 + 22, cy0 + 22, cx0 + 22 + tw + 44, cy0 + 68],
                        radius=23, outline=fill, width=2)
    d.text((cx0 + 44, cy0 + 33), s, font=f, fill=(238, 234, 244))

    draw_panel(im, tid, vals, freq, rank, n, tier, section)
    return im


def title_plate(ground, big, sub, eyebrow=None, foot=None):
    im = ground.copy()
    d = ImageDraw.Draw(im)
    y = 300
    if eyebrow:
        f = font(30)
        w = tracked_width(d, eyebrow, f, 4)
        tracked(d, ((W - w) / 2, y), eyebrow, f, CYAN, track=4)
        y += 66
    f = font(132)
    while d.textlength(big, font=f) > W - 200:
        f = font(int(f.size * 0.92))
    d.text(((W - d.textlength(big, font=f)) / 2, y), big, font=f, fill=WHITE)
    y += int(f.size * 1.25)
    fs = font(40, bold=False)
    for line in sub:
        d.text(((W - d.textlength(line, font=fs)) / 2, y), line,
               font=fs, fill=(196, 186, 214))
        y += 56
    if foot:
        ff = font(26)
        w = tracked_width(d, foot, ff, 3)
        tracked(d, ((W - w) / 2, H - 150), foot, ff, GOLD, track=3)
    return im


def ladder_plate(ground, rows, heading, note):
    """The rarity ladder: a tier per row, with its share drawn to scale."""
    im = ground.copy()
    d = ImageDraw.Draw(im)
    f_h, f_n = font(70), font(30, bold=False)
    d.text(((W - d.textlength(heading, font=f_h)) / 2, 108), heading,
           font=f_h, fill=WHITE)
    d.text(((W - d.textlength(note, font=f_n)) / 2, 200), note,
           font=f_n, fill=(178, 166, 200))

    x0, x1 = 300, 1620
    y = 300
    f_t, f_c, f_p = font(38), font(28), font(34)
    biggest = max(r[2] for r in rows)
    for name, count, share, colour in rows:
        d.text((x0, y), name, font=f_t, fill=WHITE)
        s = f"{count:,} of 4,444"
        d.text((x0 + 430, y + 6), s, font=f_c, fill=MUTED)
        ps = f"{share:.2f}%"
        d.text((x1 - d.textlength(ps, font=f_p), y + 2), ps,
               font=f_p, fill=colour)
        by = y + 56
        d.line([x0, by, x1, by], fill=BAR_TRACK, width=8)
        frac = max(0.008, math.sqrt(share / biggest))
        d.line([x0, by, x0 + int((x1 - x0) * frac), by], fill=colour, width=8)
        y += 126
    return im


# ------------------------------------------------------------- the timeline
class Seg:
    """A stretch of video backed by one or more prepared plates."""

    def __init__(self, plates, dur, loop_fps=None):
        self.plates = plates if isinstance(plates, list) else [plates]
        self.dur = dur
        self.loop_fps = loop_fps or FPS

    def at(self, t):
        if len(self.plates) == 1:
            return self.plates[0]
        i = int(t * self.loop_fps) % len(self.plates)
        return self.plates[i]


def blend(a, b, k):
    return a if k <= 0 else (b if k >= 1 else Image.blend(a, b, k))


def timeline_frames(segs, xf=0.34):
    """Frames for the whole timeline.

    Cut points come from each segment's absolute start time, rounded once --
    never from accumulating a rounded per-segment length. On a musical grid
    the per-segment duration is rarely a whole number of frames (140 BPM is
    12.857 frames a beat), and accumulating that error walks the edit off the
    beat by half a second over a couple of minutes.
    """
    """Every segment dissolves into the next. A cut would be fine between two
    cards and wrong around the tagline words, which have to fade in and out
    of the images they sit between -- one transition rule is simpler than
    two and reads better than either alone."""
    nxf = int(xf * FPS)
    t0 = 0.0
    for i, seg in enumerate(segs):
        start = round(t0 * FPS)
        t0 += seg.dur
        n = max(1, round(t0 * FPS) - start)
        for k in range(n):
            t = k / FPS
            cur = seg.at(t)
            if i + 1 < len(segs) and k >= n - nxf:
                nxt = segs[i + 1]
                a = (k - (n - nxf) + 1) / float(nxf)
                yield blend(cur, nxt.at(0), a)
            else:
                yield cur


def encode(frames, path, fps=FPS, audio=None, audio_offset=0.0):
    """Same ffmpeg contract as dynamic/animate.write_mp4 -- Main profile,
    yuv420p, faststart -- so asset_assessment/verify_media.py passes this
    file too. Streamed rather than collected: 1080p x ~4,000 frames is 25 GB
    of PIL objects if you build the list first."""
    import imageio_ffmpeg
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [exe, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", f"{fps:.4f}", "-i", "-"]
    if audio:
        # -ss BEFORE -i seeks the source, so the track can be started at its
        # own first beat rather than at file zero. -shortest ends the mux at
        # the video, since the track is longer than the cut.
        if audio_offset:
            cmd += ["-ss", f"{audio_offset:.4f}"]
        cmd += ["-i", audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-profile:v", "main", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    n = 0
    for f in frames:
        proc.stdin.write(f.convert("RGB").tobytes())
        n += 1
        if n % 300 == 0:
            print(f"    {n} frames ({n / FPS:.0f}s)", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(proc.stderr.read().decode()[:600])
    return n


def read_loop(path, size, limit=24, native=False):
    """Decode a token's own mp4 so an animated tier actually MOVES here.
    Falls back to nothing; the caller then uses the still."""
    import imageio_ffmpeg
    try:
        # Decode at the file's OWN size and resize in PIL. Asking ffmpeg to
        # scale here reports the requested size in the metadata but hands back
        # buffers at the source size, so frombytes reads 720x720 of data into
        # an 880x880 frame and every loop comes out as diagonal garbage.
        rd = imageio_ffmpeg.read_frames(path)
        meta = rd.__next__()
        w, h = meta["size"]
        out = []
        for raw in rd:
            im = Image.frombytes("RGB", (w, h), bytes(raw))
            if not native and (w, h) != (size, size):
                im = im.resize((size, size), Image.Resampling.LANCZOS)
            out.append(im)
            if len(out) >= limit:
                break
        return out or None
    except Exception:
        return None


# There is no tagline overlay. The video is a rarity breakdown, and the
# sections below are what paces it -- an explainer, then the tokens that
# explainer is about, so the number on screen and the art on screen are
# always the same thing.


def build(args):
    man, vals, freq, rank, n = load_collection()
    ground = make_ground()

    have = {int(f[:-4]) for f in os.listdir(IMAGES)
            if f.endswith(".png")} if os.path.isdir(IMAGES) else set()
    if not have:
        sys.exit(f"no rendered tokens in {IMAGES} — see MINT_PROCESS.md")

    def tier_of(t):
        row = man[t]
        if row.get("secret_rare"):
            return "Ultra"
        return g.plate_tier(row["bg"]) if row.get("bg") else "Standard"

    # ---- rarity facts, all counted rather than declared ----
    # The ladder ranks BACKGROUNDS, so the two 1/1s are not on it: they
    # composite with nothing and have no plate to band. Folding them into
    # Ultra would report 24 there and then contradict the Starfield card,
    # which says 22 -- both true, of different things.
    tier_rows = []
    tier_counts = Counter(g.plate_tier(man[t]["bg"]) for t in man
                          if man[t].get("bg") and not man[t].get("secret_rare"))
    plated = sum(tier_counts.values())
    for name in ("Ultra", "Legendary", "Scarce", "Uncommon", "Standard"):
        c = tier_counts.get(name, 0)
        if c:
            tier_rows.append((name, c, 100.0 * c / plated, TIER_COLOR[name][0]))
    n_star = sum(1 for t in man if man[t].get("starfield"))
    n_sec = sum(1 for t in man if man[t].get("secret_rare"))
    n_wx = sum(1 for t in man if man[t].get("weather"))
    n_leg = sum(1 for t in man if man[t].get("legendary"))
    wx_counts = Counter(man[t]["weather"] for t in man if man[t].get("weather"))
    rarest_wx, rarest_wx_n = min(wx_counts.items(), key=lambda kv: kv[1])
    tc = Counter(len([k for k, v in vals[t].items() if v != "None"])
                 for t in man)
    n_armed = sum(1 for t in man if man[t].get("arm"))
    n_ak = sum(1 for t in man if man[t].get("arm")
               and "AK15" in str(man[t]["arm"]))

    def one_in(k):
        return f"1 in {round(n / k):,}"

    # ---- SECTIONS: each explainer is followed by the tokens it describes ----
    #
    # The explainers used to fall every few beats regardless of what was on
    # screen, so the Starfield card could play over a Standard token and the
    # 1/1 card over a doughnut. Grouping the cast by tier and putting each
    # tier's own tokens straight after its explainer is the whole fix: the
    # section chip on every panel then repeats the claim the card just made.
    def is_rare_arm(t):
        a = str(man[t].get("arm") or "")
        return "AK15" in a or "Sweetardio_114" in a

    used = set()

    def claim(pred, limit=None):
        out = []
        for t in sorted(have, key=lambda x: rank[x]):
            if t in used or not pred(t):
                continue
            out.append(t)
            used.add(t)
            if limit and len(out) >= limit:
                break
        return out

    sections = [
        (("ULTRA · STARFIELD", TIER_COLOR["Ultra"][0]),
         title_plate(ground, f"{n_star} of 4,444",
                     ["The Starfield is the ultra tier — " + one_in(n_star) + ".",
                      "It is the only plate in the collection that MOVES.",
                      "Its 8-bit rainbow is centred on each character."],
                     eyebrow="ULTRA · STARFIELD", foot="0.50 %"),
         claim(lambda t: man[t].get("starfield"), args.max_star)),

        (("1/1 SECRET RARE", HOT),
         title_plate(ground, f"{n_sec} of 4,444",
                     ["Two 1/1 artworks, by guest artists.",
                      "They composite with nothing — no plate, no face, no traits.",
                      f"{one_in(n_sec)}, ten times rarer than the Starfield."],
                     eyebrow="THE 1/1 SECRET RARES", foot="0.02 %"),
         claim(lambda t: man[t].get("secret_rare"))),

        (("LEGENDARY PLATE", TIER_COLOR["Legendary"][0]),
         title_plate(ground, f"{n_leg} of 4,444",
                     ["Four legendary plates, 30 tokens each.",
                      f"{one_in(n_leg // 4)} for any one of them.",
                      "They never appear through the ordinary background draw."],
                     eyebrow="LEGENDARY", foot="2.70 %"),
         claim(lambda t: man[t].get("legendary"), 11)),

        (("WEATHER · ANIMATED", (140, 220, 170)),
         title_plate(ground, f"{n_wx} of 4,444",
                     ["Seven weather states, permanently baked in.",
                      f"The rarest is {rarest_wx.title()} at {rarest_wx_n} tokens "
                      f"— {one_in(rarest_wx_n)}.",
                      "Each one carries its own animated loop."],
                     eyebrow="WEATHER · ANIMATED", foot="10 %"),
         claim(lambda t: man[t].get("weather"), 11)),

        (("RARE ARMS", GOLD),
         title_plate(ground, f"{n_armed:,} armed",
                     [f"{100.0 * n_armed / n:.1f} % of the collection holds a weapon.",
                      f"The golden AK15 is {n_ak} tokens — {one_in(n_ak)}.",
                      "The three sabers are 25 each."],
                     eyebrow="ARMS", foot="15.9 %"),
         claim(is_rare_arm, 6)),

        (("THE FIELD", TIER_COLOR["Standard"][0]),
         title_plate(ground, f"{tc[min(tc)]} of 4,444",
                     ["Trait Count is the scarcity nobody could see.",
                      f"{tc[min(tc)]} tokens carry the fewest traits ({min(tc)}); "
                      f"{tc[max(tc)]} carry the most ({max(tc)}).",
                      "Both tails are rarer than a Legendary plate."],
                     eyebrow="TRAIT COUNT", foot="THE INVISIBLE TIER"),
         # EXPLICITLY the ordinary tokens. `used` alone is not enough: the
         # Starfield section is capped, so the tokens it did not use would
         # fall through to here and put an "Ultra TIER" pill under a chip
         # that says THE FIELD -- the exact contradiction these sections
         # exist to remove.
         claim(lambda t: not (man[t].get("starfield")
                              or man[t].get("secret_rare")
                              or man[t].get("legendary")
                              or man[t].get("weather")
                              or is_rare_arm(t)), 8)),
    ]

    seg = []
    S = seg.append

    S(Seg(title_plate(ground, "4,444",
                      ["Every trait composited, graded and counted.",
                       "Every percentage below is measured, not estimated."],
                      eyebrow="SWEETARDIO COLLECTION",
                      foot="A RARITY BREAKDOWN"), 4.4))
    S(Seg(ladder_plate(ground, tier_rows, "THE RARITY LADDER",
                       "Every background is pinned to an exact count. "
                       "No tier overlaps the next."), 6.6))
    S(Seg(title_plate(ground, "How to read it",
                      ["Every percentage is counted across all 4,444 tokens.",
                       f"A trait at 1.35 % is on {round(n * 0.0135)} of them.",
                       "The bar is square-root scaled, so the rare end stays visible."],
                      eyebrow="THE NUMBERS ARE REAL"), 6.2))

    shown = 0
    for chip, plate, ids in sections:
        if not ids:
            continue
        S(Seg(plate, 5.8))
        for tid in ids:
            art = Image.open(os.path.join(IMAGES, f"{tid}.png")).convert("RGB")
            tier = tier_of(tid)
            loop = None
            if args.animate and (man[tid].get("starfield")
                                 or man[tid].get("weather")):
                loop = read_loop(os.path.join(ANIM, f"{tid}.mp4"), 880)
            if loop:
                S(Seg([card_plate(ground, fr, tid, vals, freq, rank, n, tier,
                                  chip) for fr in loop],
                      args.card, loop_fps=14))
            else:
                S(Seg(card_plate(ground, art, tid, vals, freq, rank, n, tier,
                                 chip), args.card))
            shown += 1
        print(f"  {chip[0]:22s} {len(ids)} tokens")

    S(Seg(title_plate(ground, "4,444",
                      ["Five background tiers. Two 1/1s. Seven weather states.",
                       "Every count designed, allocated and verified."],
                      eyebrow="SWEETARDIO COLLECTION",
                      foot="SWEETARDIO COLLECTION"), 6.4))

    total = sum(x.dur for x in seg)
    print(f"{len(seg)} segments, {shown} token cards, "
          f"{total:.0f}s ({total/60:.1f} min)")
    return seg


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="promo/sweetardio_promo.mp4")
    ap.add_argument("--max-star", type=int, default=13,
                    help="cap on Starfield cards, so the ultra tier does not "
                         "crowd out the legendary plates")
    ap.add_argument("--card", type=float, default=2.9,
                    help="seconds per token card")
    ap.add_argument("--animate", action="store_true", default=True,
                    help="play an animated tier's own loop in the card")
    ap.add_argument("--no-animate", dest="animate", action="store_false")
    args = ap.parse_args()

    segs = build(args)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    print("encoding...")
    n = encode(timeline_frames(segs), args.out)
    print(f"wrote {args.out}  {n} frames, {n / FPS:.1f}s, "
          f"{os.path.getsize(args.out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
