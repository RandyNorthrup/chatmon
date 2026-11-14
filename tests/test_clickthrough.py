"""Click-through on Windows and macOS: the stage window takes the mouse only while the pointer is over
something of ours. On Windows that's WS_EX_TRANSPARENT on its native window, switched on its own: the
rest of the window's style, WS_EX_LAYERED above all, is left as it is."""

import ctypes
import sys

import pytest
from PyQt6.QtCore import Qt

from chatmon import clickthrough

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

WS_EX_LAYERED, WS_EX_TOOLWINDOW, WS_EX_TOPMOST = 0x80000, 0x80, 0x8
WS_POPUP = 0x80000000
OVER_CHATMON, OVER_FIRST_BUTTON, NOWHERE = "penguin", 0, None  # what Stage._target_at says


class Handle:
    """Qt's window for the stage, as far as PointerToggle uses it."""

    def __init__(self):
        self.transparent = []

    def setFlag(self, flag, on):
        assert flag == Qt.WindowType.WindowTransparentForInput
        self.transparent.append(on)


class Widget:
    """The stage window: a native window (or none), and Qt's window, which on Windows mustn't be touched."""

    def __init__(self, hwnd=0, handle=None):
        self.hwnd, self.handle = hwnd, handle

    def winId(self):
        return self.hwnd

    def mapFromGlobal(self, point):
        return point

    def windowHandle(self):
        if self.handle is None:
            raise AssertionError("Qt's window flags were changed")
        return self.handle


def test_the_first_bubble_button_takes_clicks(qapp):
    handle = Handle()
    toggle = clickthrough.PointerToggle(Widget(handle=handle))
    toggle.follow_pointer(lambda pos: NOWHERE)
    toggle.follow_pointer(lambda pos: OVER_FIRST_BUTTON)
    assert handle.transparent == [True, False]


@pytest.fixture
def user32():
    lib = ctypes.WinDLL("user32", use_last_error=True)
    lib.CreateWindowExW.restype = ctypes.c_void_p
    lib.CreateWindowExW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32] + [ctypes.c_int] * 4 + [ctypes.c_void_p] * 4
    lib.DestroyWindow.argtypes = [ctypes.c_void_p]
    lib.GetWindowLongPtrW.restype, lib.GetWindowLongPtrW.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int]
    lib.SetWindowLongPtrW.restype, lib.SetWindowLongPtrW.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    return lib


@pytest.fixture
def hwnd(user32):
    """A layered tool window of the test's own, styled as Qt styles the stage's, never shown."""
    window = user32.CreateWindowExW(WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST, "STATIC", "chatmon test", WS_POPUP, 0, 0, 64, 64, None, None, None, None)
    assert window, ctypes.get_last_error()
    yield window
    user32.DestroyWindow(window)


def style(user32, hwnd):
    return user32.GetWindowLongPtrW(hwnd, clickthrough.GWL_EXSTYLE)


@windows_only
def test_clicks_go_through_from_the_start(qapp, user32, hwnd):
    clickthrough.WindowsPointerToggle(Widget(hwnd))
    assert style(user32, hwnd) == WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | clickthrough.WS_EX_TRANSPARENT


@windows_only
def test_takes_the_mouse_only_over_the_chatmon_and_keeps_the_window_layered(qapp, user32, hwnd):
    toggle = clickthrough.WindowsPointerToggle(Widget(hwnd))
    others = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
    for target, transparent in ((OVER_CHATMON, False), (NOWHERE, True), (OVER_FIRST_BUTTON, False), (NOWHERE, True)) * 3:
        toggle.follow_pointer(lambda pos, target=target: target)
        assert style(user32, hwnd) == others | (clickthrough.WS_EX_TRANSPARENT if transparent else 0), target


@windows_only
def test_puts_its_style_back_when_something_else_changes_it(qapp, user32, hwnd):
    toggle = clickthrough.WindowsPointerToggle(Widget(hwnd))
    toggle.follow_pointer(lambda pos: NOWHERE)
    user32.SetWindowLongPtrW(hwnd, clickthrough.GWL_EXSTYLE, style(user32, hwnd) & ~clickthrough.WS_EX_TRANSPARENT)  # as Qt would, setting styles again
    toggle.follow_pointer(lambda pos: NOWHERE)
    assert style(user32, hwnd) & clickthrough.WS_EX_TRANSPARENT


