"""The penguin's menu, drawn on the stage.

On the Wayland overlay a QMenu can't be used: Qt's menus there are XWayland
popup windows, which sit under the overlay, and Hyprland doesn't deliver
clicks to them. So the stage draws the menu itself, like its speech bubbles,
from the same QMenu (its actions, checks, sections and submenus), and passes
the click to the chosen action.

While it's open the whole stage takes clicks, as a popup menu would: a click
anywhere else closes it. It takes the keyboard too (`key`): Esc, the arrows,
Home and End, Enter, and a letter to jump. A menu taller than the screen
scrolls, by its arrows, the wheel or the keyboard. A submenu opens once the
pointer has rested on its item for SUBMENU_DELAY, so a diagonal move towards
an open submenu doesn't switch it on the way.

The menu has no clock of its own: what's due later (a submenu, the next step
of a scroll arrow held) is done by `tick`, which the stage calls when
`next_change` says.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from PyQt6.QtCore import QEvent, QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QAction, QColor, QFont, QFontMetrics, QKeyEvent, QKeySequence, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QMenu

from .bubble import ACCENT, colours

ROW = 26  # the least a row is high, whatever the font
ROW_PAD = 8  # a row's height over its font's
SEPARATOR = 9
SECTION = 22
SECTION_PAD = 6
INSET = 4  # above the first row and below the last
PAD_X = 10
CHECK = 22  # room for a check mark
ARROW = 18  # room for a submenu arrow
RADIUS = 8
MARGIN = 4  # from the edges of the screen
MIN_WIDTH = 140
SHORTCUT_GAP = 24  # between an item and its shortcut
SCROLLER = 16  # the strip at the top and bottom of a menu that scrolls, with its arrow
SUBMENU_DELAY = 0.25  # s the pointer rests on an item before its submenu opens (or another closes)
SCROLL_REPEAT = 0.06  # s between steps while the pointer rests on a scroll arrow
WHEEL_ROWS = 3  # rows a notch of the wheel scrolls
CONTRAST = 4.5  # WCAG AA for text: headers, shortcuts and the highlighted row's label reach it
MUTED_AIM = 5.0  # what the muted text aims for, a little over CONTRAST, with the fill's slight transparency
FOCUS_PEN = 2.0  # the outline round the highlighted row


def label_parts(action: QAction) -> tuple[str, str]:
    """An item's label without its mnemonic marks (&File: F underlined in Qt's
    own menus), and its shortcut, which Qt's standard menus append after a tab."""
    text, _, shortcut = action.text().partition("\t")
    text = text.replace("&&", "\0").replace("&", "").replace("\0", "&")
    if not shortcut and not action.shortcut().isEmpty():
        shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
    return text, shortcut


def mnemonic(action: QAction) -> str:
    """The letter after an item's & mark ("&Quit": "q"), lower case; "" without one."""
    text = action.text().partition("\t")[0].replace("&&", "")
    at = text.find("&")
    return text[at + 1].lower() if 0 <= at < len(text) - 1 else ""


# -- colour, by the numbers (WCAG 2.x relative luminance and contrast ratio)


def _luminance(c: QColor) -> float:
    def channel(v: float) -> float:
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(c.redF()) + 0.7152 * channel(c.greenF()) + 0.0722 * channel(c.blueF())


def contrast(a: QColor, b: QColor) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    """a, moved t of the way to b (opaque)."""
    return QColor.fromRgbF(*(x + (y - x) * t for x, y in zip(a.getRgbF()[:3], b.getRgbF()[:3], strict=True)), 1.0)


def muted(text: QColor, fill: QColor, aim: float = MUTED_AIM, most: float = 0.5) -> QColor:
    """The text colour moved towards the fill as far as it can go while keeping `aim`:1 against it (and no
    more than `most` of the way): quieter than the labels, still readable."""
    if contrast(text, fill) <= aim:
        return QColor(text)
    lo, hi = 0.0, most
    for _ in range(24):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if contrast(_mix(text, fill, mid), fill) >= aim else (lo, mid)
    return _mix(text, fill, lo)


def on(background: QColor) -> QColor:
    """Black or white, whichever reads better on `background`."""
    black, white = QColor(0, 0, 0), QColor(255, 255, 255)
    return black if contrast(black, background) >= contrast(white, background) else white


@dataclass(frozen=True)
class Palette:
    fill: QColor  # the menu
    text: QColor  # its labels
    muted: QColor  # section headers and shortcuts: CONTRAST at least
    disabled: QColor  # items that can't be picked (exempt from the contrast rule, still legible)
    line: QColor  # separators
    hover: QColor  # the highlighted row, solid
    hover_text: QColor  # its label: CONTRAST at least on `hover`
    focus: QColor  # the outline round the highlighted row


