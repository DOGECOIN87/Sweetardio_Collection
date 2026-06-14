#!/usr/bin/env python3
"""
SWEETARDIO â BACKGROUND "POP" GRADING SYSTEM
============================================
Processes the EXISTING background plates (assets/background/*.png) so that a
foreground subject painted in the brand palette separates cleanly from them.

The palette describes the FOREGROUND (characters / assets), NOT the background.
These grades therefore yield the "contrast budget" to the foreground using the
classic figure-ground toolkit:

  - chroma contrast   : desaturate the BG so the subject owns the saturation
  - luminance contrast: darken the BG so bright neon separates
  - depth / atmosphere: soften + recede the BG (depth-of-field)
  - colour opposition : push BG away from the palette band (temperature)
  - framing           : vignette / stage to seat a centred subject

Nothing is generated or repainted. Every operation is a deterministic,
reversible tone/colour transform of the existing plate. Originals are never
overwritten â output goes to a separate folder.

Palette (foreground, for reference only):
  Oxford Blue 070F34 Â· Zaffre 0313A6 Â· Dark Violet 9201CB
  Hollywood Cerise F715AB Â· Fluorescent Cyan 34EDF3
"""

from __future__ import annotations
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from pathlib import Path
import numpy as np
import argparse

# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# PALETTE (foreground reference â drawn as chips on samples to show separation)
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
PALETTE = [
    ("Oxford Blue",      (0x07, 0x0F, 0x34)),
    ("Zaffre",           (0x03, 0x13, 0xA6)),
    ("Dark Violet",      (0x92, 0x01, 0xCB)),
    ("Hollywood Cerise", (0xF7, 0x15, 0xAB)),
    ("Fluorescent Cyan", (0x34, 0xED, 0xF3)),
]

# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# FLOAT <-> IMAGE
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def to_arr(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0

def to_img(a: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(a * 255.0, 0, 255).astype(np.uint8), "RGB")

def lum(a: np.ndarray) -> np.ndarray:
    return (0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2])[..., None]

# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# PRIMITIVE TONE / COLOUR OPS  (all operate on float RGB arrays, 0..1)
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def desaturate(a, amt):                 # amt 0..1 toward greyscale
    return a * (1 - amt) + lum(a) * amt

def saturate(a, amt):                   # amt > 0 boosts chroma
    l = lum(a)
    return np.clip(l + (a - l) * (1 + amt), 0, 1)

def exposure(a, mult):                  # multiplicative brightness
    return a * mult

def smoothstep_contrast(a, k):          # gentle filmic S-curve, pivot 0.5
    s = a * a * (3 - 2 * a)
    return a * (1 - k) + s * k

def lift_gamma_gain(a, lift=0.0, gamma=1.0, gain=1.0):
    x = np.clip(a * gain + lift, 0, 1)
    return np.power(x, 1.0 / gamma)

def split_tone(a, shadow_rgb, hi_rgb, amt):
    """Push shadows toward shadow_rgb and highlights toward hi_rgb (centred)."""
    l = lum(a)
    sh = np.array(shadow_rgb, np.float32) - 0.5
    hi = np.array(hi_rgb, np.float32) - 0.5
    bias = sh * (1 - l) + hi * l
    return np.clip(a + bias * amt, 0, 1)

def vignette(a, strength, radius=0.62, power=1.7, tint=(0, 0, 0)):
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    v = np.clip((d - radius) / (np.sqrt(2) - radius), 0, 1) ** power * strength
    v = v[..., None]
    t = np.array(tint, np.float32)
    return a * (1 - v) + t * v

def reduce_local_contrast(im, amt, radius):
    """Flatten high-frequency detail (clarity down) so the plate reads calmer."""
    base = to_arr(im.filter(ImageFilter.GaussianBlur(radius)))
    a = to_arr(im)
    return to_img(base + (a - base) * (1 - amt))

def bloom(im, radius, strength):
    a = to_arr(im)
    b = to_arr(im.filter(ImageFilter.GaussianBlur(radius)))
    screen = 1 - (1 - a) * (1 - b)
    return to_img(a * (1 - strength) + screen * strength)

# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# PROFESSIONAL LOOKS  (PIL image -> PIL image)
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def look_chroma_stage(im: Image.Image) -> Image.Image:
    """A â Chroma Stage. Desaturation-led. Subject owns all the saturation.
       Cleanest / safest. Marketplace-friendly."""
    a = to_arr(im)
    a = desaturate(a, 0.45)
    a = exposure(a, 0.90)
    a = smoothstep_contrast(a, 0.18)
    a = vignette(a, 0.20)
    return to_img(a)

def look_deep_focus(im: Image.Image) -> Image.Image:
    """B â Deep Focus. Luminance-led dark stage. Best for bright neon subjects."""
    a = to_arr(im)
    a = desaturate(a, 0.22)
    a = lift_gamma_gain(a, lift=-0.02, gamma=0.92, gain=0.80)  # darken, keep shadow detail
    a = smoothstep_contrast(a, 0.30)
    a = vignette(a, 0.38, radius=0.55, tint=(0.02, 0.03, 0.08))
    return to_img(a)

def look_atmosphere(im: Image.Image) -> Image.Image:
    """C â Atmosphere. Depth-of-field + cool recede + bloom. Most cinematic."""
    w, h = im.size
    im = im.filter(ImageFilter.GaussianBlur(max(1.2, (w + h) / 2 * 0.0045)))
    im = reduce_local_contrast(im, amt=0.35, radius=max(2.0, (w + h) / 2 * 0.01))
    a = to_arr(im)
    a = desaturate(a, 0.30)
    a = exposure(a, 0.86)
    a = split_tone(a, shadow_rgb=(0.10, 0.16, 0.42), hi_rgb=(0.52, 0.52, 0.58), amt=0.16)
    a = vignette(a, 0.30, radius=0.58, tint=(0.03, 0.04, 0.10))
    im = to_img(a)
    im = bloom(im, radius=max(6, (w + h) / 2 * 0.02), strength=0.06)
    return im

def look_complement_pop(im: Image.Image) -> Image.Image:
    """D â Complement Pop. Temperature opposition. Warms the BG so the cool
       cyan/blue/violet palette contrasts by hue. Bolder / riskier."""
    a = to_arr(im)
    a = smoothstep_contrast(a, 0.22)
    a = split_tone(a, shadow_rgb=(0.28, 0.18, 0.10), hi_rgb=(0.62, 0.50, 0.28), amt=0.20)
    a = saturate(a, 0.06)
    a = exposure(a, 0.92)
    a = vignette(a, 0.24, tint=(0.06, 0.03, 0.0))
    return to_img(a)

LOOKS = {
    "01_chroma_stage":    ("Chroma Stage",    look_chroma_stage),
    "02_deep_focus":      ("Deep Focus",      look_deep_focus),
    "03_atmosphere":      ("Atmosphere",      look_atmosphere),
    "04_complement_pop":  ("Complement Pop",  look_complement_pop),
}


def look_even_mix(im: Image.Image, weights=None) -> Image.Image:
    """E â Even Mix. Average all four look outputs (25% each by default).
       Balanced premium grade: moderate desat + darken, a subtle soft-glow
       from the 25% Atmosphere layer, near-neutral temperature, combined vignette."""
    arrs = [to_arr(fn(im)) for _, fn in LOOKS.values()]
    if weights is None:
        weights = [1.0 / len(arrs)] * len(arrs)
    w = np.array(weights, np.float32)
    w = w / w.sum()
    out = np.zeros_like(arrs[0])
    for a, wi in zip(arrs, w):
        out += a * wi
    return to_img(out)


# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# THE ULTIMATE GRADE  â asset-grounded, adaptive per-plate
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# Foreground reality (measured from assets/): bodies are WARM, bright, saturated
# (chocolate / tan / gold / pink / orange / white food); neon palette lives in
# the small cool eyes/accents. The ultimate background is therefore a COOL,
# DESATURATED, MID-KEY stage so warm bodies pop by temperature + chroma and
# bright cool eyes pop by luminance. Parameters adapt to each plate's measured
# brightness (L), saturation (S), busyness, and temperature (cool, pink).

