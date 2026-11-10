"""The penguin's menu, drawn on the stage.

On the Wayland overlay a QMenu can't be used: Qt's menus there are XWayland
popup windows, which sit under the overlay, and Hyprland doesn't deliver
clicks to them. So the stage draws the menu itself, like its speech bubbles,
from the same QMenu (its actions, checks, sections and submenus), and passes
the click to the chosen action.

While it's open the whole stage takes clicks, as a popup menu would: a click
anywhere else closes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QAction, QColor, QFont, QFontMetrics, QKeySequence, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QMenu

from .bubble import ACCENT, colours

ROW = 26
SEPARATOR = 9
SECTION = 22
PAD_X = 10
CHECK = 22  # room for a check mark
ARROW = 18  # room for a submenu arrow
RADIUS = 8
MARGIN = 4  # from the edges of the screen
MIN_WIDTH = 140
SHORTCUT_GAP = 24  # between an item and its shortcut


def label_parts(action: QAction) -> tuple[str, str]:
    """An item's label without its mnemonic marks (&File: F underlined in Qt's
    own menus, which have keyboard navigation this one doesn't), and its
    shortcut, which Qt's standard menus append after a tab."""
    text, _, shortcut = action.text().partition("\t")
    text = text.replace("&&", "\0").replace("&", "").replace("\0", "&")
    if not shortcut and not action.shortcut().isEmpty():
        shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
    return text, shortcut


@dataclass
class _Item:
    action: QAction
    rect: QRect
    kind: str  # "action", "separator" or "section"


@dataclass
class _Panel:
    menu: QMenu
    rect: QRect
    items: list[_Item] = field(default_factory=list)


