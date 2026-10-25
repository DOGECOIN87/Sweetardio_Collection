#!/usr/bin/env python3
"""Curate and render the 444-token Cookie Chain Edition.

    python3 cookie_chain/build_cookie_chain.py plan            # pool -> score -> select
    python3 cookie_chain/build_cookie_chain.py sheet           # 50-token approval sheet
    python3 cookie_chain/build_cookie_chain.py render --out <cookie-chain repo>

PLAN draws a candidate pool several times the supply, renders every candidate
through the real compositor at full size, and scores what it sees (below).
It then picks the 444 that score highest in total SUBJECT TO the edition's
exact trait counts -- a 0/1 linear program, so the counts are met exactly
rather than approximately and no greedy pass can paint itself into a corner.
The chosen layer stacks go to cookie_chain/plan.json, which is the record:
`sheet` and `render` only ever read it, so the 50 approved on the sheet are
the 50 that ship.

WHAT "VISUALLY APPEALING" IS MEASURED AS, on each rendered candidate:

  edge      local colour contrast (CIE76 dE) across the figure's outline,
            figure side vs plate side, at the WORST fifth of the edge -- one
            stretch of outline melting into the plate is what a viewer sees
  contrast  the same, averaged over the whole outline
  face      the skin ball against the body round the face hole, so a black
            ball inside a chocolate body (a face that disappears) loses out
  busy      band-pass energy of the plate just outside the figure; a busy
            plate fights the character for attention
  overlap   any part of the figure under the sticker or the plaque

RARITY. Every count below is exact. The Rarity attribute is assigned last:
Mythic Chase is exactly the five one-of-one legendary plates, and every other
tier is filled by RANK of the token's statistical rarity (sum of -ln(share)
over its traits, an absent optional trait counted as its own value), so the
label is true -- a Legendary Chase token really is among the rarest 22.
"""

import argparse
import json
import math
import os
import random
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from multiprocessing import get_context
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board as bd  # noqa: E402
import cc_common as cc  # noqa: E402

PLAN = cc.PLAN
WORK = cc.WORK

# ---- exact trait counts (supply 444) ----------------------------------------
# Characters: the main collection's ladder at 444 scale -- the four chase
# bodies, the ten uncommon silhouettes, and the thirteen common shapes sharing
# the rest (22 or 23 each).
CHASE = ["og_gummy_bear", "gold_waffle", "churro", "zebra_cake"]
UNCOMMON = ["chocolate_sandwich_cookie", "ding_dong", "Nutty_Bar", "Twinkie",
            "marshmallow", "smores", "waffle", "cyan_frosted_poptart",
            "rice_crispy_treat", "oatmeal_cream_pie"]
CHASE_EACH, UNCOMMON_EACH = 6, 13

# Backgrounds: the four one-of-one Legendary plates, then a monotone ladder.
SCARCE_PLATES = ["Cookboy_Paisley.png", "Cookie_Vault.png", "Emyr_Gallery.png",
                 "Fairdevs_Night.png", "Marsel_Blue.png",
                 "Short_The_Banks_Vault.png", "Simplex_Arcade.png",
                 "Welders_Equipment.png", "Gold_Cookie_Emboss.png"]
UNCOMMON_PLATES = ["Black_Cookie_Emboss.png", "Chocolate_Cookie_Emboss.png",
                   "Silver_Cookie_Emboss.png"]
SCARCE_EACH, UNCOMMON_PLATE_EACH = 16, 24

# Arms: the two Cookie Chain held items keep their approved 22 each; the main
# collection's eleven join them on its own ladder (AK15 rarest, Cash commonest).
ARM_COUNTS = {
    cc.GAME_DEVICE: 22, cc.PRINTER: 22,
    "Arms_Cash.png": 12, "Armz_Katana.png": 11,
    "layer-layer-layer-layer-Nerf_Blaster.png": 10,
    "layer-layer-layer-layer-Military_Brat.png": 9, "Armz_Knives.png": 8,
    "layer-layer-layer-layer-AR47.png": 7, "Sweetardio_115 (11).png": 6,
    "Sweetardio_114 (4).png": 4, "Sweetardio_114 (5).png": 4,
    "Sweetardio_114 (6).png": 4, "layer-layer-layer-layer-AK15.png": 3,
}
WAT_COUNTS = {"layer-Bunny_Slippers": 22, "layer-Shiba": 22, "layer-Pepe": 20,
              "Cookie_Monster_Slippers": 18, "gorbhouse": 18}
SKIN_SHARE = {"Alien": 7, "Black": 37, "White": 56}     # traits/skin_weights.json
NIGHTLY_STICKER = "Nightly_Wallet.png"

# Mythic Chase is exactly the one-of-one legendary plates; the other tiers
# are filled by rank of statistical rarity.
RARITY_TIERS = [("Mythic Chase", 5), ("Legendary Chase", 17), ("Rare", 66),
                ("Uncommon", 134), ("Core", 222)]

SOFT_TOL = 0.25      # eyes / mouths / skins may sit within +-25% of target
EDGE_FLOOR = 21      # dE at the worst fifth of the outline; below it a figure
                     # visibly melts into its plate (a brownie on chocolate emboss)
PAIR_CAP = 3         # at most this many tokens share a character x plate; at 2 the
                     # dark bodies cannot all reach the camouflage floor below


def apportion(total, weights):
    """Largest-remainder split of `total` in proportion to `weights`."""
    keys = list(weights)
    w = np.array([weights[k] for k in keys], float)
    raw = total * w / w.sum()
    base = np.floor(raw).astype(int)
    for i in np.argsort(-(raw - base))[: total - base.sum()]:
        base[i] += 1
    return dict(zip(keys, base.tolist()))


def quotas(g):
    chars = sorted({g.char_base_name(f) for f in g.get_files(g.CHARACTERZ)})
    common = [c for c in chars if c not in CHASE + UNCOMMON]
    q_char = {c: CHASE_EACH for c in CHASE}
    q_char.update({c: UNCOMMON_EACH for c in UNCOMMON})
    rest = cc.SUPPLY - sum(q_char.values())
    q_char.update(apportion(rest, {c: 1 for c in common}))

    plates = sorted(cc.BACKGROUND_NAMES)
    regular = [p for p in plates if p not in cc.ONE_OF_ONE_BACKGROUNDS]
    q_bg = {p: 1 for p in cc.ONE_OF_ONE_BACKGROUNDS}
    q_bg.update({p: SCARCE_EACH for p in SCARCE_PLATES})
    q_bg.update({p: UNCOMMON_PLATE_EACH for p in UNCOMMON_PLATES})
    standard = [p for p in regular if p not in SCARCE_PLATES + UNCOMMON_PLATES]
    q_bg.update(apportion(cc.SUPPLY - sum(q_bg.values()), {p: 1 for p in standard}))

    stickers = sorted(cc.STICKER_NAMES)
    q_st = apportion(cc.SUPPLY, {s: 1 for s in stickers})

    q_arm = dict(ARM_COUNTS)
    q_arm[None] = cc.SUPPLY - sum(ARM_COUNTS.values())
    q_wat = dict(WAT_COUNTS)
    q_wat[None] = cc.SUPPLY - sum(WAT_COUNTS.values())

    eyes, mouths = g.get_files(g.EYEZ), g.get_files(g.MOUTHZ)
    rw = json.load(open(os.path.join(g.TRAITS_DIR, "rarity_weights.json")))
    q_eye = apportion(cc.SUPPLY, {e: rw["eyez"]["target"].get(e, 10) for e in eyes})
    q_mouth = apportion(cc.SUPPLY, {m: rw["mouthz"]["target"].get(m, 10) for m in mouths})
    q_skin = apportion(cc.SUPPLY, SKIN_SHARE)
    for q in (q_char, q_bg, q_st, q_arm, q_wat, q_eye, q_mouth, q_skin):
        assert sum(q.values()) == cc.SUPPLY, q
    return dict(character=q_char, background=q_bg, sticker=q_st, arm=q_arm,
                footwear=q_wat, eyes=q_eye, mouth=q_mouth, skin=q_skin)


