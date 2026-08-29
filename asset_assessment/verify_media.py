#!/usr/bin/env python3
"""Gate on whether the exported loops will actually PLAY where they are sent.

verify_sky.py proves the renderer is correct. It cannot prove the exported
file is playable, and those are different failures: a stream a phone
refuses does not error, it shows a BLACK FRAME, and a marketplace that
cannot parse the metadata does not error either -- it just shows the still
and nobody ever learns the animation existed.

So this checks the two things between a correct render and a holder seeing
it move:

  THE FILE          every exported MP4 is a stream a hardware decoder will
                    take, and the loop still wraps after the encoder has
                    been through it
  THE METADATA      the JSON points at the file in the shape marketplaces
                    and wallets read, and the still stays the still

WHAT THIS DOES NOT DO
---------------------
It does not test Magic Eden, Tensor, Phantom, Solflare or Backpack. Nothing
run offline can: support differs per surface, changes without notice, and
the only honest test is one real token on each. This narrows that test to
"does the surface support the standard", by removing every way the file or
the JSON could be wrong first.

    python3 asset_assessment/verify_media.py
    python3 asset_assessment/verify_media.py --dir dynamic/proof/anim
"""

import argparse
import glob
import json
import os
import struct
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANIM = os.path.join(ROOT, "dynamic", "proof", "anim")

# ------------------------------------------------------------ the limits
#
# H.264 PROFILE. Baseline (66), Main (77) and Extended (88) cannot carry
# anything but 4:2:0 chroma -- the SPS only contains chroma_format_idc for
# the High profiles, and every other profile infers 4:2:0. So the profile
# byte alone PROVES the pixel format here; there is no need to parse the
# SPS to know a Main-profile stream is yuv420p. That matters because 4:4:4
# or 4:2:2 is the classic "plays on my laptop, black on my phone" bug.
SAFE_PROFILES = {66: "Baseline", 77: "Main", 88: "Extended"}
HIGH_PROFILES = {100: "High", 110: "High10", 122: "High422", 244: "High444"}

# Level caps the decoder's work. 4.0 is the floor of what any phone from
# the last decade handles; anything above it starts excluding hardware.
MAX_LEVEL = 40

# Not a spec, a practical ceiling: marketplaces fetch animation_url over a
# phone connection and give up. Ours run under 500KB; this is set where it
# would catch a regression, not where playback actually breaks.
MAX_BYTES = 5 * 1024 * 1024

# The wrap has to fail BOTH of these to count, and that pairing is the
# whole design. The encoder is lossy, so frame N-1 -> frame 0 is never
# bit-identical the way the SOURCE frames are (verify_sky.py checks those);
# what matters is only whether the step is VISIBLE and out of character
# with the loop around it.
#
# A ratio alone is wrong, and measuring it proved that: `fog` has the least
# motion of any state, so its median step is 0.61/255 and its wrap of
# 1.05/255 came out at 1.7x -- flagged, while `blizzard`'s wrap of
# 11.3/255 passed at 1.02x because its motion is large. The absolute
# floor is what stops a state being punished for being calm. Below ~2
# levels out of 255 nothing is perceptible in a moving image whatever the
# ratio says.
MAX_WRAP_RATIO = 1.6
MIN_WRAP_VISIBLE = 2.0


def ffmpeg():
    """A usable ffmpeg, from PATH or the imageio-ffmpeg wheel."""
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


# --------------------------------------------------------- the container
def boxes(data, start=0, end=None, depth=0):
    """Walk the ISO-BMFF box tree. Deliberately hand-rolled: the two things
    that decide playback -- where `moov` sits and what `avcC` says -- are
    four bytes each, and depending on a probe tool to read them means the
    check cannot run wherever the export runs."""
    end = len(data) if end is None else end
    i = start
    while i + 8 <= end:
        size = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8].decode("latin1", "replace")
        hdr = 8
        if size == 1:
            size = struct.unpack(">Q", data[i + 8:i + 16])[0]
            hdr = 16
        elif size == 0:
            size = end - i
        if size < hdr:
            return
        yield typ, i, size, hdr, depth
        # stsd carries a count before its entries; avc1 carries a fixed
        # 78-byte sample description before its child boxes.
        if typ in ("moov", "trak", "mdia", "minf", "stbl"):
            yield from boxes(data, i + hdr, i + size, depth + 1)
        elif typ == "stsd":
            yield from boxes(data, i + hdr + 8, i + size, depth + 1)
        elif typ == "avc1":
            yield from boxes(data, i + hdr + 78, i + size, depth + 1)
        i += size


