"""Chat bubble styles: painted bubbles, and the animated effects that run round their rims.

Each style has painted art (see art/bubbles/README.md): a panel drawn as a
9-slice so it fits a bubble of any size, a tail, and sprite sheets for its rim
effect. The motion is code: lightning arcs crackle along the electric rim,
a ring of fire races round the fire rim (violet spirit fire round the ghost's)
like a lit fuse, leaving glowing embers behind it, bees and butterflies flit
round the leaf rim while a caterpillar crawls along it, and sparkles circle the
fairy rim.
Everything is a function of the bubble's age, so any frame can be drawn at any
moment without keeping particles between frames. The plain style is drawn in
the desktop's own colours, with no art.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import cache

from PyQt6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen, QPixmap, QRadialGradient
from PyQt6.QtWidgets import QApplication

from . import paths

DEFAULT = "electric"
POP = 0.32  # seconds the bubble takes to pop up
PAD = 16.0  # text padding inside a plain bubble
TAIL = 12.0  # a plain bubble's tail
RADIUS = 14.0


@dataclass(frozen=True)
class Style:
    name: str
    label: str
    fill: str  # the bubble's fill, close to the painted one; empty: the desktop's own colours
    text: str
    accent: str  # buttons, links, the entry box, scroll bars
    on_accent: str  # text on a filled accent button
    effect: str  # what runs round the rim
    margins: tuple[float, float, float, float] = (0, 0, 0, 0)  # how far the effect reaches out: left, top, right, bottom

    def colours(self) -> tuple[QColor, QColor]:
        """Fill and text colours."""
        if not self.fill:
            pal = QApplication.palette()
            fill = QColor(pal.color(QPalette.ColorRole.Base))
            fill.setAlpha(248)
            return fill, QColor(pal.color(QPalette.ColorRole.Text))
        return QColor(self.fill), QColor(self.text)

    def dark(self) -> bool:
        return self.colours()[1].lightness() > 128

    def reach(self, animate: bool) -> QMarginsF:
        """Room the bubble needs around it for its rim's effect."""
        return QMarginsF(*self.margins) if animate and self.effect else QMarginsF()


STYLES: dict[str, Style] = {
    s.name: s
    for s in (
        Style("electric", "Electric: lightning", "#0d1a3a", "#eaf6ff", "#3fcaf2", "#0b1426", "lightning", (16, 16, 16, 16)),
        Style("fire", "Fire: ring of fire", "#1f120e", "#fff1e6", "#ff9a3c", "#1a0f0c", "fire", (44, 44, 44, 44)),
        Style("leaf", "Leaf: bees and butterflies", "#f7efd9", "#26261a", "#2f7a3b", "#ffffff", "critters", (56, 56, 56, 56)),
        Style("fairy", "Fairy: sparkles", "#f9dcea", "#3a2131", "#b83d78", "#ffffff", "sparkles", (18, 18, 18, 18)),
        Style("ghost", "Ghost: spirit fire", "#1e1338", "#efe9ff", "#b49cff", "#161124", "spirit", (44, 44, 44, 44)),
        Style("plain", "Plain: desktop colours", "", "", "#26b8d9", "#ffffff", ""),
    )
}


def get(name: str | None) -> Style:
    return STYLES.get((name or "").strip().lower(), STYLES[DEFAULT])


# -- the painted art


