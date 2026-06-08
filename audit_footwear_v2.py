import cv2
import numpy as np
import pandas as pd
from pathlib import Path

FOOT_DIR = Path("traits/what_are_thosez")

results = []

def analyze_base(img):
    if img.shape[2] == 4:
        alpha = img[:, :, 3]
        rgb = img[:, :, :3]
        mask = alpha > 10
    else:
        rgb = img
        mask = np.ones(rgb.shape[:2], dtype=bool)

    gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)

    h, w = gray.shape

    left_mask = np.zeros_like(mask)
    left_mask[:, :w//2] = True

    right_mask = np.zeros_like(mask)
    right_mask[:, w//2:] = True

    top_mask = np.zeros_like(mask)
    top_mask[:h//2, :] = True

    bottom_mask = np.zeros_like(mask)
    bottom_mask[h//2:, :] = True

    def safe_mean(region):
        vals = gray[region & mask]
        return vals.mean() if len(vals) else 0

    left = safe_mean(left_mask)
    right = safe_mean(right_mask)

    top = safe_mean(top_mask)
    bottom = safe_mean(bottom_mask)

    score = 100

    if left <= right:
        score -= 25

    if bottom >= top:
        score -= 25

    return max(0, score)

for file in FOOT_DIR.glob("*Base*.png"):

    img = cv2.imread(str(file), cv2.IMREAD_UNCHANGED)

    if img is None:
        continue

    score = analyze_base(img)

    if score >= 90:
        status = "PASS"
    elif score >= 75:
        status = "LIKELY_PASS"
    elif score >= 50:
        status = "MANUAL_REVIEW"
    else:
        status = "REWORK"

    results.append({
        "asset": file.name,
        "lighting_score": score,
        "status": status
    })

df = pd.DataFrame(results)

Path("qa_reports").mkdir(exist_ok=True)

df.to_csv(
    "qa_reports/footwear_base_lighting.csv",
    index=False
)

print(df.sort_values("lighting_score"))
