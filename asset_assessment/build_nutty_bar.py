import sys, os
sys.path.insert(0, "asset_assessment"); sys.path.insert(0, ".")
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
import generator as g
from register_character import register, TARGET_HOLE_W
from clean_alpha import bleed

SRC = "/root/.claude/uploads/1e83c719-56de-5065-81fe-595a21a7928d/1785de4e-1000666748.png"

def build(drop=0, out_path=None):
    """drop: extra px of hole added BELOW the fitted ellipse's centre line."""
    src = Image.open(SRC).convert("RGBA")
    a = np.asarray(src); rgb = a[..., :3].astype(np.int16); al0 = a[..., 3]
    chroma = rgb.max(2) - rgb.min(2); lum = rgb.mean(2)
    checker = (chroma <= 10) & ((np.abs(lum-255) <= 14) | (np.abs(lum-227) <= 14))
    lab, n = ndimage.label(checker)
    border = set(lab[0].tolist())|set(lab[-1].tolist())|set(lab[:,0].tolist())|set(lab[:,-1].tolist())
    border.discard(0)
    outside = np.isin(lab, list(border))
    solid = ndimage.binary_fill_holes(~outside)
    slab, sn = ndimage.label(solid); ssz = ndimage.sum(solid, slab, range(1, sn+1))
    solid = slab == int(np.argmax(ssz))+1
    raw = ndimage.binary_fill_holes((al0 == 0) | (checker & solid))

    hy, hx = np.where(raw)
    cy, cx = hy.mean(), hx.mean()
    u = np.stack([hx-cx, hy-cy]); cov = (u @ u.T)/u.shape[1]
    w, v = np.linalg.eigh(cov); axes = 2*np.sqrt(w)
    Y, X = np.mgrid[0:g.CANVAS_SIZE, 0:g.CANVAS_SIZE]
    p = v.T @ np.stack([(X-cx).ravel(), (Y-cy).ravel()])
    px, py = p[0].reshape(Y.shape), p[1].reshape(Y.shape)
    # Extend the hole downward as the UNION of the fitted ellipse with a copy
    # of itself shifted down. Stretching the lower semi-axis instead kinks the
    # outline where the two halves meet; a union of two identical ellipses is
    # tangent-continuous down both sides.
    e = lambda dy: ((px/axes[0])**2 + ((py-dy)/axes[1])**2) <= 1
    hole = (e(0) | e(drop)) & solid
    keep = solid & ~hole

    band = (ndimage.binary_dilation(~solid, iterations=2) & solid) | \
           (ndimage.binary_dilation(hole, iterations=2) & solid)
    trusted = solid & ~checker & (al0 > 0) & ~band
    tmp = src.copy(); tmp.putalpha(Image.fromarray((trusted*255).astype(np.uint8)))
    tmp = bleed(tmp)
    alpha = Image.fromarray((keep*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))
    out = tmp.copy(); out.putalpha(alpha)
    reg, _ = register(out, hole, TARGET_HOLE_W)
    if out_path:
        reg.save(out_path)
    return reg
