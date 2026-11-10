"""Render every chat bubble style, animated, to check them by eye.

usage: python art/tools/bubble-preview.py OUT_DIR [--seconds 3]

Writes, for each style, <style>-dark.gif and <style>-light.gif (the bubble
popping up and its rim effect running, over a dark and a light desktop), and
contact.png: every style at eight moments, on both backgrounds. Needs PyQt6 and
Pillow; runs without a display (it uses Qt's offscreen platform).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt" and Path(os.environ.get("WINDIR", r"C:\Windows"), "Fonts").is_dir():  # the offscreen platform has no fonts of its own
    os.environ.setdefault("QT_QPA_FONTDIR", str(Path(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image, ImageDraw  # noqa: E402
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

BACKGROUNDS = {"dark": "#1e2128", "light": "#e9ebf0"}
MOMENTS = (0.04, 0.1, 0.18, 0.3, 0.6, 1.0, 1.6, 2.4)
FPS = 30


def render(bubble, style, t: float, background: str) -> Image.Image:
    m = bubble.margins()
    pad = 6
    width = int(bubble.size.width() + m.left() + m.right()) + 2 * pad
    height = int(bubble.size.height() + m.top() + m.bottom()) + 2 * pad
    # Drawn on a transparent image, then laid over the desktop colour, the
    # way the compositor shows the companion's see-through window.
    img = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.translate(m.left() + pad, m.top() + pad)
    bubble.paint(p, bubble.size.width() * 0.5, t)
    p.end()
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    layer = Image.frombuffer("RGBA", (width, height), bytes(img.constBits().asarray(img.sizeInBytes())), "raw", "RGBA", 0, 1)
    return Image.alpha_composite(Image.new("RGBA", (width, height), background), layer).convert("RGB")


def main() -> None:
    out = Path(sys.argv[1])
    seconds = float(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 3.0
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    families = QFontDatabase.families()
    for family in ("Segoe UI", "Cantarell", "Noto Sans", "DejaVu Sans", "Helvetica Neue"):  # the offscreen platform picks an odd default
        if family in families:
            app.setFont(QFont(family, 9))
            break
    from penguin_companion import styles
    from penguin_companion.bubble import SpeechBubble

    rows = []
    for name, style in styles.STYLES.items():
        bubble = SpeechBubble()
        bubble.set_style(style, True)
        bubble.show("Sparky", "Your build finished: **all 98 tests passed**. Want me to open the report?", [("Open", None), ("Later", None)], None, 0.0)
        for bg_name, bg in BACKGROUNDS.items():
            frames = [render(bubble, style, i / FPS, bg) for i in range(int(seconds * FPS))]
            frames[0].save(out / f"{name}-{bg_name}.gif", save_all=True, append_images=frames[1:], duration=round(1000 / FPS), loop=0)
            rows.append((f"{style.label} ({bg_name})", [render(bubble, style, t, bg) for t in MOMENTS]))
    cell_w = max(img.width for _, imgs in rows for img in imgs)
    cell_h = max(img.height for _, imgs in rows for img in imgs)
    sheet = Image.new("RGB", (cell_w * len(MOMENTS), (cell_h + 18) * len(rows) + 22), "#101114")
    draw = ImageDraw.Draw(sheet)
    draw.text((6, 4), "Bubble styles at " + ", ".join(f"{t:g}s" for t in MOMENTS), fill="#d0d4dc")
    for r, (label, imgs) in enumerate(rows):
        y = 22 + r * (cell_h + 18)
        draw.text((6, y + 2), label, fill="#d0d4dc")
        for c, img in enumerate(imgs):
            sheet.paste(img, (c * cell_w, y + 16))
    sheet.save(out / "contact.png")
    print("wrote", out)


if __name__ == "__main__":
    main()
