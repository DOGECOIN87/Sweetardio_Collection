"""Repackage a finished mint into the single folder launchmynft.io wants.

LMNFT's upload step takes ONE folder holding every image beside its own
`<id>.json` ("drag in one folder ... one json per image"), with the media
path written as a leading-slash filename -- their worked example is
`"image": "/1.png"`. The repo's own mint layout is three folders and bare
filenames, because that is what the Metaplex standard and verify_mint.py
use; neither shape is wrong, they are for different consumers.

So this writes a SECOND view of the same render rather than converting it:
output/mint/ stays the canonical, verified artifact and output/launchmynft/
is the upload folder. The PNGs and MP4s are HARDLINKED, not copied -- the
stills alone are ~11 GB and duplicating them buys nothing.

The Metaplex `properties` block is carried through untouched. LMNFT does not
document it, but a marketplace reads it after deploy, and an ignored field
costs nothing where a missing one costs playback.

`creators` is deliberately NOT written: LMNFT collects royalties and payout
in Step 1 and injects them at deploy. A guessed address here would be worse
than an absent one.

`seller_fee_basis_points` is the same story one step further. Royalties are
ENFORCED from the on-chain metadata account, which LMNFT writes at deploy
from the GUI -- so the off-chain number here is read by aggregators and
nothing else. It is exposed as a flag rather than baked in so it can be
matched to the GUI at the last minute, or dropped entirely, without
re-rendering: --royalty-bps N rewrites it, --strip-royalty removes it.

--loop-repeat N is the answer to "will it actually loop". An MP4 carries no
loop flag -- GIF has one, H.264 does not -- so repeating is the player's
choice and no file can force it. What a file CAN do is contain the loop
more than once, so a player that stops after one pass still shows N passes.
`-stream_loop` re-muxes with -c copy: no re-encode, no quality change, and
it only works because the seam is already invisible (verify_media measures
it). Default 1 = off, because this is worth deciding after seeing what the
target surface actually does, not before.
"""


def _ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _repeat(src, dst, n, exe):
    """Concatenate the loop n times without re-encoding a single frame."""
    r = subprocess.run([exe, "-y", "-loglevel", "error",
                        "-stream_loop", str(n - 1), "-i", src,
                        "-c", "copy", "-movflags", "+faststart", dst],
                       capture_output=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg failed on {src}: {r.stderr.decode()[:300]}")
import json, os, shutil, subprocess, sys, argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mint", default="output/mint")
    ap.add_argument("--out", default="output/launchmynft")
    ap.add_argument("--royalty-bps", type=int, default=None,
                    help="overwrite seller_fee_basis_points to match what "
                         "you enter in the LMNFT GUI (on-chain wins anyway)")
    ap.add_argument("--strip-royalty", action="store_true",
                    help="drop seller_fee_basis_points entirely and let the "
                         "deploy step be the only source of truth")
    ap.add_argument("--loop-repeat", type=int, default=1, metavar="N",
                    help="write each loop N times end-to-end so a player "
                         "that does not repeat still shows N passes "
                         "(lossless re-mux; default 1 = off)")
    ap.add_argument("--prefix", default="/",
                    help="path prefix for image/animation_url (LMNFT's "
                         "example uses '/'; pass '' for bare filenames)")
    a = ap.parse_args()

    img_d = os.path.join(a.mint, "images")
    met_d = os.path.join(a.mint, "metadata")
    ani_d = os.path.join(a.mint, "anim")
    for d in (img_d, met_d):
        if not os.path.isdir(d):
            sys.exit(f"missing {d} -- run the mint first")

    os.makedirs(a.out, exist_ok=True)
    if os.listdir(a.out):
        sys.exit(f"{a.out} is not empty; remove it first")

    exe = None
    if a.loop_repeat > 1:
        exe = _ffmpeg()
        if exe is None:
            sys.exit("--loop-repeat needs ffmpeg on PATH")

    ids = sorted(int(f[:-5]) for f in os.listdir(met_d) if f.endswith(".json"))
    n_anim = 0
    for tid in ids:
        j = json.load(open(os.path.join(met_d, f"{tid}.json")))

        if a.strip_royalty:
            j.pop("seller_fee_basis_points", None)
        elif a.royalty_bps is not None:
            j["seller_fee_basis_points"] = a.royalty_bps

        png = os.path.join(img_d, f"{tid}.png")
        if not os.path.exists(png):
            sys.exit(f"token {tid}: metadata without an image")
        os.link(png, os.path.join(a.out, f"{tid}.png"))
        j["image"] = f"{a.prefix}{tid}.png"

        if "animation_url" in j:
            mp4 = os.path.join(ani_d, f"{tid}.mp4")
            if not os.path.exists(mp4):
                sys.exit(f"token {tid}: animation_url without a file")
            out_mp4 = os.path.join(a.out, f"{tid}.mp4")
            if a.loop_repeat > 1:
                _repeat(mp4, out_mp4, a.loop_repeat, exe)
            else:
                os.link(mp4, out_mp4)
            j["animation_url"] = f"{a.prefix}{tid}.mp4"
            n_anim += 1

        # keep properties.files pointing at the same names we just wrote
        props = j.get("properties")
        if isinstance(props, dict):
            for f in props.get("files", []):
                if isinstance(f, dict) and "uri" in f:
                    f["uri"] = f"{a.prefix}{os.path.basename(f['uri'])}"

        with open(os.path.join(a.out, f"{tid}.json"), "w") as fh:
            json.dump(j, fh, indent=2, ensure_ascii=False)

    roy = ("stripped" if a.strip_royalty
           else (a.royalty_bps if a.royalty_bps is not None else "as minted"))
    print(f"{a.out}: {len(ids)} images + {len(ids)} json + {n_anim} mp4 "
          f"= {len(ids)*2 + n_anim} files  |  seller_fee_basis_points: {roy}"
          f"  |  loop x{a.loop_repeat}")

if __name__ == "__main__":
    main()
