"""Before/after contact sheet of the built mockups (needs Pillow)."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

from screenshot import FONT

ROWS = [("meridian-plaza-80x24-256-before", "meridian-plaza-80x24-256", "Meridian Plaza 80x24"),
        ("clinic-row-80x24-256-before", "clinic-row-80x24-256", "Clinic Row 80x24"),
        ("lattice-vatside-80x24-256-before", "lattice-vatside-80x24-256", "Vatside sector, jacked in, 80x24")]
TIERS = ["meridian-plaza-80x24-16", "clinic-row-80x24-16", "lattice-vatside-80x24-16"]


def main(folder: Path) -> None:
    w, h, gap, cap = 720, 432, 24, 28
    rows = len(ROWS) + 1
    sheet = Image.new("RGB", (2 * w + gap, rows * (h + cap + gap)), (28, 28, 28))
    draw = ImageDraw.Draw(sheet)
    for i, (before, after, title) in enumerate(ROWS):
        y = i * (h + cap + gap)
        draw.text((0, y + 4), f"{title}: shipped renderer (main)", font=FONT, fill=(200, 200, 200))
        draw.text((w + gap, y + 4), f"{title}: proposal, same game state", font=FONT, fill=(255, 255, 255))
        sheet.paste(Image.open(folder / f"{before}.png"), (0, y + cap))
        sheet.paste(Image.open(folder / f"{after}.png"), (w + gap, y + cap))
    y = len(ROWS) * (h + cap + gap)
    draw.text((0, y + 4), "16-colour tier of the proposal (Plaza, Clinic Row)", font=FONT, fill=(200, 200, 200))
    for j, name in enumerate(TIERS[:2]):
        sheet.paste(Image.open(folder / f"{name}.png"), (j * (w + gap), y + cap))
    sheet.save(folder / "before-after.png")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
