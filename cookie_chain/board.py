"""The Rarity Board: the owner's and co-creator's decisions, as build input.

The board is a shared claude.ai page with one document per section in its
`cfg` collection (backgrounds, ladder, label, traits_<section>). A section
nobody has touched has no document and keeps `board_defaults.json`. Export the
collection to a folder of JSON files, fold it into one file with

    python3 cookie_chain/board.py merge <export dir> cookie_chain/board.json

and `build_cookie_chain.py plan --board cookie_chain/board.json` builds from it.

The board names things the way people do (`Side_Eye`, `Pepe_Slippers`,
`Blue_Saber`); this module maps every key onto the compositor's own filename,
and refuses an unknown key instead of quietly dropping it. Background counts
are computed exactly as the page computes them, so the number the board shows
under a plate is the number that ships.
"""

import json
import sys
from pathlib import Path

BOARD_DIR = Path(__file__).resolve().parent
DEFAULTS = BOARD_DIR / "board_defaults.json"
SUPPLY = 444
TIERS = ("one", "legendary", "rare", "uncommon", "common")

# board key -> the compositor's own key, for every section whose files the
# main collection still names by their authoring history
EYES = {
    "Alien": "layer-Sweetardio_nft (15).png", "Beady": "layer-art_mattrick_011.png",
    "Blue": "Blue.png", "Cerise": "Cerise.png",
    "Clueless": "layer-file_0000000062b071f8b3d115704b04609c (1).png",
    "Cyan": "layer-Eyes_Cyan (1).png",
    "Cyborg": "layer-file_000000001e1c71fd9d410745ea63114e (1).png",
    "Googly": "layer-Eyes_Googly (1).png", "Side_Eye": "layer-Eyes_Side_Eye (1).png",
    "Smug": "layer-file_00000000a21871f894573a9d4ee67519 (2).png",
}
MOUTHS = {
    "Awkward_Smile": "Awkward_smile.png", "Diamond_Grill": "layer-Mouth_Diamond_Grill (1).png",
    "Fang": "layer-Mouth_Fang (1).png", "Flat": "layer-Mouth_Flat (1).png",
    "Lollipop": "layer-Mouth_Lollipop (1).png", "Sad": "layer-layer-layer-Mouth_Sad (1).png",
    "Smirk": "layer-Mouth_Smirk (1).png", "Smoke": "layer-Mouth_Smoke (1).png",
    "Tasty": "layer-Mouth_Tasty-1.png",
}
FOOTWEAR = {
    "Bunny_Slippers": "layer-Bunny_Slippers", "Cookie_Monster_Slippers": "Cookie_Monster_Slippers",
    "Gorbhouse": "gorbhouse", "Pepe_Slippers": "layer-Pepe", "Shiba_Slippers": "layer-Shiba",
}
ARMS = {
    "Cookboy_Handheld": "Cookboy_Handheld.png", "Printer": "Printer.png",
    "Cash": "Arms_Cash.png", "Katana": "Armz_Katana.png", "Knives": "Armz_Knives.png",
    "Blue_Saber": "Sweetardio_114 (4).png", "Pink_Saber": "Sweetardio_114 (5).png",
    "Cyan_Saber": "Sweetardio_114 (6).png", "Dual_Uzis": "Sweetardio_115 (11).png",
    "AK15": "layer-layer-layer-layer-AK15.png", "AR47": "layer-layer-layer-layer-AR47.png",
    "Military_Brat": "layer-layer-layer-layer-Military_Brat.png",
    "Nerf_Blaster": "layer-layer-layer-layer-Nerf_Blaster.png",
}
SKINS = {"Alien": "Alien", "Black": "Black", "White": "White"}
WEATHER = {w: w for w in ("rain", "snow", "fog", "storm", "blizzard", "flooded", "tornado")}


def load(path=None):
    """The page's starting state with an exported board laid over it."""
    board = json.loads(DEFAULTS.read_text())
    if path:
        for doc, body in json.loads(Path(path).read_text()).items():
            if doc not in board:
                continue
            for key, value in body.items():
                if key in ("by", "at"):
                    continue
                if key == "items":
                    for item, v in value.items():
                        cur = board[doc]["items"].get(item)
                        if isinstance(v, dict) and isinstance(cur, dict):
                            cur.update(v)
                        else:
                            board[doc]["items"][item] = v
                else:
                    board[doc][key] = value
    return board