# ---- the design: what the 444 must contain -----------------------------------------
# Without --board the build uses the constants above. With it, the Rarity Board
# decides (cookie_chain/board.py), and plan.json records the result under
# "design", so sheet / render / validate check against what was planned rather
# than against whatever the constants say on the day they run.

METHOD = "traits"          # how the Rarity tiers below the 1/1s are ranked
EXACT_FACE = False         # eyes / mouths / skins exact (board) or within SOFT_TOL


def default_design(g):
    q = quotas(g)
    q["weather"] = {None: cc.SUPPLY}
    return {"q": q, "names": dict(cc.BACKGROUND_NAMES),
            "ones": list(cc.ONE_OF_ONE_BACKGROUNDS), "secrets": [],
            "tiers": [list(t) for t in RARITY_TIERS], "method": "traits",
            "exact_face": False}


def board_design(g, path):
    """The board's decisions as a design. A whole-token 1/1 (the Cookboy) takes
    one of the 444 and carries no character, plate, sticker or face, so each
    of those lists gives up one token from its most common value -- the board
    says so beside the Cookboy card."""
    b = bd.load(path)
    counts, tiers, names = bd.backgrounds(b)
    secrets = [f for f in counts if f in cc.SECRET_RARES]
    ones = [f for f in counts if tiers[f] == "one" and f not in secrets]
    chars = sorted({g.char_base_name(f) for f in g.get_files(g.CHARACTERZ)})
    q = bd.quotas(b, chars)
    q["background"] = {f: n for f, n in counts.items() if f not in secrets}
    for key in ("character", "sticker", "eyes", "mouth", "skin"):
        for _ in secrets:
            top = max(sorted(q[key]), key=lambda k: q[key][k])
            q[key][top] -= 1
    for key in ("arm", "footwear", "weather"):
        q[key][None] -= len(secrets)
        if q[key][None] < 0:
            raise SystemExit(f"board: {key} leave no room for the 1/1 token(s)")
    rtiers, method = bd.rarity_tiers(b, len(ones) + len(secrets))
    return {"q": q, "names": {f: n for f, n in names.items() if f not in secrets},
            "ones": ones, "secrets": secrets, "tiers": rtiers, "method": method,
            "exact_face": True}


def apply_design(d):
    global RARITY_TIERS, METHOD, EXACT_FACE
    cc.BACKGROUND_NAMES.update(d["names"])
    cc.ONE_OF_ONE_BACKGROUNDS = tuple(d["ones"])
    RARITY_TIERS = [tuple(t) for t in d["tiers"]] if d["tiers"] else None
    METHOD, EXACT_FACE = d["method"], d.get("exact_face", False)
    return d


def design_json(d):
    """JSON keys cannot be None; the 'no arm' / 'no footwear' count is
    written as "none"."""
    out = dict(d)
    out["q"] = {k: {("none" if v is None else v): n for v, n in qq.items()}
                for k, qq in d["q"].items()}
    return out


def design_from_json(d):
    d = dict(d)
    d["q"] = {k: {(None if v == "none" else v): n for v, n in qq.items()}
              for k, qq in d["q"].items()}
    return d


def bias_draw(g, q):
    """Draw the pool's eyes, mouths and skins in proportion to the design, so
    an exact board count is not asked of a pool drawn for another one."""
    eye_g = {f: q["eyes"].get(f, 0) + 1 for f in g.get_files(g.EYEZ)}
    mouth_g = {f: q["mouth"].get(f, 0) + 1 for f in g.get_files(g.MOUTHZ)}
    g.load_rarity_gains = lambda cat: {g.EYEZ: eye_g, g.MOUTHZ: mouth_g}.get(cat, {})
    skin_w = {k: q["skin"].get(k, 0) + 1 for k in SKIN_SHARE}
    g.load_skin_weights = lambda: (skin_w, 1)


# ---- candidate pool -------------------------------------------------------------

def describe(g, layers, char):
    """The trait keys of a layer stack, by folder."""
    d = {"character": char, "arm": None, "footwear": None}
    for li in layers:
        p = os.path.normpath(li["path"])
        f = os.path.basename(p)
        folder = os.path.basename(os.path.dirname(p))
        if p.startswith(os.path.normpath(str(cc.BACKGROUNDS)) + os.sep):
            d["background"] = f
        elif p.startswith(os.path.normpath(str(cc.STICKERS)) + os.sep):
            d["sticker"] = f
        elif p.startswith(os.path.normpath(g.ARMZ) + os.sep):
            d["arm"] = f
        elif folder == g.SKINZ:
            d["skin"] = next(k for k in SKIN_SHARE if k.lower() in f.lower())
        elif folder == g.EYEZ:
            d["eyes"] = f
        elif folder == g.MOUTHZ:
            d["mouth"] = f
        elif p.startswith(os.path.normpath(os.path.join(g.TRAITS_DIR, g.WHAT_ARE_THOSEZ)) + os.sep) \
                and "_base" in f.lower():
            d["footwear"] = ("gorbhouse" if "gorbhouse" in f.lower()
                             else f.split("_Base")[0].split("_base")[0]
                             .replace(" (1)", ""))
    return d


def signature(d):
    return tuple(d.get(k) for k in ("character", "background", "skin", "eyes",
                                    "mouth", "footwear", "arm", "sticker"))


def affinity(pool):
    """Expected score of each character x plate pairing, from a scored pool.

    A pair has only a few samples, so its mean is shrunk toward the additive
    estimate (character mean + plate mean - global mean): dark bodies score
    low everywhere and the gold / chocolate emboss plates low for everyone,
    and the additive part carries that where a pair has not been drawn."""
    reg = [c for c in pool if c["traits"]["background"] not in cc.ALL_ONE_OF_ONE_BACKGROUNDS]
    m = np.mean([c["score"] for c in reg])
    by_c, by_p, by_cp = defaultdict(list), defaultdict(list), defaultdict(list)
    for c in reg:
        t = c["traits"]
        by_c[t["character"]].append(c["score"])
        by_p[t["background"]].append(c["score"])
        by_cp[(t["character"], t["background"])].append(c["score"])
    mc = {k: np.mean(v) for k, v in by_c.items()}
    mp = {k: np.mean(v) for k, v in by_p.items()}
    k = 2.0
    return {(ch, pl): (sum(by_cp.get((ch, pl), [])) + k * (mc[ch] + mp[pl] - m))
            / (len(by_cp.get((ch, pl), [])) + k)
            for ch in mc for pl in mp}, mc