class Look:
    """One style's painted art: the 9-slice panel, the tail and the effect's frames."""

    def __init__(self, name: str, entry: dict):
        folder = paths.bubbles_dir()
        self.panel = QPixmap(str(folder / f"{name}-panel.png"))
        self.tail = QPixmap(str(folder / f"{name}-tail.png"))
        if self.panel.isNull() or self.tail.isNull():
            raise FileNotFoundError(name)
        k = self.k = float(entry["scale"])  # display px per art px
        self.slice = [int(v) for v in entry["slice"]]
        self.rim = [v * k for v in entry["rim"]]
        tw, th, overlap = entry["tail"]
        self.tail_size = QSizeF(tw * k, th * k)
        self.overlap = overlap * k
        self.frames, self.fx_size = self._sheet(folder / f"{name}-fx.png", entry["fx"])
        self.frames2, self.fx2_size = self._sheet(folder / f"{name}-fx2.png", entry["fx2"]) if "fx2" in entry else ([], QSizeF())
        self._cache: dict[tuple[int, int, float], QPixmap] = {}

    def _sheet(self, path, fx: dict) -> tuple[list[QPixmap], QSizeF]:
        strip = QPixmap(str(path))
        if strip.isNull():
            raise FileNotFoundError(path)
        frames = [strip.copy(i * fx["w"], 0, fx["w"], fx["h"]) for i in range(int(fx["frames"]))]
        return frames, QSizeF(fx["w"] * self.k, fx["h"] * self.k)

    def pad(self) -> float:
        return max(PAD, max(self.rim) + 11)

    def tail_height(self) -> float:
        return self.tail_size.height() - self.overlap

    def _panel(self, width: int, height: int, ratio: float) -> QPixmap:
        """The panel stretched to this size, its nine pieces put together once
        (drawn piece by piece, their joins would show while it fades and pops)."""
        key = (width, height, ratio)
        if key not in self._cache:
            if len(self._cache) > 6:
                self._cache.clear()
            pix = QPixmap(max(1, round(width * ratio)), max(1, round(height * ratio)))
            pix.setDevicePixelRatio(ratio)
            pix.fill(Qt.GlobalColor.transparent)
            q = QPainter(pix)
            q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            l, t, r, b = self.slice
            dl, dt, dr, db = (round(v * self.k) for v in self.slice)
            sw, sh = self.panel.width(), self.panel.height()
            xs, sxs = (0, dl, width - dr, width), (0, l, sw - r, sw)
            ys, sys_ = (0, dt, height - db, height), (0, t, sh - b, sh)
            for i in range(3):
                for j in range(3):
                    target = QRectF(xs[j], ys[i], xs[j + 1] - xs[j], ys[i + 1] - ys[i])
                    source = QRectF(sxs[j], sys_[i], sxs[j + 1] - sxs[j], sys_[i + 1] - sys_[i])
                    if target.width() > 0 and target.height() > 0:
                        q.drawPixmap(target, self.panel, source)
            q.end()
            self._cache[key] = pix
        return self._cache[key]

    def paint(self, p: QPainter, box: QRectF, tail_x: float) -> None:
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        x0, y0 = round(box.left()), round(box.top())
        width, height = round(box.right()) - x0, round(box.bottom()) - y0
        ratio = max(1.0, p.device().devicePixelRatioF()) if p.device() else 1.0
        p.drawPixmap(x0, y0, self._panel(width, height, ratio))
        tw, th = self.tail_size.width(), self.tail_size.height()
        p.drawPixmap(QRectF(round(tail_x - tw / 2), y0 + height - self.overlap, tw, th), self.tail, QRectF(self.tail.rect()))


