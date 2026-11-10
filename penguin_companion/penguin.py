"""The stage: the penguin and its speech bubbles, drawn over the screen the
penguin is on.

They're drawn on one see-through surface covering that screen, so moving them
is just drawing them somewhere else: nothing moves, so nothing lags or leaves a
trail. Only the patch that changed is redrawn, and clicks go through the
surface everywhere except the penguin and its bubble.

The surface is a layer-shell overlay on Wayland desktops that have one (see
layer.py), and a window everywhere else (StageWindow, with clickthrough). On
the overlay the stage also draws the penguin's menus (stagemenu.py) and hosts
the ask box: its Qt widgets live in a QGraphicsScene the stage draws, and get
the overlay's pointer and keyboard.
"""

from __future__ import annotations

import time

from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QContextMenuEvent,
    QFont,
    QGuiApplication,
    QInputMethodEvent,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QRegion,
    QScreen,
    QTextCharFormat,
    QWheelEvent,
)
from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsScene, QGraphicsView, QLineEdit, QMenu, QWidget

from . import clickthrough, layer
from .behavior import Behavior, Frame
from .bubble import SpeechBubble
from .sprites import Sprites
from .stagemenu import StageMenu

EDGE = 50  # keep the penguin's centre this far from the screen's sides
FPS = 60  # while it walks, falls or a bubble fades
SLOW_FPS = 30  # otherwise


class StageWindow(QWidget):
    """The stage's surface as a window over the screen: X11 (and XWayland
    where there's no layer shell), Windows and macOS."""

    def __init__(self, stage: Stage):
        xcb = QGuiApplication.platformName() == "xcb"
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus
        # On X11 the stage skips the window manager, so it stays above
        # everything, panels included, and never shows in the taskbar.
        flags |= Qt.WindowType.X11BypassWindowManagerHint if xcb else Qt.WindowType.Tool
        super().__init__(None, flags)
        self.stage = stage
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)  # macOS hides tool windows otherwise
        self.setMouseTracking(True)
        self.setWindowTitle("Penguin companion")
        self.winId()  # the native window, so clicks can pass through before it first shows
        self.input = clickthrough.for_window(self)
        self._closing = False

    def set_screen(self, screen: QScreen, geometry: QRect) -> None:
        self.setGeometry(geometry)
        if not self.isVisible():
            self.show()

    def damage(self, region: QRegion) -> None:
        self.update(region)

    def set_input(self, rects: list[QRect]) -> None:
        self.input.update(rects)

    def follow_pointer(self, hit) -> None:
        self.input.follow_pointer(hit)

    def device_scale(self) -> float:
        return self.devicePixelRatioF()

    def close(self) -> None:
        self._closing = True
        self.input.close()
        super().close()

    def closeEvent(self, event) -> None:
        # Only quitting closes the stage. A window manager's close (Super+C on
        # a stage it shouldn't be managing) would leave the penguin running
        # with nothing to be drawn on.
        if self._closing:
            event.accept()
        else:
            event.ignore()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        self.stage.paint(p, event.region())

    def mousePressEvent(self, event) -> None:
        if not self.stage.press(event.position(), event.globalPosition(), event.button()):
            event.ignore()

    def mouseMoveEvent(self, event) -> None:
        self.stage.move(event.position(), event.globalPosition())

    def mouseReleaseEvent(self, event) -> None:
        self.stage.release(event.position(), event.globalPosition(), event.button())

    def leaveEvent(self, event) -> None:
        self.stage.pointer_left()


CURSORS = {
    Qt.CursorShape.IBeamCursor: "text",
    Qt.CursorShape.PointingHandCursor: "pointer",
}