def make_pool(g, q, size, seed, existing=None, aff=None, tau=0.35):
    """Draw unique candidates. With `existing` + `aff` (from affinity()), the
    draw is TARGETED: each character is drawn more often the worse it scored,
    and its plate is drawn in proportion to quota x exp(affinity / tau), so
    the pool fills in the pairings that will actually be chosen."""
    rng = random.Random(seed)
    bias_draw(g, q)
    # Every plate, arm, footwear and sticker is drawn, weighted by the design
    # plus a small floor: the pool outlives one set of board choices, and
    # `plan --reuse` can then re-select for the next set without re-rendering.
    chars = sorted({g.char_base_name(f) for f in g.get_files(g.CHARACTERZ)})
    cw = [q["character"].get(c, 0) + 2 for c in chars]
    regular = {p: q["background"].get(p, 0) + 4 for p in sorted(cc.BACKGROUND_NAMES)
               if p not in cc.ALL_ONE_OF_ONE_BACKGROUNDS}
    plates, pw = zip(*regular.items())
    arms = {a: q["arm"].get(a, 0) + 2 for a in sorted(os.listdir(g.ARMZ)) if a.endswith(".png")}
    regular_wat = {w: q["footwear"].get(w, 0) + 3 for w in bd.FOOTWEAR.values()
                   if w != "gorbhouse"}
    stickers = [s for s in sorted(cc.STICKER_NAMES) if s != NIGHTLY_STICKER] + [NIGHTLY_STICKER]
    pool = list(existing or [])
    seen = {signature(c["traits"]) for c in pool}
    target = len(pool) + size if existing else size
    new_from = len(pool)

    if aff:
        table, char_mean = aff
        top = max(char_mean.values())
        cw = [w * (1 + 2.0 * (top - char_mean[c]) / max(1e-6, top)) for c, w in zip(chars, cw)]

    def add(i, **force):
        random.seed(seed * 1_000_003 + i)
        layers, char = g.generate_random_combination(**force)
        d = describe(g, layers, char)
        if force.get("force_wat") not in (None, "auto") and d["footwear"] is None:
            return False
        if force.get("force_arm") not in (None, "auto") and d["arm"] is None:
            return False
        sig = signature(d)
        if sig in seen:
            return False
        seen.add(sig)
        pool.append({"id": len(pool), "layers": layers, "traits": d})
        return True

    i = 0
    if not existing:
        # the one-of-one plates: a handful of candidates each, Nightly paired
        # with its own wallet sticker as in the previous release
        for plate in cc.ALL_ONE_OF_ONE_BACKGROUNDS:
            made = 0
            while made < 10:
                i += 1
                st = NIGHTLY_STICKER if plate == "Legendary_Nightly.png" else \
                    rng.choice(stickers[:-1])
                made += add(i, force_bg=(g.BACKGROUNDZ, plate),
                            force_char=rng.choices(chars, cw)[0],
                            force_arm=None, force_wat=None, force_sticker=st)
    while len(pool) < target:
        i += 1
        char = rng.choices(chars, cw)[0]
        if aff:
            best = max(table[(char, p)] for p in plates)
            w = [n * math.exp((table[(char, p)] - best) / tau) for p, n in zip(plates, pw)]
            plate = rng.choices(plates, w)[0]
        else:
            plate = rng.choices(plates, pw)[0]
        if plate == cc.STARFIELD and char not in g.STARFIELD_CHARS:
            char = rng.choice([c for c in chars if c in g.STARFIELD_CHARS])
        arm = None
        if rng.random() < max(0.25, min(0.75, 1.6 * sum(n for a, n in q["arm"].items() if a)
                                         / max(1, sum(q["character"].values())))):
            arm = rng.choices(list(arms), list(arms.values()))[0]
            if not g.armz_allowed(arm, char):
                arm = None
        wat = None
        if not g.is_wat_excluded(char) and rng.random() < max(0.35, min(0.8, 2.2 * sum(
                n for w, n in q["footwear"].items() if w) / max(1, sum(q["character"].values())))):
            opts = dict(regular_wat)
            if g.gets_gorbhouse_overlay(char):
                opts["gorbhouse"] = (q["footwear"].get("gorbhouse", 0) + 3) * 2.5
            wat = rng.choices(list(opts), list(opts.values()))[0]
        add(i, force_bg=(g.BACKGROUNDZ, plate), force_char=char, force_arm=arm,
            force_wat=wat, force_sticker=stickers[i % len(stickers)])
    for c in pool[new_from:]:
        c["layers"] = cc.apply_figure_scale(g, c["layers"], c["traits"]["character"])
    return pool


# ---- render + score ---------------------------------------------------------------

def _lab(rgb):
    """sRGB uint8 (H, W, 3) -> CIE Lab."""
    c = rgb.astype(np.float32) / 255
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = c @ np.array([[0.4124, 0.2126, 0.0193], [0.3576, 0.7152, 0.1192],
                        [0.1805, 0.0722, 0.9505]], np.float32)
    xyz /= np.array([0.9505, 1.0, 1.089], np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], -1)


def _masked_blur(img, mask, sigma):
    m = mask.astype(np.float32)
    num = np.stack([ndimage.gaussian_filter(img[..., k] * m, sigma) for k in range(img.shape[-1])], -1)
    den = ndimage.gaussian_filter(m, sigma)[..., None]
    return num / np.maximum(den, 1e-4), den[..., 0]


def render_token(g, layers, path, capture=None):
    """Composite one token (+ plaque) to `path`. When `capture` is a dict it
    receives every layer's rendered alpha, keyed by kind."""
    orig = g._render_layer

    def spy(li):
        img = orig(li)
        if capture is not None and img is not None:
            capture.setdefault("layers", []).append((li["path"], img))
        return img
    g._render_layer = spy
    try:
        g.create_image(layers, path)
    finally:
        g._render_layer = orig
    cc.add_plaque(path)


def score_candidate(job):
    cand, thumb_dir = job
    g = cc.setup()
    cap = {}
    tmp = os.path.join(thumb_dir, f"_tmp_{os.getpid()}.bmp")   # fast to write
    render_token(g, cand["layers"], tmp, cap)
    final = Image.open(tmp).convert("RGB")
    final.resize((512, 512), Image.Resampling.LANCZOS).save(
        os.path.join(thumb_dir, f"{cand['id']:05d}.jpg"), quality=90)

    R = 464                                         # score at 1/3 size
    comp = np.asarray(final.resize((R, R), Image.Resampling.BILINEAR))
    fig = np.zeros((R, R), np.float32)
    ball = np.zeros_like(fig)
    body = np.zeros_like(fig)
    sticker = np.zeros_like(fig)
    for path, img in cap["layers"]:
        a = np.asarray(img.getchannel("A").resize((R, R), Image.Resampling.BILINEAR),
                       np.float32) / 255
        p = os.path.normpath(path)
        folder = os.path.basename(os.path.dirname(p))
        if p.startswith(os.path.normpath(str(cc.BACKGROUNDS)) + os.sep):
            continue
        if p.startswith(os.path.normpath(str(cc.STICKERS)) + os.sep):
            sticker = np.maximum(sticker, a)
            continue
        fig = np.maximum(fig, a)
        if folder == g.SKINZ:
            ball = np.maximum(ball, a)
        elif folder == g.CHARACTERZ:
            body = np.maximum(body, a)
    plaque = np.asarray(Image.open(cc.PLAQUE).getchannel("A").resize((R, R)), np.float32) / 255

    lab = _lab(comp)
    F = fig > 0.5
    inner = F & ~ndimage.binary_erosion(F, iterations=3)
    outer = ndimage.binary_dilation(F, iterations=7) & ~ndimage.binary_dilation(F, iterations=1)
    in_mean, _ = _masked_blur(lab, inner, 5)
    out_mean, _ = _masked_blur(lab, outer, 5)
    edge = F & ~ndimage.binary_erosion(F)
    de = np.linalg.norm(in_mean - out_mean, axis=-1)[edge]
    edge_p20 = float(np.percentile(de, 20)) if de.size else 0.0
    edge_mean = float(de.mean()) if de.size else 0.0

    luma = lab[..., 0]
    band = np.abs(ndimage.gaussian_filter(luma, 1.5) - ndimage.gaussian_filter(luma, 8))
    ring = ndimage.binary_dilation(F, iterations=14) & ~F & (sticker < 0.05) & (plaque < 0.05)
    busy = float(band[ring].mean()) if ring.any() else 0.0

    hole = (ball > 0.5) & (body < 0.5)
    B = body > 0.5
    face = 0.0
    if hole.any():
        rim_in = hole & ndimage.binary_dilation(B, iterations=3)
        rim_out = B & ndimage.binary_dilation(hole, iterations=3)
        if rim_in.any() and rim_out.any():
            face = float(np.linalg.norm(lab[rim_in].mean(0) - lab[rim_out].mean(0)))

    ov_sticker = float((fig * sticker).sum() / max(1.0, sticker.sum()))
    ov_plaque = float((fig * plaque).sum() / max(1.0, plaque.sum()))

    os.remove(tmp)
    return cand["id"], {"edge_p20": round(edge_p20, 2),
                        "edge_mean": round(edge_mean, 2), "face": round(face, 2),
                        "busy": round(busy, 3), "ov_sticker": round(ov_sticker, 4),
                        "ov_plaque": round(ov_plaque, 4)}


