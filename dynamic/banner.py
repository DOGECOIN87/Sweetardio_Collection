#!/usr/bin/env python3
"""Render the 1500x500 Sweetardio banner as an animated, seamless loop.

Three tokens side by side at 500x500 each -- exactly 1500 wide -- with the
wordmark centred over the middle one. Every panel animates, each with its
own sky phase and weather, all sharing one loop length so the whole banner
returns to frame 0 together.

It reuses the dynamic sky pass rather than compositing anything new, so the
same rule holds here as everywhere else: the effect touches the background
plate and nothing else. The characters, stickers and arms are exactly as
they would mint.

From the repo root:

    python3 dynamic/banner.py --still      # one frame, fast, for judging
    python3 dynamic/banner.py              # the mp4
"""

import argparse
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import generator as gen
from dynamic import sky as skymod
from dynamic.animate import _ffmpeg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proof", "banner")
FONTS = "/mnt/skills/examples/canvas-design/canvas-fonts"

W, H = 1500, 500
CELL = 500

# Three panels, left to right. 'Flooded' is the storm weather state -- there
# is no plate by that name; the flood is the weather, which is the whole
# point of the banner.
PANELS = [
    dict(name="flooded_twinkie",
         char="Twinkie", bg="Empty_Fridge.png",
         sticker="20_The_meme_is_the_tech.png", arm=None, wat=None,
         phase="blue_dusk", weather="flooded", seed=101),
    # The arcade plate is the one that carries the mark: its own neon is
    # the same register as the sign, so the logo reads as part of the scene
    # instead of pasted onto it. Katana held high leaves the lower third
    # clear for the lockup.
    dict(name="hero",
         char="chocolate_chip_cookie", bg="Legendary_Simplex.png",
         sticker="Sweetardio_200 (30).png",
         arm="Armz_Katana.png", wat=None,
         phase="blue_dusk", weather="snow", seed=202),
    dict(name="og_poptart_starfield",
         char="og_poptart", bg="Legendary_Tenders.png",
         sticker="21_Straight_outta_Gulag.png",
         arm="Sweetardio_114 (6).png", wat=None,
         # night + snow, not fog: fog lifts the blacks and erases the star
         # field entirely, while fine snow over it reads as drifting dust
         phase="night", weather="snow", seed=303),
]

LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "assets", "sweetardio_logo.png")


