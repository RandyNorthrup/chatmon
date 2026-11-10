"""Make the app icons the installers use, from the penguin's first idle frame (the tray icon's picture).

Usage: python packaging/make_icons.py      (needs Pillow; writes packaging/icons, which is committed)

- chatmon.ico   Windows: the programs, shortcuts and installer, 16 to 256 px
- chatmon.icns  macOS: the app bundle, 16 to 1024 px
- chatmon-N.png Linux: the hicolor icon theme, 48 to 512 px
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ANIM = ROOT / "chatmon" / "anim"
OUT = Path(__file__).resolve().parent / "icons"
MARGIN = 0.06  # of the square, on each side
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
PNG_SIZES = [48, 64, 128, 256, 512]


def penguin() -> Image.Image:
    """The first idle frame, cut to the penguin, on a transparent square."""
    info = json.loads((ANIM / "manifest.json").read_text(encoding="utf-8"))["idle"]
    strip = Image.open(ANIM / "idle.png").convert("RGBA")
    frame = strip.crop((0, 0, info["w"], info["h"]))
    frame = frame.crop(frame.getchannel("A").getbbox())
    side = round(max(frame.size) / (1 - 2 * MARGIN))
    square = Image.new("RGBA", (side, side))
    square.alpha_composite(frame, ((side - frame.width) // 2, (side - frame.height) // 2))
    return square


def sized(image: Image.Image, px: int) -> Image.Image:
    return image.resize((px, px), Image.Resampling.LANCZOS)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    art = penguin()
    big = sized(art, 1024)  # the frame is 240 px high: larger sizes are drawn up from it
    big.save(OUT / "chatmon.ico", sizes=[(s, s) for s in ICO_SIZES])
    big.save(OUT / "chatmon.icns")
    for px in PNG_SIZES:
        sized(art, px).save(OUT / f"chatmon-{px}.png", optimize=True)
    for path in sorted(OUT.iterdir()):
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