def combine(m):
    """One appeal score from the measured metrics (see module docstring)."""
    return round(float(
        1.6 * np.clip((m["edge_p20"] - 6) / 34, 0, 1.2)
        + 0.8 * np.clip((m["edge_mean"] - 10) / 50, 0, 1.2)
        + 0.5 * np.clip((m["face"] - 6) / 40, 0, 1.0)
        - 0.6 * np.clip(m["busy"] / 10, 0, 1.5)
        - 6.0 * m["ov_sticker"] - 3.0 * m["ov_plaque"]), 5)


# ---- selection ----------------------------------------------------------------------

def select(pool, q):
    """Max total score, exact counts, via a 0/1 MILP (HiGHS). Candidates whose
    outline melts into the plate (edge_p20 under EDGE_FLOOR) are not eligible;
    the floor steps down only if the exact counts cannot otherwise be met."""
    # a candidate carrying anything the design does not ask for (a removed
    # plate, an arm set to 0) is not merely unconstrained -- it must be out
    allowed = [c for c in pool if all(c["traits"].get(k) in q[k] for k in
                                      ("character", "background", "sticker", "arm",
                                       "footwear", "eyes", "mouth", "skin"))]
    for floor in range(EDGE_FLOOR, -1, -3):
        eligible = [c for c in allowed if c["edge_p20"] >= floor
                    or c["traits"]["background"] in cc.ONE_OF_ONE_BACKGROUNDS]
        try:
            chosen, res = _select(eligible, q)
            print(f"camouflage floor: edge_p20 >= {floor} "
                  f"({len(eligible)} of {len(pool)} eligible)")
            return chosen, res
        except SystemExit as e:
            print(f"floor {floor}: {e}")
    raise SystemExit("selection infeasible at every floor")


def _select(pool, q):
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import lil_matrix

    n = len(pool)
    rows, lo, hi = [], [], []

    def group(key, exact=True, tol=0.0):
        values = defaultdict(list)
        for i, c in enumerate(pool):
            values[c["traits"].get(key)].append(i)
        for v, target in q[key].items():
            idx = values.get(v, [])
            if exact:
                rows.append(idx); lo.append(target); hi.append(target)
            else:
                rows.append(idx)
                lo.append(max(0, math.floor(target * (1 - tol))))
                hi.append(math.ceil(target * (1 + tol)) + 1)

    for key in ("character", "background", "sticker", "arm", "footwear"):
        group(key)
    for key in ("eyes", "mouth", "skin"):
        group(key, exact=EXACT_FACE, tol=SOFT_TOL if key != "skin" else 0.15)
    pairs = defaultdict(list)
    for i, c in enumerate(pool):
        pairs[(c["traits"]["character"], c["traits"]["background"])].append(i)
    for idx in pairs.values():
        if len(idx) > PAIR_CAP:
            rows.append(idx); lo.append(0); hi.append(PAIR_CAP)
    # the Nightly plate keeps its own wallet sticker
    nightly = [i for i, c in enumerate(pool)
               if c["traits"]["background"] == "Legendary_Nightly.png"
               and c["traits"]["sticker"] != NIGHTLY_STICKER]
    if nightly:
        rows.append(nightly); lo.append(0); hi.append(0)
    total = sum(q["character"].values())       # 444 less any whole-token 1/1
    rows.append(list(range(n))); lo.append(total); hi.append(total)

    A = lil_matrix((len(rows), n))
    for r, idx in enumerate(rows):
        for i in idx:
            A[r, i] = 1
    cost = -np.array([c["score"] for c in pool])
    res = milp(cost, constraints=LinearConstraint(A.tocsr(), lo, hi),
               integrality=np.ones(n), bounds=Bounds(0, 1),
               options={"time_limit": 600, "mip_rel_gap": 1e-4})
    if res.x is None:
        raise SystemExit(f"selection infeasible: {res.message}")
    chosen = [pool[i] for i in np.nonzero(res.x > 0.5)[0]]
    assert len(chosen) == total
    return chosen, res


def assign_weather(chosen, q, seed):
    """Weather is a grade laid over the finished token, so it changes nothing
    the selector scored; it lands at exact counts on the tokens it may cover
    -- never a 1/1 plate, never the Starfield (both own animation_url)."""
    for c in chosen:
        c["traits"]["weather"] = None
    want = {w: n for w, n in q.get("weather", {}).items() if w}
    if not want:
        return
    free = sorted((c for c in chosen
                   if c["traits"]["background"] not in cc.ONE_OF_ONE_BACKGROUNDS
                   and c["traits"]["background"] != cc.STARFIELD), key=lambda c: c["id"])
    if sum(want.values()) > len(free):
        raise SystemExit(f"weather: {sum(want.values())} tokens asked for, "
                         f"{len(free)} can carry it")
    random.Random(seed).shuffle(free)
    pos = 0
    for w in cc.WEATHER_STATES:
        for c in free[pos:pos + want.get(w, 0)]:
            c["traits"]["weather"] = w
        pos += want.get(w, 0)


def assign_rarity(chosen, n_secret=0):
    """The first tier is exactly the 1/1s (plates, plus any whole-token 1/1,
    which the caller places there); the rest are ranked by statistical rarity
    or, on METHOD "looks", by score."""
    keys = ("character", "background", "skin", "eyes", "mouth", "footwear", "arm", "sticker",
            "weather")
    counts = {k: Counter(c["traits"].get(k) for c in chosen) for k in keys}
    for c in chosen:
        c["rarity_score"] = round(sum(-math.log(counts[k][c["traits"].get(k)] / len(chosen))
                                      for k in keys), 5)
    if RARITY_TIERS is None:                 # the board dropped the attribute
        for c in chosen:
            c["rarity"] = None
        return
    first = lambda c: c["traits"]["background"] not in cc.ONE_OF_ONE_BACKGROUNDS
    if METHOD == "looks":
        ranked = sorted(chosen, key=lambda c: (first(c), -c["score"]))
    else:
        ranked = sorted(chosen, key=lambda c: (first(c), -c["rarity_score"], -c["score"]))
    tiers = list(RARITY_TIERS)
    tiers[0] = (tiers[0][0], tiers[0][1] - n_secret)
    assert sum(n for _, n in tiers) == len(chosen)
    assert tiers[0][1] == len(cc.ONE_OF_ONE_BACKGROUNDS)
    pos = 0
    for tier, n in tiers:
        for c in ranked[pos:pos + n]:
            c["rarity"] = tier
        pos += n


# ---- metadata -------------------------------------------------------------------------

