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
import cc_common as cc  # noqa: E402

PLAN = cc.CC_ROOT / "plan.json"
WORK = cc.CC_ROOT / "build"

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
PAIR_CAP = 2         # at most this many tokens share a character x plate


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
        elif folder == g.WHAT_ARE_THOSEZ and "_base" in f.lower():
            d["footwear"] = ("gorbhouse" if "gorbhouse" in f.lower()
                             else f.split("_Base")[0].split("_base")[0]
                             .replace(" (1)", ""))
    return d


def signature(d):
    return tuple(d.get(k) for k in ("character", "background", "skin", "eyes",
                                    "mouth", "footwear", "arm", "sticker"))


def make_pool(g, q, size, seed):
    rng = random.Random(seed)
    chars, cw = zip(*q["character"].items())
    regular = {p: n for p, n in q["background"].items()
               if p not in cc.ONE_OF_ONE_BACKGROUNDS}
    plates, pw = zip(*regular.items())
    arms = {a: n for a, n in q["arm"].items() if a}
    regular_wat = {w: n for w, n in q["footwear"].items() if w and w != "gorbhouse"}
    stickers = [s for s in q["sticker"] if s != NIGHTLY_STICKER] + [NIGHTLY_STICKER]
    pool, seen = [], set()

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
    # the one-of-one plates: a handful of candidates each, Nightly paired
    # with its own wallet sticker as in the previous release
    for plate in cc.ONE_OF_ONE_BACKGROUNDS:
        made = 0
        while made < 10:
            i += 1
            st = NIGHTLY_STICKER if plate == "Legendary_Nightly.png" else \
                rng.choice(stickers[:-1])
            made += add(i, force_bg=(g.BACKGROUNDZ, plate), force_char=rng.choices(chars, cw)[0],
                        force_arm=None, force_wat=None, force_sticker=st)
    while len(pool) < size:
        i += 1
        char = rng.choices(chars, cw)[0]
        plate = rng.choices(plates, pw)[0]
        arm = None
        if rng.random() < 0.45:
            arm = rng.choices(list(arms), list(arms.values()))[0]
            if not g.armz_allowed(arm, char):
                arm = None
        wat = None
        if not g.is_wat_excluded(char) and rng.random() < 0.6:
            opts = dict(regular_wat)
            if g.gets_gorbhouse_overlay(char):
                opts["gorbhouse"] = q["footwear"]["gorbhouse"] * 2.5
            wat = rng.choices(list(opts), list(opts.values()))[0]
        add(i, force_bg=(g.BACKGROUNDZ, plate), force_char=char, force_arm=arm,
            force_wat=wat, force_sticker=stickers[i % len(stickers)])
    for c in pool:
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
    """Max total score, exact counts, via a 0/1 MILP (HiGHS)."""
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
        group(key, exact=False, tol=SOFT_TOL if key != "skin" else 0.15)
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
    rows.append(list(range(n))); lo.append(cc.SUPPLY); hi.append(cc.SUPPLY)

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
    assert len(chosen) == cc.SUPPLY
    return chosen, res


def assign_rarity(chosen):
    keys = ("character", "background", "skin", "eyes", "mouth", "footwear", "arm", "sticker")
    counts = {k: Counter(c["traits"].get(k) for c in chosen) for k in keys}
    for c in chosen:
        c["rarity_score"] = round(sum(-math.log(counts[k][c["traits"].get(k)] / len(chosen))
                                      for k in keys), 5)
    ranked = sorted(chosen, key=lambda c: (
        c["traits"]["background"] not in cc.ONE_OF_ONE_BACKGROUNDS,
        -c["rarity_score"], -c["score"]))
    assert sum(n for _, n in RARITY_TIERS) == len(chosen)
    assert RARITY_TIERS[0][1] == len(cc.ONE_OF_ONE_BACKGROUNDS)
    pos = 0
    for tier, n in RARITY_TIERS:
        for c in ranked[pos:pos + n]:
            c["rarity"] = tier
        pos += n


# ---- metadata -------------------------------------------------------------------------