@windows_only
def test_for_window_picks_it_on_windows(qapp, monkeypatch, hwnd):
    class Gui:
        @staticmethod
        def platformName():
            return "windows"

    monkeypatch.setattr(clickthrough, "QGuiApplication", Gui)
    assert type(clickthrough.for_window(Widget(hwnd))) is clickthrough.WindowsPointerToggle


def test_the_x_input_shape_is_in_device_pixels_rounded_outward():
    logical = ((10, 20, 30, 4), (0, 0, 1, 1), (7, 3, 5, 9))
    assert clickthrough.device_rects(logical, 1.0) == logical
    assert clickthrough.device_rects(logical, 2.0) == ((20, 40, 60, 8), (0, 0, 2, 2), (14, 6, 10, 18))
    # 1.5: 7 * 1.5 = 10.5 and 12 * 1.5 = 18 (the right edge): the shape starts at 10 and covers both half pixels.
    assert clickthrough.device_rects(((7, 3, 5, 9),), 1.5) == ((10, 4, 8, 14),)
    for x, y, w, h in logical:
        (dx, dy, dw, dh), = clickthrough.device_rects(((x, y, w, h),), 1.25)
        assert dx <= x * 1.25 and dy <= y * 1.25 and dx + dw >= (x + w) * 1.25 and dy + dh >= (y + h) * 1.25


class _XlibWindow:
    """A window of the test's own on the X server in DISPLAY, and a way to read back its input shape."""

    def __init__(self):
        import ctypes.util
        import os

        if not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"):
            pytest.skip("needs an X server (DISPLAY), as under Xvfb")
        x11_name, xext_name = ctypes.util.find_library("X11"), ctypes.util.find_library("Xext")
        if not x11_name or not xext_name:
            pytest.skip("libX11 and libXext aren't installed")
        self.x11, self.xext = ctypes.CDLL(x11_name), ctypes.CDLL(xext_name)
        self.x11.XOpenDisplay.restype = ctypes.c_void_p
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XDefaultRootWindow.restype = ctypes.c_ulong
        self.x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.x11.XCreateSimpleWindow.restype = ctypes.c_ulong
        self.x11.XCreateSimpleWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong] + [ctypes.c_int] * 2 + [ctypes.c_uint] * 3 + [ctypes.c_ulong] * 2
        self.x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.x11.XDestroyWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.x11.XFree.argtypes = [ctypes.c_void_p]
        self.xext.XShapeGetRectangles.restype = ctypes.POINTER(clickthrough._XRectangle)
        self.xext.XShapeGetRectangles.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        self.display = self.x11.XOpenDisplay(None)
        if not self.display:
            pytest.skip("can't open the X display")
        self.window = self.x11.XCreateSimpleWindow(self.display, self.x11.XDefaultRootWindow(self.display), 0, 0, 400, 300, 0, 0, 0)
        self.x11.XSync(self.display, 0)

    def input_shape(self) -> set:
        self.x11.XSync(self.display, 0)
        count, ordering = ctypes.c_int(), ctypes.c_int()
        rects = self.xext.XShapeGetRectangles(self.display, self.window, clickthrough.XShapeInput.SHAPE_INPUT, ctypes.byref(count), ctypes.byref(ordering))
        found = {(rects[i].x, rects[i].y, rects[i].width, rects[i].height) for i in range(count.value)}
        if rects:
            self.x11.XFree(rects)
        return found

    def close(self):
        self.x11.XDestroyWindow(self.display, self.window)
        self.x11.XCloseDisplay(self.display)


class _ScaledWidget:
    def __init__(self, window, ratio):
        self.window, self.ratio = window, ratio

    def winId(self):
        return self.window

    def devicePixelRatioF(self):
        return self.ratio


def test_the_x_server_gets_the_shape_in_device_pixels(qapp):
    win = _XlibWindow()
    try:
        widget = _ScaledWidget(win.window, 2.0)
        shape = clickthrough.XShapeInput(widget)
        shape.update([(10, 20, 30, 4), (100, 120, 7, 9)])
        assert win.input_shape() == {(20, 40, 60, 8), (200, 240, 14, 18)}  # twice the logical rectangles, where they are
        widget.ratio = 1.5  # the scale changed, the rectangles didn't: sent again
        shape.update([(10, 20, 30, 4), (100, 120, 7, 9)])
        assert win.input_shape() == {(15, 30, 45, 6), (150, 180, 11, 14)}
        shape.close()
    finally:
        win.close()
