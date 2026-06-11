#!/usr/bin/env python3
"""Render 10 curated high-separation showcase combinations.

Plates come from the graded set (traits/backgroundz_pop). Layer semantics
follow generator.py exactly: background -> footwear base -> character ->
footwear overlay -> skin -> eyes -> mouth -> arms -> gorbhouse -> sticker ->
paired background overlay last. Offsets follow the generator rules
(footwear or cone-style characters are never offset).

Pairings were chosen from the Phase 1/2 measurements: each plate sits
opposite its character in temperature and well below it in saturation, and
the cast covers dark/bright/warm/cool/dual-tone bodies.

Usage: python3 background_pop_studies/make_showcase.py
Output: background_pop_studies/showcase/*.png + showcase_sheet.png
"""

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, ".")
from generator import create_image

BG = "traits/backgroundz_pop"
CH = "traits/characterz"
WAT = "traits/what_are_thosez"
SK = "traits/skinz"
EY = "traits/eyez"
MO = "traits/mouthz"
AR = "traits/armz"
ST = "traits/stickerz"
OUT = "background_pop_studies/showcase"

WHITE = f"{SK}/layer-layer-layer-Skin_White (2).png"
BLACK = f"{SK}/layer-Skin_Black (3).png"
GOLD = f"{SK}/layer-Skin_Gold_Foil (1).png"
CYANSKIN = f"{SK}/layer-Skin_Fluorescent_Cyan (2).png"
SHY = f"{AR}/layer-layer-layer-layer-Shy-1.png"
NERF = f"{AR}/layer-layer-layer-layer-Nerf_Blaster.png"
AK = f"{AR}/layer-layer-layer-layer-AK15.png"

BUNNY = ("layer-Bunny_Slippers_Base (1).png",
         ["layer-Bunny_Slippers_Overlay (1).png"])
PEPE = ("layer-Pepe_Base (1).png", ["layer-Pepe_Overlay (1).png"])
SHIBA = ("layer-Shiba_Base (1).png", ["layer-Shiba_Overlay_Left (1).png",
                                      "layer-Shiba_Overlay_Right (1).png"])

# (name, plate, character, footwear, skin, eyes, mouth, arms, sticker,
#  offset, extras)
COMBOS = [
    ("01_glazed_on_tootsie_navy", "Sweetardio_11327.png",
     "after_skinz_glazed_doughnut.png", BUNNY, WHITE,
     "layer-Eyes_Googly (1).png", "Awkward_smile.png", SHY, None, False, []),
    ("02_cyan_sherbert_in_bakery", "Sweetardio_11325.png",
     "before_skinz_cyan_sherbert_ice_cream.png", None, WHITE,
     "Cerise.png", "layer-Mouth_Tasty-1.png", SHY, None, False, []),
    ("03_brownie_on_spotlight_stage", "Sweetardio_115 (1).png",
     "after_skinz_brownie_bite.png", SHIBA, GOLD,
     "layer-Eyes_Cyan (1).png", "layer-Mouth_Blunt (1).png", SHY,
     "07_Rare_Candy.png", False, []),
    ("04_pink_sherbert_at_castle", "Sweetardio_114 (15).png",
     "before_skinz_pink_sherbert_ice_cream.png", None, WHITE,
     "layer-Eyes_Cyan (1).png", "layer-Mouth_Lollipop (1).png", SHY,
     None, False, []),
    ("05_twinkie_gorbhouse_waffle", "Sweetardio_114 (10).png",
     "Twinkie.png", None, BLACK,
     "layer-Eyes_Side_Eye (1).png", "layer-Mouth_Flat (1).png", SHY,
     "25_Zombieland_Twinkie.png", False,
     [f"{WAT}/Gorbhouse_overlay.png"]),
    ("06_marshmallow_gum_corridor",
     "file_000000002bb471fdac3ce6f00e2304bd.png",
     "after_skinz_marshmallow.png", PEPE, WHITE,
     "Blue.png", "layer-Mouth_Fang (1).png", NERF, None, False, []),
    ("07_cookie_whitehouse_lawn", "Sweetardio_11314.png",
     "after_skinz_chocolate_chip_cookie.png", BUNNY, WHITE,
     "Blue.png", "Awkward_smile.png", SHY, None, False,
     [f"{BG}/Whitehouse_Lawn_Overlay.png"]),
    ("08_zaffre_sherbert_canyon", "Sweetardio_114 (18).png",
     "before_skinz_zaffre_sherbert_ice_cream.png", None, WHITE,
     "layer-Eyes_Googly (1).png", "layer-Mouth_Tasty-1.png", SHY,
     None, False, []),
    ("09_churro_liberty_coin", "Sweetardio_114 (29).png",
     "layer-after_skinz_churro (1) (1).png", None, CYANSKIN,
     "layer-Eyes_Lowkey (1).png", "layer-Mouth_Blunt (1).png", AK,
     "24_Golden_Ticket.png", False, []),
    ("10_gummy_worm_money_bed",
     "file_00000000c78071f8bca305176ffecb04.png",
     "layer-after_skinz_gummy_worm (1).png", None, WHITE,
     "Cerise.png", "layer-layer-layer-Mouth_Sad (1).png", SHY,
     "22_Sweet_Tooth.png", True, []),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    outs = []
    for (name, plate, char, foot, skin, eyes, mouth, arms, sticker,
         offset, extras) in COMBOS:
        layers = [{"path": f"{BG}/{plate}", "offset": False}]
        if foot:
            layers.append({"path": f"{WAT}/{foot[0]}", "offset": False})
        layers.append({"path": f"{CH}/{char}", "offset": offset})
        if foot:
            for ov in foot[1]:
                layers.append({"path": f"{WAT}/{ov}", "offset": False})
        layers.append({"path": skin, "offset": offset})
        layers.append({"path": f"{EY}/{eyes}", "offset": offset})
        layers.append({"path": f"{MO}/{mouth}", "offset": offset})
        layers.append({"path": arms, "offset": offset})
        for ex in extras:
            if "Gorbhouse" in ex:
                layers.append({"path": ex, "offset": offset})
        if sticker:
            layers.append({"path": f"{ST}/{sticker}", "offset": False})
        for ex in extras:  # paired background overlays go absolutely last
            if "Gorbhouse" not in ex:
                layers.append({"path": ex, "offset": False})
        out = f"{OUT}/{name}.png"
        create_image(layers, out)
        outs.append(out)
        print("rendered", out)

    cell = 420
    sheet = Image.new("RGB", (cell * 5, (cell + 16) * 2), (14, 14, 14))
    d = ImageDraw.Draw(sheet)
    for i, p in enumerate(outs):
        im = Image.open(p).convert("RGB").resize((cell, cell))
        x, y = (i % 5) * cell, (i // 5) * (cell + 16)
        sheet.paste(im, (x, y))
        d.text((x + 4, y + cell + 2), os.path.basename(p)[:46],
               fill=(235, 235, 235))
    sheet.save(f"{OUT}/showcase_sheet.png")
    print("wrote", f"{OUT}/showcase_sheet.png")


if __name__ == "__main__":
    main()