class Hosted(QObject):
    """A top-level widget (the ask box) drawn on the stage instead of being a
    window: it lives in a QGraphicsScene, at its own screen coordinates, and
    gets the stage's pointer and keyboard. A view that's never shown turns
    mouse events into scene events, as it would for one on screen."""

    def __init__(self, stage: Stage, widget: QWidget):
        super().__init__(stage)
        self.stage, self.widget = stage, widget
        self.scene = QGraphicsScene(self)
        shown = widget.isVisible()
        self.proxy = self.scene.addWidget(widget)
        widget.setVisible(shown)  # addWidget shows it; it opens when the app opens it
        self.view = QGraphicsView(self.scene)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        QApplication.sendEvent(self.scene, QEvent(QEvent.Type.WindowActivate))
        self.scene.clearFocus()  # until the keyboard arrives
        self.scene.changed.connect(self._changed)
        self.was_visible = shown  # the stage notices it opening and closing (see Stage._tick)
        # Its context menus are drawn by the stage too (a QMenu would be an XWayland window).
        for child in widget.findChildren(QWidget):
            if child.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu and hasattr(child, "createStandardContextMenu"):
                child.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                child.customContextMenuRequested.connect(lambda pos, c=child: self._context_menu(c, pos))

    def visible(self) -> bool:
        return self.widget.isVisible()

    def rect(self) -> QRect:
        """Where it is, in Qt's screen coordinates."""
        return self.widget.geometry()

    def input_rects(self) -> list[QRect]:
        """The parts that take clicks (not the see-through corners), screen coordinates."""
        shape = getattr(self.widget, "input_rects", None)
        rects = shape() if shape else [self.widget.rect()]
        return [r.translated(self.rect().topLeft()) for r in rects]

    def contains(self, gpos: QPointF) -> bool:
        return self.visible() and any(r.contains(gpos.toPoint()) for r in self.input_rects())

    def _changed(self, rects) -> None:
        origin = self.stage.origin()
        region = QRegion()
        for r in rects:
            region = region.united(QRegion(r.toAlignedRect().translated(-origin)))
        if not region.isEmpty():
            self.stage.damage(region)

    def paint(self, p: QPainter, region: QRegion) -> None:
        if not self.visible():
            return
        target = QRectF(self.rect().translated(-self.stage.origin()))
        if not region.intersects(target.toAlignedRect()):
            return
        self.scene.render(p, target, QRectF(self.rect()))

    # -- input

    def _sync_view(self) -> None:
        r = self.rect()
        self.view.setSceneRect(QRectF(r))
        self.view.resize(r.size())

    def mouse(self, kind: QEvent.Type, gpos: QPointF, button: Qt.MouseButton, buttons: Qt.MouseButton) -> None:
        self._sync_view()
        local = gpos - QPointF(self.rect().topLeft())
        viewport = self.view.viewport()
        event = QMouseEvent(kind, local, viewport.mapToGlobal(local), button, buttons, QGuiApplication.keyboardModifiers())
        QApplication.sendEvent(viewport, event)
        if kind == QEvent.Type.MouseButtonPress and button == Qt.MouseButton.RightButton:
            menu = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local.toPoint(), viewport.mapToGlobal(local.toPoint()))
            QApplication.sendEvent(viewport, menu)

    def wheel(self, gpos: QPointF, dx: int, dy: int) -> None:
        self._sync_view()
        local = gpos - QPointF(self.rect().topLeft())
        viewport = self.view.viewport()
        event = QWheelEvent(
            local, viewport.mapToGlobal(local), QPoint(), QPoint(dx, dy), Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False,
        )
        QApplication.sendEvent(viewport, event)

    def cursor_at(self, gpos: QPointF) -> str:
        child = self.widget.childAt((gpos - QPointF(self.rect().topLeft())).toPoint())
        while child is not None and not child.testAttribute(Qt.WidgetAttribute.WA_SetCursor):
            child = child.parentWidget()
        if child is None:
            return "default"
        return CURSORS.get(child.cursor().shape(), "default")  # a text browser sets a hand over links

    def key(self, event: QKeyEvent) -> None:
        QApplication.sendEvent(self.scene, event)

    # -- input methods: what Qt's own platform plugins do for a window

    def text_state(self) -> layer.TextState | None:
        """The focused text field, if it takes input-method text, for the input method."""
        if not self.visible() or self.scene.focusItem() is None or not self.scene.hasFocus():
            return None
        if not self.scene.inputMethodQuery(Qt.InputMethodQuery.ImEnabled):
            return None
        text = self.scene.inputMethodQuery(Qt.InputMethodQuery.ImSurroundingText) or ""
        cursor = self.scene.inputMethodQuery(Qt.InputMethodQuery.ImCursorPosition) or 0
        anchor = self.scene.inputMethodQuery(Qt.InputMethodQuery.ImAnchorPosition)
        rect = self.scene.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle)  # scene = screen coordinates
        rect = QRectF(rect).toAlignedRect() if isinstance(rect, (QRect, QRectF)) else QRect()  # QRect or QRectF, by widget
        return layer.TextState(str(text), int(cursor), int(cursor if anchor is None else anchor), rect.translated(-self.stage.origin()))

    def input_method(self, preedit: str, cursor: tuple[int, int] | None, commit: str, before: int, after: int) -> None:
        """Text from the input method: the composing text (shown underlined,
        with its cursor), and committed text replacing what it says to delete."""
        attributes = []
        if preedit:
            underline = QTextCharFormat()
            underline.setFontUnderline(True)
            length = len(preedit.encode("utf-16-le", errors="surrogatepass")) // 2
            attributes.append(QInputMethodEvent.Attribute(QInputMethodEvent.AttributeType.TextFormat, 0, length, underline))
        shown = cursor is not None
        attributes.append(QInputMethodEvent.Attribute(QInputMethodEvent.AttributeType.Cursor, cursor[1] if shown else 0, 1 if shown else 0))
        event = QInputMethodEvent(preedit, attributes)
        if commit or before or after:
            event.setCommitString(commit, -before, before + after)
        QApplication.sendEvent(self.scene, event)

    def keyboard_focus(self, on: bool) -> None:
        if on:
            self.scene.setFocus()
        else:
            self.scene.clearFocus()

    def _context_menu(self, child: QWidget, pos: QPoint) -> None:
        try:
            menu = child.createStandardContextMenu(pos)
        except TypeError:
            menu = child.createStandardContextMenu()
        # Its clipboard items use Qt's clipboard, which isn't the one the overlay has.
        for action in menu.actions():
            name = action.objectName()
            if name == "link-copy":
                link = child.anchorAt(pos)
                self._rewire(action, lambda link=link: self.stage.clipboard_copy(link))
            elif name in ("edit-copy", "edit-cut", "edit-paste"):
                self._rewire(action, {"edit-copy": self.copy, "edit-cut": self.cut, "edit-paste": self.paste}[name])
                if name == "edit-paste":  # Qt judged it by its own clipboard
                    action.setEnabled(self.stage.clipboard_has_text() and self.editable())
        self.stage.open_menu(menu, child.mapTo(self.widget, pos) + self.rect().topLeft(), owned=True)

    @staticmethod
    def _rewire(action, slot) -> None:
        try:
            action.triggered.disconnect()
        except TypeError:
            pass
        action.triggered.connect(lambda _checked=False: slot())

    # -- the clipboard, through the stage's surface

    def editable(self) -> bool:
        return bool(self.scene.inputMethodQuery(Qt.InputMethodQuery.ImEnabled)) and not self.scene.inputMethodQuery(
            Qt.InputMethodQuery.ImReadOnly
        )

    def selected_text(self) -> str:
        return str(self.scene.inputMethodQuery(Qt.InputMethodQuery.ImCurrentSelection) or "")

    def copy(self) -> None:
        self.stage.clipboard_copy(self.selected_text())

    def cut(self) -> None:
        if self.selected_text() and self.editable():
            self.copy()
            QApplication.sendEvent(self.scene, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier))

    def paste(self) -> None:
        if self.editable():
            self.stage.clipboard_paste(self.insert)

    def middle_click(self, gpos: QPointF) -> None:
        """Linux's other paste: the primary selection, where you click."""
        self.mouse(QEvent.Type.MouseButtonPress, gpos, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)  # put the cursor there
        self.mouse(QEvent.Type.MouseButtonRelease, gpos, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
        if self.editable():
            self.stage.clipboard_paste(self.insert, "primary")

    def insert(self, text: str) -> None:
        """Typed-in text: replaces the selection, at the cursor."""
        if not self.visible() or not text:
            return
        if isinstance(self.widget.focusWidget(), QLineEdit):
            text = " ".join(text.splitlines())  # one line
        event = QInputMethodEvent("", [])
        event.setCommitString(text)
        QApplication.sendEvent(self.scene, event)


def make_surface(stage: Stage):
    """A layer-shell overlay where Wayland offers one, a window otherwise."""
    if layer.wanted():
        surface = layer.LayerSurface.create(stage)
        if surface is not None:
            return surface
    return StageWindow(stage)


class Stage(QObject):
    clicked = pyqtSignal()
    menu_requested = pyqtSignal(QPoint)
    head_moved = pyqtSignal()
    message_closed = pyqtSignal()
    menu_closed = pyqtSignal()
    scale_changed_to = pyqtSignal(float)  # device pixels per stage pixel: draw the sprites for it

    def __init__(self, sprites: Sprites, behavior: Behavior, surface_factory=make_surface):
        super().__init__()
        self.behavior = behavior
        self.sprites = sprites
        self.bubble = SpeechBubble()
        self.bubble.on_close = self.message_closed.emit
        self._clock = time.monotonic
        self._frame: Frame | None = None
        self._geo = QRect()  # the screen the stage covers, in Qt's coordinates
        self._penguin = QRect()  # where the penguin was last drawn, local
        self._bubble_box = QRectF()
        self._head = QPoint()
        self._key = None
        self._press: QPoint | None = None
        self._press_on: str | int | None = None
        self._grab = QPointF()
        self._dragging = False
        self._screen: QScreen | None = None
        self.menu = StageMenu()
        self._menu_rects: list[QRect] = []
        self._owned_menu: QMenu | None = None
        self.hosted: Hosted | None = None
        self._clear_of: QWidget | None = None  # the ask box: bubbles go above it, not under it
        self._hosted_press = False  # a button went down on the hosted widget: it gets the rest
        self._text_state: layer.TextState | None = None  # what the input method was last told
        self._primary = ""  # the selected text last made the primary selection
        self.surface = surface_factory(self)
        self._use_screen(QGuiApplication.screenAt(QPoint(int(behavior.x), 0)) or QGuiApplication.primaryScreen())
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000 // FPS)

    # -- what the app uses

    def set_sprites(self, sprites: Sprites) -> None:
        self.sprites = sprites
        self._key = None
        self.surface.damage(QRegion(0, 0, self._geo.width(), self._geo.height()))

    def show_message(self, title: str, text: str = "", buttons=None, timeout_s: float | None = 12) -> None:
        self.bubble.show(title, text, buttons, timeout_s, self._clock())
        self._key = None

    def dismiss_message(self) -> None:
        self.bubble.dismiss(self._clock())

    def message_visible(self) -> bool:
        return self.bubble.visible()

    def head_point(self) -> QPoint:
        """Above the penguin's head, in screen coordinates: where bubbles point."""
        return self._head + self._geo.topLeft()

    def screen(self) -> QScreen | None:
        return self._screen

    def draws_menus(self) -> bool:
        """Whether menus have to be drawn on the stage (its surface says so)."""
        return bool(getattr(self.surface, "draws_menus", False))

    def hosts_windows(self) -> bool:
        """Whether the ask box has to be drawn on the stage too (its surface says so)."""
        return bool(getattr(self.surface, "hosts_windows", False))

    def host(self, widget: QWidget) -> None:
        """Draw this top-level widget on the stage instead of as a window."""
        self.hosted = Hosted(self, widget)
        self.keep_clear_of(widget)

    def keep_clear_of(self, widget: QWidget) -> None:
        """Put speech bubbles above this widget (the ask box) while it's open:
        it opens over the penguin's head too, where it would hide them."""
        self._clear_of = widget

    def origin(self) -> QPoint:
        """The stage's top-left, in screen coordinates."""
        return self._geo.topLeft()

    def damage(self, region: QRegion) -> None:
        self.surface.damage(region)

    def device_scale(self) -> float:
        return self.surface.device_scale()

    def open_menu(self, menu, at: QPoint, owned: bool = False) -> None:
        """Show a QMenu's actions on the stage, its corner at `at` (screen
        coordinates); an `owned` menu is deleted once it closes."""
        self._close_owned()
        self.menu.open(menu, QPointF(at - self._geo.topLeft()), QRect(0, 0, self._geo.width(), self._geo.height()))
        self._owned_menu = menu if owned else None
        self._key = None

    def close_menu(self) -> None:
        if self.menu.is_open():
            self.menu.close()
            self._menu_gone()

    def _menu_gone(self) -> None:
        self._key = None
        self._close_owned()
        self.menu_closed.emit()

    def _close_owned(self) -> None:
        if self._owned_menu is not None:
            self._owned_menu.deleteLater()
            self._owned_menu = None

    # -- what the surface tells the stage

    def hosted_shown(self, hosted: Hosted, on: bool, grab: bool) -> None:
        """The hosted widget opened (taking the keyboard if `grab`) or closed."""
        if not on:
            self._hosted_press = False
        focus = getattr(self.surface, "focus_keyboard", None)
        if focus is not None:
            focus(on, grab)
        self._key = None

    def key(self, key, pressed: bool, repeat: bool) -> None:
        if self.hosted is None or not self.hosted.visible():
            return
        kind = QEvent.Type.KeyPress if pressed else QEvent.Type.KeyRelease
        event = QKeyEvent(kind, int(key.key), key.modifiers, key.text, repeat)
        if pressed and hasattr(self.surface, "paste"):  # the overlay's clipboard, not Qt's
            for shortcut, do in (
                (QKeySequence.StandardKey.Paste, self.hosted.paste),
                (QKeySequence.StandardKey.Copy, self.hosted.copy),
                (QKeySequence.StandardKey.Cut, self.hosted.cut),
            ):
                if event.matches(shortcut):
                    do()
                    return
        self.hosted.key(event)

    # The clipboard ("clipboard") and the primary selection ("primary"), when
    # the surface keeps them (the overlay); Qt's own are used everywhere else.

    def clipboard_has_text(self, which: str = "clipboard") -> bool:
        has = getattr(self.surface, "clipboard_has_text", None)
        return bool(has and has(which))

    def clipboard_copy(self, text: str, which: str = "clipboard") -> None:
        if text and hasattr(self.surface, "copy"):
            self.surface.copy(text, which)

    def clipboard_paste(self, then, which: str = "clipboard") -> None:
        if hasattr(self.surface, "paste"):
            self.surface.paste(then, which)

    def keyboard_focus(self, on: bool) -> None:
        if self.hosted is not None:
            self.hosted.keyboard_focus(on)

    def input_method(self, preedit: str, cursor: tuple[int, int] | None, commit: str, before: int, after: int) -> None:
        """Text from an input method (the surface's text-input protocol)."""
        if self.hosted is not None and self.hosted.visible():
            self.hosted.input_method(preedit, cursor, commit, before, after)

    def wheel(self, pos: QPointF, gpos: QPointF, dx: int, dy: int) -> None:
        if self.hosted is not None and self.hosted.contains(gpos) and not self.menu.is_open():
            self.hosted.wheel(gpos, dx, dy)

    def scale_changed(self, scale: float) -> None:
        if scale > 0:
            self.scale_changed_to.emit(scale)

    def close_stage(self) -> None:
        self._timer.stop()
        self.surface.close()

    # -- screens: the stage covers the one the penguin is on

    def _use_screen(self, screen: QScreen) -> None:
        if screen is self._screen:
            return
        self._screen = screen
        self._geo = screen.geometry()
        self._key = None  # draw it all again there
        self.surface.set_screen(screen, self._geo)
        self._floor()

    def _floor(self) -> int:
        """The floor's height on the stage, and keep the walking range current."""
        avail = self._screen.availableGeometry()
        self.behavior.set_floor(avail.x() + EDGE, avail.x() + avail.width() - EDGE)
        return avail.y() + avail.height() - self._geo.y()

    # -- every frame

    def _tick(self) -> None:
        now = self._clock()
        if not self._dragging:
            here = QGuiApplication.screenAt(QPoint(int(self.behavior.x), self._geo.center().y()))
            if here is not None:
                self._use_screen(here)
        floor = self._floor()
        f = self.behavior.tick(now)
        self.bubble.tick(now)
        self._frame = f
        origin = self._geo.topLeft()

        penguin, outline = QRect(), []
        if f.anim is not None:
            sprite = self.sprites.frame(f.anim, f.index, f.mirror)
            left = round(f.x) - origin.x() - sprite.anchor
            top = floor - sprite.height() - round(f.lift)
            penguin = QRect(left, top, sprite.width(), sprite.height())
            outline = [r.translated(left, top) for r in sprite.outline]
            head = QPoint(round(f.x) - origin.x(), top + 4)
        else:
            head = QPoint(round(f.x) - origin.x(), floor)
        zs = self._z_rect(penguin) if self._sleeping(f) else QRect()

        bubble_box = QRectF()
        if self.bubble.drawn():
            size = self.bubble.size
            x = min(max(head.x() - size.width() / 2, 4), self._geo.width() - size.width() - 4)
            top = head.y()
            if self._clear_of is not None and self._clear_of.isVisible():
                top = min(top, self._clear_of.geometry().top() - origin.y())
            y = max(top - size.height(), 4)
            bubble_box = QRectF(x, y, size.width(), size.height())
            if self.bubble.visible():
                outline.append(bubble_box.toAlignedRect())

        z_phase = int(now * 1.2) % 3 if zs.isValid() else -1
        fade = round(self.bubble.opacity(now) * 20) if self.bubble.drawn() else -1
        menu_rects = self.menu.rects()
        key = (f.anim, f.index, f.mirror, penguin.topLeft(), z_phase, bubble_box.topLeft(), self.bubble.hover, fade, self.menu.key(), self.bubble.anim_key(now))
        if key != self._key:
            dirty = QRegion(self._penguin.adjusted(-2, -2, 2, 2)).united(QRegion(penguin.adjusted(-2, -2, 2, 2)))
            dirty = dirty.united(QRegion(self._z_rect(self._penguin))).united(QRegion(zs))
            dirty = dirty.united(QRegion(self._bubble_box.toAlignedRect().adjusted(-3, -3, 3, 3)))
            dirty = dirty.united(QRegion(bubble_box.toAlignedRect().adjusted(-3, -3, 3, 3)))
            for r in self._menu_rects + menu_rects:
                dirty = dirty.united(QRegion(r.adjusted(-2, -2, 2, 2)))
            self._menu_rects = menu_rects
            self._key = key
            self._penguin, self._bubble_box = penguin, bubble_box
            self.surface.damage(dirty)
        if zs.isValid():
            outline.append(zs)
        if self.hosted is not None:
            # Read each frame rather than from Show and Hide events, so however
            # it opens or closes, the keyboard and input region follow.
            shown = self.hosted.visible()
            if shown != self.hosted.was_visible:
                self.hosted.was_visible = shown
                self.hosted_shown(self.hosted, shown, shown and getattr(self.hosted.widget, "wants_keyboard", True))
            if shown:
                outline += [r.translated(-origin) for r in self.hosted.input_rects()]
            # Selected text is the primary selection, as in any Linux app.
            selected = self.hosted.selected_text() if shown else ""
            if selected and selected != self._primary:
                self.clipboard_copy(selected, "primary")
            self._primary = selected
            # The focused field's text and cursor, for an input method, when they change.
            state = self.hosted.text_state()
            if state != self._text_state:
                self._text_state = state
                set_text_input = getattr(self.surface, "set_text_input", None)
                if set_text_input is not None:
                    set_text_input(state)
        if self.menu.is_open():  # like any popup menu: a click anywhere else closes it
            outline = [QRect(0, 0, self._geo.width(), self._geo.height())]
        self.surface.set_input(outline)
        self.surface.follow_pointer(self._target_at)
        if head != self._head:
            self._head = head
            self.head_moved.emit()
        # Full speed while anything moves; the sprites' own frame rates are 10 fps or less.
        moving = f.anim == "walk" or self.behavior.held or self.behavior.falling or 0 <= fade < 20
        interval = 1000 // FPS if moving else 1000 // SLOW_FPS
        if self._timer.interval() != interval:
            self._timer.setInterval(interval)

    def _sleeping(self, f: Frame) -> bool:
        return f.anim == "sleep" and f.index >= 3

    def _z_rect(self, penguin: QRect) -> QRect:
        if penguin.isNull():
            return QRect()
        return QRect(penguin.center().x() + 6, penguin.top() - 30, 48, 44)

    # -- drawing

    def paint(self, p: QPainter, region: QRegion) -> None:
        """Draw the stage's `region` (local coordinates) with a painter its surface made."""
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(region.boundingRect(), Qt.GlobalColor.transparent)  # the surface clips it to the region
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        f, now = self._frame, self._clock()
        if f is not None and f.anim is not None and not self._penguin.isNull():
            p.drawPixmap(self._penguin.topLeft(), self.sprites.frame(f.anim, f.index, f.mirror).pixmap)
            if self._sleeping(f):
                self._paint_zs(p, self._z_rect(self._penguin), int(now * 1.2) % 3)
        if self.bubble.drawn() and not self._bubble_box.isNull():
            p.save()
            p.translate(self._bubble_box.topLeft())
            self.bubble.paint(p, self._head.x() - self._bubble_box.x(), now)
            p.restore()
        if self.hosted is not None:
            self.hosted.paint(p, region)
        if self.menu.is_open():
            self.menu.paint(p)

    def _paint_zs(self, p: QPainter, rect: QRect, phase: int) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i, (size, dx, dy) in enumerate(((12, 2, 30), (15, 15, 17), (19, 29, 3))):
            if i > phase:
                break
            font = QFont()
            font.setBold(True)
            font.setPixelSize(size)
            path = QPainterPath()
            path.addText(rect.x() + dx, rect.y() + dy + size, font, "z" if i < 2 else "Z")
            p.setPen(QPen(QColor(30, 30, 40, 200), 3))
            p.drawPath(path)
            p.fillPath(path, QColor("#e9fbff"))

    # -- the mouse

    def _target_at(self, pos: QPoint) -> str | int | None:
        """What's under a point on the stage: a bubble part, "penguin", or None."""
        if self.bubble.visible() and self._bubble_box.contains(QPointF(pos)):
            return self.bubble.hit(QPointF(pos) - self._bubble_box.topLeft())
        f = self._frame
        if f is not None and f.anim is not None and self._penguin.contains(pos):
            sprite = self.sprites.frame(f.anim, f.index, f.mirror)
            local = pos - self._penguin.topLeft()
            if any(sprite.hit(local.x() + dx, local.y() + dy) for dx, dy in ((0, 0), (3, 0), (-3, 0), (0, 3), (0, -3))):
                return "penguin"
        return None

    # Surfaces pass the pointer on in local (stage) and global (Qt) coordinates.

    def press(self, pos: QPointF, gpos: QPointF, button: Qt.MouseButton) -> bool:
        """A button went down; False if it's not on anything of ours."""
        if self.menu.is_open():
            action = self.menu.press(pos)
            if not self.menu.is_open():
                self._menu_gone()
            if action is not None:
                action.trigger()
            return True
        if self.hosted is not None and self.hosted.contains(gpos) and button == Qt.MouseButton.MiddleButton:
            if hasattr(self.surface, "paste"):
                self.hosted.middle_click(gpos)
            return True
        if self.hosted is not None and self.hosted.contains(gpos):
            self._hosted_press = True
            self.hosted.mouse(QEvent.Type.MouseButtonPress, gpos, button, button)
            return True
        target = self._target_at(pos.toPoint())
        if target is None:
            return False
        if button == Qt.MouseButton.RightButton and target == "penguin":
            self.menu_requested.emit(gpos.toPoint())
        elif button == Qt.MouseButton.LeftButton:
            self._press, self._press_on, self._dragging = gpos.toPoint(), target, False
            self._grab = gpos - QPointF(self.behavior.x, self._screen_floor() - self.behavior.lift)
        return True

    def move(self, pos: QPointF, gpos: QPointF) -> None:
        if self.menu.is_open():
            self.menu.move(pos)
            self._set_cursor("default")
            return
        if self.hosted is not None and (self._hosted_press or self.hosted.contains(gpos)):
            held = Qt.MouseButton.LeftButton if self._hosted_press else Qt.MouseButton.NoButton
            self.hosted.mouse(QEvent.Type.MouseMove, gpos, Qt.MouseButton.NoButton, held)
            self._set_cursor(self.hosted.cursor_at(gpos))
            return
        self._set_cursor("grabbing" if self._dragging else "default")
        if self._press is None:
            hover = self._target_at(pos.toPoint())
            self.bubble.hover = hover if isinstance(hover, int) else None
            return
        if self._press_on != "penguin":
            return
        if not self._dragging and (gpos.toPoint() - self._press).manhattanLength() < 6:
            return
        self._dragging = True
        screen = QGuiApplication.screenAt(gpos.toPoint())
        if screen is not None:
            self._use_screen(screen)
        foot = gpos - self._grab
        self.behavior.hold(foot.x(), self._screen_floor() - foot.y(), self._clock())

    def release(self, pos: QPointF, gpos: QPointF, button: Qt.MouseButton) -> None:
        if self._hosted_press and self.hosted is not None:
            self._hosted_press = False
            self.hosted.mouse(QEvent.Type.MouseButtonRelease, gpos, button, Qt.MouseButton.NoButton)
            return
        if button != Qt.MouseButton.LeftButton or self._press is None:
            return
        target, self._press = self._press_on, None
        if self._dragging:
            self._dragging = False
            self.behavior.release(self._clock())
        elif target == "penguin":
            self.clicked.emit()
        elif target == "close" or (target == "body" and not self.bubble.buttons):
            self.dismiss_message()
        elif isinstance(target, int) and self._target_at(pos.toPoint()) == target:
            action = self.bubble.buttons[target].action
            self.dismiss_message()
            if action:
                action()

    def pointer_left(self) -> None:
        self.bubble.hover = None

    def _set_cursor(self, shape: str) -> None:
        set_cursor = getattr(self.surface, "set_cursor", None)
        if set_cursor is not None:
            set_cursor(shape)

    def _screen_floor(self) -> float:
        avail = self._screen.availableGeometry()
        return avail.y() + avail.height()