@cache
def _manifest() -> dict:
    try:
        return json.loads((paths.bubbles_dir() / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


_looks: dict[str, Look | None] = {}


def look(style: Style) -> Look | None:
    """The style's painted art, or None (the plain style, or art that's missing)."""
    if style.name not in _looks:
        entry = _manifest().get(style.name)
        try:
            _looks[style.name] = Look(style.name, entry) if entry and style.effect else None
        except (FileNotFoundError, KeyError, TypeError, ValueError):
            _looks[style.name] = None
    return _looks[style.name]


def padding(style: Style) -> float:
    art = look(style)
    return art.pad() if art else PAD


def tail_height(style: Style) -> float:
    art = look(style)
    return art.tail_height() if art else TAIL


# -- helpers


def _h(*keys: int) -> float:
    """A repeatable random number in [0, 1) for these keys."""
    x = 0x9E3779B1
    for k in keys:
        x = ((x ^ (k & 0xFFFFFFFF)) * 0x85EBCA6B) & 0xFFFFFFFF
        x ^= x >> 13
        x = (x * 0xC2B2AE35) & 0xFFFFFFFF
        x ^= x >> 16
    return x / 0x100000000


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def ease_out_back(x: float) -> float:
    x = _clamp(x) - 1
    return 1 + 2.70158 * x**3 + 1.70158 * x**2


def ease_out(x: float) -> float:
    return 1 - (1 - _clamp(x)) ** 3


def pop_scale(age: float) -> float:
    """The bubble's size as it pops up: a little overshoot, then settled."""
    return 0.72 + 0.28 * ease_out_back(age / POP)


class Rim:
    """Points and outward normals round a rounded box, by fraction of the way round."""

    N = 256

    def __init__(self, box: QRectF, radius: float = RADIUS):
        path = QPainterPath()
        path.addRoundedRect(box, radius, radius)
        self.box = QRectF(box)
        self.radius = radius
        self.length = path.length()
        inner = box.adjusted(radius, radius, -radius, -radius)
        self.points: list[tuple[float, float]] = []
        self.normals: list[tuple[float, float]] = []
        for i in range(self.N):
            p = path.pointAtPercent(i / self.N)
            qx = min(max(p.x(), inner.left()), inner.right())
            qy = min(max(p.y(), inner.top()), inner.bottom())
            dx, dy = p.x() - qx, p.y() - qy
            n = math.hypot(dx, dy) or 1.0
            self.points.append((p.x(), p.y()))
            self.normals.append((dx / n, dy / n))
        area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(self.points, self.points[1:] + self.points[:1], strict=True))
        self.clockwise = area > 0  # on screen, where y grows downwards

    def nearest(self, x: float, y: float) -> float:
        """The fraction of the way round of the rim point nearest (x, y)."""
        best = min(range(self.N), key=lambda i: (self.points[i][0] - x) ** 2 + (self.points[i][1] - y) ** 2)
        return best / self.N

    def heading(self, u: float) -> float:
        """The direction (degrees, 0 = right, 90 = down) of travel at `u` going clockwise."""
        step = 0.5 / self.N if self.clockwise else -0.5 / self.N
        x0, y0, _, _ = self.at(u - step)
        x1, y1, _, _ = self.at(u + step)
        return math.degrees(math.atan2(y1 - y0, x1 - x0))

    def at(self, u: float) -> tuple[float, float, float, float]:
        """x, y and the outward normal at fraction `u` of the way round."""
        f = (u % 1.0) * self.N
        i = int(f) % self.N
        a = f - int(f)
        j = (i + 1) % self.N
        (x0, y0), (x1, y1) = self.points[i], self.points[j]
        (nx0, ny0), (nx1, ny1) = self.normals[i], self.normals[j]
        nx, ny = nx0 + (nx1 - nx0) * a, ny0 + (ny1 - ny0) * a
        n = math.hypot(nx, ny) or 1.0
        return x0 + (x1 - x0) * a, y0 + (y1 - y0) * a, nx / n, ny / n

    def path(self, inset: float = 0.0) -> QPainterPath:
        path = QPainterPath()
        r = max(1.0, self.radius - inset)
        path.addRoundedRect(self.box.adjusted(inset, inset, -inset, -inset), r, r)
        return path


def _sprite(p: QPainter, pix: QPixmap, x: float, y: float, w: float, h: float, angle: float = 0.0, left: bool = False, flip: bool = False, alpha: float = 1.0) -> None:
    """Draw `pix` at (x, y), turned `angle` degrees: centred there, or with its left end there."""
    if w < 0.5 or h < 0.5 or alpha <= 0.01:
        return
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    if flip:
        p.scale(1, -1)
    p.setOpacity(p.opacity() * min(1.0, alpha))
    p.drawPixmap(QRectF(0 if left else -w / 2, -h / 2, w, h), pix, QRectF(pix.rect()))
    p.restore()


def _blob(p: QPainter, x: float, y: float, r: float, colour: QColor) -> None:
    g = QRadialGradient(QPointF(x, y), r)
    g.setColorAt(0, colour)
    g.setColorAt(1, QColor(colour.red(), colour.green(), colour.blue(), 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    p.drawEllipse(QPointF(x, y), r, r)


def _tangent(nx: float, ny: float) -> float:
    """The rim's direction (degrees) where its outward normal is (nx, ny), going round the way `u` grows."""
    return math.degrees(math.atan2(nx, -ny))


# -- the bubble


def bubble_path(box: QRectF, tail_x: float, tail: float = TAIL) -> QPainterPath:
    """A rounded box with a tail under it pointing down at `tail_x` (the plain style)."""
    path = QPainterPath()
    path.addRoundedRect(box, RADIUS, RADIUS)
    point = QPainterPath()
    point.moveTo(tail_x - 9, box.bottom() - 1)
    point.lineTo(tail_x, box.bottom() + tail)
    point.lineTo(tail_x + 9, box.bottom() - 1)
    point.closeSubpath()
    return path.united(point)


def paint_body(p: QPainter, style: Style, box: QRectF, tail_x: float) -> None:
    """The bubble itself: its painted panel and tail, or the plain shape."""
    art = look(style)
    if art:
        art.paint(p, box, tail_x)
        return
    fill, _ = style.colours()
    path = bubble_path(box, tail_x)
    p.fillPath(path, fill)
    p.setPen(QPen(QColor(style.accent), 2))
    p.drawPath(path)


def paint_under(p: QPainter, style: Style, rim: Rim, age: float, animate: bool) -> None:
    """What sits behind the bubble: the ghost's spirit orbs."""
    art = look(style)
    if not (art and animate):
        return
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    k = ease_out(age / POP)
    if style.effect == "spirit":
        _orbs(p, rim, age, k)
    p.restore()


def paint_over(p: QPainter, style: Style, rim: Rim, age: float, animate: bool) -> None:
    """What runs round the rim, on top of the bubble."""
    art = look(style)
    if not (art and animate):
        return
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    k = ease_out(age / POP)
    if style.effect == "lightning":
        _lightning(p, art, rim, age, k)
    elif style.effect == "fire":
        _fire_ring(p, art, rim, age, k, FIRE)
    elif style.effect == "spirit":
        _fire_ring(p, art, rim, age, k, SPIRIT)
    elif style.effect == "critters":
        _critters(p, art, rim, age, k)
    elif style.effect == "sparkles":
        _sparkles(p, art, rim, age, k)
    p.restore()


# -- electric: arcs crackling along the neon tube, a burst of them as it appears


def _lightning(p: QPainter, art: Look, rim: Rim, age: float, k: float) -> None:
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    tick = int(age / 0.07)
    inset = art.rim[1] * 0.5  # the middle of the tube
    count = max(4, int(rim.length / 85)) * (2 if age < 0.45 else 1)
    w, h = art.fx_size.width(), art.fx_size.height()
    for i in range(count):
        if _h(i, tick, 3) < 0.3:  # arcs blink in and out
            continue
        drift = age * (0.04 + 0.04 * _h(i, 1)) * (1 if i % 2 == 0 else -1)
        x, y, nx, ny = rim.at(_h(i, 2) + drift + (_h(i, tick, 4) - 0.5) * 0.03)
        size = (0.65 + 0.5 * _h(i, tick, 6)) * k
        frame = art.frames[int(_h(i, tick, 5) * len(art.frames))]
        _sprite(p, frame, x - nx * inset, y - ny * inset, w * size, h * size, _tangent(nx, ny), flip=_h(i, tick, 7) < 0.5)


# -- fire and ghost: a ring of fire racing round the rim like a lit fuse


@dataclass(frozen=True)
class Fire:
    hot: tuple[int, int, int]  # the head's glow and the freshest embers
    cool: tuple[int, int, int]  # embers as they die down
    lap: float  # seconds for one lap
    alpha: float  # the flames' opacity


FIRE = Fire((255, 196, 80), (200, 50, 16), 4.2, 1.0)
SPIRIT = Fire((214, 196, 255), (110, 70, 220), 5.4, 0.92)


def _fire_ring(p: QPainter, art: Look, rim: Rim, age: float, k: float, fire: Fire) -> None:
    """Two heads of fire, lit where the tail meets the bubble, chase each other
    clockwise round the rim. Each flares at its head; behind it the flames
    shrink and lean back and the rim glows like a cooling ember; sparks fly off
    the head."""
    w, h = art.fx_size.width(), art.fx_size.height()
    n = len(art.frames)
    way = 1 if rim.clockwise else -1
    inset = art.rim[1] * 0.5
    lit = rim.nearest(rim.box.center().x(), rim.box.bottom())
    grow = ease_out(age / 0.9)  # the fire catches and spreads from the tail
    trail = min(0.3, 230 / rim.length) * grow
    step = 10 / rim.length  # a flame every 10 px
    count = max(1, int(trail / step))
    for c in range(2):
        head = lit + c * 0.5 + way * age / fire.lap
        # The ember line: the rim glowing behind the head, cooling as it goes.
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        embers = max(1, int(trail * rim.length / 3))
        for j in range(embers):
            x, y, nx, ny = rim.at(head - way * j * 3 / rim.length)
            cool = j / embers
            r, g, b = (round(a + (bb - a) * cool) for a, bb in zip(fire.hot, fire.cool, strict=True))
            flicker = 0.7 + 0.3 * _h(c, j, int(age * 16))
            _blob(p, x - nx * inset, y - ny * inset, 4.5, QColor(r, g, b, int(140 * (1 - cool) ** 1.4 * flicker * k)))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        # The flames, back to front: small and leaning back at the end of the trail, big at the head.
        for j in reversed(range(-2, count)):
            u = head - way * j * step
            x, y, nx, ny = rim.at(u)
            nearness = 1.0 if j < 0 else 1 - j / count
            if j < 0:  # the flare at the head
                size = (1.15 if j == -1 else 0.95) * (0.9 + 0.2 * math.sin(age * 9 + c)) * k
            else:
                size = (0.2 + 0.85 * nearness**2.2) * (0.75 + 0.5 * _h(c, j, int(u * 997), 31)) * k
            if size < 0.16:
                continue
            lean = -way * (18 + 22 * nearness)
            angle = math.degrees(math.atan2(ny, nx)) + 90 + lean
            frame = art.frames[int(age * (12 + 5 * _h(c, j, 32)) + j * 3 + c * 5) % n]
            hs = h * size
            bx, by = x - nx * inset, y - ny * inset
            fade = fire.alpha * min(1.0, nearness * 2.5)
            _sprite(p, frame, bx + nx * hs * 0.4, by + ny * hs * 0.4, w * size, hs, angle, alpha=fade)
        # Sparks thrown off the head.
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for i in range(12):
            period = 0.5 + 0.5 * _h(c, i, 41)
            t = age + _h(c, i, 42) * period
            cycle, s = int(t / period), (t % period) / period
            x, y, nx, ny = rim.at(head - way * s * period / fire.lap)
            spread = (_h(c, i, cycle, 43) - 0.5) * 1.4
            dist = 10 + s * (24 + 22 * _h(c, i, cycle, 44))
            dx = nx * math.cos(spread) - ny * math.sin(spread)
            dy = ny * math.cos(spread) + nx * math.sin(spread)
            r, g, b = fire.hot
            _blob(p, x + dx * dist, y + dy * dist - s * 10, 2.0, QColor(r, g, b, int(235 * (1 - s) * grow * k)))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)


# -- leaf: bees and butterflies flitting round the rim, a caterpillar crawling along it


def _critters(p: QPainter, art: Look, rim: Rim, age: float, k: float) -> None:
    w, h = art.fx_size.width(), art.fx_size.height()
    way = 1 if rim.clockwise else -1
    if art.frames2:  # the caterpillar crawls clockwise round the whole rim, feet on it
        cw, ch = art.fx2_size.width(), art.fx2_size.height()
        u = 0.15 + way * age * 15 / rim.length
        x, y, nx, ny = rim.at(u)
        lift = ch * 0.5 - art.rim[1] * 0.35
        frame = art.frames2[int(age * 9) % len(art.frames2)]
        _sprite(p, frame, x + nx * lift, y + ny * lift, cw, ch, rim.heading(u), alpha=k)
    for i in range(4):  # two bees (fast, buzzy) and two butterflies (slow, fluttery)
        bee = i < 2
        speed = (0.05 + 0.03 * _h(i, 91)) if bee else (0.022 + 0.012 * _h(i, 91))
        direction = way if i % 2 == 0 else -way
        u = _h(i, 92) + direction * age * speed
        x, y, nx, ny = rim.at(u)
        if bee:
            out = 16 + 7 * math.sin(age * 1.3 + i * 2)
            bob = 2.5 * math.sin(age * 19 + i)
            frame = art.frames[int(age * 26 + i) % 4]
        else:
            out = 20 + 12 * math.sin(age * 0.8 + i * 2)
            bob = 6 * math.sin(age * 2.6 + i)
            frame = art.frames[4 + int(age * 9 + i) % 4]
        ahead_x, _, _, _ = rim.at(u + direction * 0.004)
        facing_left = ahead_x < x - 0.05
        size = (1.3 if bee else 1.45) * k
        tilt = 0 if bee else 10 * math.sin(age * 1.7 + i)
        p.save()
        p.translate(x + nx * out, y + ny * out + bob)
        if facing_left:
            p.scale(-1, 1)
        _sprite(p, frame, 0, 0, w * size, h * size, tilt)
        p.restore()


# -- fairy: two comets of twinkles circling the rim, twinkles popping up


def _sparkles(p: QPainter, art: Look, rim: Rim, age: float, k: float) -> None:
    w, h = art.fx_size.width(), art.fx_size.height()
    n = len(art.frames)
    peak = n // 2 - 1  # the frame where the twinkle is at full size
    for c in range(2):
        head = c * 0.5 + age * 0.15
        for j in range(10):
            x, y, nx, ny = rim.at(head - j * 0.012)
            frame = art.frames[min(n - 1, peak + j // 2)] if j else art.frames[peak + int(age * 10) % 2]
            size = (1.0 if j == 0 else 0.75 - 0.05 * j) * k
            wob = math.sin(age * 7 + j * 1.3) * 2.5
            _sprite(p, frame, x + nx * wob, y + ny * wob, w * size, h * size, alpha=1 - j / 11)
    for i in range(10):
        period = 1.1 + 0.9 * _h(i, 61)
        t = age + _h(i, 62) * period
        cycle, s = int(t / period), (t % period) / period
        x, y, nx, ny = rim.at(_h(i, cycle, 63))
        off = (2 * _h(i, cycle, 64) - 0.3) * 8
        size = (0.5 + 0.35 * _h(i, cycle, 65)) * k
        _sprite(p, art.frames[min(n - 1, int(s * n))], x + nx * off, y + ny * off, w * size, h * size)


# -- ghost: spirit orbs floating up behind the rim (its spirit fire is the fire ring, slower)


def _orbs(p: QPainter, rim: Rim, age: float, k: float) -> None:
    for i in range(4):
        period = 2.6 + 1.0 * _h(i, 81)
        t = age + _h(i, 82) * period
        cycle, s = int(t / period), (t % period) / period
        x, y, nx, ny = rim.at(_h(i, cycle, 83))
        if ny > -0.4:
            continue
        a = math.sin(math.pi * s) * k
        ox, oy = x + math.sin(s * 5 + i) * 6, y - 8 - s * 26
        _blob(p, ox, oy, 6.0, QColor(154, 123, 255, int(115 * a)))
        _blob(p, ox, oy, 2.6, QColor(243, 237, 255, int(230 * a)))
