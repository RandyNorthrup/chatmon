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