def palette() -> Palette:
    fill, text = colours()
    solid = QColor(fill)
    solid.setAlpha(255)
    hover = QColor(ACCENT)
    hover.setAlpha(255)
    fill.setAlpha(250)
    quiet = muted(text, solid)
    return Palette(fill, QColor(text), quiet, _mix(text, solid, 0.55), _mix(text, solid, 0.6), hover, on(hover), QColor(text))


@dataclass
class _Item:
    action: QAction
    rect: QRect  # in the panel's content, which scrolls
    kind: str  # "action", "separator" or "section"

    def pickable(self) -> bool:
        return self.kind == "action" and self.action.isEnabled()


@dataclass
class _Panel:
    menu: QMenu
    rect: QRect  # on the stage
    items: list[_Item] = field(default_factory=list)
    height: int = 0  # all of its content, which may be more than shows
    scroll: int = 0  # content scrolled off the top
    active: int | None = None  # the highlighted item
    opener: int | None = None  # the item of the panel before that opened this one

    def scrolls(self) -> bool:
        return self.height > self.rect.height()

    def view(self) -> QRect:
        """Where items show, in the panel."""
        if self.scrolls():
            return QRect(0, SCROLLER, self.rect.width(), self.rect.height() - 2 * SCROLLER)
        return QRect(0, 0, self.rect.width(), self.rect.height())

    def max_scroll(self) -> int:
        return max(0, self.height - self.view().height()) if self.scrolls() else 0

    def item_rect(self, i: int) -> QRect:
        """An item's place in the panel, as scrolled."""
        offset = SCROLLER - self.scroll if self.scrolls() else 0
        return self.items[i].rect.translated(0, offset)

    def scroll_to(self, pixels: int) -> None:
        self.scroll = min(max(0, pixels), self.max_scroll())

    def show_item(self, i: int) -> None:
        """Scroll as little as it takes for item i to show whole."""
        r, view = self.items[i].rect, self.view().height()
        if r.top() - INSET < self.scroll:
            self.scroll_to(r.top() - INSET)
        elif r.bottom() + 1 + INSET > self.scroll + view:
            self.scroll_to(r.bottom() + 1 + INSET - view)