def font(name, size):
    for cand in (os.path.join(FONTS, name),
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(cand):
            try:
                return ImageFont.truetype(cand, size)
            except OSError:
                pass
    return ImageFont.load_default()


def mint_panels(force=False):
    """Render each panel's token once, with its protect mask."""
    os.makedirs(OUT, exist_ok=True)
    out = []
    for p in PANELS:
        base = os.path.join(OUT, f"{p['name']}.png")
        mask = os.path.join(OUT, f"{p['name']}_mask.png")
        if force or not (os.path.exists(base) and os.path.exists(mask)):
            import random
            random.seed(p["seed"])
            layers, char = gen.generate_random_combination(
                force_char=p["char"],
                force_bg=(gen.BACKGROUNDZ, p["bg"]),
                force_arm=p["arm"] if p["arm"] else None,
                force_wat=p["wat"], force_sticker=p["sticker"])
            gen.create_image(layers, base, mask_path=mask)
            print(f"  minted {char} on {p['bg']}")
        b = Image.open(base).convert("RGBA").resize(
            (CELL, CELL), Image.Resampling.LANCZOS)
        m = Image.open(mask).convert("L").resize(
            (CELL, CELL), Image.Resampling.LANCZOS)
        out.append((p, b, m, skymod.grade_static(b, p["phase"], p["weather"])))
    return out


def draw_wordmark(img, width, wy, scrim):
    """Composite the REAL Sweetardio mark -- the pink neon sign that already
    exists on traits/backgroundz_originals/Sweetardio.png, cut out by
    dynamic/extract_logo.py.

    It sits BELOW centre. Dead-centre put it straight across the hero
    token's face and deleted it; low, it clears the character and still
    reads as centred on a 1500x500 banner.

    The scrim is a bloom lifted from the mark's OWN alpha rather than a
    drawn box, so it darkens exactly what sits behind the neon and nothing
    else -- a solid bar would just delete the middle token.
    """
    if not os.path.exists(LOGO):
        raise SystemExit("run: python3 dynamic/extract_logo.py")
    logo = Image.open(LOGO).convert("RGBA")
    h = max(1, round(logo.height * width / logo.width))
    logo = logo.resize((width, h), Image.Resampling.LANCZOS)

    x = (W - width) // 2
    y = int((H - h) * wy)

    if scrim > 0:
        a = logo.split()[3].filter(ImageFilter.GaussianBlur(width * 0.09))
        a = a.point(lambda v: min(255, int(v * 2.4 * scrim)))
        pad = Image.new("L", (W, H), 0)
        pad.paste(a, (x, y))
        img.alpha_composite(Image.merge(
            "RGBA", (Image.new("L", (W, H), 5), Image.new("L", (W, H), 6),
                     Image.new("L", (W, H), 11), pad)))

    img.alpha_composite(logo, (x, y))
    return img


def compose(panels, t, width, scrim, wy):
    banner = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    for i, (p, b, m, static) in enumerate(panels):
        fr = skymod.frame(static, m, t=t, seed=p["seed"])
        banner.paste(fr.convert("RGB"), (i * CELL, 0))
    return draw_wordmark(banner, width, wy, scrim)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", action="store_true", help="one frame only")
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--ms", type=int, default=50)
    ap.add_argument("--logo-w", dest="logo_w", type=int, default=430,
                    help="rendered width of the neon mark, px")
    ap.add_argument("--scrim", type=float, default=1.5)
    ap.add_argument("--wy", type=float, default=0.88,
                    help="wordmark vertical position, 0=top 1=bottom")
    ap.add_argument("--gif", action="store_true",
                    help="also write a half-size GIF fallback")
    ap.add_argument("--remint", action="store_true")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    print("minting / loading panels")
    panels = mint_panels(force=args.remint)
    for p, _, _, _ in panels:
        print(f"  {p['name']:<22} {p['phase']} + {p['weather']}")

    if args.still:
        path = os.path.join(OUT, f"banner_still{args.tag}.png")
        compose(panels, 0.12, args.logo_w, args.scrim,
                args.wy).convert("RGB").save(path)
        print(path)
        return

    frames = [compose(panels, i / args.frames, args.logo_w, args.scrim,
                      args.wy).convert("RGB")
              for i in range(args.frames)]
    exe = _ffmpeg()
    if exe is None:
        sys.exit("no ffmpeg (pip install imageio-ffmpeg)")
    path = os.path.join(OUT, "sweetardio_banner.mp4")
    cmd = [exe, "-y", "-loglevel", "error", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", f"{1000.0 / args.ms:.4f}", "-i", "-", "-an",
           "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-profile:v", "main", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for f in frames:
        proc.stdin.write(f.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit(proc.stderr.read().decode()[:400])
    print(f"{path}  {os.path.getsize(path) / 1024:.0f} KB  "
          f"{args.frames * args.ms / 1000:.2f}s loop")

    # A GIF of this is 26MB at full size and still bands -- opt-in only,
    # and halved, for a surface that genuinely cannot take video.
    if args.gif:
        gif = os.path.join(OUT, "sweetardio_banner_preview.gif")
        half = [f.resize((W // 2, H // 2), Image.Resampling.LANCZOS)
                for f in frames]
        q = [f.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
             for f in half]
        q[0].save(gif, save_all=True, append_images=q[1:], duration=args.ms,
                  loop=0, optimize=True)
        print(f"{gif}  {os.path.getsize(gif) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
