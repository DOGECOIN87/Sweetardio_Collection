#!/usr/bin/env python3
"""Render each weather state as a seamless animated loop.

Weather is the half of the dynamic trait that moves. The structural point
this file exists to exploit is in sky.py: the tone grade, the haze and the
diffusion are identical in every frame, so a loop costs ONE graded plate
plus N cheap frames rather than N full grades.

That is also the shape of the production path. A live view does not need a
video at all -- it needs the single graded still plus a particle pass in a
canvas, which is what makes an `animation_url` page small enough to be
worth shipping.

Outputs, into dynamic/proof/anim/:

  weather_<state>.mp4         H.264/yuv420p — the animation_url format
                              Solana marketplaces and wallets handle most
                              reliably
  weather_<state>.webp        the seamless loop, for states that move
  weather_<state>.png         a LOSSLESS still, for states that do not
  weather_<state>_strip.png   a filmstrip of 6 frames, for reading on paper
  weather_all.png             every moving state's filmstrip stacked

There is no `clear` state to export: a clear sky is the absence of weather
and the minted PNG already is it, so nothing here should ever re-encode a
copy of the mint. The motionless branch below stays as the guard that
keeps it that way -- a named state that did not move would be a state for
doing nothing, which is what `clear` was.

From the repo root:

    python3 dynamic/animate.py                       # all seven
    python3 dynamic/animate.py --size 640
    python3 dynamic/animate.py --only blizzard tornado
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont

from dynamic import sky as skymod

PROOF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proof")
ANIM = os.path.join(PROOF, "anim")
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# What each state is actually doing, for the filmstrip captions -- and so
# the motion design is written down somewhere other than the numbers.
MOTION = {
    "fog": "a ground bank whose top edge rolls; the sky above stays sharp",
    "rain": "two depth bands falling down-and-right, near band 2x faster",
    "snow": "slow fall with a sideways sway, one cycle per loop",
    "storm": "heavy rain, plus a lightning strike and its echo",
    "blizzard": "driven snow over a whiteout band, on settled drifts",
    "tornado": "the funnel snakes once, its banding climbs three times, "
               "the debris orbits twice and more blows past",
    "flooded": "the surface rolls and the refraction wobbles beneath it; "
               "the only state that touches the character",
}


def _ffmpeg():
    """A usable ffmpeg, from PATH or from the imageio-ffmpeg wheel."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def write_mp4(frames, path, fps):
    """H.264 in yuv420p -- the format Solana marketplaces and wallets
    handle most reliably for `animation_url`.

    yuv420p and even dimensions are not optional: a stream in yuv444p or
    with an odd dimension is exactly what a hardware decoder or a phone
    refuses, and it fails as a black frame rather than as an error. The
    loop is already seamless, so players that repeat it show no jump.
    """
    exe = _ffmpeg()
    if exe is None:
        return None
    w, h = frames[0].size
    if w % 2 or h % 2:                      # H.264 needs even dimensions
        w, h = w - w % 2, h - h % 2
        frames = [f.crop((0, 0, w, h)) for f in frames]
    cmd = [exe, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-r", f"{fps:.4f}", "-i", "-", "-an",
           "-c:v", "libx264", "-preset", "slow", "-crf", "20",
           "-profile:v", "main", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    for f in frames:
        proc.stdin.write(f.convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(proc.stderr.read().decode()[:400])
    return path


def write_gif(frames, path, ms):
    """GIF is the widest-supported animated format and the worst-looking:
    256 colours per frame band these graded plates visibly. Emitted only as
    a fallback for a surface that will not take video."""
    rgb = [f.convert("RGB") for f in frames]
    pal = rgb[0].quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    q = [im.quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG)
         for im in rgb]
    q[0].save(path, save_all=True, append_images=q[1:], duration=ms,
              loop=0, optimize=True, disposal=2)
    return path


def _font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def loop_frames(base, protect, phase, weather, n, seed, size, afloat=None):
    """n seamless frames. grade_static runs ONCE; only frame() repeats."""
    if base.size != (size, size):
        base = base.resize((size, size), Image.Resampling.LANCZOS)
        protect = protect.resize((size, size), Image.Resampling.LANCZOS)
        if afloat is not None:
            afloat = afloat.resize((size, size), Image.Resampling.LANCZOS)
    t0 = time.time()
    static = skymod.grade_static(base, phase, weather)
    t_grade = time.time() - t0
    t0 = time.time()
    frames = [skymod.frame(static, protect, t=i / n, seed=seed,
                           afloat=afloat)
              for i in range(n)]
    return frames, t_grade, (time.time() - t0) / n


def filmstrip(frames, label, motion, cell, out_path, picks=6):
    """Six evenly spaced frames of the loop, side by side."""
    idx = [round(i * len(frames) / picks) % len(frames) for i in range(picks)]
    pad, top, cap = 8, 52, 26
    w = picks * cell + pad * (picks + 1)
    h = top + cell + cap + pad * 2
    sheet = Image.new("RGB", (w, h), (16, 17, 21))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad + 2, 10), label, font=_font(23), fill=(238, 240, 246))
    draw.text((pad + 2, 33), motion, font=_font(16), fill=(150, 156, 172))
    for j, i in enumerate(idx):
        x = pad + j * (cell + pad)
        sheet.paste(frames[i].convert("RGB").resize(
            (cell, cell), Image.Resampling.LANCZOS), (x, top + pad))
        draw.text((x + 2, top + pad + cell + 5), f"t = {i / len(frames):.2f}",
                  font=_font(15), fill=(150, 156, 172))
    sheet.save(out_path)
    return sheet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", type=int, default=1)
    ap.add_argument("--phase", default="day",
                    choices=list(skymod.SKY_STATES))
    ap.add_argument("--frames", type=int, default=36)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--ms", type=int, default=55, help="frame duration")
    ap.add_argument("--cell", type=int, default=210)
    ap.add_argument("--quality", type=int, default=88,
                    help="WebP quality for the states that DO move")
    ap.add_argument("--formats", nargs="*", default=["webp", "mp4"],
                    choices=["webp", "mp4", "gif"],
                    help="mp4 is the safest bet for marketplaces/wallets")
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()

    b = os.path.join(PROOF, f"token_{args.token}.png")
    m = os.path.join(PROOF, f"token_{args.token}_mask.png")
    if not (os.path.exists(b) and os.path.exists(m)):
        sys.exit("no sample token; run: python3 dynamic/render.py --tokens 3")
    base = Image.open(b).convert("RGBA")
    protect = Image.open(m).convert("L")
    f = os.path.join(PROOF, f"token_{args.token}_float.png")
    afloat = Image.open(f).convert("L") if os.path.exists(f) else None
    os.makedirs(ANIM, exist_ok=True)

    states = args.only or list(skymod.WEATHER_STATES)
    strips = []
    print(f"phase={args.phase}  {args.frames} frames @ {args.ms}ms  "
          f"({args.frames * args.ms / 1000:.2f}s loop)  size={args.size}")

    for wx in states:
        # A STATE WITH NO MOTION IS NEVER EXPORTED AS AN ANIMATION.
        # Encoding N identical frames of a still spends a downscale and a
        # lossy round-trip to say nothing at all. No named state should
        # reach this branch any more -- it is the guard, and verify_sky.py
        # fails if one does.
        if not skymod.has_motion(wx):
            still = skymod.apply_sky(base, protect, args.phase, wx,
                                     seed=args.token, afloat=afloat)
            out = os.path.join(ANIM, f"weather_{wx}.png")
            still.save(out, optimize=True)
            same = skymod.is_identity(args.phase, wx)
            print(f"  {wx:<9} STILL — no motion; lossless PNG at "
                  f"{still.width}px"
                  + ("  (bit-identical to the mint)" if same else "")
                  + f"   {os.path.getsize(out) / 1024:.0f} KB")
            continue

        frames, t_grade, t_frame = loop_frames(
            base, protect, args.phase, wx, args.frames, args.token,
            args.size, afloat=afloat)
        fps = 1000.0 / args.ms
        wrote = []
        if "webp" in args.formats:
            path = os.path.join(ANIM, f"weather_{wx}.webp")
            rgb = [f.convert("RGB") for f in frames]
            rgb[0].save(path, save_all=True, append_images=rgb[1:],
                        duration=args.ms, loop=0, quality=args.quality,
                        method=6)
            wrote.append(path)
        if "mp4" in args.formats:
            path = write_mp4(frames, os.path.join(ANIM, f"weather_{wx}.mp4"),
                             fps)
            if path:
                wrote.append(path)
            elif wx == states[0]:
                print("  (no ffmpeg — skipping mp4; "
                      "pip install imageio-ffmpeg)")
        if "gif" in args.formats:
            wrote.append(write_gif(
                frames, os.path.join(ANIM, f"weather_{wx}.gif"), args.ms))

        strip = os.path.join(ANIM, f"weather_{wx}_strip.png")
        strips.append(filmstrip(frames, f"{wx.upper()}  ·  {args.phase}",
                                MOTION.get(wx, ""), args.cell, strip))
        sizes = "  ".join(f"{os.path.splitext(p)[1][1:]} "
                          f"{os.path.getsize(p) / 1024:.0f}KB" for p in wrote)
        print(f"  {wx:<9} grade {t_grade * 1000:5.0f} ms once + "
              f"{t_frame * 1000:4.0f} ms/frame   {sizes}")

    if len(strips) > 1:
        w = max(s.width for s in strips)
        h = sum(s.height for s in strips) + 8 * (len(strips) - 1)
        allp = Image.new("RGB", (w, h), (16, 17, 21))
        y = 0
        for s in strips:
            allp.paste(s, (0, y))
            y += s.height + 8
        out = os.path.join(ANIM, "weather_all.png")
        allp.save(out)
        print(f"  {out}")


if __name__ == "__main__":
    main()
