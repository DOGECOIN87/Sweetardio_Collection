import math
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

TRAITS_DIR = Path("traits")
OUTPUT_DIR = Path("trait_sheets")

OUTPUT_DIR.mkdir(exist_ok=True)

IMAGE_EXTS = {".png", ".webp", ".jpg", ".jpeg"}

for category in sorted([p for p in TRAITS_DIR.iterdir() if p.is_dir()]):

    images = []

    for file in sorted(category.iterdir()):
        if file.suffix.lower() not in IMAGE_EXTS:
            continue

        try:
            img = Image.open(file).convert("RGBA")
            images.append((file.stem, img))
        except:
            pass

    if not images:
        continue

    thumb_size = 256

    cols = math.ceil(math.sqrt(len(images)))
    rows = math.ceil(len(images) / cols)

    sheet = Image.new(
        "RGBA",
        (
            cols * thumb_size,
            rows * thumb_size
        ),
        (25,25,25,255)
    )

    for idx, (name, img) in enumerate(images):

        img.thumbnail(
            (
                thumb_size - 10,
                thumb_size - 30
            )
        )

        cell = Image.new(
            "RGBA",
            (
                thumb_size,
                thumb_size
            ),
            (35,35,35,255)
        )

        x = (thumb_size - img.width) // 2
        y = 10

        cell.alpha_composite(img, (x, y))

        draw = ImageDraw.Draw(cell)

        draw.text(
            (5, thumb_size - 18),
            name[:28],
            fill="white"
        )

        col = idx % cols
        row = idx // cols

        sheet.alpha_composite(
            cell,
            (
                col * thumb_size,
                row * thumb_size
            )
        )

    out_file = OUTPUT_DIR / f"{category.name}_sheet.png"

    sheet.save(out_file)

    print(f"Created: {out_file}")

print("\\nDone.")