def attributes(g, cand):
    if cand.get("secret"):
        attrs = [{"trait_type": "1/1", "value": cc.SECRET_RARES[cand["secret"]]},
                 {"trait_type": "Edition", "value": cc.EDITION}]
        if cand.get("rarity"):
            attrs.append({"trait_type": "Rarity", "value": cand["rarity"]})
        return attrs
    t = cand["traits"]
    attrs = [{"trait_type": "Character", "value": g.trait_name(g.CHARACTERZ, t["character"])},
             {"trait_type": "Background", "value": cc.BACKGROUND_NAMES[t["background"]]}]
    for layer in cand["layers"]:
        folder = os.path.basename(os.path.dirname(os.path.normpath(layer["path"])))
        f = os.path.basename(layer["path"])
        if folder == g.SKINZ:
            attrs.append({"trait_type": "Skin", "value": g.trait_name(g.SKINZ, f)})
    attrs.append({"trait_type": "Eyes", "value": g.trait_name(g.EYEZ, t["eyes"])})
    attrs.append({"trait_type": "Mouth", "value": g.trait_name(g.MOUTHZ, t["mouth"])})
    if t["footwear"]:
        key = "Gorbhouse" if t["footwear"] == "gorbhouse" else t["footwear"]
        # by the CATEGORY key, never g.WHAT_ARE_THOSEZ / g.ARMZ: setup() points
        # those at the edition's folders, and TRAIT_NAMES is keyed by category
        attrs.append({"trait_type": "Footwear", "value": g.trait_name("what_are_thosez", key)})
    if t["arm"]:
        attrs.append({"trait_type": "Arms",
                      "value": cc.ARM_NAMES.get(t["arm"]) or g.trait_name("armz", t["arm"])})
    attrs.append({"trait_type": "Sticker", "value": cc.STICKER_NAMES[t["sticker"]]})
    if t.get("weather"):
        attrs.append({"trait_type": "Weather", "value": t["weather"].title()})
    attrs.append({"trait_type": "Edition", "value": cc.EDITION})
    if cand.get("rarity"):
        attrs.append({"trait_type": "Rarity", "value": cand["rarity"]})
    return attrs


def is_animated(t):
    """Ships a loop: the animated 1/1, a Starfield token, a Weather token."""
    return (t.get("secret") in cc.ANIMATED_SECRET_RARES
            or t["traits"].get("background") == cc.STARFIELD
            or bool(t["traits"].get("weather")))


def token_json(g, cand, seed):
    n = cand["token"]
    meta = {"name": f"{cc.EDITION} #{n:03d}",
            "description": f"One of {cc.SUPPLY} {cc.EDITION} collectibles.",
            "image": f"../images/{n:03d}.png"}
    animated = is_animated(cand)
    if animated:
        meta["animation_url"] = f"../animations/{n:03d}.mp4"
    meta["attributes"] = attributes(g, cand)
    if animated:
        # Metaplex reads the typed file list; some wallets read only this
        meta["properties"] = {"files": [{"uri": meta["image"], "type": "image/png"},
                                        {"uri": meta["animation_url"], "type": "video/mp4"}],
                              "category": "video"}
    if cand.get("score") is not None:
        meta["selection_score"] = cand["score"]
    meta["seed"] = seed
    return meta


# ---- commands -------------------------------------------------------------------------

def _jsonable(v):
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, np.generic):
        return v.item()
    return v


def _portable(layers):
    """Plan paths are layout-free: `traits/...` for the compositor's figure
    art, `assets/...` for the edition's own, so plan.json reads the same from
    Sweetardio_Collection/cookie_chain and from the edition repo."""
    out = []
    for li in layers:
        li = _jsonable(dict(li))
        p = Path(li["path"])
        if not p.is_absolute():
            p = cc.REPO_ROOT / p
        if p.parent == Path(cc.setup().ARMZ):            # staged arm symlink
            p = Path(os.path.realpath(p))
        p = p.resolve()
        if p.is_relative_to(cc.ASSETS.resolve()):
            li["path"] = "assets/" + str(p.relative_to(cc.ASSETS.resolve()))
        else:
            li["path"] = str(p.relative_to(cc.REPO_ROOT.resolve()))
        out.append(li)
    return out


def _resolve(g, layers):
    out = []
    for li in layers:
        li = dict(li)
        rel = li["path"]
        if rel.startswith("cookie_chain/assets/"):       # plans written before
            rel = rel[len("cookie_chain/"):]             # the layout-free paths
        if rel.startswith("traits/what_are_thosez/") and cc.FOOTWEAR.is_dir():
            rel = "assets/what_are_thosez/" + rel[len("traits/what_are_thosez/"):]
        if rel.startswith("assets/"):
            p = cc.ASSETS / rel[len("assets/"):]
        else:
            p = cc.REPO_ROOT / rel
        if rel.startswith("traits/armz/") or rel.startswith("assets/armz/"):
            p = Path(g.ARMZ) / p.name          # arms are read through the stage
        li["path"] = str(p)
        for k in ("gcenter", "ccenter", "fcenter", "acenter"):
            if k in li:
                li[k] = tuple(li[k])
        out.append(li)
    return out


def cmd_plan(args):
    g = cc.setup()
    design = apply_design(board_design(g, args.board) if args.board else default_design(g))
    q = design["q"]
    WORK.mkdir(parents=True, exist_ok=True)
    thumbs = WORK / "thumbs"
    if args.reuse or args.extend:
        # re-select from the scored pool without re-rendering it
        pool = json.loads((WORK / "pool.json").read_text())
        for c in pool:
            c["layers"] = _resolve(g, c["layers"])
    if args.extend:
        for c in pool:
            c["score"] = combine(c)
        n0 = len(pool)
        pool = make_pool(g, q, args.extend, args.seed + len(pool), existing=pool,
                         aff=affinity(pool))
        print(f"extended pool by {len(pool) - n0} targeted candidates", flush=True)
        jobs = [(c, str(thumbs)) for c in pool[n0:]]
        with get_context("fork").Pool(args.workers) as p:
            for k, (cid, sc) in enumerate(p.imap_unordered(score_candidate, jobs, chunksize=4), 1):
                pool[cid].update(sc)
                if k % 100 == 0 or k == len(jobs):
                    print(f"scored {k}/{len(jobs)}", flush=True)
        json.dump([{k: v for k, v in c.items() if k not in ("layers", "score")}
                   | {"layers": _portable(c["layers"])} for c in pool],
                  open(WORK / "pool.json", "w"))
    elif not args.reuse:
        if thumbs.exists():
            shutil.rmtree(thumbs)
        thumbs.mkdir()
        pool = make_pool(g, q, args.pool, args.seed)
        print(f"pool: {len(pool)} unique candidates", flush=True)
        jobs = [(c, str(thumbs)) for c in pool]
        with get_context("fork").Pool(args.workers) as p:
            for k, (cid, sc) in enumerate(p.imap_unordered(score_candidate, jobs, chunksize=4), 1):
                pool[cid].update(sc)
                if k % 100 == 0 or k == len(pool):
                    print(f"scored {k}/{len(pool)}", flush=True)
        json.dump([{k: v for k, v in c.items() if k != "layers"} | {"layers": _portable(c["layers"])}
                   for c in pool], open(WORK / "pool.json", "w"))
    for c in pool:
        c["score"] = combine(c)
    chosen, res = select(pool, q)
    assign_weather(chosen, q, args.seed)
    assign_rarity(chosen, len(design["secrets"]))
    secrets = [{"secret": f, "traits": {}, "layers": [], "score": None,
                "rarity": RARITY_TIERS[0][0] if RARITY_TIERS else None}
               for f in design["secrets"]]
    tokens = chosen + secrets
    rng = random.Random(args.seed)
    rng.shuffle(tokens)                      # numbering cannot be read for rarity
    for n, c in enumerate(tokens, 1):
        c["token"] = n
    plan = {"edition": cc.EDITION, "supply": cc.SUPPLY, "seed": args.seed,
            "pool": len(pool), "objective": round(-res.fun, 3),
            "figure_scale": cc.FIGURE_SCALE, "big_body_scale": cc.BIG_BODY_SCALE,
            "plaque": cc.PLAQUE_ON, "design": design_json(design),
            "tokens": [({"token": c["token"], "secret": c["secret"], "traits": {},
                         "rarity": c["rarity"], "layers": []} if c.get("secret") else
                        {"token": c["token"], "pool_id": c["id"], "traits": c["traits"],
                         "rarity": c["rarity"], "rarity_score": c["rarity_score"],
                         "score": c["score"],
                         "metrics": {k: c[k] for k in ("edge_p20", "edge_mean", "face",
                                                       "busy", "ov_sticker", "ov_plaque")},
                         "layers": _portable(c["layers"])})
                       for c in sorted(tokens, key=lambda c: c["token"])]}
    PLAN.write_text(json.dumps(plan, indent=1) + "\n")
    sel = np.array([c["score"] for c in chosen])
    allsc = np.array([c["score"] for c in pool])
    print(f"selected {len(chosen)} of {len(pool)}: mean score {sel.mean():.3f} "
          f"(pool {allsc.mean():.3f}), min {sel.min():.3f}")
    print(f"plan -> {PLAN}")


