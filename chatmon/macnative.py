"""macOS: what Qt doesn't say for the chatmon's windows, said to AppKit itself, through the Objective-C runtime
(no PyObjC). Every call has its exact prototype, as Apple silicon needs; any that fails leaves Qt's way.

- The stage and the ask box follow you to every Space and through Stage Manager, as a floating overlay
  should, and keep out of full-screen apps' own Spaces (as the other platforms keep out of full-screen apps).
  https://developer.apple.com/documentation/appkit/nswindow/collectionbehavior-swift.struct
- Clicks through the stage are switched with setIgnoresMouseEvents: rather than a Qt window flag, which has
  Qt set up the whole window again each time.
- Chatmon becomes the active app only when you open the ask box, never when a bubble shows.
"""

from __future__ import annotations

import ctypes
import ctypes.util

# NSWindowCollectionBehavior
CAN_JOIN_ALL_SPACES = 1 << 0
MOVE_TO_ACTIVE_SPACE = 1 << 1
STATIONARY = 1 << 4  # Mission Control leaves it where it is
IGNORES_CYCLE = 1 << 6  # never in Cmd-` window cycling
FULL_SCREEN_PRIMARY = 1 << 7
FULL_SCREEN_AUXILIARY = 1 << 8
CAN_JOIN_ALL_APPLICATIONS = 1 << 18  # macOS 13: floating windows and overlays, outside Stage Manager's layout
OVERLAY = CAN_JOIN_ALL_SPACES | STATIONARY | IGNORES_CYCLE | CAN_JOIN_ALL_APPLICATIONS


class _ObjC:
    def __init__(self):
        lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc") or "/usr/lib/libobjc.dylib")
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
        lib.objc_getClass.restype = ctypes.c_void_p
        lib.objc_getClass.argtypes = [ctypes.c_char_p]
        lib.sel_registerName.restype = ctypes.c_void_p
        lib.sel_registerName.argtypes = [ctypes.c_char_p]
        self.lib = lib
        send = ctypes.cast(lib.objc_msgSend, ctypes.c_void_p).value
        self.obj = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)  # -> id
        self.ulong = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)(send)  # -> NSUInteger
        self.set_ulong = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(send)
        self.set_bool = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)(send)
        self.responds = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)

    def sel(self, name: str) -> int:
        return self.lib.sel_registerName(name.encode())

    def cls(self, name: str) -> int:
        return self.lib.objc_getClass(name.encode())


_objc: _ObjC | None = None


def _rt() -> _ObjC | None:
    global _objc
    if _objc is None:
        try:
            _objc = _ObjC()
        except (AttributeError, OSError):
            return None
    return _objc


def _window(widget) -> int:
    """The NSWindow of a Qt window: its winId() is the NSView, whose -window is it."""
    rt = _rt()
    view = int(widget.winId()) if rt else 0
    return rt.obj(view, rt.sel("window")) if view else 0


def float_everywhere(widget) -> bool:
    """On every Space and outside Stage Manager's layout, not in full-screen apps' Spaces. True if done."""
    rt, window = _rt(), _window(widget)
    if not window:
        return False
    try:
        behavior = rt.ulong(window, rt.sel("collectionBehavior"))
        behavior &= ~(MOVE_TO_ACTIVE_SPACE | FULL_SCREEN_PRIMARY | FULL_SCREEN_AUXILIARY)
        rt.set_ulong(window, rt.sel("setCollectionBehavior:"), behavior | OVERLAY)
        return True
    except (ctypes.ArgumentError, OSError):
        return False


def collection_behavior(widget) -> int | None:
    rt, window = _rt(), _window(widget)
    return rt.ulong(window, rt.sel("collectionBehavior")) if window else None


def ignore_mouse(widget, on: bool) -> bool:
    """Clicks go through the window (on), or it takes them. True if done."""
    rt, window = _rt(), _window(widget)
    if not window:
        return False
    rt.set_bool(window, rt.sel("setIgnoresMouseEvents:"), on)
    return True


def activate() -> None:
    """Make Chatmon the active app (you opened its ask box, so the keyboard comes to it)."""
    rt = _rt()
    if rt is None:
        return
    app = rt.obj(rt.cls("NSApplication"), rt.sel("sharedApplication"))
    if not app:
        return
    if rt.responds(app, rt.sel("respondsToSelector:"), rt.sel("activate")):  # macOS 14: the cooperative way
        rt.obj(app, rt.sel("activate"))
    else:
        rt.set_bool(app, rt.sel("activateIgnoringOtherApps:"), True)