def attributes(g, cand):
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
        attrs.append({"trait_type": "Footwear", "value": g.trait_name(g.WHAT_ARE_THOSEZ, key)})
    if t["arm"]:
        attrs.append({"trait_type": "Arms",
                      "value": cc.ARM_NAMES.get(t["arm"]) or g.trait_name(g.ARMZ, t["arm"])})
    attrs.append({"trait_type": "Sticker", "value": cc.STICKER_NAMES[t["sticker"]]})
    attrs.append({"trait_type": "Edition", "value": cc.EDITION})
    attrs.append({"trait_type": "Rarity", "value": cand["rarity"]})
    return attrs


def token_json(g, cand, seed):
    n = cand["token"]
    return {"name": f"{cc.EDITION} #{n:03d}",
            "description": f"One of {cc.SUPPLY} {cc.EDITION} collectibles.",
            "image": f"../images/{n:03d}.png",
            "attributes": attributes(g, cand),
            "selection_score": cand["score"],
            "seed": seed}


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
    """Plan paths relative to the repo, so the plan is not tied to a checkout."""
    out = []
    for li in layers:
        li = _jsonable(dict(li))
        p = Path(os.path.realpath(li["path"])) if os.path.islink(li["path"]) else Path(li["path"])
        if not p.is_absolute():
            p = cc.REPO_ROOT / p
        li["path"] = os.path.relpath(p, cc.REPO_ROOT)
        for k in ("gcenter", "ccenter", "fcenter", "acenter"):
            if k in li:
                li[k] = list(li[k])
        out.append(li)
    return out


def _resolve(g, layers):
    out = []
    for li in layers:
        li = dict(li)
        p = cc.REPO_ROOT / li["path"]
        if str(p).startswith(str(cc.REPO_ROOT / "traits" / "armz")) or \
                str(p).startswith(str(cc.CC_ARMS)):
            p = Path(g.ARMZ) / p.name          # arms are read through the stage
        li["path"] = str(p)
        for k in ("gcenter", "ccenter", "fcenter", "acenter"):
            if k in li:
                li[k] = tuple(li[k])
        out.append(li)
    return out


def cmd_plan(args):
    g = cc.setup()
    q = quotas(g)
    WORK.mkdir(exist_ok=True)
    thumbs = WORK / "thumbs"
    if args.reuse:
        # re-select from the scored pool without re-rendering it
        pool = json.loads((WORK / "pool.json").read_text())
        for c in pool:
            c["layers"] = _resolve(g, c["layers"])
    else:
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
    assign_rarity(chosen)
    rng = random.Random(args.seed)
    rng.shuffle(chosen)                      # numbering cannot be read for rarity
    for n, c in enumerate(chosen, 1):
        c["token"] = n
    plan = {"edition": cc.EDITION, "supply": cc.SUPPLY, "seed": args.seed,
            "pool": len(pool), "objective": round(-res.fun, 3),
            "figure_scale": cc.FIGURE_SCALE, "big_body_scale": cc.BIG_BODY_SCALE,
            "tokens": [{"token": c["token"], "pool_id": c["id"], "traits": c["traits"],
                        "rarity": c["rarity"], "rarity_score": c["rarity_score"],
                        "score": c["score"],
                        "metrics": {k: c[k] for k in ("edge_p20", "edge_mean", "face",
                                                      "busy", "ov_sticker", "ov_plaque")},
                        "layers": _portable(c["layers"])} for c in chosen]}
    PLAN.write_text(json.dumps(plan, indent=1) + "\n")
    sel = np.array([c["score"] for c in chosen])
    allsc = np.array([c["score"] for c in pool])
    print(f"selected {len(chosen)} of {len(pool)}: mean score {sel.mean():.3f} "
          f"(pool {allsc.mean():.3f}), min {sel.min():.3f}")
    print(f"plan -> {PLAN.relative_to(cc.REPO_ROOT)}")


