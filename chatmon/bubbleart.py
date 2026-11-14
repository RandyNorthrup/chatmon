"""Painted chat bubbles: a still painted bubble drawn round any text, with effects that move along its border.

Each style's art (see art/bubbles/README.md) is one painted bubble with its notch. It never moves: it is
drawn as a 9-slice (corners keep their shape, edges stretch, the bottom edge is split once more so the
notch can sit anywhere along it) and put together once per size.

The motion is separate layers drawn over it, every one periodic by construction, so a loop always closes:
tileable strips drifting along the border (a whole number of tiles round it), pulses of light running
round it, a baked flame loop, the still's own rim glowing on a sine, and single sprites (arcs of
lightning, sparkles, embers, a caterpillar) placed and faded on a fixed timeline. `loop_period()` is the time after which the whole picture repeats exactly.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import cache

from PyQt6.QtCore import QPointF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient, QTransform

from . import paths

TAU = 2 * math.pi


def _h(*keys: int) -> float:
    """A repeatable random number in [0, 1) for these keys."""
    x = 0x9E3779B1
    for k in keys:
        x = ((x ^ (k & 0xFFFFFFFF)) * 0x85EBCA6B) & 0xFFFFFFFF
        x ^= x >> 13
        x = (x * 0xC2B2AE35) & 0xFFFFFFFF
        x ^= x >> 16
    return x / 0x100000000


def device_ratio(p: QPainter) -> float:
    """Device pixels per display pixel where `p` draws: what pixmaps drawn with it should be made at.
    Its transform says, not its device: the ask box is painted through a scene onto the 2x overlay, by a
    painter scaled by 2, on a widget whose own ratio is 1."""
    t = p.combinedTransform()
    return max(1.0, math.hypot(t.m11(), t.m12()))


def _spans(a: float, b: float, lit: list[tuple[float, float]] | None) -> list[tuple[float, float]]:
    """The parts of the border from `a` to `b` (distances along it) that `lit` covers; all of it if `lit` is None."""
    if lit is None:
        return [(a, b)]
    return [(max(a, lo), min(b, hi)) for lo, hi in lit if min(b, hi) > max(a, lo)]


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


@dataclass(frozen=True)
class Frame:
    """Where things are in the drawn bubble, in display pixels."""

    size: QSizeF  # the whole frame, effect room included
    text: QRectF  # where text may go
    tail: tuple[float, float]  # the notch's tip
    effect: tuple[float, float, float, float]  # how far the frame reaches past the text area: left, top, right, bottom


class Rim:
    """The border's centre line for one bubble size: a rounded rectangle walked clockwise from the start
    of the top edge. Distances are display pixels along it."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float, r: float, notch: tuple[float, float]):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.r = r = max(1.0, min(r, (x1 - x0) / 2 - 1, (y1 - y0) / 2 - 1))
        self.notch = notch  # x range on the bottom edge the notch grows out of
        a, b = (x1 - x0) - 2 * r, (y1 - y0) - 2 * r
        q = math.pi * r / 2
        # (kind, length, start x, start y, heading in degrees or arc centre x, y and start angle)
        self.parts = [
            ("line", a, x0 + r, y0, 0.0),
            ("arc", q, x1 - r, y0 + r, -90.0),
            ("line", b, x1, y0 + r, 90.0),
            ("arc", q, x1 - r, y1 - r, 0.0),
            ("line", a, x1 - r, y1, 180.0),
            ("arc", q, x0 + r, y1 - r, 90.0),
            ("line", b, x0, y1 - r, 270.0),
            ("arc", q, x0 + r, y0 + r, 180.0),
        ]
        self.starts = []
        s = 0.0
        for part in self.parts:
            self.starts.append(s)
            s += part[1]
        self.length = s
        self.top = (0.0, a)  # distance range of the top edge
        self.straight = [(self.starts[i], self.parts[i][1]) for i in (0, 2, 4, 6)]

    def at(self, s: float) -> tuple[float, float, float]:
        """x, y and heading (degrees, 0 = right, 90 = down) at distance `s` along the border."""
        s %= self.length
        for (kind, length, px, py, ang), start in zip(self.parts, self.starts, strict=True):
            if s <= start + length:
                d = s - start
                if kind == "line":
                    rad = math.radians(ang)
                    return px + math.cos(rad) * d, py + math.sin(rad) * d, ang
                theta = math.radians(ang) + d / self.r
                return px + math.cos(theta) * self.r, py + math.sin(theta) * self.r, math.degrees(theta) + 90
        return self.x0 + self.r, self.y0, 0.0

    def path(self, inset: float = 0.0) -> QPainterPath:
        path = QPainterPath()
        r = max(0.5, self.r - inset)
        path.addRoundedRect(QRectF(self.x0 + inset, self.y0 + inset, self.x1 - self.x0 - 2 * inset, self.y1 - self.y0 - 2 * inset), r, r)
        return path

    def on_straight(self, f: float) -> float:
        """A distance on one of the straight edges (never a corner or the notch), from a fraction 0..1."""
        spans = []
        for i, (start, length) in enumerate(self.straight):
            if i == 2:  # the bottom edge runs right to left; keep clear of the notch
                right, left = self.x1 - self.r, self.x0 + self.r
                n0, n1 = self.notch
                if n1 + 14 < right - 14:
                    spans.append((start + 6, right - (n1 + 14) - 12))
                if left + 14 < n0 - 14:
                    spans.append((start + (right - (n0 - 14)) + 6, (n0 - 14) - left - 12))
            elif length > 28:
                spans.append((start + 14, length - 28))
        spans = [(s, n) for s, n in spans if n > 4] or [(0.0, max(1.0, self.top[1]))]
        total = sum(n for _, n in spans)
        d = (f % 1.0) * total
        for s, n in spans:
            if d <= n:
                return s + d
            d -= n
        return spans[-1][0]


# -- layers: each draws one periodic effect. `period` is the time after which it repeats exactly.


