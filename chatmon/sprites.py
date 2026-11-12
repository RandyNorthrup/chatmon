"""The animation strips, cut into frames and scaled for the screen once.

Frames are scaled to the screen's real pixels (`scale`: device pixels per
logical pixel, 2 on a 2x screen), so the penguin is as sharp as the art
allows; sizes, hit tests and outlines stay in logical pixels.

Every companion (companions.py) has its own folder of strips and manifest;
`Sprites` loads the one folder it is given.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QImage, QPainter, QPixmap, QTransform

# Animations drawn side-on (facing right), mirrored to face left.
SIDE_VIEWS = {"walk", "beam"}
OPAQUE = 40  # alpha above which a pixel counts as part of the penguin
BAND = 4  # rows per rectangle in a frame's outline


@dataclass
class SpriteFrame:
    pixmap: QPixmap  # device pixels, with its device pixel ratio set
    image: QImage  # the same, for exact hit tests
    anchor: int  # x of the penguin's centre line within the frame (logical)
    outline: list[QRect]  # the opaque area as a few rectangles, for click-through (logical)
    scale: float = 1.0  # device pixels per logical pixel
    rects: tuple[tuple[int, int, int, int], ...] = ()  # the outline as plain (x, y, w, h): cheap to move every frame

    def __post_init__(self) -> None:
        self.rects = tuple((r.x(), r.y(), r.width(), r.height()) for r in self.outline)

    def width(self) -> int:
        return round(self.image.width() / self.scale)

    def height(self) -> int:
        return round(self.image.height() / self.scale)

    def hit(self, x: int, y: int) -> bool:
        """Whether the penguin is at (x, y), logical pixels within the frame."""
        dx, dy = int(x * self.scale), int(y * self.scale)
        if not (0 <= dx < self.image.width() and 0 <= dy < self.image.height()):
            return False
        return self.image.pixelColor(dx, dy).alpha() > OPAQUE


@dataclass
class AnimInfo:
    frames: int
    fps: float
    loop: bool


def _alpha_rows(img: QImage) -> list[bytes]:
    w, bpl = img.width(), img.bytesPerLine()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    data = bytes(ptr)
    return [data[y * bpl + 3 : y * bpl + 4 * w : 4] for y in range(img.height())]


def _foot_centre(img: QImage) -> float:
    """Mean x of the opaque pixels in the bottom quarter: where the feet are,
    which stays put when a beam or an aura sticks out to one side."""
    rows = _alpha_rows(img)
    total = count = 0
    for alphas in rows[len(rows) * 3 // 4 :]:
        for x, a in enumerate(alphas):
            if a > OPAQUE:
                total += x
                count += 1
    return total / count if count else img.width() / 2


_SOLID = bytes(1 if a > OPAQUE else 0 for a in range(256))  # an alpha byte to 1 where it counts as the penguin


def _outline(img: QImage) -> list[QRect]:
    rows = _alpha_rows(img)
    rects = []
    for top in range(0, len(rows), BAND):
        left, right = img.width(), -1
        for alphas in rows[top : top + BAND]:
            solid = alphas.translate(_SOLID)  # bytes, at C speed: a frame has some fifty thousand pixels
            first = solid.find(1)
            if first >= 0:
                left, right = min(left, first), max(right, solid.rfind(1))
        if right >= left:
            rects.append(QRect(left - 1, top, right - left + 3, min(BAND, len(rows) - top)))
    return rects


def _frame(img: QImage, anchor: int, scale: float) -> SpriteFrame:
    pixmap = QPixmap.fromImage(img)
    pixmap.setDevicePixelRatio(scale)
    outline = []
    for r in _outline(img):  # device pixels to logical, rounding outward
        left, top = int(r.left() / scale), int(r.top() / scale)
        right, bottom = -int(-(r.right() + 1) // scale), -int(-(r.bottom() + 1) // scale)
        outline.append(QRect(left, top, right - left, bottom - top))
    return SpriteFrame(pixmap, img, anchor, outline, scale)


def silhouette(frame: SpriteFrame) -> QPixmap:
    """The frame's shape in black, cut to the pixels it covers: what macOS's menu bar takes as a template
    image, which it draws in its own colour, light or dark as the menu bar is."""
    img = frame.image
    bounds = QRect()
    for r in _outline(img):  # device pixels
        bounds = bounds.united(r)
    bounds = bounds.intersected(img.rect())
    if bounds.isEmpty():
        bounds = img.rect()
    out = img.copy(bounds).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(out)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)  # keep each pixel's alpha, black
    p.fillRect(out.rect(), Qt.GlobalColor.black)
    p.end()
    pixmap = QPixmap.fromImage(out)
    pixmap.setDevicePixelRatio(frame.scale)
    return pixmap


class Sprites:
    """One companion's animations, scaled for the screen. Each is cut into frames the first time one of its
    frames is asked for (`load_next` cuts the rest ahead, a little at a time): cutting all of them at once
    took seconds at every start, and again whenever the screen's scale or the companion changed."""

    def __init__(self, anim_dir: Path, size: int, scale: float = 1.0):
        self.scale = scale = max(0.5, float(scale))
        self._dir, self._size = anim_dir, size
        self._manifest = json.loads((anim_dir / "manifest.json").read_text(encoding="utf-8"))
        self.info: dict[str, AnimInfo] = {
            name: AnimInfo(int(m["frames"]), float(m["fps"]), bool(m["loop"])) for name, m in self._manifest.items()
        }
        self._frames: dict[tuple[str, bool], list[SpriteFrame]] = {}
        heights = []
        for m in self._manifest.values():
            factor = float(m.get("scale", 1.0)) * size / int(m["h"])
            heights.append(round(max(1, round(int(m["h"]) * factor * scale)) / scale))
        self.height = max(heights)

    def load_next(self) -> bool:
        """Cut the next animation not cut yet; False when they all are."""
        for name in self._manifest:
            if (name, False) not in self._frames:
                self._load(name)
                return True
        return False

    def _load(self, name: str) -> None:
        m, anim_dir, size, scale = self._manifest[name], self._dir, self._size, self.scale
        flip = QTransform().scale(-1, 1)
        strip = QImage(str(anim_dir / f"{name}.png")).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        w, h = int(m["w"]), int(m["h"])
        factor = float(m.get("scale", 1.0)) * size / h  # art pixels to logical
        dw, dh = max(1, round(w * factor * scale)), max(1, round(h * factor * scale))
        # Where the floor pins the frame: the manifest says (the newer companions: a ghost has
        # no feet, and flames and mist would pull a measured one), or it is the first frame's feet.
        foot = float(m["anchor"]) if "anchor" in m else _foot_centre(strip.copy(0, 0, w, h))
        anchor = round(foot * factor)
        normal, mirrored = [], []
        for i in range(self.info[name].frames):
            img = strip.copy(i * w, 0, w, h).scaled(
                dw, dh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            normal.append(_frame(img, anchor, scale))
            if name in SIDE_VIEWS:
                mirrored.append(_frame(img.transformed(flip), round(dw / scale) - anchor, scale))
        self._frames[(name, False)] = normal
        self._frames[(name, True)] = mirrored or normal

    def frame(self, anim: str, index: int, mirror: bool) -> SpriteFrame:
        frames = self._frames.get((anim, mirror))
        if frames is None:
            self._load(anim)
            frames = self._frames[(anim, mirror)]
        return frames[index]

    def anims(self) -> dict[str, tuple[int, float, bool]]:
        return {name: (i.frames, i.fps, i.loop) for name, i in self.info.items()}