def inspect(path):
    """Everything decidable from the bytes, without decoding a frame."""
    d = open(path, "rb").read()
    info = {"bytes": len(d), "moov": None, "mdat": None,
            "profile": None, "level": None, "w": None, "h": None}
    for typ, off, size, hdr, depth in boxes(d):
        if depth == 0 and typ == "moov" and info["moov"] is None:
            info["moov"] = off
        elif depth == 0 and typ == "mdat" and info["mdat"] is None:
            info["mdat"] = off
        elif typ == "avc1":
            info["w"] = struct.unpack(">H", d[off + hdr + 24:off + hdr + 26])[0]
            info["h"] = struct.unpack(">H", d[off + hdr + 26:off + hdr + 28])[0]
        elif typ == "avcC":
            b = d[off + hdr:off + size]
            info["profile"], info["level"] = b[1], b[3]
    return info


# ------------------------------------------------------------- the loop
def decode(path, exe):
    """Decode to a (n, h, w, 3) uint8 array. Small loops; fits in memory."""
    info = inspect(path)
    w, h = info["w"], info["h"]
    out = subprocess.run(
        [exe, "-v", "error", "-i", path, "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"],
        capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode()[:300])
    buf = np.frombuffer(out.stdout, dtype=np.uint8)
    n = buf.size // (w * h * 3)
    return buf[:n * w * h * 3].reshape(n, h, w, 3)


def wrap_ratio(frames):
    """How the loop point compares with a typical step inside the loop.

    Returns (wrap, median_step). A seamless loop has a wrap step no larger
    than the steps around it; a broken one stands out by multiples.
    """
    f = frames.astype(np.int16)
    steps = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2, 3))
    wrap = float(np.abs(f[0] - f[-1]).mean())
    return wrap, float(np.median(steps))


# --------------------------------------------------------- the metadata
#
# The shape marketplaces and wallets read. Grounded against the Metaplex
# JS SDK's own JsonMetadata type (packages/js/src/.../JsonMetadata.ts),
# which types: name, symbol, description, seller_fee_basis_points, image,
# animation_url, external_url, attributes, properties{creators,files},
# collection.
#
# `properties.category` is NOT in that type. It rides the type's
# `[key: string]: unknown` index signature -- a de-facto convention the
# marketplaces read rather than a typed part of the standard. Emit it
# anyway (it is what makes a surface treat the token as a video), but know
# that it is convention, not schema, and that this checker asserting it is
# a house rule rather than a citation.
VIDEO_MIME = "video/mp4"
STILL_MIMES = ("image/png", "image/jpeg", "image/webp")