def backgrounds(board):
    """({plate file: count}, {plate file: tier}, {plate file: public name}),
    for kept plates only. Exactly the page's ladderPlan(): plates in the
    page's order, Common plates splitting the remainder, the first ones
    taking any odd token."""
    order = json.loads((BOARD_DIR / "plate_order.json").read_text())
    items, ladder = board["backgrounds"]["items"], board["ladder"]
    kept = [f for f in order if items[f[:-4]]["keep"]]
    by = {t: [f for f in kept if items[f[:-4]].get("tier", "common") == t] for t in TIERS}
    per = {"one": 1, "legendary": int(ladder["legendary"]), "rare": int(ladder["rare"]),
           "uncommon": int(ladder["uncommon"])}
    counts = {f: per[t] for t in ("one", "legendary", "rare", "uncommon") for f in by[t]}
    rem, commons = SUPPLY - sum(counts.values()), by["common"]
    if rem < 0 or (rem and not commons) or (commons and rem < len(commons)):
        raise SystemExit(f"board: the background ladder does not fit {SUPPLY} "
                         f"({rem} tokens left for {len(commons)} Common plates)")
    base, extra = divmod(rem, len(commons)) if commons else (0, 0)
    for i, f in enumerate(commons):
        counts[f] = base + (1 if i < extra else 0)
    tiers = {f: items[f[:-4]].get("tier", "common") for f in kept}
    names = {f: items[f[:-4]]["name"] for f in kept}
    return counts, tiers, names


def _section(board, name, mapping=None, required=True):
    items = {k: int(v) for k, v in board["traits_" + name]["items"].items() if int(v) > 0}
    if mapping is not None:
        unknown = sorted(set(items) - set(mapping))
        if unknown:
            raise SystemExit(f"board: unknown {name}: {', '.join(unknown)}")
        items = {mapping[k]: v for k, v in items.items()}
    total = sum(items.values())
    if required and total != SUPPLY:
        raise SystemExit(f"board: {name} add up to {total}, not {SUPPLY}")
    if not required and total > SUPPLY:
        raise SystemExit(f"board: {name} assign {total}, more than {SUPPLY}")
    return items


def quotas(board, characters):
    """Every exact count the selector meets, keyed the way the plan is."""
    counts, _, _ = backgrounds(board)
    q_char = _section(board, "characters")
    unknown = sorted(set(q_char) - set(characters))
    if unknown:
        raise SystemExit(f"board: unknown characters: {', '.join(unknown)}")
    q_arm = _section(board, "arms", ARMS, required=False)
    q_wat = _section(board, "footwear", FOOTWEAR, required=False)
    q_wx = _section(board, "weather", WEATHER, required=False) if "traits_weather" in board else {}
    q_arm[None] = SUPPLY - sum(q_arm.values())
    q_wat[None] = SUPPLY - sum(q_wat.values())
    q_wx[None] = SUPPLY - sum(q_wx.values())
    return dict(character=q_char, background=counts,
                sticker={f"{k}.png": v for k, v in _section(board, "stickers").items()},
                arm=q_arm, footwear=q_wat, weather=q_wx,
                eyes=_section(board, "eyes", EYES), mouth=_section(board, "mouths", MOUTHS),
                skin=_section(board, "skins", SKINS))


def rarity_tiers(board, ones):
    """[(name, count)]: the first tier is exactly the 1-of-1 tokens, the last
    takes whatever the middle tiers leave."""
    label = board["label"]
    if label["method"] == "none":
        return None, "none"
    tiers = label["tiers"]
    middle = [(t["name"], int(t["count"])) for t in tiers[1:-1]]
    last = SUPPLY - ones - sum(n for _, n in middle)
    if last < 0:
        raise SystemExit(f"board: the Rarity tiers need {-last} more tokens than exist")
    return [(tiers[0]["name"], ones)] + middle + [(tiers[-1]["name"], last)], label["method"]


def merge(src, dst):
    """Fold an export of the board's cfg collection into one JSON file."""
    out = {}
    for p in sorted(Path(src).rglob("*.json")):
        body = json.loads(p.read_text())
        out[body.get("id", p.stem)] = {k: v for k, v in body.get("data", body).items()
                                       if k not in ("by", "at")}
    Path(dst).write_text(json.dumps(out, indent=1) + "\n")
    print(f"{len(out)} board sections -> {dst}: {', '.join(sorted(out)) or 'none'}")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "merge":
        merge(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