def measure(im: Image.Image) -> dict:
    s = np.asarray(im.convert("RGB").resize((160, 160)), np.float32) / 255.0
    Lc = lum(s)
    mx = s.max(-1); mn = s.min(-1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return dict(
        L=float(Lc.mean()), S=float(sat.mean()), busy=float(Lc.std()),
        cool=float((s[..., 2] - s[..., 0]).mean()),
        pink=float(((s[..., 0] + s[..., 2]) / 2 - s[..., 1]).mean()),
    )

def ultimate_params(m: dict) -> dict:
    relu = lambda x: max(x, 0.0)
    L, S, busy, cool, pink = m["L"], m["S"], m["busy"], m["cool"], m["pink"]
    return dict(
        desat   = min(0.62, 0.30 + 0.40 * S),                       # below body chroma
        gain    = min(1.10, max(0.55, 0.34 / max(L, 0.06))),        # -> mid-key 0.34
        k       = min(0.22, max(0.08, 0.22 - 1.1 * (busy - 0.10))), # contrast (less if busy)
        blur    = 0.0,                                              # blur disabled (min) for all plates
        clarity = min(0.32, max(0.0, (busy - 0.14) * 2.2)),         # declutter busy only
        cool_amt= min(0.28, max(0.08, 0.14 + 0.18 * relu(-cool) / 0.20
                                      + 0.08 * relu(pink) / 0.17
                                      - 0.10 * relu(cool) / 0.50)),  # cool warm/pink plates most
        vig     = min(0.32, max(0.20, 0.20 + 0.16 * L)),
        bloom_s = min(0.06, max(0.03, 0.03 + 0.04 * L)),
    )

def look_ultimate(im: Image.Image, p: dict | None = None) -> Image.Image:
    if p is None:
        p = ultimate_params(measure(im))
    w, h = im.size
    avg = (w + h) / 2.0
    if p["blur"] > 0.05:
        im = im.filter(ImageFilter.GaussianBlur(p["blur"] * avg / 1343.0))
    if p["clarity"] > 0.01:
        im = reduce_local_contrast(im, p["clarity"], max(2.0, avg * 0.01))
    a = to_arr(im)
    a = desaturate(a, p["desat"])
    a = lift_gamma_gain(a, lift=-0.015, gamma=0.94, gain=p["gain"])
    a = smoothstep_contrast(a, p["k"])
    a = split_tone(a, shadow_rgb=(0.05, 0.13, 0.30), hi_rgb=(0.42, 0.52, 0.60), amt=p["cool_amt"])
    a = vignette(a, p["vig"], radius=0.58, tint=(0.02, 0.04, 0.10))
    im = to_img(a)
    im = bloom(im, radius=max(6, avg * 0.018), strength=p["bloom_s"])
    return im

def batch_ultimate(src_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(src_dir.glob("*.png"))
    log = ["# Ultimate Grade â per-plate adaptive parameters\n",
           "Asset-grounded cool/desaturated/mid-key stage. Originals untouched.\n",
           "| plate | desat | gain | cool | blur | vig |",
           "|---|---|---|---|---|---|"]
    print(f"Ultimate batch â {len(files)} plates -> {out_dir}")
    for i, p in enumerate(files, 1):
        im = Image.open(p).convert("RGB")
        prm = ultimate_params(measure(im))
        out = look_ultimate(im, prm).convert("RGB")
        src_rgba = Image.open(p)
        if src_rgba.mode == "RGBA":
            out = out.convert("RGBA"); out.putalpha(src_rgba.getchannel("A"))
        out.save(out_dir / p.name)
        log.append(f"| {p.stem} | {prm['desat']:.2f} | {prm['gain']:.2f} | "
                   f"{prm['cool_amt']:.2f} | {prm['blur']:.1f} | {prm['vig']:.2f} |")
        print(f"  [{i:2d}/{len(files)}] {p.name}")
    log_path = Path("background_pop_studies/GRADE1_GRADE_LOG.md")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log))
    print(f"done. log -> {log_path}")

# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# SAMPLE COMPARISON RENDER (vertical stack, mobile-friendly, palette chips)
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def _font(sz, bold=True):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else "")
    try:
        return ImageFont.truetype(p, sz)
    except Exception:
        return ImageFont.load_default(size=sz)