def load_plan(g):
    plan = json.loads(PLAN.read_text())
    apply_design(design_from_json(plan["design"]) if "design" in plan else default_design(g))
    for t in plan["tokens"]:
        t["layers"] = _resolve(g, t["layers"])
        t.setdefault("score", None)
    return plan


def _font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def pick_sheet(tokens, count):
    """`count` tokens that between them show as much of the edition as
    possible: every arm, footwear, sticker, character and plate it can reach,
    and every rarity tier; ties go to the better-scoring token."""
    keys = ("character", "background", "arm", "footwear", "sticker")
    covered = defaultdict(set)
    picked = []
    tiers = Counter()
    names = [n for n, _ in (RARITY_TIERS or [])]
    want_tier = dict(zip(names, (RARITY_TIERS[0][1] if names else 0, 4, 9, 14)))
    for _ in range(count):
        def gain(t):
            g_ = sum(t["traits"].get(k) not in covered[k] for k in keys)
            g_ += 1.5 * (t["traits"].get("arm") is not None and t["traits"]["arm"] not in covered["arm"])
            g_ += 2 * (tiers[t["rarity"]] < want_tier.get(t["rarity"], 0))
            return g_ + 0.2 * (t["score"] or 0)
        best = max((t for t in tokens if t not in picked), key=gain)
        picked.append(best)
        tiers[best["rarity"]] += 1
        for k in keys:
            covered[k].add(best["traits"].get(k))
    return sorted(picked, key=lambda t: t["token"])


