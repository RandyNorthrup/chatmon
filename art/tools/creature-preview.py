"""Previews of the companions as the app draws them: its own sprite code, at the size on screen.

Usage: python creature-preview.py <out-dir> [<companion> ...] [--size 120]
  out-dir    where the previews go
  companion  which to render (default: all five, the penguin included)
Per companion it writes
  <id>-all.webp      every animation in turn, named, on a dark desktop (#1e2128), at the manifest's
                     frame rates; walk and beam also mirrored, as the app shows them facing left
  <id>-light.webp    the same on a light desktop (#e9ebf0)
  <id>-contact.png   every frame of every strip at 2x (drawn for a 2x screen), on dark and on light
The frames come from chatmon.sprites.Sprites and are placed as the stage places them: the
anchor on one spot of the floor, the frame's bottom edge on the floor line. Run it with
QT_QPA_PLATFORM=offscreen; nothing opens on the desktop. Needs PyQt6, Pillow and numpy.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PyQt6.QtCore import QPoint  # noqa: E402
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from chatmon import companions  # noqa: E402
from chatmon.sprites import SIDE_VIEWS, Sprites  # noqa: E402

DARK, LIGHT = "#1e2128", "#e9ebf0"
MIN_PLAY = 1.6  # seconds: short loops go round until they have played this long
HOLD = 0.5  # seconds a one-off rests on its last frame


def _array(img: QImage) -> np.ndarray:
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    return np.frombuffer(bytes(ptr), np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)[:, : img.width(), :3].copy()


def _label(img: Image.Image, at: tuple[int, int], text: str, colour: str, px: int) -> None:
    """Labels are drawn with Pillow's own font: an offscreen Qt has none on some systems."""
    ImageDraw.Draw(img).text(at, text, fill=colour, font=ImageFont.load_default(px))


def movie(sprites: Sprites, background: str, title: str) -> tuple[list[Image.Image], list[int]]:
    """Every animation in turn, as frames and their durations in ms."""
    widest = max(f.width() for fs in sprites._frames.values() for f in fs)
    width, top = widest * 2 + 24, 30
    height = top + sprites.height + 28
    floor, x = top + sprites.height + 4, width // 2
    ink = "#e9ebf0" if background == DARK else "#1e2128"
    frames, times = [], []
    for anim, (count, fps, loop) in sprites.anims().items():
        for mirror in (False, True) if anim in SIDE_VIEWS else (False,):
            order = list(range(count))
            if loop:
                order *= max(1, int(np.ceil(MIN_PLAY * fps / count)))
            for step, index in enumerate(order):
                sprite = sprites.frame(anim, index, mirror)
                img = QImage(width, height, QImage.Format.Format_RGB32)
                img.fill(QColor(background))
                p = QPainter(img)
                p.fillRect(0, floor, width, 1, QColor(ink if background == DARK else "#b8bcc6"))
                p.drawPixmap(QPoint(x - sprite.anchor, floor - sprite.height()), sprite.pixmap)
                p.end()
                frame = Image.fromarray(_array(img))
                _label(frame, (8, 6), f"{title}   {anim}{' (facing left)' if mirror else ''}   {index + 1}/{count}   {fps:g} fps", ink, 13)
                frames.append(frame)
                last = not loop and step == len(order) - 1
                times.append(round(1000 / fps) + (round(HOLD * 1000) if last else 0))
    return frames, times


def contact(sprites: Sprites, title: str) -> Image.Image:
    """Every frame of every strip, drawn for a 2x screen, on dark and on light."""
    cell_w = max(f.image.width() for fs in sprites._frames.values() for f in fs) + 12
    row_h = max(f.image.height() for fs in sprites._frames.values() for f in fs) + 40
    anims = sprites.anims()
    cols = max(count for count, _, _ in anims.values())
    width, block = 16 + cols * cell_w, 36 + len(anims) * row_h
    img = QImage(width, block * 2, QImage.Format.Format_RGB32)
    p = QPainter(img)
    labels = []
    for half, (background, ink) in enumerate(((DARK, "#e9ebf0"), (LIGHT, "#1e2128"))):
        y0 = half * block
        p.fillRect(0, y0, width, block, QColor(background))
        labels.append(((10, y0 + 6), f"{title}: every frame as drawn on a 2x screen", ink, 20))
        for row, (anim, (count, fps, loop)) in enumerate(anims.items()):
            floor = y0 + 36 + (row + 1) * row_h - 8
            labels.append(((10, floor - row_h + 12), f"{anim}   {count} frames, {fps:g} fps{', loops' if loop else ''}", ink, 16))
            p.fillRect(8, floor, width - 16, 1, QColor("#5a6070" if background == DARK else "#b8bcc6"))
            for i in range(count):  # an animation's frames are one width: side by side they line up as on screen
                sprite = sprites.frame(anim, i, False)
                p.drawImage(QPoint(8 + i * cell_w + (cell_w - sprite.image.width()) // 2, floor - sprite.image.height()), sprite.image)
    p.end()
    sheet = Image.fromarray(_array(img))
    for at, text, ink, px in labels:
        _label(sheet, at, text, ink, px)
    return sheet


def main(argv: list[str]) -> None:
    args = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--size")]
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 120
    if not args:
        sys.exit(__doc__)
    out = args[0]
    os.makedirs(out, exist_ok=True)
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    for name in args[1:] or list(companions.COMPANIONS):
        companion = companions.COMPANIONS[name]
        sprites = Sprites(companion.anim_dir(), size, 1.0)
        for background, suffix in ((DARK, "all"), (LIGHT, "light")):
            frames, times = movie(sprites, background, companion.label)
            path = os.path.join(out, f"{companion.id}-{suffix}.webp")
            frames[0].save(path, save_all=True, append_images=frames[1:], duration=times, loop=0, lossless=True, method=4)
            print(path, f"{len(frames)} frames, {sum(times) / 1000:.1f} s, {frames[0].width}x{frames[0].height}")
        sheet = contact(Sprites(companion.anim_dir(), size, 2.0), companion.label)
        path = os.path.join(out, f"{companion.id}-contact.png")
        sheet.save(path, optimize=True)
        print(path, f"{sheet.width}x{sheet.height}")
    del app


if __name__ == "__main__":
    main(sys.argv[1:])
