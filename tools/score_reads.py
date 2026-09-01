"""Score a rendered token for how well it READS, not how many traits it has.

The owner's reference (a flooded Twinkie) is a bold silhouette popping off a
quiet background with the weather clearly visible. The opposite -- what the
film was picking -- is a token buried under a saber, slippers and a busy
plate. Both are measurable:

  POP    mean CIE76 dE between the character's own pixels and the ring of
         plate immediately around it. High = the silhouette separates.
  CALM   band-pass energy of the plate the character does NOT cover, the
         same |blur(8)-blur(40)| the compositor already uses to decide how
         hard SUBJECT_SEPARATION has to work. Low = the background is not
         fighting the character.
  FILL   how much of the frame the character occupies. Too small reads as
         lost, too large as cropped.
"""
import json, os, sys
sys.path.insert(0, '.')
import numpy as np
from PIL import Image, ImageFilter
import generator as g

IMAGES, MASKS = "output/mint/images", "output/mint/masks"

def rgb2lab(a):
    a = a.astype(np.float64) / 255.0
    a = np.where(a > .04045, ((a + .055) / 1.055) ** 2.4, a / 12.92)
    m = np.array([[.4124,.3576,.1805],[.2126,.7152,.0722],[.0193,.1192,.9505]])
    xyz = a @ m.T / np.array([.95047, 1.0, 1.08883])
    f = np.where(xyz > .008856, np.cbrt(xyz), 7.787 * xyz + 16/116)
    return np.stack([116*f[...,1]-16, 500*(f[...,0]-f[...,1]),
                     200*(f[...,1]-f[...,2])], -1)

def score(tid):
    ip = os.path.join(IMAGES, f"{tid}.png"); mp = os.path.join(MASKS, f"{tid}.png")
    if not (os.path.exists(ip) and os.path.exists(mp)): return None
    im = Image.open(ip).convert("RGB").resize((464, 464), Image.Resampling.LANCZOS)
    mk = Image.open(mp).convert("L").resize((464, 464), Image.Resampling.LANCZOS)
    a = np.asarray(im); m = np.asarray(mk) >= 128
    if m.sum() < 500: return None
    lab = rgb2lab(a)
    grown = np.asarray(mk.filter(ImageFilter.MaxFilter(21))) >= 128
    ring = grown & ~m
    if ring.sum() < 200: return None
    pop = float(np.linalg.norm(lab[m].mean(0) - lab[ring].mean(0)))
    grey = im.convert("L")
    band = np.abs(np.asarray(grey.filter(ImageFilter.GaussianBlur(3)), float)
                  - np.asarray(grey.filter(ImageFilter.GaussianBlur(14)), float))
    busy = float(band[~m].mean())
    fill = float(m.mean())
    return dict(pop=pop, busy=busy, fill=fill)

man = {int(k): v for k, v in json.load(open('output/mint_manifest.json')).items()}
have = sorted(int(f[:-4]) for f in os.listdir(IMAGES) if f.endswith('.png'))
rows = []
for t in have:
    s = score(t)
    if s: s['tid'] = t; rows.append(s)
pops = np.array([r['pop'] for r in rows]); busys = np.array([r['busy'] for r in rows])
fills = np.array([r['fill'] for r in rows])
def nrm(v, arr): return (v - arr.min()) / max(float(np.ptp(arr)), 1e-6)
for r in rows:
    # reads-well = pops off the plate, quiet plate, sensibly sized
    r['read'] = (0.5 * nrm(r['pop'], pops)
                 + 0.35 * (1 - nrm(r['busy'], busys))
                 + 0.15 * (1 - abs(r['fill'] - 0.20) / 0.20))
rows.sort(key=lambda r: -r['read'])
json.dump({str(r['tid']): r for r in rows}, open(
    "/tmp/claude-0/-home-user-Sweetardio-Collection/1a35e559-9834-529a-a8ed-77f0f6bd0f3a/scratchpad/read_scores.json","w"))
print(f"{'tid':>6} {'read':>5} {'pop':>6} {'busy':>6} {'fill':>5}  traits")
for r in rows[:14]:
    t = r['tid']; v = man[t]
    extra = sum(1 for k in ('arm','wat','sticker') if v.get(k))
    print(f"  #{t:<5d} {r['read']:.2f} {r['pop']:6.1f} {r['busy']:6.2f} "
          f"{r['fill']:.2f}  +{extra}")
print("  ...")
for r in rows[-5:]:
    t = r['tid']; v = man[t]
    extra = sum(1 for k in ('arm','wat','sticker') if v.get(k))
    print(f"  #{t:<5d} {r['read']:.2f} {r['pop']:6.1f} {r['busy']:6.2f} "
          f"{r['fill']:.2f}  +{extra}")