def draw_palette_strip(panel: Image.Image, h_frac=0.085):
    """Draw the 5 palette colours as chips along the bottom of a panel so the
       viewer can judge how the foreground palette separates from the grade."""
    w, h = panel.size
    ch = int(h * h_frac)
    cw = ch
    gap = int(cw * 0.28)
    total = len(PALETTE) * cw + (len(PALETTE) - 1) * gap
    x0 = (w - total) // 2
    y0 = h - ch - int(ch * 0.35)
    d = ImageDraw.Draw(panel, "RGBA")
    # subtle plate behind chips for consistent legibility of the chips themselves
    pad = int(ch * 0.30)
    d.rectangle([x0 - pad, y0 - pad, x0 + total + pad, y0 + ch + pad],
                fill=(0, 0, 0, 90))
    x = x0
    for _, rgb in PALETTE:
        d.rectangle([x, y0, x + cw, y0 + ch], fill=rgb + (255,),
                    outline=(255, 255, 255, 160), width=max(1, ch // 28))
        x += cw + gap
    return panel

def label_panel(panel: Image.Image, title: str, sub: str = ""):
    w, h = panel.size
    d = ImageDraw.Draw(panel, "RGBA")
    fs = max(20, w // 26)
    f = _font(fs)
    fsub = _font(int(fs * 0.62))
    pad = int(fs * 0.45)
    tw = d.textlength(title, font=f)
    bar_h = fs + (int(fs * 0.62) + pad if sub else 0) + pad * 2
    d.rectangle([0, 0, max(tw + pad * 2, w * 0.42), bar_h], fill=(0, 0, 0, 150))
    d.text((pad, pad), title, font=f, fill=(255, 255, 255, 255))
    if sub:
        d.text((pad, pad + fs + int(pad * 0.5)), sub, font=fsub, fill=(200, 220, 255, 255))
    return panel

def render_comparison(bg_path: Path, out_path: Path, panel_w=760, with_chips=True):
    src = Image.open(bg_path).convert("RGB")
    scale = panel_w / src.width
    src_s = src.resize((panel_w, int(src.height * scale)), Image.LANCZOS)
    ph = src_s.height

    panels = []
    orig = src_s.copy()
    label_panel(orig, "ORIGINAL", bg_path.stem)
    if with_chips:
        draw_palette_strip(orig)
    panels.append(orig)

    for key, (name, fn) in LOOKS.items():
        p = fn(src_s).convert("RGB")
        tag = key.split("_", 1)[0]
        label_panel(p, f"{tag} Â· {name}")
        if with_chips:
            draw_palette_strip(p)
        panels.append(p)

    gap = 10
    W = panel_w
    H = len(panels) * ph + (len(panels) - 1) * gap
    sheet = Image.new("RGB", (W, H), (16, 16, 20))
    y = 0
    for p in panels:
        sheet.paste(p, (0, y))
        y += ph + gap
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return out_path

# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
# BATCH
# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
def batch(look_key: str, src_dir: Path, out_dir: Path):
    name, fn = LOOKS[look_key]
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(src_dir.glob("*.png"))
    print(f"Batch '{look_key}' ({name}) â {len(files)} plates -> {out_dir}")
    for i, p in enumerate(files, 1):
        im = Image.open(p).convert("RGB")
        out = fn(im).convert("RGB")
        # preserve original RGBA alpha if present (plates are opaque, but be safe)
        src_rgba = Image.open(p)
        if src_rgba.mode == "RGBA":
            out = out.convert("RGBA")
            out.putalpha(src_rgba.getchannel("A"))
        out.save(out_dir / p.name)
        print(f"  [{i:2d}/{len(files)}] {p.name}")
    print("done.")

# âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Sweetardio background pop-grade. "
                    "`ultimate` regenerates all 56 graded plates.")
    ap.add_argument("mode", choices=["samples", "batch", "ultimate"])
    ap.add_argument("--src", default="traits/backgroundz_originals")
    ap.add_argument("--look", default="01_chroma_stage",
                    help="look key for `batch` mode (see LOOKS)")
    ap.add_argument("--out", default="background_pop_studies/grade1_out")
    ap.add_argument("--samples", nargs="*",
                    default=["Candy_Land", "Bubble_Trouble", "Celestial", "Ayotollah"])
    args = ap.parse_args()

    src = Path(args.src)
    if args.mode == "samples":
        outdir = Path("background_pop_studies/samples")
        for stem in args.samples:
            bp = src / f"{stem}.png"
            if not bp.exists():
                print("skip (missing):", bp); continue
            op = render_comparison(bp, outdir / f"compare_{stem}.png")
            print("wrote", op)
    elif args.mode == "ultimate":
        batch_ultimate(src, Path(args.out))
    else:
        batch(args.look, src, Path(args.out))