class StageMenu:
    def __init__(self):
        self.panels: list[_Panel] = []
        self.hover: tuple[int, int] | None = None  # (panel, item)
        self._area = QRect()

    def is_open(self) -> bool:
        return bool(self.panels)

    def open(self, menu: QMenu, at: QPointF, area: QRect) -> None:
        """Open `menu` with its corner at `at`, kept within `area` (local coordinates)."""
        self._area = QRect(area)
        self.panels = [self._layout(menu, QRect(at.toPoint(), at.toPoint()), first=True)]
        self.hover = None

    def close(self) -> None:
        self.panels = []
        self.hover = None

    def rects(self) -> list[QRect]:
        return [p.rect for p in self.panels]

    def key(self) -> tuple:
        """Changes whenever the menu looks different."""
        return (tuple((p.rect.x(), p.rect.y(), p.rect.width(), p.rect.height()) for p in self.panels), self.hover)

    # -- the pointer

    def move(self, pos: QPointF) -> None:
        hit = self._hit(pos)
        if hit is None:
            return  # keep what's open while the pointer crosses a gap
        self.hover = hit if self._enabled(hit) else None
        panel_i, item_i = hit
        item = self.panels[panel_i].items[item_i]
        del self.panels[panel_i + 1 :]
        sub = item.action.menu()
        if item.kind == "action" and sub is not None and item.action.isEnabled():
            self.panels.append(self._layout(sub, item.rect.translated(self.panels[panel_i].rect.topLeft()), first=False))

    def press(self, pos: QPointF) -> QAction | None:
        """A click: the action to run once the menu's closed, if it was on one."""
        hit = self._hit(pos)
        if hit is None:
            if not any(p.rect.contains(pos.toPoint()) for p in self.panels):
                self.close()  # a click elsewhere closes it
            return None
        item = self.panels[hit[0]].items[hit[1]]
        if item.kind != "action" or not item.action.isEnabled():
            return None
        if item.action.menu() is not None:
            self.move(pos)  # open the submenu
            return None
        self.close()
        return item.action

    def _hit(self, pos: QPointF) -> tuple[int, int] | None:
        point = pos.toPoint()
        for pi in range(len(self.panels) - 1, -1, -1):  # submenus are on top
            panel = self.panels[pi]
            if panel.rect.contains(point):
                local = point - panel.rect.topLeft()
                for ii, item in enumerate(panel.items):
                    if item.rect.contains(local):
                        return pi, ii
                return None
        return None

    def _enabled(self, hit: tuple[int, int]) -> bool:
        item = self.panels[hit[0]].items[hit[1]]
        return item.kind == "action" and item.action.isEnabled()

    # -- layout

    def _font(self, bold: bool = False) -> QFont:
        font = QFont(QApplication.font())
        font.setBold(bold)
        return font

    def _layout(self, menu: QMenu, anchor: QRect, first: bool) -> _Panel:
        fm, bold = QFontMetrics(self._font()), QFontMetrics(self._font(bold=True))
        actions = [a for a in menu.actions() if a.isVisible()]
        width = MIN_WIDTH
        for a in actions:
            label, shortcut = label_parts(a)
            if a.isSeparator():
                width = max(width, bold.horizontalAdvance(label) + 2 * PAD_X)
            else:
                extra = SHORTCUT_GAP + fm.horizontalAdvance(shortcut) if shortcut else 0
                width = max(width, CHECK + fm.horizontalAdvance(label) + extra + ARROW + PAD_X)
        items, y = [], 4
        for a in actions:
            if a.isSeparator():
                kind, h = ("section", SECTION) if a.text() else ("separator", SEPARATOR)
            else:
                kind, h = "action", ROW
            items.append(_Item(a, QRect(0, y, width, h), kind))
            y += h
        size = QRect(0, 0, width, y + 4)
        area = self._area.adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)
        if first:  # at the pointer, going up and left if there's no room
            x = anchor.x() if anchor.x() + size.width() <= area.right() else anchor.x() - size.width()
            y0 = anchor.y() if anchor.y() + size.height() <= area.bottom() else anchor.y() - size.height()
        else:  # beside the item it came from
            x = anchor.right() + 2 if anchor.right() + 2 + size.width() <= area.right() else anchor.left() - size.width() - 2
            y0 = anchor.top() - 4
        x = min(max(x, area.left()), max(area.left(), area.right() - size.width()))
        y0 = min(max(y0, area.top()), max(area.top(), area.bottom() - size.height()))
        return _Panel(menu, size.translated(x, y0), items)

    # -- drawing

    def paint(self, p: QPainter) -> None:
        fill, text = colours()
        fill.setAlpha(250)
        dim = QColor(text)
        dim.setAlpha(110)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for pi, panel in enumerate(self.panels):
            box = QRectF(panel.rect).adjusted(0.5, 0.5, -0.5, -0.5)
            path = QPainterPath()
            path.addRoundedRect(box, RADIUS, RADIUS)
            p.fillPath(path, fill)
            p.setPen(QPen(ACCENT, 1.5))
            p.drawPath(path)
            for ii, item in enumerate(panel.items):
                r = item.rect.translated(panel.rect.topLeft())
                if item.kind == "separator":
                    p.setPen(QPen(dim, 1))
                    y = r.center().y() + 0.5
                    p.drawLine(QPointF(r.left() + PAD_X, y), QPointF(r.right() - PAD_X, y))
                    continue
                label, shortcut = label_parts(item.action)
                if item.kind == "section":
                    p.setFont(self._font(bold=True))
                    p.setPen(dim)
                    p.drawText(r.adjusted(PAD_X, 0, -PAD_X, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
                    continue
                enabled = item.action.isEnabled()
                if self.hover == (pi, ii):
                    hl = QColor(ACCENT)
                    hl.setAlpha(70)
                    p.fillRect(QRectF(r).adjusted(3, 1, -3, -1), hl)
                p.setFont(self._font())
                p.setPen(text if enabled else dim)
                if item.action.isCheckable() and item.action.isChecked():
                    p.drawText(QRect(r.left(), r.top(), CHECK + 4, r.height()), Qt.AlignmentFlag.AlignCenter, "✓")
                p.drawText(r.adjusted(CHECK + 2, 0, -ARROW, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
                if shortcut:
                    p.setPen(dim)
                    p.drawText(r.adjusted(0, 0, -ARROW, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, shortcut)
                if item.action.menu() is not None:
                    p.drawText(QRect(r.right() - ARROW, r.top(), ARROW - 4, r.height()), Qt.AlignmentFlag.AlignCenter, "›")
        p.restore()
