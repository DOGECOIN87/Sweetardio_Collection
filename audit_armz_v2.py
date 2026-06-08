import cv2
import numpy as np
import pandas as pd
from pathlib import Path

ARMZ_DIR = Path("traits/armz")
results = []

def analyze_lighting(img):
    if img.shape[2] == 4:
        alpha = img[:, :, 3]
        rgb = img[:, :, :3]
        mask = alpha > 10
    else:
        rgb = img
        mask = np.ones(rgb.shape[:2], dtype=bool)

    gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    tl_mask = np.zeros_like(mask); tl_mask[:h//2, :w//2] = True
    tr_mask = np.zeros_like(mask); tr_mask[:h//2, w//2:] = True
    bl_mask = np.zeros_like(mask); bl_mask[h//2:, :w//2] = True
    br_mask = np.zeros_like(mask); br_mask[h//2:, w//2:] = True

    def safe_mean(region):
        vals = gray[region & mask]
        return vals.mean() if len(vals) else 0

    tl = safe_mean(tl_mask)
    tr = safe_mean(tr_mask)
    bl = safe_mean(bl_mask)
    br = safe_mean(br_mask)

    score = 100

    if tl <= tr: score -= 25
    if tl <= bl: score -= 25
    if br >= tl: score -= 25
    if br >= bl: score -= 25

    return max(0, score)

for file in ARMZ_DIR.glob("*.png"):
    img = cv2.imread(str(file), cv2.IMREAD_UNCHANGED)
    if img is None:
        continue

    score = analyze_lighting(img)

    if score >= 90:
        status = "PASS"
    elif score >= 75:
        status = "LIKELY_PASS"
    elif score >= 50:
        status = "RELIGHT"
    else:
        status = "REWORK"

    results.append({
        "asset": file.name,
        "lighting_score": score,
        "status": status
    })

df = pd.DataFrame(results)

Path("qa_reports").mkdir(exist_ok=True)
df.to_csv("qa_reports/armz_lighting_v2.csv", index=False)

print(df.sort_values("lighting_score"))
