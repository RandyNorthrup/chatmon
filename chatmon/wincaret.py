"""Windows: let Magnifier find a new bubble. Magnifier follows the mouse, keyboard focus and the text cursor (the
system caret). A bubble appears away from all three, so someone using Magnifier never sees it. A hidden system caret
placed over the bubble raises the caret's location event (EVENT_OBJECT_LOCATIONCHANGE for OBJID_CARET), which
Magnifier follows, so it pans there. This is an option, and the caret is only placed while Magnifier runs.

A thread has one caret (it belongs to the message queue), and Chatmon's windows are all on the Qt thread: place it
from there, and never while the ask box has focus, whose own caret it would replace. Imports anywhere; does nothing
except on Windows.
https://learn.microsoft.com/en-us/windows/win32/menurc/using-carets
https://learn.microsoft.com/en-us/windows/win32/winauto/event-constants"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

logger = logging.getLogger(__name__)

MAGNIFIER_CLASS = "MagUIClass"  # the window class of Magnifier's own window (Magnify.exe)

_user32 = None


def _api():
    global _user32
    if _user32 is None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        user32.CreateCaret.argtypes = [wintypes.HWND, wintypes.HBITMAP, ctypes.c_int, ctypes.c_int]
        user32.CreateCaret.restype = wintypes.BOOL
        user32.SetCaretPos.argtypes = [ctypes.c_int, ctypes.c_int]
        user32.SetCaretPos.restype = wintypes.BOOL
        user32.DestroyCaret.argtypes = []
        user32.DestroyCaret.restype = wintypes.BOOL
        _user32 = user32
    return _user32


def magnifier_running() -> bool:
    """Is Magnifier open? Its window is there while it runs, docked, as a lens or full screen."""
    if sys.platform != "win32":
        return False
    try:
        return bool(_api().FindWindowW(MAGNIFIER_CLASS, None))
    except (AttributeError, OSError) as exc:
        logger.debug("couldn't tell whether Magnifier is open: %s", exc)
        return False


class Caret:
    """The Qt thread's system caret, put over a bubble and taken away again."""

    def __init__(self) -> None:
        self.window: int | None = None  # where the caret is, while it is

    def place(self, hwnd: int, x: int, y: int, width: int, height: int) -> bool:
        """Put a hidden caret on `hwnd` over the bubble: its rectangle in the window's own pixels (Qt's logical
        coordinates times the window's devicePixelRatio). False if it couldn't be."""
        if sys.platform != "win32" or not hwnd:
            return False
        user32 = _api()
        # A caret of the bubble's size: Magnifier brings the caret's whole rectangle into view where it can.
        if not user32.CreateCaret(hwnd, None, max(1, int(width)), max(1, int(height))):
            return False
        self.window = hwnd
        # Never shown (no ShowCaret): only Magnifier and other assistive tools know it's there.
        return bool(user32.SetCaretPos(int(x), int(y)))

    def clear(self) -> None:
        """Take the caret away (as the bubble closes)."""
        if self.window is not None:
            _api().DestroyCaret()
            self.window = None


_caret = Caret()


def place(hwnd: int, x: int, y: int, width: int, height: int) -> bool:
    return _caret.place(hwnd, x, y, width, height)


def clear() -> None:
    _caret.clear()
