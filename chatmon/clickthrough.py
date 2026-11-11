"""Let clicks through the stage window everywhere except the penguin and its
bubbles, so the window can cover the screen without getting in the way.

- X11 and XWayland: an X input shape (the SHAPE extension, through libXext),
  which changes only where clicks land, never what's drawn.
- Windows and macOS: the whole window ignores the mouse except while the
  pointer is over something of ours, checked every frame. On Windows that's
  the native window's WS_EX_TRANSPARENT style, never Qt's window flags (see
  WindowsPointerToggle).
- Anything else: Qt's window mask (on Wayland, the surface's input region).
"""

from __future__ import annotations

import ctypes
import ctypes.util

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QGuiApplication, QRegion
from PyQt6.QtWidgets import QWidget



def _key(rects) -> tuple:
    """Rectangles as (x, y, w, h) tuples: the stage sends them so; QRects are taken too."""
    return tuple(rects) if not rects or isinstance(rects[0], tuple) else tuple((r.x(), r.y(), r.width(), r.height()) for r in rects)

class _XRectangle(ctypes.Structure):
    _fields_ = [("x", ctypes.c_short), ("y", ctypes.c_short), ("width", ctypes.c_ushort), ("height", ctypes.c_ushort)]


class XShapeInput:
    SHAPE_INPUT = 2
    SHAPE_SET = 0

    def __init__(self, widget: QWidget):
        x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        xext = ctypes.CDLL(ctypes.util.find_library("Xext") or "libXext.so.6")
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XFlush.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xext.XShapeQueryExtension.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        xext.XShapeCombineRectangles.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(_XRectangle), ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ]
        self._x11, self._xext = x11, xext
        self._display = x11.XOpenDisplay(None)
        event, error = ctypes.c_int(), ctypes.c_int()
        if not self._display or not xext.XShapeQueryExtension(self._display, ctypes.byref(event), ctypes.byref(error)):
            raise OSError("no X SHAPE extension")
        self._window = int(widget.winId())
        self._last: tuple | None = None
        self.update([])

    def update(self, rects) -> None:
        key = _key(rects)
        if key == self._last:
            return
        self._last = key
        array = (_XRectangle * max(1, len(key)))(*[_XRectangle(*r) for r in key])
        self._xext.XShapeCombineRectangles(self._display, self._window, self.SHAPE_INPUT, 0, 0, array, len(key), self.SHAPE_SET, 0)
        self._x11.XFlush(self._display)

    def follow_pointer(self, hit) -> None:
        pass

    def close(self) -> None:
        if self._display:
            self._x11.XCloseDisplay(self._display)
            self._display = None


class PointerToggle:
    """macOS: switch mouse input on only under the pointer, with Qt's
    WindowTransparentForInput."""

    def __init__(self, widget: QWidget):
        self._widget = widget
        self._accepting: bool | None = None

    def update(self, rects) -> None:
        pass

    def follow_pointer(self, hit) -> None:
        local = self._widget.mapFromGlobal(QCursor.pos())
        # A press on the chatmon keeps the mouse until it's let go: a drag can outrun the sprite.
        dragging = QGuiApplication.mouseButtons() != Qt.MouseButton.NoButton and bool(self._accepting)
        # Not bool(hit): the bubble's first button is index 0, and a click on it would go through.
        self._accept(hit(local) is not None or dragging)

    def _accept(self, accepting: bool) -> None:
        handle = self._widget.windowHandle()
        if handle is not None and accepting != self._accepting:
            self._accepting = accepting
            handle.setFlag(Qt.WindowType.WindowTransparentForInput, not accepting)

    def close(self) -> None:
        pass


GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20  # on a layered window: every click goes through it, to the window below


class WindowsPointerToggle(PointerToggle):
    """Windows: the same, by switching WS_EX_TRANSPARENT on the stage's native
    window and nothing else.

    Not with Qt's WindowTransparentForInput: changing a flag makes Qt work out
    the window's whole extended style again, and that drops WS_EX_LAYERED for a
    moment. Windows throws away a layered window's picture when it does, and the
    stage only redraws what changed, so the next frame put up just that patch:
    the chatmon vanished, and since a layered window lets clicks through
    wherever it's transparent, it couldn't be clicked either."""

    def __init__(self, widget: QWidget):
        super().__init__(widget)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._get_style = user32.GetWindowLongPtrW
        self._get_style.restype, self._get_style.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int]
        self._set_style = user32.SetWindowLongPtrW
        self._set_style.restype, self._set_style.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        self._accept(False)  # the window covers the screen: clicks go through it from the start

    def _accept(self, accepting: bool) -> None:
        # The style is read every frame, not remembered: if Qt ever sets the window's styles again, the
        # next frame puts this one back.
        hwnd = int(self._widget.winId())
        style = self._get_style(hwnd, GWL_EXSTYLE)
        wanted = style & ~WS_EX_TRANSPARENT if accepting else style | WS_EX_TRANSPARENT
        if style and wanted != style:
            self._set_style(hwnd, GWL_EXSTYLE, wanted)
        self._accepting = accepting


class MaskInput:
    def __init__(self, widget: QWidget):
        self._widget = widget
        self._last: tuple | None = None
        self.update([])

    def update(self, rects) -> None:
        key = _key(rects)
        if key == self._last:
            return
        self._last = key
        region = QRegion()
        for r in key:
            region = region.united(QRegion(*r))
        # An empty mask means "no mask" to Qt; keep one invisible pixel instead.
        self._widget.setMask(region if not region.isEmpty() else QRegion(0, 0, 1, 1))

    def follow_pointer(self, hit) -> None:
        pass

    def close(self) -> None:
        pass


def for_window(widget: QWidget):
    platform = QGuiApplication.platformName()
    if platform == "xcb":
        try:
            return XShapeInput(widget)
        except OSError:
            return MaskInput(widget)
    if platform == "windows":
        return WindowsPointerToggle(widget)
    if platform == "cocoa":
        return PointerToggle(widget)
    return MaskInput(widget)