def load_plan(g):
    plan = json.loads(PLAN.read_text())
    for t in plan["tokens"]:
        t["layers"] = _resolve(g, t["layers"])
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
    want_tier = {"Mythic Chase": 5, "Legendary Chase": 4, "Rare": 9, "Uncommon": 14}
    for _ in range(count):
        def gain(t):
            g_ = sum(t["traits"].get(k) not in covered[k] for k in keys)
            g_ += 1.5 * (t["traits"].get("arm") is not None and t["traits"]["arm"] not in covered["arm"])
            g_ += 2 * (tiers[t["rarity"]] < want_tier.get(t["rarity"], 0))
            return g_ + 0.2 * t["score"]
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
    jobs = [(t["layers"], str(out_dir / f"{t['token']:03d}.png")) for t in picked]
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
               f"#{t['token']:03d}  {attrs['Character']}  ·  {t['rarity']}",
               font=f1, fill=(240, 240, 244))
        extra = [attrs["Background"]] + [attrs[k] for k in ("Arms", "Footwear") if k in attrs]
        d.text((x + 10, y + cell + 36), "  ·  ".join(extra)[:62], font=f2, fill=(170, 170, 182))
    path = Path(args.sheet_out) if args.sheet_out else WORK / "approval_sheet_50.jpg"
    sheet.save(path, quality=92)
    (WORK / "approval_sheet_50.json").write_text(json.dumps([t["token"] for t in picked]) + "\n")
    print(f"sheet -> {path}")


def _render_job(job):
    layers, path = job
    g = cc.setup()
    render_token(g, layers, path)
    return path


def cmd_render(args):
    g = cc.setup()
    plan = load_plan(g)
    out = Path(args.out).resolve()
    images, metadata = out / "images", out / "metadata"
    for d in (images, metadata):
        if d.exists():
            for f in d.iterdir():
                f.unlink()
        d.mkdir(parents=True, exist_ok=True)
    jobs = [(t["layers"], str(images / f"{t['token']:03d}.png")) for t in plan["tokens"]]
    with get_context("fork").Pool(args.workers) as p:
        for k, _ in enumerate(p.imap_unordered(_render_job, jobs), 1):
            if k % 25 == 0 or k == len(jobs):
                print(f"rendered {k}/{len(jobs)}", flush=True)
    for t in plan["tokens"]:
        (metadata / f"{t['token']:03d}.json").write_text(
            json.dumps(token_json(g, t, plan["seed"]), indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(plan['tokens'])} images + metadata -> {out}")


def cmd_validate(args):
    """The finished output, checked against the plan and the edition rules."""
    g = cc.setup()
    plan = json.loads(PLAN.read_text())
    q = quotas(g)
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
        attrs = {a["trait_type"]: a["value"] for a in m["attributes"]}
        sig = tuple(sorted((k, v) for k, v in attrs.items() if k not in ("Rarity", "Edition")))
        if sig in seen:
            errors.append(f"{w}: duplicate trait combination")
        seen.add(sig)
        for k, v in attrs.items():
            counts[k][v] += 1
        t = by_token[int(w)]
        if attrs.get("Rarity") != t["rarity"]:
            errors.append(f"{w}: Rarity {attrs.get('Rarity')} != plan {t['rarity']}")
    tiers = dict(RARITY_TIERS)
    if dict(counts["Rarity"]) != tiers:
        errors.append(f"rarity tiers {dict(counts['Rarity'])} != {tiers}")
    names = {"Background": {cc.BACKGROUND_NAMES[k]: n for k, n in q["background"].items()},
             "Sticker": {cc.STICKER_NAMES[k]: n for k, n in q["sticker"].items()}}
    for trait, expect in names.items():
        if dict(counts[trait]) != expect:
            errors.append(f"{trait} counts differ from the design")
    if sum(counts["Arms"].values()) != sum(ARM_COUNTS.values()):
        errors.append(f"{sum(counts['Arms'].values())} armed tokens, expected {sum(ARM_COUNTS.values())}")
    if sum(counts["Footwear"].values()) != sum(WAT_COUNTS.values()):
        errors.append(f"{sum(counts['Footwear'].values())} shod tokens, expected {sum(WAT_COUNTS.values())}")
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
                   help="re-select from build/pool.json without re-rendering")
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