def cmd_sheet(args):
    g = cc.setup()
    plan = load_plan(g)
    picked = pick_sheet(plan["tokens"], args.count)
    out_dir = WORK / "sheet"
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(t, str(out_dir / f"{t['token']:03d}.png"), None) for t in picked]
    with get_context("fork").Pool(args.workers) as p:
        list(p.imap_unordered(_render_job, jobs))
    cols, cell, lab = 5, 560, 64
    rows = math.ceil(len(picked) / cols)
    sheet = Image.new("RGB", (cols * cell, rows * (cell + lab)), (14, 14, 18))
    d = ImageDraw.Draw(sheet)
    f1, f2 = _font(22), _font(17)
    for i, t in enumerate(picked):
        im = Image.open(out_dir / f"{t['token']:03d}.png").convert("RGB").resize(
            (cell, cell), Image.Resampling.LANCZOS)
        x, y = (i % cols) * cell, (i // cols) * (cell + lab)
        sheet.paste(im, (x, y))
        attrs = {a["trait_type"]: a["value"] for a in attributes(g, t)}
        d.text((x + 10, y + cell + 6),
               f"#{t['token']:03d}  {attrs.get('Character') or attrs.get('1/1')}  ·  {t['rarity']}",
               font=f1, fill=(240, 240, 244))
        extra = ([attrs["Background"]] if "Background" in attrs else ["animated 1/1"]) + \
            [attrs[k] for k in ("Arms", "Footwear") if k in attrs]
        d.text((x + 10, y + cell + 36), "  ·  ".join(extra)[:62], font=f2, fill=(170, 170, 182))
    path = Path(args.sheet_out) if args.sheet_out else WORK / "approval_sheet_50.jpg"
    sheet.save(path, quality=92)
    (WORK / "approval_sheet_50.json").write_text(json.dumps([t["token"] for t in picked]) + "\n")
    print(f"sheet -> {path}")


def render_secret(g, name, path, anim_dir=None, tid=None):
    """A whole-token 1/1: its finished still, and for an animated one the
    12-frame loop dynamic/cookboy.py re-composites per starfield frame."""
    still = Image.open(os.path.join(cc.REPO_ROOT, "traits", "secret_rarez", name)).convert("RGBA")
    plaque = Image.open(cc.PLAQUE).convert("RGBA") if cc.PLAQUE_ON else None
    if plaque is not None:
        still.alpha_composite(plaque)
    still.convert("RGB").save(path, compress_level=6)
    if anim_dir is None or name not in cc.ANIMATED_SECRET_RARES:
        return
    sys.path.insert(0, str(cc.REPO_ROOT / "dynamic"))
    import cookboy                                     # the one animated 1/1
    from dynamic.animate import write_mp4
    frames = cookboy.build_loop(str(anim_dir), tid, size=cc.LOOP_SIZE)
    if plaque is not None:
        small = plaque.resize(frames[0].size, Image.Resampling.LANCZOS)
        frames = [Image.alpha_composite(f.convert("RGBA"), small) for f in frames]
    if write_mp4(frames, os.path.join(anim_dir, f"{tid}.mp4"), 1000.0 / cc.LOOP_MS) is None:
        sys.exit("no ffmpeg -- pip install imageio-ffmpeg")


def centre_starfield(g, layers):
    """dynamic/starfield.centre_figure for a figure the edition scales. The
    drop is measured on the SCALED render, and a layer's dy is applied before
    the scale about FIGURE_PIVOT, so the drop goes in as dy / scale -- as is,
    centre_figure would leave every starfield figure 12% short of centre."""
    import starfield as sf
    d = sf.figure_drop(layers, g)
    if not d:
        return layers
    moves = sf._folders(g, *[getattr(g, n) for n in sf.FIGURE_MOVES])
    out = []
    for i, l in enumerate(layers):
        l = dict(l)
        if i and os.path.normpath(l["path"]).startswith(moves):
            l["dy"] = l.get("dy", 0) + int(round(d / l.get("gscale", 1.0)))
        out.append(l)
    return out


def render_full(g, t, path, anim_dir=None):
    """A composited token as it ships: the still at `path` and, for a
    Starfield or Weather token when `anim_dir` is given, its loop."""
    tid = f"{t['token']:03d}"
    layers, wx = t["layers"], t["traits"].get("weather")
    if t["traits"].get("background") == cc.STARFIELD:
        import starfield as sf
        from dynamic.animate import write_mp4
        tmp = WORK / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        # centre the figure FIRST, then the rainbow on where it now stands
        layers, dy, plate = sf.centre_layers(centre_starfield(g, layers), str(tmp), tid, g)
        try:
            render_token(g, layers, path)
            if anim_dir is not None:
                frames = sf.loop_layers(layers, str(tmp), tid, g, size=cc.LOOP_SIZE, dy=dy)
                if write_mp4(frames, os.path.join(anim_dir, f"{tid}.mp4"),
                             1000.0 / cc.LOOP_MS) is None:
                    sys.exit("no ffmpeg -- pip install imageio-ffmpeg")
        finally:
            os.remove(plate)
        return
    if not wx:
        render_token(g, layers, path)
        return
    # Weather: render clear WITH the protect and float masks, then grade.
    from dynamic import sky
    from dynamic.animate import write_mp4
    tmp = Path(tempfile.mkdtemp(dir=WORK))
    try:
        clear, mask, fl = tmp / "clear.png", tmp / "mask.png", tmp / "float.png"
        g.create_image(layers, str(clear), mask_path=str(mask), float_mask_path=str(fl))
        base = Image.open(clear).convert("RGBA")
        protect = Image.open(mask).convert("L")
        afloat = Image.open(fl).convert("L") if fl.exists() else None
        still = sky.apply_sky(base, protect, "day", wx, seed=t["token"], t=0.0, afloat=afloat)
        still.convert("RGB").save(path, compress_level=6)
        cc.add_plaque(path)
        if anim_dir is not None:
            n = cc.WEATHER_SIZE
            sm = base.resize((n, n), Image.Resampling.LANCZOS)
            mk = protect.resize((n, n), Image.Resampling.LANCZOS)
            fk = afloat.resize((n, n), Image.Resampling.LANCZOS) if afloat else None
            static = sky.grade_static(sm, "day", wx)
            frames = [sky.frame(static, mk, t=i / cc.WEATHER_FRAMES, seed=t["token"], afloat=fk)
                      for i in range(cc.WEATHER_FRAMES)]
            if write_mp4(frames, os.path.join(anim_dir, f"{tid}.mp4"),
                         1000.0 / cc.WEATHER_MS) is None:
                sys.exit("no ffmpeg -- pip install imageio-ffmpeg")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _render_job(job):
    t, path, anim_dir = job
    g = cc.setup()
    if str(cc.REPO_ROOT / "dynamic") not in sys.path:
        sys.path.insert(0, str(cc.REPO_ROOT / "dynamic"))
    if t.get("secret"):
        render_secret(g, t["secret"], path, anim_dir, f"{t['token']:03d}")
    else:
        render_full(g, t, path, anim_dir)
    return path


def cmd_render(args):
    g = cc.setup()
    plan = load_plan(g)
    out = Path(args.out).resolve()
    images, metadata, anims = out / "images", out / "metadata", out / "animations"
    for d in (images, metadata, anims):
        if d.exists():
            for f in d.iterdir():
                f.unlink()
    for d in (images, metadata):
        d.mkdir(parents=True, exist_ok=True)
    if any(is_animated(t) for t in plan["tokens"]):
        anims.mkdir(exist_ok=True)
    elif anims.exists():
        anims.rmdir()
    jobs = [(t, str(images / f"{t['token']:03d}.png"), anims) for t in plan["tokens"]]
    with get_context("fork").Pool(args.workers) as p:
        for k, _ in enumerate(p.imap_unordered(_render_job, jobs), 1):
            if k % 25 == 0 or k == len(jobs):
                print(f"rendered {k}/{len(jobs)}", flush=True)
    for t in plan["tokens"]:
        (metadata / f"{t['token']:03d}.json").write_text(
            json.dumps(token_json(g, t, plan["seed"]), indent=2, ensure_ascii=False) + "\n")
    write_readme(g, plan, out)
    print(f"wrote {len(plan['tokens'])} images + metadata + README -> {out}")


REBUILD_SECTION = """## Rebuilding the collection

Everything the build needs is in this repository:

| Path | What it is |
| --- | --- |
| `scripts/` | the build scripts |
| `assets/` | the edition's plates, stickers (+ sources), re-cut footwear, two held items and plaque |
| `compositor/` | the Sweetardio compositor and figure art it draws from (vendored; see its README) |
| `plan.json` | the curated 444: every token's exact layer stack, traits and rarity |

Requirements: Python 3.10+ and `pip install -r requirements.txt` (Pillow,
NumPy, SciPy). About 2 GB of free disk for the output.

```bash
python3 scripts/build_cookie_chain.py render   --out .   # rewrites images/ + metadata/ + this README (~5 min on 4 cores)
python3 scripts/build_cookie_chain.py validate --out .   # checks pairing, counts, uniqueness, name bytes
```

`render` reads only `plan.json`, so it reproduces this exact collection.
`--workers N` sets the number of parallel renders (default 4).

Optional steps:

```bash
python3 scripts/build_cookie_chain.py sheet            # the 50-token preview sheet -> work/approval_sheet_50.jpg
python3 scripts/prepare_assets.py --sheet work/s.png   # rebuild the 22 stickers + plaque from assets/sticker_sources
python3 scripts/prepare_footwear.py --sheet work/f.jpg # re-cut the footwear outlines from compositor/traits
python3 scripts/build_cookie_chain.py plan             # re-curate from scratch: new pool, scores, selection (~1.5 h)
python3 scripts/build_cookie_chain.py plan --extend 1100   # add candidates aimed at the best pairings, re-select
```

Re-running `plan` writes a NEW `plan.json` — a different 444. Commit it only
if that is the intent.
"""


def write_readme(g, plan, out):
    """The edition repo's README, with every count read from the output."""
    counts = defaultdict(Counter)
    for t in plan["tokens"]:
        for a in attributes(g, t):
            counts[a["trait_type"]][a["value"]] += 1
    one = sorted((t["token"], cc.SECRET_RARES[t["secret"]] + " (animated)"
                  if t["secret"] in cc.ANIMATED_SECRET_RARES else cc.SECRET_RARES[t["secret"]])
                 if t.get("secret") else (t["token"], cc.BACKGROUND_NAMES[t["traits"]["background"]])
                 for t in plan["tokens"]
                 if t.get("secret") or t["traits"]["background"] in cc.ONE_OF_ONE_BACKGROUNDS)
    animated = [t["token"] for t in plan["tokens"] if t.get("secret") in cc.ANIMATED_SECRET_RARES]
    looping = [t for t in plan["tokens"] if is_animated(t)]

    def table(trait):
        rows = sorted(counts[trait].items(), key=lambda kv: (-kv[1], kv[0]))
        return "\n".join(f"| {k} | {n} |" for k, n in rows)

    n_arm, n_wat = sum(counts["Arms"].values()), sum(counts["Footwear"].values())
    text = f"""# Cookie Chain Edition — {cc.SUPPLY} Tokens

This repository holds the finished collection: {cc.SUPPLY} images and their {cc.SUPPLY} matching
metadata files.

| Folder | Contents |
| --- | --- |
| `images/` | `001.png` … `{cc.SUPPLY}.png` — 1393×1393 PNG |
| `metadata/` | `001.json` … `{cc.SUPPLY}.json` — one per image |{f"""
| `animations/` | one H.264 `.mp4` loop per animated token ({len(looping)}): the animated 1/1, every Starfield token and every Weather token; its metadata's `animation_url` points at it |""" if looping else ""}

The numbers pair up: `metadata/007.json` describes `images/007.png`.

Everything needed to rebuild it is in this repository too — see
[Rebuilding the collection](#rebuilding-the-collection). `plan.json` records
the exact layer stack of every token.

## How to download

### Option 1 — Download everything as a ZIP (no tools needed)

1. Click the green **Code** button at the top of this page.
2. Choose **Download ZIP**.
3. Unzip the file. You'll get the `images` and `metadata` folders inside.

### Option 2 — Clone with git (skips old history)

```bash
git clone --depth 1 https://github.com/iamabotama/sweetardio-cookie-chain-edition.git
```

### Option 3 — Grab a single token

Open `images/` or `metadata/` above, click the file you want, then use the
download button on the file page.

## What a metadata file looks like

```json
{json.dumps(token_json(g, next(t for t in plan["tokens"] if not t.get("secret")), plan["seed"]), indent=2, ensure_ascii=False)}
```

The `image` path is relative, so it resolves as long as `images/` and
`metadata/` sit side by side.

`Footwear` and `Arms` are optional and appear only on the tokens that have them
({n_wat} and {n_arm} tokens). Every other trait type is on every composited
token.{"".join(f""" Token #{n:03d} is the animated 1/1: finished artwork rather than a
composited character, so it carries `1/1`, `Edition` and `Rarity` only, plus an
`animation_url` pointing at `animations/{n:03d}.mp4`.""" for n in animated)}

## What's in the collection

{len(counts["Character"])} characters, {len(counts["Background"])} backgrounds,
{len(counts["Sticker"])} stickers, {len(counts["Skin"])} skins, {len(counts["Eyes"])} eyes,
{len(counts["Mouth"])} mouths, {len(counts["Footwear"])} footwear traits and
{len(counts["Arms"])} arm traits. Every token is a unique combination.

**Rarity tiers**

| Tier | Count |
| --- | --- |
{chr(10).join(f"| {tier} | {counts['Rarity'][tier]} |" for tier, _ in (RARITY_TIERS or []))}

**{RARITY_TIERS[0][0] if RARITY_TIERS else "The 1/1s"}** {"is" if RARITY_TIERS else "are"} exactly the {len(one)} one-of-one tokens:
{", ".join(f"{name} (#{n:03d})" for n, name in one)}. Every other tier is
ranked by {"the build's visual score" if METHOD == "looks" else "statistical rarity (the sum of each trait's -ln(share)), so the label agrees with what a trait-frequency ranking would say"}.

{f"""**Weather** ({sum(counts["Weather"].values())} tokens) — a still showing the weather, plus a loop

| Weather | Tokens |
| --- | --- |
{table("Weather")}

""" if counts["Weather"] else ""}**Arms** ({n_arm} tokens)

| Arm | Tokens |
| --- | --- |
{table("Arms")}

**Footwear** ({n_wat} tokens)

| Footwear | Tokens |
| --- | --- |
{table("Footwear")}

**Backgrounds**

| Background | Tokens |
| --- | --- |
{table("Background")}

**Characters**

| Character | Tokens |
| --- | --- |
{table("Character")}

**Stickers** — one on every token

| Sticker | Tokens |
| --- | --- |
{table("Sticker")}

{REBUILD_SECTION}"""
    (out / "README.md").write_text(text)


def cmd_validate(args):
    """The finished output, checked against the plan and the edition rules."""
    g = cc.setup()
    plan = load_plan(g)
    q = design_from_json(plan["design"])["q"] if "design" in plan else quotas(g)
    out = Path(args.out).resolve()
    errors = []
    imgs = sorted(p.name for p in (out / "images").glob("*"))
    metas = sorted(p.name for p in (out / "metadata").glob("*"))
    want = [f"{i:03d}" for i in range(1, cc.SUPPLY + 1)]
    if imgs != [w + ".png" for w in want]:
        errors.append(f"images/ holds {len(imgs)} files, not 001..{cc.SUPPLY}.png")
    if metas != [w + ".json" for w in want]:
        errors.append(f"metadata/ holds {len(metas)} files, not 001..{cc.SUPPLY}.json")
    seen = set()
    counts = defaultdict(Counter)
    by_token = {t["token"]: t for t in plan["tokens"]}
    for w in want:
        mp, ip = out / "metadata" / f"{w}.json", out / "images" / f"{w}.png"
        if not mp.exists() or not ip.exists():
            continue
        m = json.loads(mp.read_text())
        if m["image"] != f"../images/{w}.png":
            errors.append(f"{w}: image field {m['image']!r}")
        if len(m["name"].encode()) > 32:
            errors.append(f"{w}: name {m['name']!r} is over 32 bytes")
        with Image.open(ip) as im:
            if im.size != (1393, 1393):
                errors.append(f"{w}: image is {im.size}")
        t = by_token[int(w)]
        if is_animated(t):
            if m.get("animation_url") != f"../animations/{w}.mp4" or \
                    not (out / "animations" / f"{w}.mp4").exists():
                errors.append(f"{w}: an animated token has no loop at animations/{w}.mp4")
        elif "animation_url" in m:
            errors.append(f"{w}: animation_url on a still token")
        attrs = {a["trait_type"]: a["value"] for a in m["attributes"]}
        sig = tuple(sorted((k, v) for k, v in attrs.items() if k not in ("Rarity", "Edition")))
        if sig in seen:
            errors.append(f"{w}: duplicate trait combination")
        seen.add(sig)
        for k, v in attrs.items():
            counts[k][v] += 1
        if attrs.get("Rarity") != t["rarity"]:
            errors.append(f"{w}: Rarity {attrs.get('Rarity')} != plan {t['rarity']}")
    tiers = dict(RARITY_TIERS or [])
    if dict(counts["Rarity"]) != tiers:
        errors.append(f"rarity tiers {dict(counts['Rarity'])} != {tiers}")
    names = {"Background": {cc.BACKGROUND_NAMES[k]: n for k, n in q["background"].items()},
             "Sticker": {cc.STICKER_NAMES[k]: n for k, n in q["sticker"].items()}}
    for trait, expect in names.items():
        if dict(counts[trait]) != expect:
            errors.append(f"{trait} counts differ from the design")
    for trait, key in (("Arms", "arm"), ("Footwear", "footwear"), ("Weather", "weather")):
        want = sum(n for v, n in q.get(key, {}).items() if v)
        if sum(counts[trait].values()) != want:
            errors.append(f"{sum(counts[trait].values())} tokens with {trait}, expected {want}")
    for bg in cc.ONE_OF_ONE_BACKGROUNDS:
        n = counts["Background"][cc.BACKGROUND_NAMES[bg]]
        if n != 1:
            errors.append(f"{bg}: {n} tokens, expected exactly 1")
    for e in errors:
        print("FAIL", e)
    print(f"{'FAILED' if errors else 'OK'}: {len(metas)} metadata, {len(imgs)} images, "
          f"{len(seen)} unique combinations")
    return 1 if errors else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--pool", type=int, default=1600)
    p.add_argument("--seed", type=int, default=871004)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--reuse", action="store_true",
                   help="re-select from work/pool.json without re-rendering")
    p.add_argument("--extend", type=int, default=0,
                   help="add N candidates targeted at the best pairings, then select")
    p.add_argument("--board", help="the Rarity Board's exported choices "
                                   "(board.py merge); default: the constants above")
    s = sub.add_parser("sheet")
    s.add_argument("--count", type=int, default=50)
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--sheet-out")
    r = sub.add_parser("render")
    r.add_argument("--out", required=True)
    r.add_argument("--workers", type=int, default=4)
    v = sub.add_parser("validate")
    v.add_argument("--out", required=True)
    args = ap.parse_args()
    sys.exit({"plan": cmd_plan, "sheet": cmd_sheet, "render": cmd_render,
              "validate": cmd_validate}[args.cmd](args) or 0)


if __name__ == "__main__":
    main()
