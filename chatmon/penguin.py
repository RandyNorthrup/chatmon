"""The stage: the penguin and its speech bubbles, drawn over the screen the
penguin is on.

They're drawn on one see-through surface covering that screen, so moving them
is just drawing them somewhere else: nothing moves, so nothing lags or leaves a
trail. Only the patch that changed is redrawn, and clicks go through the
surface everywhere except the penguin and its bubble.

The stage's clock sleeps until the next change it can see (a frame of the
creature's, a bubble's fade or expiry, a menu's submenu), at most a second, and
anything it's told (the pointer, a key, a message, the app changing the
behaviour) wakes it within a frame. While something moves all the time it
ticks at the screen's refresh rate; positions are in device pixels.

The surface is a layer-shell overlay on Wayland desktops that have one (see
layer.py), and a window everywhere else (StageWindow, with clickthrough). On
the overlay the stage also draws the penguin's menus (stagemenu.py) and hosts
the ask box: its Qt widgets live in a QGraphicsScene the stage draws, and get
the overlay's pointer and keyboard.
"""

from __future__ import annotations

import math
import sys
import time

from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QContextMenuEvent,
    QCursor,
    QFont,
    QGuiApplication,
    QInputMethodEvent,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRegion,
    QScreen,
    QTextCharFormat,
    QWheelEvent,
)
from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsScene, QGraphicsView, QLineEdit, QMenu, QWidget

from . import bubble as bubbles
from . import clickthrough, layer
from .behavior import Behavior, Frame
from .bubble import SpeechBubble
from .bubbleart import device_ratio
from .sprites import Sprites
from .stagemenu import StageMenu