class StageMenu:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.panels: list[_Panel] = []
        self._area = QRect()
        self._clock = clock
        self._pending: tuple[int, int | None, float] | None = None  # (panel, item, when): a submenu to switch to
        self._scrolling: tuple[int, int, float] | None = None  # (panel, -1 up or 1 down, next step): an arrow held
        self._chosen: QAction | None = None  # picked by the keyboard, for the stage to run once the menu's closed

    def is_open(self) -> bool:
        return bool(self.panels)

    def open(self, menu: QMenu, at: QPointF, area: QRect) -> None:
        """Open `menu` with its corner at `at`, kept within `area` (local coordinates)."""
        self._area = QRect(area)
        self.panels = [self._layout(menu, QRect(at.toPoint(), at.toPoint()), first=True)]
        self._pending = self._scrolling = None
        self._chosen = None

    def close(self) -> None:
        self.panels = []
        self._pending = self._scrolling = None

    def rects(self) -> list[QRect]:
        return [p.rect for p in self.panels]

    def look(self) -> tuple:
        """Changes whenever the menu looks different."""
        return tuple((p.rect.x(), p.rect.y(), p.rect.width(), p.rect.height(), p.scroll, p.active) for p in self.panels)

    @property
    def hover(self) -> tuple[int, int] | None:
        """The highlighted item of the innermost panel that has one: (panel, item)."""
        for pi in range(len(self.panels) - 1, -1, -1):
            if self.panels[pi].active is not None:
                return pi, self.panels[pi].active
        return None

    def take_chosen(self) -> QAction | None:
        chosen, self._chosen = self._chosen, None
        return chosen

    # -- what's due later

    def next_change(self) -> float:
        due = math.inf
        if self._pending is not None:
            due = self._pending[2]
        if self._scrolling is not None:
            due = min(due, self._scrolling[2])
        return due

    def tick(self, now: float | None = None) -> None:
        now = self._clock() if now is None else now
        if self._pending is not None and now >= self._pending[2]:
            pi, ii, _ = self._pending
            self._pending = None
            if pi < len(self.panels):
                self._open_from(pi, ii)
        if self._scrolling is not None and now >= self._scrolling[2]:
            pi, step, _ = self._scrolling
            if pi < len(self.panels):
                panel = self.panels[pi]
                before = panel.scroll
                panel.scroll_to(panel.scroll + step * self._row_height())
                self._scrolling = (pi, step, now + SCROLL_REPEAT) if panel.scroll != before else None
            else:
                self._scrolling = None

    # -- the pointer

    def move(self, pos: QPointF) -> None:
        hit = self._hit(pos)
        if hit is None or hit[1] in ("up", "down"):
            if hit is None:
                self._scrolling = None
            else:  # resting on a scroll arrow: it scrolls, a step at a time
                step = -1 if hit[1] == "up" else 1
                if self._scrolling is None or self._scrolling[:2] != (hit[0], step):
                    self._scrolling = (hit[0], step, self._clock())
            return  # crossing a gap, or off the menu: what's open stays
        pi, ii = hit
        self._scrolling = None
        # On a submenu (perhaps on the way from its parent): its parents keep the items it came from lit.
        for p in range(pi):
            self.panels[p].active = self.panels[p + 1].opener
        if self._pending is not None and self._pending[0] < pi:
            self._pending = None  # it got there in time: the submenu stays
        panel = self.panels[pi]
        wanted = ii if panel.items[ii].pickable() else None
        if wanted == panel.active and (self._pending is None or self._pending[1] == ii):
            return  # the same item: nothing to build again
        panel.active = wanted
        if pi + 1 < len(self.panels) and self.panels[pi + 1].opener == ii:
            self._pending = None  # back on the item whose submenu is open
        elif pi + 1 < len(self.panels) or self._has_submenu(pi, ii):
            self._pending = (pi, ii, self._clock() + SUBMENU_DELAY)

    def press(self, pos: QPointF) -> QAction | None:
        """A click: the action to run once the menu's closed, if it was on one."""
        hit = self._hit(pos)
        if hit is None:
            if not any(p.rect.contains(pos.toPoint()) for p in self.panels):
                self.close()  # a click elsewhere closes it
            return None
        pi, part = hit
        if part in ("up", "down"):
            panel = self.panels[pi]
            panel.scroll_to(panel.scroll + (-1 if part == "up" else 1) * self._row_height())
            return None
        item = self.panels[pi].items[part]
        if not item.pickable():
            return None
        if item.action.menu() is not None:
            self._pending = None
            self._open_from(pi, part)  # at once, on a click
            return None
        self.close()
        return item.action

    def wheel(self, pos: QPointF, dy: int) -> None:
        """Qt's angle delta (120 a notch, up positive) over the menu: the panel under it scrolls."""
        hit = self._hit(pos)
        pi = hit[0] if hit is not None else next((i for i in range(len(self.panels) - 1, -1, -1) if self.panels[i].rect.contains(pos.toPoint())), None)
        if pi is None or not dy:
            return
        panel = self.panels[pi]
        panel.scroll_to(panel.scroll - round(dy / 120 * WHEEL_ROWS * self._row_height()))

    def _hit(self, pos: QPointF) -> tuple[int, int | str] | None:
        """(panel, item index or "up" or "down" for a scroll arrow) under a point, or None."""
        point = pos.toPoint()
        for pi in range(len(self.panels) - 1, -1, -1):  # submenus are on top
            panel = self.panels[pi]
            if panel.rect.contains(point):
                local = point - panel.rect.topLeft()
                if panel.scrolls() and not panel.view().contains(local):
                    return pi, "up" if local.y() < SCROLLER else "down"
                for ii in range(len(panel.items)):
                    if panel.item_rect(ii).contains(local):
                        return pi, ii
                return None
        return None

    def _has_submenu(self, pi: int, ii: int) -> bool:
        item = self.panels[pi].items[ii]
        return item.pickable() and item.action.menu() is not None

    def _open_from(self, pi: int, ii: int | None) -> None:
        """Close what's open beyond panel pi; open item ii's submenu if it has one."""
        del self.panels[pi + 1 :]
        panel = self.panels[pi]
        if ii is None or not self._has_submenu(pi, ii):
            return
        panel.active = ii
        anchor = panel.item_rect(ii).translated(panel.rect.topLeft())
        self.panels.append(self._layout(panel.items[ii].action.menu(), anchor, first=False, opener=ii))

    # -- the keyboard

    def key(self, event: QKeyEvent) -> bool:
        """A key while the menu is open. Every key is the menu's while it's open (as with any popup menu), so
        this is True whenever it's open; an item picked with Enter or its letter is left for take_chosen()."""
        if not self.panels:
            return False
        if event.type() != QEvent.Type.KeyPress:
            return True
        self._pending = self._scrolling = None
        # The keys are the innermost menu's with a lit item: a submenu the pointer opened takes them once
        # you're in it (Right, or the pointer), as in Qt's menus.
        pi = max((i for i, p in enumerate(self.panels) if p.active is not None), default=0)
        panel = self.panels[pi]
        key = event.key()
        if key == Qt.Key.Key_Escape:
            if len(self.panels) > 1:
                del self.panels[-1:]  # back to the menu it came from
            else:
                self.close()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self._step(panel, -1 if key in (Qt.Key.Key_Up, Qt.Key.Key_Backtab) else 1)
            self._close_beyond(pi)
        elif key in (Qt.Key.Key_Home, Qt.Key.Key_End):
            pickable = self._pickable(panel)
            if pickable:
                self._activate(panel, pickable[0 if key == Qt.Key.Key_Home else -1])
                self._close_beyond(pi)
        elif key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            rows = max(1, panel.view().height() // self._row_height() - 1)
            for _ in range(rows):
                self._step(panel, -1 if key == Qt.Key.Key_PageUp else 1, wrap=False)
            self._close_beyond(pi)
        elif key == Qt.Key.Key_Right:
            if panel.active is not None and self._has_submenu(pi, panel.active):
                self._enter(pi, panel.active)
        elif key == Qt.Key.Key_Left:
            if pi:
                del self.panels[pi:]
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if panel.active is not None:
                self._pick(pi, panel.active)
        else:
            self._letter(pi, event.text())
        return True

    def _pickable(self, panel: _Panel) -> list[int]:
        return [i for i, item in enumerate(panel.items) if item.pickable()]

    def _close_beyond(self, pi: int) -> None:
        """The lit item of panel pi moved off the one whose submenu is open: that submenu closes."""
        if pi + 1 < len(self.panels) and self.panels[pi + 1].opener != self.panels[pi].active:
            del self.panels[pi + 1 :]

    def _activate(self, panel: _Panel, i: int) -> None:
        panel.active = i
        panel.show_item(i)

    def _step(self, panel: _Panel, by: int, wrap: bool = True) -> None:
        pickable = self._pickable(panel)
        if not pickable:
            return
        if panel.active not in pickable:
            self._activate(panel, pickable[0 if by > 0 else -1])
            return
        at = pickable.index(panel.active) + by
        if not wrap:
            at = min(max(at, 0), len(pickable) - 1)
        self._activate(panel, pickable[at % len(pickable)])

    def _enter(self, pi: int, ii: int) -> None:
        """Open item ii's submenu from the keyboard, its first item lit."""
        self._open_from(pi, ii)
        sub = self.panels[-1]
        pickable = self._pickable(sub)
        if pickable:
            self._activate(sub, pickable[0])

    def _pick(self, pi: int, ii: int) -> None:
        if self._has_submenu(pi, ii):
            self._enter(pi, ii)
        elif self.panels[pi].items[ii].pickable():
            self._chosen = self.panels[pi].items[ii].action
            self.close()

    def _letter(self, pi: int, text: str) -> None:
        """An item's & letter picks it, if it's the only one with it; otherwise a letter lights the next item
        whose label starts with it."""
        letter = text.lower()
        if len(letter) != 1 or not letter.isprintable() or letter.isspace():
            return
        panel = self.panels[pi]
        pickable = self._pickable(panel)
        marked = [i for i in pickable if mnemonic(panel.items[i].action) == letter]
        if len(marked) == 1:
            self._activate(panel, marked[0])
            self._pick(pi, marked[0])
            return
        starting = [i for i in pickable if label_parts(panel.items[i].action)[0].lower().startswith(letter)]
        if starting:
            after = [i for i in starting if panel.active is None or i > panel.active]
            self._activate(panel, (after or starting)[0])

    # -- layout

    def _font(self, bold: bool = False) -> QFont:
        font = QFont(QApplication.font())
        font.setBold(bold)
        return font

    def _row_height(self) -> int:
        return max(ROW, QFontMetrics(self._font()).height() + ROW_PAD)

    def _layout(self, menu: QMenu, anchor: QRect, first: bool, opener: int | None = None) -> _Panel:
        fm, bold = QFontMetrics(self._font()), QFontMetrics(self._font(bold=True))
        row, section = self._row_height(), max(SECTION, bold.height() + SECTION_PAD)
        actions = [a for a in menu.actions() if a.isVisible()]
        width = MIN_WIDTH
        for a in actions:
            label, shortcut = label_parts(a)
            if a.isSeparator():
                width = max(width, bold.horizontalAdvance(label) + 2 * PAD_X)
            else:
                extra = SHORTCUT_GAP + fm.horizontalAdvance(shortcut) if shortcut else 0
                width = max(width, CHECK + fm.horizontalAdvance(label) + extra + ARROW + PAD_X)
        items, y = [], INSET
        for a in actions:
            if a.isSeparator():
                kind, h = ("section", section) if a.text() else ("separator", SEPARATOR)
            else:
                kind, h = "action", row
            items.append(_Item(a, QRect(0, y, width, h), kind))
            y += h
        area = self._area.adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)
        content = y + INSET
        size = QRect(0, 0, width, min(content, max(row + 2 * SCROLLER, area.height())))  # taller than the screen: it scrolls
        if first:  # at the pointer, going up and left if there's no room
            x = anchor.x() if anchor.x() + size.width() <= area.right() else anchor.x() - size.width()
            y0 = anchor.y() if anchor.y() + size.height() <= area.bottom() else anchor.y() - size.height()
        else:  # beside the item it came from
            x = anchor.right() + 2 if anchor.right() + 2 + size.width() <= area.right() else anchor.left() - size.width() - 2
            y0 = anchor.top() - INSET
        x = min(max(x, area.left()), max(area.left(), area.right() - size.width()))
        y0 = min(max(y0, area.top()), max(area.top(), area.bottom() - size.height()))
        return _Panel(menu, size.translated(x, y0), items, height=content, opener=opener)

    # -- drawing

    def paint(self, p: QPainter) -> None:
        colours_ = palette()
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for panel in self.panels:
            box = QRectF(panel.rect).adjusted(0.5, 0.5, -0.5, -0.5)
            path = QPainterPath()
            path.addRoundedRect(box, RADIUS, RADIUS)
            p.fillPath(path, colours_.fill)
            p.setPen(QPen(ACCENT, 1.5))
            p.drawPath(path)
            p.save()
            p.setClipRect(panel.view().translated(panel.rect.topLeft()))
            for ii in range(len(panel.items)):
                r = panel.item_rect(ii).translated(panel.rect.topLeft())
                if r.intersects(panel.view().translated(panel.rect.topLeft())):
                    self._paint_item(p, panel.items[ii], r, panel.active == ii, colours_)
            p.restore()
            if panel.scrolls():
                self._paint_scrollers(p, panel, colours_)
        p.restore()

    def _paint_item(self, p: QPainter, item: _Item, r: QRect, lit: bool, c: Palette) -> None:
        if item.kind == "separator":
            p.setPen(QPen(c.line, 1))
            y = r.center().y() + 0.5
            p.drawLine(QPointF(r.left() + PAD_X, y), QPointF(r.right() - PAD_X, y))
            return
        label, shortcut = label_parts(item.action)
        if item.kind == "section":
            p.setFont(self._font(bold=True))
            p.setPen(c.muted)
            p.drawText(r.adjusted(PAD_X, 0, -PAD_X, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
            return
        enabled = item.action.isEnabled()
        text, quiet = (c.text, c.muted) if enabled else (c.disabled, c.disabled)
        if lit:
            row = QRectF(r).adjusted(3, 1, -3, -1)
            p.fillRect(row, c.hover)  # solid: the label on it is chosen to read on it
            p.setPen(QPen(c.focus, FOCUS_PEN))
            p.drawRoundedRect(row.adjusted(FOCUS_PEN / 2, FOCUS_PEN / 2, -FOCUS_PEN / 2, -FOCUS_PEN / 2), 3, 3)
            text = quiet = c.hover_text
        p.setFont(self._font())
        p.setPen(text)
        if item.action.isCheckable() and item.action.isChecked():
            p.drawText(QRect(r.left(), r.top(), CHECK + 4, r.height()), Qt.AlignmentFlag.AlignCenter, "✓")
        p.drawText(r.adjusted(CHECK + 2, 0, -ARROW, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
        if shortcut:
            p.setPen(quiet)
            p.drawText(r.adjusted(0, 0, -ARROW, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, shortcut)
        if item.action.menu() is not None:
            p.setPen(text)
            p.drawText(QRect(r.right() - ARROW, r.top(), ARROW - 4, r.height()), Qt.AlignmentFlag.AlignCenter, "›")

    def _paint_scrollers(self, p: QPainter, panel: _Panel, c: Palette) -> None:
        r = panel.rect
        p.setFont(self._font())
        for top, can, arrow in ((r.top(), panel.scroll > 0, "▲"), (r.bottom() + 1 - SCROLLER, panel.scroll < panel.max_scroll(), "▼")):
            p.setPen(c.text if can else c.disabled)
            p.drawText(QRect(r.left(), top, r.width(), SCROLLER), Qt.AlignmentFlag.AlignCenter, arrow)