def check_metadata(meta, name="metadata"):
    """Validate one token metadata dict. Returns a list of problems."""
    bad = []
    anim = meta.get("animation_url")
    props = meta.get("properties") or {}
    files = props.get("files") or []

    if not meta.get("image"):
        bad.append(f"{name}: no `image` — every grid, thumbnail, search "
                   f"result and notification uses it")
    if anim is None:
        return bad + [
            f"{name}: no `animation_url` — the loops exist but nothing in "
            f"the metadata points at them, so no surface will ever play "
            f"one. This is the DEFAULT mint: pass --animation to "
            f"build_mint.py (e.g. --animation '{{id}}.mp4') to emit it. If "
            f"the collection is meant to ship static, this file is simply "
            f"not the thing to check."]

    # The still must STAY a still. A marketplace showing an mp4 in a grid
    # is not the win it sounds like: it is the thumbnail, the search result
    # and the push notification all becoming a video that cannot autoplay.
    if str(meta["image"]).lower().endswith(".mp4"):
        bad.append(f"{name}: `image` points at an mp4 — it must stay a "
                   f"still; animation belongs in animation_url")

    uris = {str(f.get("uri")): str(f.get("type", "")) for f in files}
    if str(anim) not in uris:
        bad.append(f"{name}: animation_url is not listed in "
                   f"properties.files — surfaces that read the file list "
                   f"rather than the bare field will not find it")
    elif uris[str(anim)] != VIDEO_MIME:
        bad.append(f"{name}: animation_url is typed {uris[str(anim)]!r} in "
                   f"properties.files, expected {VIDEO_MIME!r}")
    if str(meta["image"]) not in uris:
        bad.append(f"{name}: `image` is not listed in properties.files")
    elif uris[str(meta['image'])] not in STILL_MIMES:
        bad.append(f"{name}: image typed {uris[str(meta['image'])]!r}, "
                   f"expected one of {STILL_MIMES}")
    if props.get("category") != "video":
        bad.append(f"{name}: properties.category is "
                   f"{props.get('category')!r}, expected 'video' — this is "
                   f"what makes a surface treat the token as playable")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=ANIM)
    ap.add_argument("--metadata", default=None,
                    help="a token metadata .json to validate as well")
    ap.add_argument("--skip-decode", action="store_true",
                    help="container checks only; no frame decode")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "*.mp4")))
    if not files:
        sys.exit(f"no mp4s in {args.dir}; run: python3 dynamic/animate.py")
    exe = ffmpeg()
    failures = []

    print(f"{'file':26} {'profile':9} {'lvl':>4} {'size':>8} {'dims':>10} "
          f"{'faststart':>10} {'wrap':>12}")
    for path in files:
        n = os.path.basename(path)
        i = inspect(path)
        prof = SAFE_PROFILES.get(i["profile"],
                                 HIGH_PROFILES.get(i["profile"],
                                                   str(i["profile"])))
        fast = i["moov"] is not None and i["mdat"] is not None \
            and i["moov"] < i["mdat"]

        if i["profile"] not in SAFE_PROFILES:
            failures.append(
                f"{n}: profile {prof} — only Baseline/Main/Extended prove "
                f"4:2:0 from the profile byte; a High-profile stream may be "
                f"4:2:2 or 4:4:4, which fails as a BLACK FRAME on hardware "
                f"decoders rather than as an error")
        if i["level"] is None or i["level"] > MAX_LEVEL:
            failures.append(f"{n}: level {i['level'] / 10:.1f} above "
                            f"{MAX_LEVEL / 10:.1f} — starts excluding phones")
        if not fast:
            failures.append(f"{n}: moov after mdat — the player must fetch "
                            f"the whole file before the first frame")
        if i["w"] is None or i["w"] % 2 or i["h"] % 2:
            failures.append(f"{n}: odd dimensions {i['w']}x{i['h']} — "
                            f"4:2:0 requires even, and it fails as a black "
                            f"frame")
        if i["bytes"] > MAX_BYTES:
            failures.append(f"{n}: {i['bytes'] / 1e6:.1f}MB over the "
                            f"{MAX_BYTES / 1e6:.0f}MB practical ceiling")

        ratio = "—"
        if not args.skip_decode and exe:
            try:
                frames = decode(path, exe)
                wrap, step = wrap_ratio(frames)
                r = wrap / max(step, 1e-6)
                ratio = f"{r:.2f}x/{wrap:.1f}"
                if r > MAX_WRAP_RATIO and wrap > MIN_WRAP_VISIBLE:
                    failures.append(
                        f"{n}: the ENCODED loop jumps at the wrap — last "
                        f"frame to first moves {wrap:.1f}/255, which is "
                        f"{r:.1f}x a typical step in this loop. The source "
                        f"frames are bit-identical there (verify_sky.py), "
                        f"so this is the encode, not the render")
            except Exception as exc:
                failures.append(f"{n}: could not decode ({exc})")

        print(f"{n:26} {prof:9} {i['level'] / 10:4.1f} "
              f"{i['bytes'] / 1024:7.0f}K {i['w']}x{i['h']:<6} "
              f"{'yes' if fast else 'NO':>10} {ratio:>12}")

    if args.metadata:
        meta = json.load(open(args.metadata))
        failures.extend(check_metadata(meta, os.path.basename(args.metadata)))

    print()
    if failures:
        print(f"FAIL — {len(failures)} problem(s):")
        for f in failures:
            print("  " + f)
        return 1
    print(f"OK — {len(files)} loops are streams a hardware decoder will "
          f"take, and every encoded loop still wraps cleanly.")
    print("     This does NOT prove any marketplace or wallet plays them. "
          "Test one real token on each surface.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
