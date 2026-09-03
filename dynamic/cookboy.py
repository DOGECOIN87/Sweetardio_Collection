#!/usr/bin/env python3
"""Cookboy Blue Raspberry: the one 1/1 secret rare built on the starfield.

DIFFERENT FROM THE OTHER TWO 1/1s. Duhnut Candy Man and Radbro Webring are
static full-canvas artwork -- each is its own scene, lit by the artist, with
no plate underneath to move. Cookboy is the pixel-face motif flown across
the SAME moving starfield plate the 22 composited starfield tokens use, so
it is the only secret rare that can loop at all: the other two have nothing
to swap frame to frame.

WHY THIS IS ITS OWN MODULE rather than routed through dynamic/starfield.py's
character path (centre_figure/centre_layers, which build_mint.py drives for
the 22 real characters). Those anchor on traits/characterz/ and
traits/what_are_thosez/ by trait-folder path -- the whole reason
_figure(layers, gen, parts) filters by folder is that a character's stack
mixes body, skin, eyes, arms and footwear, and only some of those should
anchor the band or the drop. Cookboy's stack is one flat cutout with none of
that structure: there is no separate body to single out, no footwear to
include, no arm to exclude. Reusing the character path on it would either
silently no-op (the folder filters match nothing, so centre_figure's drop
and centre_dy's clamp both fall back to 0) or need fake folder membership
that means nothing for this piece. So this module owns its own construction
end to end and reuses only the pure math and the plate mechanics
(_centre_dy_from_masks, from_gif, loop_layers) that do not care what kind of
figure they are placing.

Two things this module builds:

  THE STILL. Already committed at
  traits/secret_rarez/Secret_Cookboy_Blue_Raspberry.png -- a single flattened
  PNG, because a secret rare composites with nothing at mint time (see
  CLAUDE.md, "A secret rare composites with NOTHING") and the grounding
  shadow / separation pocket it needs have to be baked in here, by running
  the real compositor over [plate, figure] once. --write rebuilds it and
  should reproduce that file bit-for-bit; if it does not, something about
  the source, the cut, or the placement moved and the committed asset needs
  a fresh eyeball before it is replaced.

  THE LOOP. Not yet wired into a shipped mint as of this module's addition.
  build_loop() re-composites [plate_frame_i, figure] once per of the 12
  plate frames, the same re-compositing loop_layers() already does for
  every real starfield character, for the same reason: the plate carries
  the grounding shadow, so a loop built by swapping the plate under a
  finished PNG would lose it and the figure would float.
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generator as g               # noqa: E402
import starfield as sf              # noqa: E402

SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "cookboy_source.webp")
STILL_PATH = os.path.join(g.TRAITS_DIR, g.SECRET_RAREZ,
                          "Secret_Cookboy_Blue_Raspberry.png")
CANVAS = g.CANVAS_SIZE

# Chosen off a rendered ladder at 760 / 860 / 960 / 1060 (see CLAUDE.md,
# "880px tall"): above it the piece crowds the frame, below it it stops
# reading as a hero.
HEIGHT = 880

# The source is the figure composited over pure black (measured: the
# frame's outer 6px band peaks at luma 1). So its RGB is already
# premultiplied and the cut is a luma ramp plus an UNPREMULTIPLY -- a
# straight alpha threshold would keep black RGB at partial alpha and leave
# a dark fringe all the way round the anti-aliased edge.
_LO, _HI = 3.0, 18.0


def cut(source=SOURCE):
    """The figure alone, alpha-cut from its black backing, cropped to its
    own bbox."""
    rgb = np.asarray(Image.open(source).convert("RGB")).astype(np.float32)
    a = np.clip((rgb.max(2) - _LO) / (_HI - _LO), 0.0, 1.0)
    out = np.zeros(rgb.shape[:2] + (4,), np.float32)
    safe = np.maximum(a, 1e-3)[..., None]
    out[..., :3] = np.clip(rgb / safe, 0, 255)
    out[..., 3] = a * 255.0
    im = Image.fromarray(out.round().astype(np.uint8), "RGBA")
    return im.crop(im.getchannel("A").point(lambda v: 255 if v > 8 else 0)
                   .getbbox())


def figure(height=HEIGHT, cy=None):
    """The cut figure, resized to `height` and centred on the full canvas."""
    fig = cut()
    w = max(1, int(round(fig.width * height / fig.height)))
    small = fig.resize((w, int(height)), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    cy = CANVAS // 2 if cy is None else cy
    out.paste(small, ((CANVAS - w) // 2, int(cy - height / 2)), small)
    return out


def dy_for(fig_img):
    """Band offset for this figure, via the same math centre_dy() runs for
    a character -- see _centre_dy_from_masks's docstring for why a single
    mask can stand in for both its body and figure arguments here."""
    a = np.asarray(fig_img.getchannel("A")) >= 128
    return sf._centre_dy_from_masks(a, a)


def _assert_cut_hidden(fig_img, dy):
    """The one way this feature fails ugly (see dynamic/starfield.py's
    verify_cover): the rainbow's flat cut has to stay behind the figure
    over the band's full swept height. Asserted at build time rather than
    only in a separate --verify pass, because a broken build should not
    produce a file that looks fine at a glance."""
    top, bot = sf.band_bbox(dy)
    col = np.asarray(fig_img.getchannel("A")) >= 128
    lead = int(round(sf.LEAD * sf.CANVAS_PER_SRC))
    cover = col[:, max(0, lead - sf.FIGURE_PAD):lead + 1].all(1)
    hidden = bool(cover[int(np.floor(top)):int(np.ceil(bot)) + 1].all())
    if not hidden:
        raise SystemExit(
            f"cookboy: the rainbow's flat cut is exposed at height={fig_img.height} "
            f"dy={dy} (band {top:.0f}..{bot:.0f}, cut x{lead})")


def build_still(path=STILL_PATH, height=HEIGHT):
    """Build the flattened 1/1 PNG through the real compositor. Returns dy.

    create_image() takes layers[0] as the plate and everything after it as
    the figure -- handing it [plate, figure] gives this piece the same
    grounding shadow and subject-separation pocket the 22 minted starfield
    tokens get, rather than a hand-painted approximation of it.
    """
    fig = figure(height)
    dy = dy_for(fig)
    _assert_cut_hidden(fig, dy)
    tmp_dir = os.path.dirname(os.path.abspath(path))
    fp = os.path.join(tmp_dir, f"_cookboy_fig_{os.getpid()}.png")
    pp = os.path.join(tmp_dir, f"_cookboy_plate_{os.getpid()}.png")
    fig.save(fp)
    try:
        sf.from_gif(sf.GIF_PATH, size=(CANVAS, CANVAS), dy=dy)[0].save(pp)
        layers = [{"path": pp, "offset": False},
                  {"path": fp, "offset": False}]
        g.create_image(layers, path)
    finally:
        for p in (fp, pp):
            if os.path.exists(p):
                os.remove(p)
    return dy


def build_loop(out_dir, tid, size=None, ms=None, height=HEIGHT):
    """The 12-frame loop, re-composited once per plate frame exactly as
    loop_layers() does for a real starfield character. Returns the frames;
    the caller encodes them (build_mint.py already imports write_mp4)."""
    fig = figure(height)
    dy = dy_for(fig)
    _assert_cut_hidden(fig, dy)
    os.makedirs(out_dir, exist_ok=True)
    fp = os.path.join(out_dir, f"_cookboy_fig_{tid}.png")
    fig.save(fp)
    try:
        layers = [{"path": fp, "offset": False},   # placeholder; loop_layers
                  {"path": fp, "offset": False}]    # replaces layers[0] per frame
        return sf.loop_layers(layers, out_dir, f"cookboy_{tid}", g,
                              size=size, dy=dy)
    finally:
        if os.path.exists(fp):
            os.remove(fp)


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help=f"rebuild {STILL_PATH} (should reproduce it "
                         f"bit-for-bit)")
    ap.add_argument("--verify", action="store_true",
                    help="the cut stays hidden, and the still matches what "
                         "is committed")
    ap.add_argument("--strip", metavar="PNG", default=None,
                    help="write the 12 loop frames as a filmstrip proof")
    a = ap.parse_args(argv)
    rc = 0

    if a.write:
        dy = build_still()
        print(f"wrote {STILL_PATH}  (band dy {dy:+d})")

    if a.verify:
        import hashlib
        tmp = STILL_PATH + ".verify.png"
        dy = build_still(tmp)
        want = hashlib.md5(open(STILL_PATH, "rb").read()).hexdigest()
        got = hashlib.md5(open(tmp, "rb").read()).hexdigest()
        os.remove(tmp)
        match = want == got
        print(f"still  band dy {dy:+d}  rebuild {'matches' if match else 'DIFFERS FROM'} "
              f"the committed asset ({got[:8]} vs {want[:8]})")
        if not match:
            rc = 1
        frames = build_loop("/tmp", "verifyrun", size=512)
        a0 = np.asarray(frames[0], np.int16)
        a12 = np.asarray(build_loop("/tmp", "verifyrun2", size=512)[0], np.int16)
        seam = bool((a0 == a12).all())
        print(f"loop   {len(frames)} frames, frame 0 reproducible: "
              f"{'OK' if seam else 'FAIL'}")
        rc = rc or (0 if seam else 1)
        print("cookboy  " + ("OK" if rc == 0 else "FAIL"))

    if a.strip:
        frames = build_loop(os.path.dirname(os.path.abspath(a.strip)) or ".",
                            "strip", size=300)
        w, h = frames[0].size
        sheet = Image.new("RGB", (w * len(frames), h))
        for i, f in enumerate(frames):
            sheet.paste(f, (i * w, 0))
        sheet.save(a.strip)
        print(f"wrote {a.strip}  ({len(frames)} frames)")

    if not (a.write or a.verify or a.strip):
        ap.print_help()
    return rc


if __name__ == "__main__":
    sys.exit(_main())