class Layer:
    period = 1.0

    def __init__(self, folder, entry: dict, k: float):
        self.k = k

    def cycle(self, rim: Rim) -> float:
        return self.period

    def paint(self, p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        raise NotImplementedError

    def strip(self) -> bool:
        """Whether it follows the border all the way round (and so is masked off the notch)."""
        return False


def _load(folder, name: str) -> QPixmap:
    pix = QPixmap(str(folder / name))
    if pix.isNull():
        raise FileNotFoundError(name)
    return pix


class Scroll(Layer):
    """A tileable strip drifting along the whole border. A whole number of tiles fit round it, so there
    is no seam in space. In time it is two copies of the strip, half a cycle apart: each drifts at `speed`
    and is faded right out at the moment it steps back to where it began, while the other is at full
    strength. So the drift can be as slow as wanted (it need not cover a whole tile per cycle) and the
    loop still closes exactly."""

    MARGIN = 8.0  # display px of pattern kept past each end of the unrolled band

    def __init__(self, folder, entry: dict, k: float):
        super().__init__(folder, entry, k)
        self.pix = _load(folder, entry["file"])
        self.tile = self.pix.width() * k  # display px, before fitting to the border
        self.height = self.pix.height() * k
        self.period = float(entry["period"])
        self.speed = float(entry["speed"])  # display px a second; the sign is the direction
        self.offset = float(entry.get("offset", 0.0))  # display px outward from the border line
        self.opacity = float(entry.get("opacity", 1.0))
        self.breathe = float(entry.get("breathe", 0.0))  # share of the opacity that swells and fades once a cycle
        self.phase = float(entry.get("phase", 0.0))
        self._fit: dict[int, tuple[QPixmap, float]] = {}
        self._band: QPixmap | None = None
        self._corners: dict[tuple, list] = {}
        self._layouts: dict[tuple, tuple] = {}  # per border and band (a Runner lays two bands of its own)
        self._together: QPixmap | None = None  # several layers' bands added up (`paint_together`)
        self._corner_layers: dict[tuple[int, int], QPixmap] = {}

    def strip(self) -> bool:
        return True

    def fitted(self, rim: Rim) -> tuple[QPixmap, float]:
        """The strip scaled so a whole number of tiles go round this border: (three tiles side by side,
        one tile's width in display px)."""
        key = round(rim.length * 4)
        if key not in self._fit:
            if len(self._fit) > 4:
                self._fit.clear()
            n = max(1, round(rim.length / self.tile))
            tile = rim.length / n
            w, h = max(2, round(tile)), max(2, round(self.height))
            if abs(tile - w) < 0.02:  # never exactly one pixmap px per display px: Qt then moves it only by whole pixels
                w += 1
            one = self.pix.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            two = QPixmap(3 * w, h)
            two.fill(Qt.GlobalColor.transparent)
            q = QPainter(two)
            for i in range(3):
                q.drawPixmap(i * w, 0, one)
            q.end()
            # The pixmap's tile is w px but must cover `tile` display px: the painter is scaled by tile / w.
            self._fit[key] = (two, tile)
        return self._fit[key]

    def alpha(self, t: float) -> float:
        if not self.breathe:
            return self.opacity
        return self.opacity * (1 - self.breathe * (0.5 - 0.5 * math.cos(TAU * (t / self.period + self.phase))))

    def copies(self, t: float, tile: float) -> list[tuple[float, float]]:
        """(weight, shift along the border in display px) for each of the two copies at time `t`. The
        weights always add up to 1, and a copy's weight is 0 when its shift steps back."""
        travel = self.speed * self.period  # how far a copy drifts while it is shown
        out = []
        for copy in (0, 1):
            f = (t / self.period + 0.5 * copy) % 1.0
            weight = _smooth(1 - abs(2 * f - 1))
            out.append((weight, (travel * (f - 0.5) + copy * 0.382 * tile) % tile))
        return out

    def band(self, rim: Rim, copies: list[tuple[float, float]], ratio: float, lit: list[tuple[float, float]] | None = None) -> QPixmap:
        """The strip as it lies along the whole border, unrolled into one straight band: the weighted copies
        summed (so their weights mix exactly), each moved its own distance. `MARGIN` px of the pattern are
        added at both ends for the corner slices to read from. In device pixels (`ratio` per display px).
        With `lit` (distances along the border), only those stretches are filled; the rest is clear."""
        two, tile = self.fitted(rim)
        sx = tile / (two.width() / 3)  # display px per pixmap px along the border
        h = two.height()
        length = rim.length + 2 * self.MARGIN
        size = (max(1, round(length * ratio)), max(1, round(h * ratio)))
        if self._band is None or (self._band.width(), self._band.height()) != size:
            self._band = QPixmap(*size)
        band = self._band
        band.fill(Qt.GlobalColor.transparent)
        q = QPainter(band)
        q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        q.scale(ratio * sx, ratio)
        # A texture brush, not drawTiledPixmap: that one places the pattern on whole pixels only, and a
        # slow drift then moves in visible one-pixel hops. (A brush does the same at a scale of exactly 1,
        # which is why `fitted` never makes one.)
        brush = QBrush(two)
        runs = [(0.0, length)] if lit is None else [(self.MARGIN + a, self.MARGIN + b) for a, b in _spans(-self.MARGIN, rim.length + self.MARGIN, lit)]
        for weight, shift in copies:
            if weight > 0.003:
                q.setOpacity(weight)
                brush.setTransform(QTransform.fromTranslate((self.MARGIN + shift) / sx, 0))
                for a, b in runs:
                    q.fillRect(QRectF(a / sx, 0, (b - a) / sx, h), brush)
        q.end()
        return band

    @staticmethod
    def paint_together(layers: list[Scroll], p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        """Several plain Scroll layers laid round the border as one band: each one's band, at its own
        strength and its own place across the border, added into one, which is laid once. Laying is the
        same for every row of a band, so this is what laying them one by one draws, at half the cost.
        Layers whose bands don't line up on whole device pixels are laid one by one."""
        ratio = art.ratio
        bands = []
        for layer in layers:
            _, tile = layer.fitted(rim)
            band = QPixmap(layer.band(rim, layer.copies(t, tile), ratio))  # each layer reuses its own pixmap
            bands.append((layer, band, -band.height() / ratio / 2 - layer.offset))  # its top, from the border line
        lo = min(top for _, _, top in bands)
        rows = [(top - lo) * ratio for _, _, top in bands]
        if len(layers) < 2 or len({band.width() for _, band, _ in bands}) > 1 or any(abs(r - round(r)) > 0.01 for r in rows):
            for layer in layers:
                layer.paint(p, rim, t, art)
            return
        height = max(round(r) + band.height() for r, (_, band, _) in zip(rows, bands, strict=True))
        first = layers[0]
        if first._together is None or (first._together.width(), first._together.height()) != (bands[0][1].width(), height):
            first._together = QPixmap(bands[0][1].width(), height)
        together = first._together
        together.fill(Qt.GlobalColor.transparent)
        q = QPainter(together)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for (layer, band, _), row in zip(bands, rows, strict=True):
            q.setOpacity(layer.alpha(t))
            q.drawPixmap(0, round(row), band)
        q.end()
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        first.lay(p, rim, together, ratio, offset=-lo - height / ratio / 2)
        p.restore()

    def paint(self, p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        _, tile = self.fitted(rim)
        band = self.band(rim, self.copies(t, tile), art.ratio)
        p.save()
        p.setOpacity(p.opacity() * self.alpha(t))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        self.lay(p, rim, band, art.ratio)
        p.restore()

    def corners(self, rim: Rim, top: float, bottom: float) -> list[tuple[QPainterPath, float, float, float, float, float]]:
        """The corner slices for this border: (wedge to clip to, x, y, turn in degrees, half width, distance
        along the border of its middle). Worked out once per bubble size."""
        key = (rim.key, top, bottom)  # type: ignore[attr-defined]
        if key not in self._corners:
            if len(self._corners) > 6:
                self._corners.clear()
            out = []
            ro, ri = rim.r - top, max(0.0, rim.r - bottom)
            for (kind, length, px, py, ang), start in zip(rim.parts, rim.starts, strict=True):
                if kind != "arc":
                    continue
                steps = max(6, math.ceil(length / 2.5))
                ds = length / steps
                half = ds * (ro + 1) / rim.r / 2 + 1.0  # enough to cover the wedge's outer side
                for j in range(steps):
                    a0 = math.radians(ang) + (j * ds) / rim.r
                    a1 = math.radians(ang) + ((j + 1) * ds) / rim.r
                    mid = (a0 + a1) / 2
                    wedge = QPainterPath()
                    wedge.addPolygon(
                        QPolygonF(
                            [
                                QPointF(px + math.cos(a0) * (ro + 1), py + math.sin(a0) * (ro + 1)),
                                QPointF(px + math.cos(a1) * (ro + 1), py + math.sin(a1) * (ro + 1)),
                                QPointF(px + math.cos(a1) * ri, py + math.sin(a1) * ri),
                                QPointF(px + math.cos(a0) * ri, py + math.sin(a0) * ri),
                            ]
                        )
                    )
                    out.append((wedge, px + math.cos(mid) * rim.r, py + math.sin(mid) * rim.r, math.degrees(mid) + 90, half, start + (j + 0.5) * ds))
            self._corners[key] = out
        return self._corners[key]

    def layout(self, rim: Rim, band: QPixmap, ratio: float, offset: float | None = None) -> tuple:
        """How `lay` puts this band round this border, worked out once per size: (band height in display px,
        its top, the straight edges, and the four corners). A corner is its slices as fragments of the band
        with the stretch of border each covers, where the small layer it is drawn on goes, and its wedges on
        a pixmap that size, to cut the layer to. `offset`: where the band's middle is from the border line,
        outward (this layer's own, unless the band is several layers')."""
        offset = self.offset if offset is None else offset
        key = (rim.key, band.width(), band.height(), ratio, offset)  # type: ignore[attr-defined]
        if key not in self._layouts:
            if len(self._layouts) > 6:
                self._layouts.clear()
                self._corner_layers.clear()
            h = band.height() / ratio
            top, bottom = -h / 2 - offset, h / 2 - offset
            m = self.MARGIN
            edges = [(px, py, ang, start, length) for (kind, length, px, py, ang), start in zip(rim.parts, rim.starts, strict=True) if kind == "line"]
            arcs = [(start, start + length) for (kind, length, *_), start in zip(rim.parts, rim.starts, strict=True) if kind == "arc"]
            groups: list[tuple[list, QPainterPath]] = [([], QPainterPath()) for _ in arcs]
            for wedge, x, y, turn, half, at in self.corners(rim, top, bottom):
                rad = math.radians(turn)
                middle = QPointF(x + math.sin(rad) * offset, y - math.cos(rad) * offset)  # (0, -offset), turned
                source = QRectF((m + at - half) * ratio, 0, 2 * half * ratio, band.height())
                slices, outline = groups[next(i for i, (a, b) in enumerate(arcs) if a <= at <= b)]
                slices.append((QPainter.PixmapFragment.create(middle, source, 1 / ratio, 1 / ratio, turn, 1.0), at - half, at + half))
                outline.addPath(wedge)
            corners = []
            for slices, outline in groups:
                outline.setFillRule(Qt.FillRule.WindingFill)
                box = outline.boundingRect().adjusted(-2, -2, 2, 2)
                origin = QPointF(math.floor(box.left()), math.floor(box.top()))
                size = (max(1, math.ceil((box.right() - origin.x()) * ratio)), max(1, math.ceil((box.bottom() - origin.y()) * ratio)))
                mask = QPixmap(*size)
                mask.setDevicePixelRatio(ratio)
                mask.fill(Qt.GlobalColor.transparent)
                q = QPainter(mask)  # no antialiasing: a pixel is in a wedge or not, as a clip to it would have it
                q.translate(-origin.x(), -origin.y())
                q.fillPath(outline, QColor(0, 0, 0))
                q.end()
                reach = (min(a for _, a, _ in slices), max(b for _, _, b in slices)) if slices else (0.0, 0.0)
                corners.append(([f for f, _, _ in slices], reach, origin, size, mask))
            self._layouts[key] = (h, top, edges, corners)
        return self._layouts[key]

    def lay(self, p: QPainter, rim: Rim, band: QPixmap, ratio: float, lit: list[tuple[float, float]] | None = None, offset: float | None = None) -> None:
        """The unrolled band laid round the border: straight along the edges, and through each corner in
        thin slices, each turned to the border's direction there. The slices are drawn in one go on a layer
        of their own, where each one replaces what it overlaps rather than adding to it, and the layer is cut
        to the corners' wedges: so they neither overlap nor leave gaps. (One rotated draw at a time, clipped
        to its wedge, cost Qt more to set up than to draw, a hundred times a frame.) With `lit`, only those
        stretches of the border are laid."""
        h, top, edges, corners = self.layout(rim, band, ratio, offset)
        m = self.MARGIN
        for px, py, ang, start, length in edges:
            for a, b in _spans(start, start + length, lit):
                p.save()
                p.translate(px, py)
                p.rotate(ang)
                p.drawPixmap(QRectF(a - start, top, b - a, h), band, QRectF((m + a) * ratio, 0, (b - a) * ratio, band.height()))
                p.restore()
        for fragments, (a, b), origin, size, mask in corners:
            if not fragments or not _spans(a, b, lit):  # a corner is drawn whole: what isn't lit is clear
                continue
            layer = self._corner_layers.get(size)
            if layer is None:
                layer = self._corner_layers[size] = QPixmap(*size)
                layer.setDevicePixelRatio(ratio)
            layer.fill(Qt.GlobalColor.transparent)
            q = QPainter(layer)
            q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            q.translate(-origin.x(), -origin.y())
            q.drawPixmapFragments(fragments, band)
            q.resetTransform()
            q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            q.drawPixmap(0, 0, mask)
            q.end()
            p.drawPixmap(origin, layer)


def _heads(rim: Rim, t: float, period: float, count: int, laps: int) -> list[float]:
    """Where `count` evenly spaced runners are along the border at time `t`: each goes `laps` whole times
    round per `period` (the sign is the direction), so they are back where they began after one period."""
    return [((i / count + laps * t / period) % 1.0) * rim.length for i in range(count)]


class Runner(Scroll):
    """Pulses of light running round the whole border: `count` of them, evenly spaced, each a bright head
    with a tail fading out behind it. Where a pulse is, the strip's pattern shows and the border takes
    the pulse's `colour` (a soft band `halo` px across); the pattern itself only drifts slowly, as in
    `Scroll`, so nothing jagged races past. A pulse goes a whole number of times round per period
    whatever the bubble's size, so the loop closes. With `plus` off the pulse is painted over the border
    instead of added to it, so its own colour shows on a border of another colour."""

    # Tail brightness from its far end (0) to the head (1): slow to rise, then quick.
    TAIL = ((0.0, 0.0), (0.3, 0.1), (0.55, 0.3), (0.75, 0.58), (0.9, 0.86), (1.0, 1.0))
    # The halo's strength across the border line (0 and 1: its edges), near enough a bell.
    BELL = ((0.0, 0.0), (0.2, 0.05), (0.33, 0.22), (0.43, 0.62), (0.5, 1.0), (0.57, 0.62), (0.67, 0.22), (0.8, 0.05), (1.0, 0.0))

    def __init__(self, folder, entry: dict, k: float):
        super().__init__(folder, entry, k)
        self.count = max(1, int(entry.get("count", 2)))
        self.laps = int(entry.get("laps", 1)) or 1
        self.tail = float(entry.get("tail", 150.0))  # display px of light behind a head
        self.lead = float(entry.get("lead", 14.0))  # display px over which a head comes up
        self.glow = float(entry.get("glow", 0.0))  # the halo's strength on the border line; 0: none
        self.halo = float(entry.get("halo", 20.0))  # the halo's whole width across the border, display px
        self.head = float(entry.get("head", 0.0))  # radius of the hot point on each head, display px; 0: none
        self.colour = QColor(entry.get("colour", "#ffffff"))
        self.plus = bool(entry.get("plus", True))
        self._halo: tuple[tuple, QPixmap] | None = None  # (size, the halo as built): copied, never rebuilt
        self._fades: dict[tuple, QPixmap] = {}  # a pulse's fade, per band height and length (`fade`)
        self._halo_band: QPixmap | None = None

    def pulses(self, rim: Rim, t: float) -> list[tuple[float, float, float]]:
        """Each pulse at time `t` as (back, front, start) along the unrolled band, display px: its light
        rises from `back` to its head and is gone at `front`; it covers `start` to `start` + tail + lead.
        A pulse is listed again a lap either side, where it shows past an end of the band."""
        length = rim.length
        tail = max(8.0, min(self.tail, length / self.count - self.lead - 2))
        way = 1 if self.laps > 0 else -1
        out = []
        for head in _heads(rim, t, self.period, self.count, self.laps):
            for lap in (-length, 0.0, length):
                x = self.MARGIN + head + lap
                back, front = x - way * tail, x + way * self.lead
                if max(back, front) < 0 or min(back, front) > length + 2 * self.MARGIN:
                    continue
                out.append((back, front, min(back, front)))
        return out

    def fade(self, tail: float, height: int, ratio: float) -> QPixmap:
        """One pulse's brightness along the band as alpha, a band `height` device px high: from its far end
        up to its head and out at its front, with a clear pixel past each end. Drawn once per size."""
        key = (round(tail, 3), height, ratio)
        if key not in self._fades:
            if len(self._fades) > 6:
                self._fades.clear()
            length = tail + self.lead + 2
            fade = QPixmap(max(1, math.ceil(length * ratio)), height)
            fade.fill(Qt.GlobalColor.transparent)
            way = 1 if self.laps > 0 else -1
            back, front = (1.0, 1.0 + tail + self.lead) if way > 0 else (1.0 + tail + self.lead, 1.0)
            share = tail / (tail + self.lead)
            grad = QLinearGradient(back * ratio, 0, front * ratio, 0)
            for at, level in self.TAIL:
                grad.setColorAt(at * share, QColor(0, 0, 0, round(255 * level)))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            q = QPainter(fade)
            q.fillRect(QRectF(0, 0, fade.width(), height), grad)
            q.end()
            self._fades[key] = fade
        return self._fades[key]

    def envelope(self, band: QPixmap, pulses: list[tuple[float, float, float]], tail: float, ratio: float) -> None:
        """Fade `band` to how bright the pulses are along it: its alpha times each pulse's fade, where the
        pulse is. (Nothing else of the band is drawn, so the rest is left as it is.) The pulses never
        overlap: each is at most the border's length over their number. The fade reaches a pixel past
        each end, clear there, so what the bands copied in whole device pixels just past a pulse goes
        too; it is stamped on whole device pixels, a shift of half of one at most, while a pulse moves
        about seven a frame."""
        fade = self.fade(tail, band.height(), ratio)
        q = QPainter(band)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        for _, _, start in pulses:
            q.drawPixmap(round((start - 1) * ratio), 0, fade)
        q.end()

    def halo_band(self, rim: Rim, ratio: float, lit: list[tuple[float, float]]) -> QPixmap:
        """A band of `colour` the length of the unrolled border, strongest on the border line: built once
        per size, and copied where `lit` says, clear elsewhere."""
        size = (max(1, round((rim.length + 2 * self.MARGIN) * ratio)), max(2, round(self.halo * ratio)))
        if self._halo is None or self._halo[0] != size:
            built = QPixmap(*size)
            built.fill(Qt.GlobalColor.transparent)
            across = QLinearGradient(0, 0, 0, size[1])
            for at, level in self.BELL:
                c = QColor(self.colour)
                c.setAlphaF(min(1.0, self.glow * level))
                across.setColorAt(at, c)
            q = QPainter(built)
            q.fillRect(QRectF(0, 0, size[0], size[1]), across)
            q.end()
            self._halo = (size, built)
            self._halo_band = QPixmap(*size)
        built, band = self._halo[1], self._halo_band
        band.fill(Qt.GlobalColor.transparent)
        q = QPainter(band)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        for a, b in _spans(-self.MARGIN, rim.length + self.MARGIN, lit):
            x0, x1 = math.floor((self.MARGIN + a) * ratio), math.ceil((self.MARGIN + b) * ratio)
            q.drawPixmap(x0, 0, built, x0, 0, x1 - x0, size[1])
        q.end()
        return band

    def paint(self, p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        _, tile = self.fitted(rim)
        ratio = art.ratio
        tail = max(8.0, min(self.tail, rim.length / self.count - self.lead - 2))
        pulses = self.pulses(rim, t)
        lit = [(start - self.MARGIN, start - self.MARGIN + tail + self.lead) for _, _, start in pulses]  # along the border
        bands = [self.band(rim, self.copies(t, tile), ratio, lit)]
        if self.glow > 0:
            bands.insert(0, self.halo_band(rim, ratio, lit))
        p.save()
        p.setOpacity(p.opacity() * self.alpha(t))
        if self.plus:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for band in bands:
            self.envelope(band, pulses, tail, ratio)
            self.lay(p, rim, band, ratio, lit)
        if self.head > 0:
            for head in _heads(rim, t, self.period, self.count, self.laps):
                x, y, _ = rim.at(head)
                spot = QRadialGradient(QPointF(x, y), self.head)
                core = QColor(self.colour)
                core.setAlphaF(0.7)
                edge = QColor(self.colour)
                edge.setAlpha(0)
                spot.setColorAt(0.0, QColor(255, 255, 255, 215))
                spot.setColorAt(0.35, core)
                spot.setColorAt(1.0, edge)
                p.fillRect(QRectF(x - self.head, y - self.head, 2 * self.head, 2 * self.head), spot)
        p.restore()


class Glow(Layer):
    """The still's own rim, added on top of itself on a slow sine: the border brightens and settles."""

    def __init__(self, folder, entry: dict, k: float):
        super().__init__(folder, entry, k)
        self.period = float(entry["period"])
        self.amount = float(entry.get("amount", 0.2))
        self.beats = [int(v) for v in entry.get("beats", [1])]  # whole cycles per period, summed

    def paint(self, p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        level = sum(0.5 - 0.5 * math.cos(TAU * b * t / self.period + 1.7 * i) for i, b in enumerate(self.beats)) / len(self.beats)
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.setOpacity(p.opacity() * self.amount * level)
        art.draw(p, art.rim_only(rim))
        p.restore()


class Swap(Layer):
    """The same rim painted in other colours, faded in and out over the still on a cosine. The outline is
    identical, so nothing moves: only the colour drifts. The art is transparent wherever the colours are
    the same (the fill), so the text area is never drawn over."""

    def __init__(self, folder, entry: dict, k: float):
        super().__init__(folder, entry, k)
        self.pix = _load(folder, entry["file"])
        self.period = float(entry["period"])
        self.amount = float(entry.get("amount", 1.0))

    def paint(self, p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        weight = self.amount * (0.5 - 0.5 * math.cos(TAU * t / self.period))
        if weight < 0.004:
            return
        p.save()
        p.setOpacity(p.opacity() * weight)
        art.draw(p, art.composed(self.pix, "swap", rim))
        p.restore()


class Sheen(Layer):
    """Glints that glide a short way along the border and fade: the still's own border line (not its outer
    glow), added on top of itself inside a soft spot that moves along it. Each glint has its own slot on
    the timeline and its own stretch of border. It skips the notch's mouth, where there is no line."""

    def __init__(self, folder, entry: dict, k: float):
        super().__init__(folder, entry, k)
        self.period = float(entry["period"])
        self.count = int(entry.get("count", 2))  # glints per cycle
        self.life = float(entry.get("life", 2.6))  # seconds each one lasts
        self.speed = float(entry.get("speed", 34.0))  # display px a second along the border
        self.reach = float(entry.get("reach", 40.0))  # the spot's radius, display px
        self.amount = float(entry.get("amount", 0.8))
        self.seed = int(entry.get("seed", 1))
        self._layer: QPixmap | None = None

    def glints(self, rim: Rim, t: float) -> list[tuple[float, float]]:
        """(distance along the border, strength 0..1) of each glint showing at time `t`."""
        out = []
        for i in range(self.count):
            local = (t - i * self.period / self.count) % self.period
            if local < self.life:
                f = local / self.life
                start = (i + 0.15 + 0.5 * _h(self.seed, i, 1)) / self.count * rim.length
                out.append((start + self.speed * local, _smooth(f / 0.35) * _smooth((1 - f) / 0.35)))
        return out

    def paint(self, p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        r = self.reach
        size = max(2, round((2 * r + 2) * art.ratio))
        if self._layer is None or self._layer.width() != size:
            self._layer = QPixmap(size, size)
            self._layer.setDevicePixelRatio(art.ratio)
        layer = self._layer
        for s, strength in self.glints(rim, t):
            if strength < 0.004:
                continue
            x, y, _ = rim.at(s)
            ox, oy = math.floor(x - r), math.floor(y - r)  # the layer sits on whole pixels; the spot moves inside it
            layer.fill(Qt.GlobalColor.transparent)
            q = QPainter(layer)
            art.draw(q, art.rim_line(rim), -ox, -oy)
            q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            spot = QRadialGradient(QPointF(x - ox, y - oy), r)
            spot.setColorAt(0, QColor(0, 0, 0, 255))
            spot.setColorAt(0.45, QColor(0, 0, 0, 150))
            spot.setColorAt(1, QColor(0, 0, 0, 0))
            q.fillRect(QRectF(0, 0, 2 * r + 2, 2 * r + 2), spot)
            q.end()
            p.save()
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            p.setOpacity(p.opacity() * self.amount * strength)
            p.drawPixmap(QPointF(ox, oy), layer)
            p.restore()


class Flames(Layer):
    """A baked loop of a tileable flame strip, tiled along the top edge only and fading out before the
    corners. Neighbouring frames of the loop are cross-faded, so it plays smoothly at any redraw rate."""

    def __init__(self, folder, entry: dict, k: float):
        super().__init__(folder, entry, k)
        sheet = _load(folder, entry["file"])
        n, w, h = int(entry["frames"]), int(entry["w"]), int(entry["h"])
        self.frames = [sheet.copy(0, i * h, w, h) for i in range(n)]
        self.period = float(entry["period"])
        self.base = float(entry["base"]) * k  # the baseline's distance from the strip's top, display px
        self.tile, self.height = w * k, h * k
        self.fade = float(entry.get("fade", 26.0))  # display px over which the row fades out at each end
        self.reach = float(entry.get("reach", 6.0))  # how far past the straight edge the row runs, onto the corners
        self._layer: QPixmap | None = None
        self._key = None

    def paint(self, p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        x0, x1 = rim.x0 + rim.r - self.reach, rim.x1 - rim.r + self.reach
        width = x1 - x0
        if width < 20:
            return
        ratio = art.ratio
        key = (round(width * ratio), ratio)
        if self._key != key:
            self._layer = QPixmap(max(1, round(width * ratio)), max(1, round(self.height * ratio)))
            self._layer.setDevicePixelRatio(ratio)
            self._key = key
        layer = self._layer
        layer.fill(Qt.GlobalColor.transparent)
        f = (t / self.period) * len(self.frames)
        i = int(f) % len(self.frames)
        j = (i + 1) % len(self.frames)
        mix = f - int(f)
        n = max(1, round(width / self.tile))
        q = QPainter(layer)
        q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        q.scale(width / (n * self.frames[0].width()), self.height / self.frames[0].height())
        target = QRectF(0, 0, n * self.frames[0].width(), self.frames[0].height())
        q.drawTiledPixmap(target, self.frames[i])
        # Cross-fade to the next frame of the loop: A over B at weight `mix`, exactly (no brightening).
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        q.fillRect(target, QColor(0, 0, 0, round(255 * (1 - mix))))
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        q.setOpacity(mix)
        q.drawTiledPixmap(target, self.frames[j])
        q.resetTransform()
        q.scale(ratio, ratio)
        q.setOpacity(1.0)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        fade = QLinearGradient(0, 0, width, 0)
        edge = min(0.45, self.fade / width)
        fade.setColorAt(0, QColor(0, 0, 0, 0))
        fade.setColorAt(edge, QColor(0, 0, 0, 255))
        fade.setColorAt(1 - edge, QColor(0, 0, 0, 255))
        fade.setColorAt(1, QColor(0, 0, 0, 0))
        q.fillRect(QRectF(0, 0, width, self.height), fade)
        q.end()
        p.drawPixmap(QPointF(x0, rim.y0 - self.base), layer)


class Sprites(Layer):
    """Single sprites from one sheet (side by side), each shown on its own slot of a fixed timeline."""

    def __init__(self, folder, entry: dict, k: float):
        super().__init__(folder, entry, k)
        sheet = _load(folder, entry["file"])
        n, w, h = int(entry["count"]), int(entry["w"]), int(entry["h"])
        self.sprites = [sheet.copy(i * w, 0, w, h) for i in range(n)]
        self.size = QSizeF(w * k, h * k)
        self.period = float(entry["period"])
        self.slots = int(entry.get("slots", 4))  # how many appear per cycle
        self.life = float(entry.get("life", 1.2))  # seconds each one lasts
        self.seed = int(entry.get("seed", 1))
        self.scale = float(entry.get("scale", 1.0))
        self.offset = float(entry.get("offset", 0.0))  # display px outward from the border line
        self.plus = bool(entry.get("plus", False))

    def slot(self, i: int, t: float) -> tuple[float, int] | None:
        """(progress 0..1, which cycle) for slot `i` at time `t`, or None while it is dark."""
        begin = (i + 0.37 * _h(self.seed, i, 1)) / self.slots * self.period
        local = (t - begin) % self.period
        return (local / self.life, int((t - begin) // self.period)) if local < self.life else None

    def draw(self, p: QPainter, sprite: QPixmap, x: float, y: float, angle: float, scale: float, alpha: float) -> None:
        if alpha <= 0.004 or scale <= 0.02:
            return
        w, h = self.size.width() * scale * self.scale, self.size.height() * scale * self.scale
        p.save()
        p.translate(x, y)
        p.rotate(angle)
        p.setOpacity(p.opacity() * min(1.0, alpha))
        p.drawPixmap(QRectF(-w / 2, -h / 2, w, h), sprite, QRectF(sprite.rect()))
        p.restore()


class Arcs(Sprites):
    """Short lightning arcs that crackle at set places on the straight edges: each holds for a few
    flickers, then fades. They flicker in place on purpose; nothing else in the picture does."""

    def paint(self, p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        if self.plus:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for i in range(self.slots):
            got = self.slot(i, t)
            if got is None:
                continue
            f, _ = got
            x, y, ang = rim.at(rim.on_straight(_h(self.seed, i, 2)))
            beat = int(f * self.life / 0.09)  # a new look every 90 ms while it holds
            sprite = self.sprites[int(_h(self.seed, i, 3) * len(self.sprites) + (beat // 2)) % len(self.sprites)]
            flicker = (1.0, 0.7, 0.95, 0.8)[beat % 4]
            fade = _smooth(f / 0.12) * _smooth((1 - f) / 0.45)
            flip = -1 if _h(self.seed, i, 4) < 0.5 else 1
            p.save()
            p.translate(x, y)
            p.rotate(ang)
            p.translate(0, -self.offset)  # a little outside the border line
            p.scale(1, flip)
            self.draw(p, sprite, 0, 0, 0, 0.8 + 0.3 * _h(self.seed, i, 5), flicker * fade)
            p.restore()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)


class Wake(Sprites):
    """Short lightning arcs left behind a `Runner`'s heads (same `period`, `count` and `laps`): at set
    places on the straight edges, about `spacing` px apart, an arc strikes as a head passes, crackles in
    place for `life` seconds and fades. Each place fires once per head per period, so the loop closes."""

    def __init__(self, folder, entry: dict, k: float):
        super().__init__(folder, entry, k)
        self.count = max(1, int(entry.get("count", 2)))
        self.laps = int(entry.get("laps", 1)) or 1
        self.spacing = float(entry.get("spacing", 90.0))
        self._places: tuple[tuple, list[float]] | None = None

    def places(self, rim: Rim) -> list[float]:
        key = (rim.key, rim.notch)  # type: ignore[attr-defined]
        if self._places is None or self._places[0] != key:
            n = max(3, round(0.62 * rim.length / self.spacing))  # about what the straight edges hold
            spots = [rim.on_straight((j + 0.2 + 0.6 * _h(self.seed, j, 1)) / n) for j in range(n)]
            reach = self.size.width() * self.scale / 2  # an arc is straight: it needs this much edge either side
            fits = [s for s in spots if rim.at(s - reach)[2] == rim.at(s)[2] == rim.at(s + reach)[2]]
            self._places = (key, fits or spots[:1])
        return self._places[1]

    def paint(self, p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        if self.plus:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        speed = abs(self.laps) * rim.length / self.period  # display px a second
        way = 1 if self.laps > 0 else -1
        heads = _heads(rim, t, self.period, self.count, self.laps)
        for j, at in enumerate(self.places(rim)):
            for n, head in enumerate(heads):
                age = ((way * (head - at)) % rim.length) / speed  # seconds since this head passed
                if age >= self.life:
                    continue
                f = age / self.life
                beat = int(age / 0.09)  # a new look every 90 ms while it holds
                sprite = self.sprites[int(_h(self.seed, j, n, 3) * len(self.sprites) + (beat // 2)) % len(self.sprites)]
                flicker = (1.0, 0.72, 0.95, 0.8)[beat % 4]
                fade = _smooth(f / 0.1) * _smooth((1 - f) / 0.55)
                flip = -1 if _h(self.seed, j, n, 4) < 0.5 else 1
                x, y, ang = rim.at(at)
                p.save()
                p.translate(x, y)
                p.rotate(ang)
                p.translate(0, -self.offset)  # a little outside the border line
                p.scale(way, flip)
                self.draw(p, sprite, 0, 0, 0, 0.9 + 0.3 * _h(self.seed, j, n, 5), flicker * fade)
                p.restore()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)


class Sparkles(Sprites):
    """Glints that swell, turn a little and fade at set places round the border."""

    def paint(self, p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        if self.plus:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        self._glints(p, rim, t)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    def _glints(self, p: QPainter, rim: Rim, t: float) -> None:
        for i in range(self.slots):
            got = self.slot(i, t)
            if got is None:
                continue
            f, _ = got
            x, y, _ = rim.at((i + 0.5 * _h(self.seed, i, 2)) / self.slots * rim.length)
            grow = _smooth(f / 0.25)
            fade = _smooth((1 - f) / 0.55)
            sprite = self.sprites[int(_h(self.seed, i, 3) * len(self.sprites)) % len(self.sprites)]
            self.draw(p, sprite, x, y, 12 + 24 * f, 0.45 + 0.55 * grow, grow * fade)


class Embers(Sprites):
    """Embers that lift off the top edge, drift up a little and die."""

    def paint(self, p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        p.save()
        if self.plus:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        a = rim.top[1]
        for i in range(self.slots):
            got = self.slot(i, t)
            if got is None:
                continue
            f, _ = got
            x = rim.x0 + rim.r + (0.08 + 0.84 * _h(self.seed, i, 2)) * a
            sway = 3.0 * math.sin(TAU * (f * 0.9 + _h(self.seed, i, 6)))
            sprite = self.sprites[int(_h(self.seed, i, 3) * len(self.sprites)) % len(self.sprites)]
            fade = _smooth(f / 0.15) * (1 - f) ** 1.3
            self.draw(p, sprite, x + sway, rim.y0 - 3 - 15 * f, 0, 0.9 - 0.35 * f, fade)
        p.restore()


class Crawler(Layer):
    """A caterpillar inching along the top edge. Its gait is a loop of frames baked from one painted
    sprite (art/tools/bubble-cut.py), one wave from tail to head per stride. It walks the top edge, fades
    out near the corner, rests out of sight for a moment, and starts again."""

    def __init__(self, folder, entry: dict, k: float):
        super().__init__(folder, entry, k)
        sheet = _load(folder, entry["file"])
        n, w, h = int(entry["frames"]), int(entry["w"]), int(entry["h"])
        self.frames = [sheet.copy(i * w, 0, w, h) for i in range(n)]
        self.size = QSizeF(w * k, h * k)
        self.speed = float(entry.get("speed", 10.0))  # display px a second
        self.stride = float(entry.get("stride", 1.4))  # seconds per wave
        self.rest = float(entry.get("rest", 2.8))  # seconds out of sight (rounded up so the cycle is whole strides)
        self.feet = float(entry.get("feet", 0.86))  # the feet's height in the sprite, as a share from the top
        self.sink = float(entry.get("sink", 0.0))  # display px below the border line the feet stand

    def span(self, rim: Rim) -> float:
        return max(1.0, rim.top[1] - self.size.width() + 6)

    def cycle(self, rim: Rim) -> float:
        walk = self.span(rim) / self.speed
        return math.ceil((walk + self.rest) / self.stride) * self.stride  # whole strides, so the gait closes too

    def paint(self, p: QPainter, rim: Rim, t: float, art: BubbleArt) -> None:
        period = self.cycle(rim)
        walk = self.span(rim) / self.speed
        local = t % period
        if local >= walk:
            return
        fade = _smooth(min(local, walk - local) / 0.9)
        w, h = self.size.width(), self.size.height()
        x = rim.x0 + rim.r - 3 + local * self.speed
        y = rim.y0 + self.sink - h * self.feet
        # (the tiny nudge keeps a redraw that lands exactly on a frame's start from rounding to the one before)
        frame = self.frames[int((local / self.stride) * len(self.frames) + 1e-6) % len(self.frames)]
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setOpacity(p.opacity() * fade)
        p.drawPixmap(QRectF(x, y, w, h), frame, QRectF(frame.rect()))
        p.restore()


LAYERS = {
    "scroll": Scroll,
    "runner": Runner,
    "glow": Glow,
    "swap": Swap,
    "sheen": Sheen,
    "flames": Flames,
    "arcs": Arcs,
    "wake": Wake,
    "sparkles": Sparkles,
    "embers": Embers,
    "crawler": Crawler,
}


class BubbleArt:
    def __init__(self, name: str, entry: dict):
        folder = paths.bubbles_dir()
        self.name = name
        self.still = _load(folder, f"{name}-still.png")
        self.k = float(entry["scale"])  # display px per art px
        self.w, self.h = int(entry["w"]), int(entry["h"])
        self.text = [int(v) for v in entry["text"]]  # x0, y0, x1, y1 (art px): the plain fill
        self.corner = int(entry["corner"])
        self.notch = [int(v) for v in entry["notch"]]
        self.tip = [int(v) for v in entry["tail"]]
        rim = entry["rim"]
        self.rim_inset = [float(v) for v in rim["inset"]]  # art px from the frame's edges to the border line
        self.rim_radius = float(rim["radius"])
        self.rim_half = float(rim.get("half", 3.0))  # art px from the border line to the inside of the rim
        self.pad = float(PAD.get(name, 12))  # display px between the fill's edge and the text
        self.layers: list[Layer] = [LAYERS[e["type"]](folder, e, self.k) for e in entry.get("fx", [])]
        self.ratio = 1.0
        self._cache: dict[tuple, QPixmap] = {}  # pictures above the notch's band, one per size
        self._bands: dict[tuple, QPixmap] = {}  # the notch's band, one per size and notch place
        self._rims: dict[tuple, Rim] = {}
        self._overlay: QPixmap | None = None

    # -- geometry

    def margins(self) -> tuple[float, float, float, float]:
        """Display px from the text area out to the frame's edges: left, top, right, bottom."""
        x0, y0, x1, y1 = self.text
        k, d = self.k, self.pad
        return x0 * k + d, y0 * k + d, (self.w - x1) * k + d, (self.h - y1) * k + d

    def minimum(self) -> QSizeF:
        """The smallest text area the corners allow."""
        c = self.corner * self.k
        notch = (self.notch[1] - self.notch[0]) * self.k
        return QSizeF(max(2 * c, notch + 2 * c), 2 * c)

    def tail_range(self, text_width: float) -> tuple[float, float]:
        """Where along a bubble with this text width the notch's tip can go (x from the frame's left edge)."""
        k = self.k
        left, _, right, _ = self.margins()
        width = left + text_width + right
        tip = self.tip[0]
        lo = (self.text[0] + self.corner + (tip - self.notch[0])) * k
        hi = width - (self.w - self.text[2] + self.corner + (self.notch[1] - tip)) * k
        return lo, max(lo, hi)

    def frame_for(self, text: QSizeF) -> Frame:
        left, top, right, bottom = self.margins()
        size = QSizeF(left + text.width() + right, top + text.height() + bottom)
        tip_y = top + text.height() + self.pad + (self.tip[1] - self.text[3]) * self.k
        return Frame(size, QRectF(left, top, text.width(), text.height()), (0.0, tip_y), (left, top, right, bottom))

    def rim(self, tw: int, th: int, tip_x: float) -> Rim:
        """The border line for a bubble with this text size, its notch at `tip_x`. The line is worked out once per
        size (what follows it caches by `rim.key`); only where the notch is changes as the bubble follows the
        penguin, and what depends on that keys by `rim.notch` too."""
        key = (tw, th)
        k = self.k
        if key not in self._rims:
            if len(self._rims) > 8:
                self._rims.clear()
            width, height = self._size(tw, th)
            l, t, r, b = (v * k for v in self.rim_inset)
            self._rims[key] = Rim(l, t, width - r, height - b, self.rim_radius * k, (0.0, 0.0))
            self._rims[key].key = key  # type: ignore[attr-defined]
        rim = self._rims[key]
        n0 = tip_x - (self.tip[0] - self.notch[0]) * k
        rim.notch = (n0, n0 + (self.notch[1] - self.notch[0]) * k)
        rim.tip = round(tip_x)  # type: ignore[attr-defined]
        return rim

    def loop_period(self, text: QSizeF, tip_x: float | None = None) -> float:
        """Seconds after which the animated bubble repeats exactly, for this text size."""
        lo, hi = self.tail_range(text.width())
        rim = self.rim(round(text.width()), round(text.height()), round(min(max(tip_x if tip_x is not None else lo, lo), hi)))
        periods = [layer.cycle(rim) for layer in self.layers] or [1.0]
        longest = max(periods)
        for whole in range(1, 13):  # the shortest time every layer has done whole cycles
            if all(abs((longest * whole) / q - round((longest * whole) / q)) < 1e-6 for q in periods):
                return longest * whole
        return longest

    # -- drawing

    def _compose(self, pix: QPixmap, text_w: float, text_h: float, tip_x: float, ratio: float, rows: tuple[int, int] | None = None) -> QPixmap:
        """The painted bubble stretched round a text area, its notch's tip at `tip_x` (display px from the frame's
        left). With `rows`, only those rows of device pixels, [first, last): the same pixels the whole picture has
        there."""
        k = self.k
        x0, y0, x1, y1 = self.text
        c = self.corner
        n0, n1 = self.notch
        sw, sh = self.w, self.h
        left, top, right, bottom = self.margins()
        W, H = left + text_w + right, top + text_h + bottom  # the whole frame, display px
        # Source columns and rows (art px), and where they land (display px).
        L, R = x0 + c, sw - x1 + c
        T, B = y0 + c, sh - y1 + c
        dL, dR, dT, dB = L * k, R * k, T * k, B * k
        nx0 = tip_x - (self.tip[0] - n0) * k  # the notch strip's left edge, display
        nx1 = nx0 + (n1 - n0) * k
        first, last = rows if rows is not None else (0, max(1, round(H * ratio)))
        out = QPixmap(max(1, round(W * ratio)), max(1, last - first))
        out.setDevicePixelRatio(ratio)
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.translate(0, -first / ratio)

        def put(sx0, sy0, sx1, sy1, dx0, dy0, dx1, dy1):
            if dy1 * ratio <= first or dy0 * ratio >= last:  # none of it in these rows
                return
            if dx1 - dx0 > 0.01 and dy1 - dy0 > 0.01 and sx1 > sx0 and sy1 > sy0:
                p.drawPixmap(QRectF(dx0, dy0, dx1 - dx0, dy1 - dy0), pix, QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0))

        rows = ((0, T, 0, dT), (T, sh - B, dT, H - dB))
        for sy0, sy1, dy0, dy1 in rows:  # the top band and the middle: three columns each
            put(0, sy0, L, sy1, 0, dy0, dL, dy1)
            put(L, sy0, sw - R, sy1, dL, dy0, W - dR, dy1)
            put(sw - R, sy0, sw, sy1, W - dR, dy0, W, dy1)
        sy0, dy0 = sh - B, H - dB  # the bottom band: corner, stretch, notch, stretch, corner
        put(0, sy0, L, sh, 0, dy0, dL, H)
        put(L, sy0, n0, sh, dL, dy0, nx0, H)
        put(n0, sy0, n1, sh, nx0, dy0, nx1, H)
        put(n1, sy0, sw - R, sh, nx1, dy0, W - dR, H)
        put(sw - R, sy0, sw, sh, W - dR, dy0, W, H)
        p.end()
        return out

    # -- the still picture, in two parts: above the notch's band, kept per size; and the band, per notch place.
    # A bubble that follows the penguin moves its notch nearly every frame: only the band is made again.

    def band_top(self, th: int, ratio: float) -> int:
        """The first row of device pixels of the notch's band (the art's bottom edge, notch and corners)."""
        _, top, _, bottom = self.margins()
        rows = self.h - self.text[3] + self.corner  # art px: the bottom band
        return max(0, math.floor((top + th + bottom - rows * self.k) * ratio))

    def parts(self, pix: QPixmap, tag: str, rim: Rim) -> tuple[QPixmap, QPixmap, float]:
        """`pix` (the still, or art like it) composed round this rim's size and notch: (the picture above the notch's
        band, the band, the band's top in display px)."""
        tw, th = rim.key  # type: ignore[attr-defined]
        tip, ratio = rim.tip, self.ratio  # type: ignore[attr-defined]
        first = self.band_top(th, ratio)
        upper = self._cache.get((tag, tw, th, ratio))
        if upper is None:
            if len(self._cache) > 24:
                self._cache.clear()
            upper = self._cache[(tag, tw, th, ratio)] = self._compose(pix, tw, th, tip, ratio, (0, max(1, first)))
        lower = self._bands.get((tag, tw, th, tip, ratio))
        if lower is None:
            if len(self._bands) > 48:
                self._bands.clear()
            whole = round(self._size(tw, th)[1] * ratio)
            lower = self._bands[(tag, tw, th, tip, ratio)] = self._compose(pix, tw, th, tip, ratio, (first, max(first + 1, whole)))
        return upper, lower, first / ratio

    def _derived(self, tag: str, rim: Rim, make, source: tuple[QPixmap, QPixmap, float] | None = None) -> tuple[QPixmap, QPixmap, float]:
        """`source`'s parts (the still's, by default), each copied and changed by `make(pixmap, rows_top)`, and
        kept like the still's own: above the band once per size, the band once per notch place."""
        tw, th = rim.key  # type: ignore[attr-defined]
        tip, ratio = rim.tip, self.ratio  # type: ignore[attr-defined]
        upper, lower, top = source if source is not None else self.parts(self.still, "still", rim)
        up = self._cache.get((tag, tw, th, ratio))
        if up is None:
            up = self._cache[(tag, tw, th, ratio)] = make(QPixmap(upper), 0.0)
        down = self._bands.get((tag, tw, th, tip, ratio))
        if down is None:
            down = self._bands[(tag, tw, th, tip, ratio)] = make(QPixmap(lower), top)
        return up, down, top

    @staticmethod
    def draw(p: QPainter, parts: tuple[QPixmap, QPixmap, float], x: float = 0.0, y: float = 0.0) -> None:
        upper, lower, top = parts
        p.drawPixmap(QPointF(x, y), upper)
        p.drawPixmap(QPointF(x, y + top), lower)

    def composed(self, pix: QPixmap, tag: str, rim: Rim) -> tuple[QPixmap, QPixmap, float]:
        return self.parts(pix, tag, rim)

    def rim_only(self, rim: Rim) -> tuple[QPixmap, QPixmap, float]:
        """The composed still with its fill cut out: just the border and its glow."""

        def cut(pix: QPixmap, top: float) -> QPixmap:
            q = QPainter(pix)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            q.translate(0, -top)
            q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            q.fillPath(rim.path(self.rim_half * self.k + 1.5), QColor(0, 0, 0))
            n0, n1 = rim.notch  # and the notch's fill, which hangs below the border line
            q.fillRect(QRectF(n0 - 2, rim.y1 - self.rim_half * self.k - 3, n1 - n0 + 4, top + pix.height()), QColor(0, 0, 0))
            q.end()
            return pix

        return self._derived("rim", rim, cut)

    def rim_line(self, rim: Rim) -> tuple[QPixmap, QPixmap, float]:
        """Just the border line itself: the rim without the glow outside it. The soft glow is see-through,
        and adding it to itself would make it more solid (a white smear on a light desktop), so the line
        is cut to a narrow band and what is see-through in it is faded further."""
        rim_parts = self.rim_only(rim)
        mask = self._line_mask(rim)

        def line(pix: QPixmap, top: float) -> QPixmap:
            whole = QPixmap(pix)
            q = QPainter(pix)
            q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            q.drawPixmap(QPointF(0, -top), mask)
            q.drawPixmap(QPointF(0, 0), whole)  # twice through its own alpha: only what is nearly solid stays
            q.drawPixmap(QPointF(0, 0), whole)
            q.end()
            return pix

        return self._derived("line", rim, line, rim_parts)

    def _line_mask(self, rim: Rim) -> QPixmap:
        """A band along the border line, strongest on it and fading to nothing either side: the same wherever
        the notch is, so it is stroked once per size (six wide strokes round the border cost more than all the
        rest of a notch's move)."""
        tw, th = rim.key  # type: ignore[attr-defined]
        key = ("line mask", tw, th, self.ratio)
        if key not in self._cache:
            width, height = self._size(tw, th)
            mask = QPixmap(max(1, round(width * self.ratio)), max(1, round(height * self.ratio)))
            mask.setDevicePixelRatio(self.ratio)
            mask.fill(Qt.GlobalColor.transparent)
            reach = self.rim_half * self.k + 1.5  # as far in as the rim goes
            q = QPainter(mask)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            for i, strength in enumerate((10, 18, 26, 36, 46, 62)):  # strongest on the line, fading to nothing either side
                q.setPen(QPen(QColor(0, 0, 0, strength), 2 * reach * (1 - i / 6)))
                q.drawPath(rim.path())
            q.end()
            self._cache[key] = mask
        return self._cache[key]

    def mask_notch(self, q: QPainter, rim: Rim, height: float) -> None:
        """Clear what `q` drew over the notch's mouth on the bottom edge, where the fill runs into the notch:
        nothing that follows the border may draw a line across it."""
        n0, n1 = rim.notch
        soft = 12.0
        band = QRectF(n0 - soft, rim.y1 - 14, (n1 - n0) + 2 * soft, height - (rim.y1 - 14))
        fade = QLinearGradient(band.left(), 0, band.right(), 0)
        edge = soft / band.width()
        fade.setColorAt(0, QColor(0, 0, 0, 255))
        fade.setColorAt(min(0.49, 1.6 * edge), QColor(0, 0, 0, 0))
        fade.setColorAt(max(0.51, 1 - 1.6 * edge), QColor(0, 0, 0, 0))
        fade.setColorAt(1, QColor(0, 0, 0, 255))
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        q.fillRect(band, fade)

    def paint(self, p: QPainter, origin_x: float, origin_y: float, text: QSizeF, tip_x: float, age: float, animate: bool, effects: float = 1.0) -> None:
        """Draw the bubble with its frame's top-left at (origin_x, origin_y) and its notch's tip at `tip_x`
        (display px from the frame's left edge, clamped to where the notch can go). `effects`: how strongly the
        moving layers show (they fade out onto the still picture); none without `animate`."""
        lo, hi = self.tail_range(text.width())
        tip_x = round(min(max(tip_x, lo), hi))
        self.ratio = ratio = device_ratio(p)
        tw, th = round(text.width()), round(text.height())
        width, height = self._size(tw, th)
        rim = self.rim(tw, th, tip_x)
        still = self.parts(self.still, "still", rim)
        if not animate or not self.layers or effects <= 0.0:
            self.draw(p, still, origin_x, origin_y)
            return
        t = age % self.loop_period(text, tip_x)
        strips = [layer for layer in self.layers if layer.strip()]
        under = [layer for layer in self.layers if isinstance(layer, Flames)]
        over = [layer for layer in self.layers if not layer.strip() and not isinstance(layer, Flames)]
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.translate(origin_x, origin_y)
        base = p.opacity()
        p.setOpacity(base * min(1.0, effects))
        for layer in under:  # flames stand behind the bubble's edge
            layer.paint(p, rim, t, self)
        p.setOpacity(base)
        self.draw(p, still)
        p.setOpacity(base * min(1.0, effects))
        if strips:
            size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
            if self._overlay is None or (self._overlay.width(), self._overlay.height()) != size or self._overlay.devicePixelRatioF() != ratio:
                self._overlay = QPixmap(*size)
                self._overlay.setDevicePixelRatio(ratio)
            self._overlay.fill(Qt.GlobalColor.transparent)
            q = QPainter(self._overlay)
            q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            i = 0
            while i < len(strips):
                run = [strips[i]]
                while type(run[0]) is Scroll and i + len(run) < len(strips) and type(strips[i + len(run)]) is Scroll:
                    run.append(strips[i + len(run)])
                if len(run) > 1:
                    Scroll.paint_together(run, q, rim, t, self)
                else:
                    run[0].paint(q, rim, t, self)
                i += len(run)
            self.mask_notch(q, rim, height)
            q.end()
            p.drawPixmap(QPointF(0, 0), self._overlay)
        for layer in over:
            layer.paint(p, rim, t, self)
        p.restore()

    def _size(self, tw: int, th: int) -> tuple[float, float]:
        left, top, right, bottom = self.margins()
        return left + tw + right, top + th + bottom


PAD = {"leaf": 20}  # the ivy reaches into the leaf bubble's fill


@cache
def _manifest() -> dict:
    try:
        return json.loads((paths.bubbles_dir() / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


_loaded: dict[tuple[str, str], BubbleArt | None] = {}


def art(name: str, user: str = "") -> BubbleArt | None:
    """The style's painted bubble, or None if it has none (or its files are missing). Each `user` (the
    message bubble, the ask box) gets one of its own: it keeps what it drew last for the size it is, and
    two bubbles of different sizes sharing one would draw everything afresh every frame."""
    key = (name, user)
    if key not in _loaded:
        entry = _manifest().get(name)
        try:
            _loaded[key] = BubbleArt(name, entry) if entry and "rim" in entry else None
        except (FileNotFoundError, KeyError, TypeError, ValueError):
            _loaded[key] = None
    return _loaded[key]
