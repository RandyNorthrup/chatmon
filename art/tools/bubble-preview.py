"""Render the painted chat bubbles, animated, with real text and buttons, to check them by eye.

usage: python art/tools/bubble-preview.py OUT_DIR [--only electric,fire] [--max-seconds 60]

Writes <style>-dark.webp and <style>-light.webp (and the same as .gif): the bubble over a dark and a light
desktop at real size and real speed, one full cycle that loops (a cycle longer than --max-seconds is cut
short and then is not a loop; the leaf bubble's is about 34 s, its caterpillar's whole walk); contact.png,
every style at four moments on both backgrounds; and still.png, every style with animation off. The .webp
is the one to judge by: a .gif has 256 colours, which bands the soft glows. Needs PyQt6 and Pillow; runs
without a display (Qt's offscreen platform).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":  # the offscreen platform has no fonts of its own
    os.environ.setdefault("QT_QPA_FONTDIR", str(Path(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image, ImageDraw  # noqa: E402
from PyQt6.QtCore import QRectF, QSizeF, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QImage, QPainter, QPen  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

BACKGROUNDS = {"dark": "#1e2128", "light": "#e9ebf0"}
FPS = 30
TEXT = (300, 92)  # the text area of the sample message, display px


def draw_content(p: QPainter, style, area: QRectF) -> None:
    """The sample message, in the style's own text and button colours."""
    title_c, body_c = style.text_colours()
    title = QFont(QApplication.font())
    title.setPointSizeF(11.5)
    title.setBold(True)
    body = QFont(QApplication.font())
    body.setPointSizeF(10.5)
    p.setPen(title_c)
    p.setFont(title)
    p.drawText(area, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "Sparky")
    p.setFont(body)
    p.drawText(area, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, "✕")
    p.setPen(body_c)
    th = QFontMetricsF(title).height()
    p.drawText(
        area.adjusted(0, th + 6, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, "Your build finished. All 98 tests passed."
    )
    bm = QFontMetricsF(body)
    x = area.right()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for label, look in (("Later", style.other), ("Open", style.primary)):
        w = bm.horizontalAdvance(label) + 28
        r = QRectF(x - w, area.bottom() - (bm.height() + 10), w, bm.height() + 10)
        p.setBrush(QColor(look.fill))
        p.setPen(QPen(QColor(look.outline), 1.6))
        p.drawRoundedRect(r.adjusted(0.8, 0.8, -0.8, -0.8), r.height() / 2, r.height() / 2)
        p.setPen(QColor(look.text))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, label)
        x -= w + 8


def layer(art, style, text: QSizeF, t: float, animate: bool = True, content: bool = True) -> Image.Image:
    """The bubble at time `t` on a transparent image, drawn by the app's own code."""
    frame = art.frame_for(text)
    w, h = round(frame.size.width()) + 8, round(frame.size.height()) + 8
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    lo, hi = art.tail_range(text.width())
    art.paint(p, 4, 4, text, lo + (hi - lo) * 0.35, t, animate)
    if content:
        draw_content(p, style, frame.text.translated(4, 4))
    p.end()
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    return Image.frombuffer("RGBA", (w, h), bytes(img.constBits().asarray(img.sizeInBytes())), "raw", "RGBA", 0, 1).copy()


def over(rgba: Image.Image, background: str) -> Image.Image:
    return Image.alpha_composite(Image.new("RGBA", rgba.size, background), rgba).convert("RGB")


def start_app() -> QApplication:
    app = QApplication(sys.argv[:1])
    for family in ("Segoe UI", "Cantarell", "Noto Sans", "DejaVu Sans", "Helvetica Neue"):
        if family in QFontDatabase.families():
            app.setFont(QFont(family, 9))
            break
    return app


def main() -> None:
    out = Path(sys.argv[1])
    longest = float(sys.argv[sys.argv.index("--max-seconds") + 1]) if "--max-seconds" in sys.argv else 60.0
    out.mkdir(parents=True, exist_ok=True)
    app = start_app()  # noqa: F841 (kept alive while drawing)
    from penguin_companion import bubbleart, styles

    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else [s for s in styles.STYLES if s != "plain"]
    text = QSizeF(*TEXT)
    rows, stills = [], []
    for name in only:
        art, style = bubbleart.art(name), styles.get(name)
        if art is None:
            print(name, "has no art yet")
            continue
        period = art.loop_period(text)
        seconds = min(period, longest)
        frames = [layer(art, style, text, i / FPS) for i in range(round(seconds * FPS))]
        for bg_name, bg in BACKGROUNDS.items():
            flat = [over(f, bg) for f in frames]
            thirds = [(33, 33, 34)[i % 3] for i in range(len(flat))]  # whole milliseconds that add up to 30 a second
            flat[0].save(out / f"{name}-{bg_name}.webp", save_all=True, append_images=flat[1:], duration=thirds, loop=0, quality=92)
            # A GIF's frame times are whole hundredths of a second: 30, 30, 40 ms averages the 33.3 ms of 30 fps.
            times = [(30, 30, 40)[i % 3] for i in range(len(flat))]
            flat[0].save(out / f"{name}-{bg_name}.gif", save_all=True, append_images=flat[1:], duration=times, loop=0)
            rows.append((f"{name} ({bg_name}), cycle {period:.1f} s", [flat[round(i * (len(flat) - 1) / 3.5)] for i in range(4)]))
        stills.append(over(layer(art, style, text, 0.0, animate=False), BACKGROUNDS["dark"]))
        print(f"{name}: cycle {period:.2f} s, {len(frames)} frames written")
    if rows:
        cw = max(i.width for _, imgs in rows for i in imgs)
        ch = max(i.height for _, imgs in rows for i in imgs)
        sheet = Image.new("RGB", (cw * 4, (ch + 18) * len(rows)), "#101114")
        d = ImageDraw.Draw(sheet)
        for r, (label, imgs) in enumerate(rows):
            d.text((6, r * (ch + 18) + 2), label, fill="#d0d4dc")
            for c, im in enumerate(imgs):
                sheet.paste(im, (c * cw, r * (ch + 18) + 16))
        sheet.save(out / "contact.png")
        strip = Image.new("RGB", (max(s.width for s in stills), sum(s.height for s in stills)), "#1e2128")
        y = 0
        for s in stills:
            strip.paste(s, (0, y))
            y += s.height
        strip.save(out / "still.png")
    print("wrote", out)


if __name__ == "__main__":
    main()