EDGE = 50  # keep the penguin's centre this far from the screen's sides
DEFAULT_HZ = 60  # frames a second while something moves, on a screen that doesn't say its refresh rate
MIN_HZ, MAX_HZ = 24, 500  # a refresh rate outside these is a screen that doesn't know its own
SAVER_FPS = 30  # the system saving power: at most this, still three times a sprite's own frame rate
IDLE_FLOOR = 1.0  # s: the longest the clock sleeps, for what changes without saying (a screen, a setting)
COVERED_TICK = 1.0  # s between ticks while a full-screen window covers the stage: nothing to draw
ANIM_FPS = getattr(bubbles, "ANIM_FPS", 30)  # how often an animated bubble's art moves on
Z_STEP = 1 / 1.2  # s per step of the sleeping z's
NEAR = 160  # px around what takes clicks within which the pointer is polled every frame (Windows, macOS)
FAR_POLL = 0.1  # s between polls of the pointer farther away: it can't reach the chatmon in less


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
        self.setAccessibleName("Chatmon")  # what a screen reader calls it; its bubble is its description
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)  # macOS hides tool windows otherwise
        self.setMouseTracking(True)
        self.setWindowTitle("Chatmon")
        self.winId()  # the native window, so clicks can pass through before it first shows
        self.input = clickthrough.for_window(self)
        self._closing = False
        self._covered = False

    def set_covered(self, on: bool) -> None:
        if QGuiApplication.platformName() == "cocoa":
            return  # macOS keeps it out of full-screen apps' Spaces itself, and that's how one is told (macnative.py)
        if on != self._covered:
            self._covered = on
            self.setVisible(not on)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if QGuiApplication.platformName() == "cocoa":  # every Space, not full-screen apps' (macnative.py)
            from . import macnative

            macnative.float_everywhere(self)

    def set_screen(self, screen: QScreen, geometry: QRect) -> None:
        self.setGeometry(geometry)
        if not self.isVisible() and not self._covered:
            self.show()
        # A screen of another scale (a 4K monitor beside a laptop's, or the scale setting changed): sprites for it.
        self.stage.scale_changed(screen.devicePixelRatio())

    def damage(self, region: QRegion) -> None:
        self.update(region)

    def set_input(self, rects: list[QRect]) -> None:
        self.input.update(rects)

    def follow_pointer(self, hit) -> None:
        self.input.follow_pointer(hit)

    @property
    def polls_pointer(self) -> bool:
        """Windows and macOS: clicks reach the window only while it's told the pointer is over the chatmon."""
        return isinstance(self.input, clickthrough.PointerToggle)

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
        self.proxy.visibleChanged.connect(stage._wake)  # opened or closed: the stage looks at once
        self.was_visible = shown  # the stage notices it opening and closing (see Stage._tick)
        # Its animated bubble is drawn by the stage, each frame; what's in it (the text, the field) is
        # drawn from the scene only when the scene changes, and kept. (Drawing all of it from the scene
        # thirty times a second cost most of a core.)
        if hasattr(widget, "stage_draws_art"):
            widget.stage_draws_art = True
        self._contents: tuple[tuple, QPixmap] | None = None
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

    def anim_key(self, now: float) -> int:
        key = getattr(self.widget, "anim_key", None)
        return key(now) if key is not None and self.visible() else -1

    def _changed(self, rects) -> None:
        self._contents = None
        origin = self.stage.origin()
        region = QRegion()
        for r in rects:
            region = region.united(QRegion(r.toAlignedRect().translated(-origin)))
        if not region.isEmpty():
            self.stage.damage(region)
        self.stage._wake()  # its text, selection or cursor may have changed: the input method and selection follow

    def paint(self, p: QPainter, region: QRegion) -> None:
        if not self.visible():
            return
        target = QRectF(self.rect().translated(-self.stage.origin()))
        if not region.intersects(target.toAlignedRect()):
            return
        art = getattr(self.widget, "paint_art", None)
        if art is None or not art(p, target.x(), target.y()):
            self.scene.render(p, target, QRectF(self.rect()))  # the plain box: drawn whole, it doesn't move
            return
        ratio = device_ratio(p)
        key = (ratio, self.rect().size().width(), self.rect().size().height())
        if self._contents is None or self._contents[0] != key:
            size = self.rect().size()
            pix = QPixmap(max(1, round(size.width() * ratio)), max(1, round(size.height() * ratio)))
            pix.setDevicePixelRatio(ratio)
            pix.fill(Qt.GlobalColor.transparent)
            q = QPainter(pix)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            q.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            self.scene.render(q, QRectF(0, 0, size.width(), size.height()), QRectF(self.rect()))
            q.end()
            self._contents = (key, pix)
        p.drawPixmap(target.topLeft(), self._contents[1])

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
        if not self.editable():
            return
        rich = getattr(self.widget, "paste_overlay", None)  # the ask box: files and pictures attach
        if rich is not None and hasattr(self.stage.surface, "paste_rich"):
            self.stage.surface.paste_rich(rich)
        else:
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
    away_changed = pyqtSignal(bool)  # the overlay heard you've been away from the keyboard a while (True), or are back
    lock_changed = pyqtSignal(bool)  # the overlay heard the session lock (True) or unlock (Hyprland)

    def __init__(self, sprites: Sprites, behavior: Behavior, surface_factory=make_surface):
        super().__init__()
        self.behavior = behavior
        self.sprites = sprites
        self.bubble = SpeechBubble()
        self.bubble.on_close = self.message_closed.emit
        self._clock = time.monotonic
        self._frame: Frame | None = None
        self._geo = QRect()  # the screen the stage covers, in Qt's coordinates
        self._penguin = QRectF()  # where the penguin was last drawn, local (on the device pixel grid)
        self._bubble_box = QRectF()
        self._head = QPoint()
        self._key = None
        self._input_parts: tuple | None = None  # what the input region was last built from
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
        self._inputs: tuple = ()  # what takes clicks, as last sent to the surface (local x, y, w, h)
        self._covered = False  # a full-screen window is in front on this screen
        self._last_tick = -math.inf
        self._cursor_pos = QCursor.pos  # where the pointer is, in Qt's screen coordinates
        self._screen_at = QGuiApplication.screenAt
        self.surface = surface_factory(self)
        self._use_screen(self._screen_at(QPoint(int(behavior.x), 0)) or QGuiApplication.primaryScreen())
        QGuiApplication.instance().screenRemoved.connect(self._screen_removed)
        # One shot at a time, set each tick to the next change (see _next_tick); anything that happens wakes it.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        # The pointer, for a surface that has to be told when it's over the chatmon (Windows, macOS).
        self._pointer_timer = QTimer(self)
        self._pointer_timer.setSingleShot(True)
        self._pointer_timer.timeout.connect(self._poll_pointer)
        self.power_saving = False  # the system's power-saver mode: fewer frames
        self.drawing: bool | None = True  # off while nothing on screen can be seen: no frames at all; None once closed
        behavior.on_change = self._wake
        self._timer.start(0)
        self._poll_pointer()

    # -- what the app uses

    def set_sprites(self, sprites: Sprites) -> None:
        self.sprites = sprites
        self._key = None
        self.surface.damage(QRegion(0, 0, self._geo.width(), self._geo.height()))
        self._wake()

    def show_message(self, title: str, text: str = "", buttons=None, timeout_s: float | None = 12) -> None:
        self.bubble.show(title, text, buttons, timeout_s, self._clock())
        describe = getattr(self.surface, "setAccessibleDescription", None)  # the window's: the bubble, in words
        if describe is not None:
            from .a11y import spoken

            describe(spoken(title, text, [label for label, _ in buttons or []]))
        self._key = None
        self._wake()

    def set_drawing(self, on: bool) -> None:
        """Stop drawing, and the clock that moves it on, while nothing on screen can be seen (Windows asks it
        of apps while the session is locked or its display is off); carry on where it was when it can."""
        if self.drawing is None or on == self.drawing:  # closed, or no change
            return
        self.drawing = on
        if on:
            self._key = None  # everything drawn again, as it is now
            self._wake()
            self._poll_pointer()
        else:
            self._timer.stop()
            self._pointer_timer.stop()

    # -- full-screen windows, and you being away

    def away(self, on: bool) -> None:
        """The surface heard you've been away from the keyboard and mouse a while (or are back)."""
        self.away_changed.emit(on)

    def drop_at(self, gpos: QPointF) -> bool:
        """Something dragged over the overlay: would a drop here be taken? Into the ask box, while you can
        type in it, as the ask box takes a drop elsewhere (bubble.py's dropEvent)."""
        hosted = self.hosted
        if hosted is None or not hosted.contains(gpos):
            return False
        entry = getattr(hosted.widget, "entry", None)
        return hasattr(hosted.widget, "paste_overlay") and entry is not None and entry.isVisible()

    def dropped(self, mime: str, data: bytes) -> None:
        if self.hosted is not None and hasattr(self.hosted.widget, "paste_overlay"):
            self.hosted.widget.paste_overlay(mime, data)

    def locked(self, on: bool) -> None:
        """The surface heard the session lock (or unlock)."""
        self.lock_changed.emit(on)

    def raise_above(self, on: bool) -> None:
        """Above full-screen windows too (an alert or the ask box needs you), or giving way to them."""
        if hasattr(self.surface, "raise_above"):
            self.surface.raise_above(on)

    def set_covered(self, on: bool) -> None:
        """A full-screen window is in front on this screen: out of its way (the window surfaces; the overlay's
        compositor does it itself), and the clock slowed to COVERED_TICK while nothing can be seen."""
        if hasattr(self.surface, "set_covered"):
            self.surface.set_covered(on)
        if on != self._covered:
            self._covered = on
            if on:
                self._pointer_timer.stop()
            else:
                self._key = None
                self._wake()
                self._poll_pointer()

    def native_window(self) -> int:
        win = getattr(self.surface, "winId", None)
        return int(win()) if win is not None else 0

    def dialog_owner(self) -> QWidget | None:
        """The window the system's dialogs belong to, on Windows: the stage's own. A window with no owner
        can open under the stage, which stays on top; one it owns opens above it, centred on its screen."""
        if sys.platform == "win32" and isinstance(self.surface, QWidget):
            return self.surface
        return None

    def dismiss_message(self) -> None:
        self.bubble.dismiss(self._clock())
        self._wake()

    def message_visible(self) -> bool:
        return self.bubble.visible()

    def press_button(self, typed: str) -> bool:
        """The bubble's button whose label was typed (or the start of it, if that's one button's alone),
        pressed as a click would: the keyboard's and a screen reader's way to answer a bubble."""
        from .a11y import typed_button

        index = typed_button([b.label for b in self.bubble.buttons], typed) if self.bubble.visible() else None
        if index is None:
            return False
        action = self.bubble.buttons[index].action
        self.dismiss_message()
        if action:
            action()
        return True

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

    # -- the clock

    def _wake(self) -> None:
        """Something changed that could change what's drawn: tick within a frame, never sooner than a frame
        after the last tick (a mouse sends hundreds of moves a second; the screen shows one frame a refresh)."""
        if not self.drawing:
            return
        self._schedule(self._last_tick + self._frame_interval() - self._clock())

    def _schedule(self, delay: float) -> None:
        """Tick in `delay` seconds, unless a tick is already due sooner."""
        ms = math.ceil(min(delay, IDLE_FLOOR) * 1000) if delay > 0 else 0  # before the first tick: -inf, at once
        if not self._timer.isActive() or self._timer.remainingTime() > ms:
            self._timer.start(ms)

    def _refresh_hz(self) -> float:
        try:
            rate = float(self._screen.refreshRate()) if self._screen is not None else 0.0
        except (AttributeError, RuntimeError):  # a screen being unplugged
            rate = 0.0
        return min(max(rate, MIN_HZ), MAX_HZ) if rate > 0 else DEFAULT_HZ

    def _frame_interval(self) -> float:
        """Seconds per frame while something moves: the screen's refresh rate, SAVER_FPS at most when saving power."""
        hz = self._refresh_hz()
        return 1.0 / (min(hz, SAVER_FPS) if self.power_saving else hz)

    def _next_tick(self, now: float, zs: QRect) -> float:
        """Seconds until the next tick: the soonest change anything drawn will show, at least a frame from now
        and at most IDLE_FLOOR; COVERED_TICK while covered."""
        if self._covered:
            return COVERED_TICK
        due = [self.behavior.next_change(now), self._bubble_due(now)]
        if zs.isValid() and not self.behavior.reduced_motion:
            due.append((int(now / Z_STEP) + 1) * Z_STEP + 0.001)
        if self.hosted is not None and self.hosted.anim_key(now) >= 0:
            due.append(now + 1 / ANIM_FPS)
        menu_due = getattr(self.menu, "next_change", None)
        if menu_due is not None:
            due.append(menu_due())
        return min(max(min(due) - now, self._frame_interval()), IDLE_FLOOR)

    def _bubble_due(self, now: float) -> float:
        b = self.bubble
        if not b.drawn():
            return math.inf
        if not b.visible() or b.opacity(now) < 1:
            return now  # fading in or out: every frame
        own = getattr(b, "next_change", None)
        if own is not None:
            return own(now)
        due = now + 1 / ANIM_FPS if b.anim_key(now) >= 0 else math.inf
        expires = getattr(b, "_expires", None)  # until the bubble says (see the M3 plan's integration notes)
        return min(due, expires) if isinstance(expires, (int, float)) else due

    def _poll_pointer(self) -> None:
        """Tell a surface that has to know (Windows, macOS) whether the pointer is over the chatmon: every frame
        while it's near, every FAR_POLL farther off, not at all while nothing can be seen."""
        if not getattr(self.surface, "polls_pointer", False) or not self.drawing or self._covered:
            return
        self.surface.follow_pointer(self._target_at)
        local = self._cursor_pos() - self._geo.topLeft()
        near = any(x - NEAR <= local.x() < x + w + NEAR and y - NEAR <= local.y() < y + h + NEAR for x, y, w, h in self._inputs)
        self._pointer_timer.start(max(1, math.ceil((self._frame_interval() if near else FAR_POLL) * 1000)))

    def open_menu(self, menu, at: QPoint, owned: bool = False) -> None:
        """Show a QMenu's actions on the stage, its corner at `at` (screen
        coordinates); an `owned` menu is deleted once it closes."""
        self._close_owned()
        self.menu.open(menu, QPointF(at - self._geo.topLeft()), QRect(0, 0, self._geo.width(), self._geo.height()))
        self._owned_menu = menu if owned else None
        self._key = None
        self._wake()

    def close_menu(self) -> None:
        if self.menu.is_open():
            self.menu.close()
            self._menu_gone()

    def _menu_gone(self) -> None:
        self._key = None
        self._close_owned()
        self.menu_closed.emit()
        self._wake()

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
        self._wake()
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
        self._wake()
        if self.hosted is not None:
            self.hosted.keyboard_focus(on)

    def input_method(self, preedit: str, cursor: tuple[int, int] | None, commit: str, before: int, after: int) -> None:
        """Text from an input method (the surface's text-input protocol)."""
        self._wake()
        if self.hosted is not None and self.hosted.visible():
            self.hosted.input_method(preedit, cursor, commit, before, after)

    def wheel(self, pos: QPointF, gpos: QPointF, dx: int, dy: int) -> None:
        self._wake()
        if self.hosted is not None and self.hosted.contains(gpos) and not self.menu.is_open():
            self.hosted.wheel(gpos, dx, dy)

    def scale_changed(self, scale: float) -> None:
        if scale > 0:
            self.scale_changed_to.emit(scale)

    def close_stage(self) -> None:
        self._timer.stop()
        self._pointer_timer.stop()
        self.drawing = None  # for good: set_drawing never starts it again
        self.surface.close()

    # -- screens: the stage covers the one the penguin is on

    def _use_screen(self, screen: QScreen, again: bool = False) -> None:
        """Cover this screen. `again`: the same one, whose size or scale changed."""
        if screen is self._screen and not again:
            return
        self._screen = screen
        self._geo = screen.geometry()
        self._key = None  # draw it all again there
        self.surface.set_screen(screen, self._geo)
        self._floor()

    def _screen_removed(self, screen: QScreen) -> None:
        """A monitor unplugged, a laptop undocked: if the chatmon was on it, over to one that's still there
        (its walking range brings it on screen), before Qt deletes the screen from under the stage."""
        if screen is self._screen:
            self._screen = None
            self._use_screen(QGuiApplication.primaryScreen())

    def _floor(self) -> int:
        """The floor's height on the stage, and keep the walking range current."""
        avail = self._screen.availableGeometry()
        self.behavior.set_floor(avail.x() + EDGE, avail.x() + avail.width() - EDGE)
        return avail.y() + avail.height() - self._geo.y()

    # -- every frame

    def _tick(self) -> None:
        now = self._clock()
        self._last_tick = now
        self._timer.stop()  # a wake from what this tick sets off schedules the next one sooner; else _next_tick
        if not self._dragging:
            here = self._screen_at(QPoint(int(self.behavior.x), self._geo.center().y()))
            if here is not None:
                self._use_screen(here, again=here.geometry() != self._geo)  # its resolution or scale may have changed
        floor = self._floor()
        f = self.behavior.tick(now)
        self.bubble.tick(now)
        self._frame = f
        origin = self._geo.topLeft()
        k = self._device_scale()

        penguin, sprite = QRectF(), None
        if f.anim is not None:
            sprite = self.sprites.frame(f.anim, f.index, f.mirror)
            # On the device pixel grid, not whole stage pixels: half pixels on a 2x screen, so a walk moves
            # as smoothly as the screen can show.
            left = round((f.x - origin.x() - sprite.anchor) * k) / k
            top = round((floor - sprite.height() - f.lift) * k) / k
            penguin = QRectF(left, top, sprite.width(), sprite.height())
            head = QPoint(round(f.x) - origin.x(), round(top) + 4)
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
            # On whole device pixels: off them, every pixmap of an animated bubble is resampled each frame,
            # which is slow and blurs it by half a pixel.
            x, y = round(x * k) / k, math.floor(y * k) / k  # down, never up: it stays clear of what is below it
            bubble_box = QRectF(x, y, size.width(), size.height())

        # Reduced motion: all three z's, still.
        self._z_phase = (2 if self.behavior.reduced_motion else int(now / Z_STEP) % 3) if zs.isValid() else -1
        menu_tick = getattr(self.menu, "tick", None)
        if menu_tick is not None:
            menu_tick(now)  # a submenu due to open, a scroll arrow held
        fade = round(self.bubble.opacity(now) * 20) if self.bubble.drawn() else -1
        menu_rects = self.menu.rects()
        # What looks different, each part on its own: only what changed is drawn again.
        key = (
            (f.anim, f.index, f.mirror, penguin.topLeft(), self._z_phase),
            (bubble_box.topLeft(), self.bubble.hover, fade, self.bubble.anim_key(now)),
            self.menu.key(),
            self.hosted.anim_key(now) if self.hosted is not None else -1,
        )
        if key != self._key:
            old = self._key or (None, None, None, None)
            dirty = QRegion()
            if key[0] != old[0]:
                dirty = QRegion(self._penguin.toAlignedRect().adjusted(-2, -2, 2, 2)).united(QRegion(penguin.toAlignedRect().adjusted(-2, -2, 2, 2)))
                dirty = dirty.united(QRegion(self._z_rect(self._penguin))).united(QRegion(zs))
            if key[1] != old[1]:
                dirty = dirty.united(QRegion(self._bubble_box.toAlignedRect().adjusted(-3, -3, 3, 3)))
                dirty = dirty.united(QRegion(bubble_box.toAlignedRect().adjusted(-3, -3, 3, 3)))
            if key[2] != old[2]:
                for r in self._menu_rects + menu_rects:
                    dirty = dirty.united(QRegion(r.adjusted(-2, -2, 2, 2)))
            if key[3] != old[3] and self.hosted is not None and self.hosted.visible():  # its bubble moved on a frame
                dirty = dirty.united(QRegion(self.hosted.rect().translated(-origin)))
            self._menu_rects = menu_rects
            self._key = key
            self._penguin, self._bubble_box = penguin, bubble_box
            self.surface.damage(dirty)
        hosted_rects: tuple = ()
        if self.hosted is not None:
            # Looked at each tick (and the hosted scene wakes the clock when it changes), so however it opens
            # or closes, the keyboard and input region follow.
            shown = self.hosted.visible()
            if shown != self.hosted.was_visible:
                self.hosted.was_visible = shown
                self.hosted_shown(self.hosted, shown, shown and getattr(self.hosted.widget, "wants_keyboard", True))
            if shown:
                hosted_rects = tuple((r.x() - origin.x(), r.y() - origin.y(), r.width(), r.height()) for r in self.hosted.input_rects())
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
        # Where it takes clicks: built again only when something in it changed, and as plain numbers.
        bubble_rect = bubble_box.toAlignedRect() if self.bubble.visible() else None
        parts = (
            sprite.rects if sprite is not None else (),
            (penguin.x(), penguin.y()),
            (bubble_rect.x(), bubble_rect.y(), bubble_rect.width(), bubble_rect.height()) if bubble_rect is not None else None,
            (zs.x(), zs.y(), zs.width(), zs.height()) if zs.isValid() else None,
            hosted_rects,
            (self._geo.width(), self._geo.height()) if self.menu.is_open() else None,
        )
        if parts != self._input_parts:
            self._input_parts = parts
            rects, (px, py), bubble_t, zs_t, hosted_t, menu = parts
            if menu is not None:  # like any popup menu: a click anywhere else closes it
                inputs = ((0, 0, *menu),)
            else:
                # The sprite sits on half pixels on a 2x screen: whole pixels round it, outward.
                dx, dy = math.floor(px), math.floor(py)
                ex, ey = (1 if px != dx else 0), (1 if py != dy else 0)
                inputs = tuple((x + dx, y + dy, w + ex, h + ey) for x, y, w, h in rects) + tuple(r for r in (bubble_t, zs_t) if r) + hosted_t
            self._inputs = inputs
            self.surface.set_input(inputs)
        if head != self._head:
            self._head = head
            self.head_moved.emit()
        self.next_tick_in = self._next_tick(now, zs)
        self._schedule(self.next_tick_in)

    def _device_scale(self) -> float:
        scale = getattr(self.surface, "device_scale", None)
        k = scale() if scale is not None else 0.0
        return k if k > 0 else 1.0

    def _sleeping(self, f: Frame) -> bool:
        return f.anim == "sleep" and f.index >= 3

    def _z_rect(self, penguin: QRectF) -> QRect:
        if penguin.isNull():
            return QRect()
        return QRect(round(penguin.center().x()) + 6, round(penguin.top()) - 30, 48, 44)

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
                self._paint_zs(p, self._z_rect(self._penguin), self._z_phase)
        if self.bubble.drawn() and not self._bubble_box.isNull() and region.intersects(self._bubble_box.toAlignedRect().adjusted(-3, -3, 3, 3)):
            p.save()
            p.translate(self._bubble_box.topLeft())
            self.bubble.paint(p, self._head.x() - self._bubble_box.x(), now)
            p.restore()
        if self.hosted is not None:
            self.hosted.paint(p, region)
        if self.menu.is_open() and any(region.intersects(r.adjusted(-3, -3, 3, 3)) for r in self._menu_rects):
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
        if f is not None and f.anim is not None and self._penguin.contains(QPointF(pos)):
            sprite = self.sprites.frame(f.anim, f.index, f.mirror)
            x, y = math.floor(pos.x() - self._penguin.x()), math.floor(pos.y() - self._penguin.y())
            if any(sprite.hit(x + dx, y + dy) for dx, dy in ((0, 0), (3, 0), (-3, 0), (0, 3), (0, -3))):
                return "penguin"
        return None

    # Surfaces pass the pointer on in local (stage) and global (Qt) coordinates.

    def press(self, pos: QPointF, gpos: QPointF, button: Qt.MouseButton) -> bool:
        """A button went down; False if it's not on anything of ours."""
        self._wake()
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
        self._wake()  # a drag redraws on the move (within a frame), not on a clock's tick
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
            self._bubble_hovered(hover not in (None, "penguin"))
            self.behavior.hovered = hover == "penguin"
            return
        if self._press_on != "penguin":
            return
        if not self._dragging and (gpos.toPoint() - self._press).manhattanLength() < 6:
            return
        self._dragging = True
        screen = self._screen_at(gpos.toPoint())
        if screen is not None:
            self._use_screen(screen)
        foot = gpos - self._grab
        self.behavior.hold(foot.x(), self._screen_floor() - foot.y(), self._clock())

    def release(self, pos: QPointF, gpos: QPointF, button: Qt.MouseButton) -> None:
        self._wake()
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
        self._wake()
        self.bubble.hover = None
        self._bubble_hovered(False)
        self.behavior.hovered = False

    def _bubble_hovered(self, on: bool) -> None:
        """Tell the bubble the pointer is on it (or not), once it takes that (M2: a bubble waits while read)."""
        set_hovered = getattr(self.bubble, "set_hovered", None)
        if set_hovered is not None:
            set_hovered(on)

    def _set_cursor(self, shape: str) -> None:
        set_cursor = getattr(self.surface, "set_cursor", None)
        if set_cursor is not None:
            set_cursor(shape)

    def _screen_floor(self) -> float:
        avail = self._screen.availableGeometry()
        return avail.y() + avail.height()
