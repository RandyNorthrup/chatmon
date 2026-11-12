"""macOS: what Qt doesn't say for the chatmon's windows, said to AppKit itself, through the Objective-C runtime
(no PyObjC). Every call has its exact prototype, as Apple silicon needs; any that fails leaves Qt's way.

- The stage and the ask box follow you to every Space and through Stage Manager, as a floating overlay
  should, and keep out of full-screen apps' own Spaces (as the other platforms keep out of full-screen apps).
  https://developer.apple.com/documentation/appkit/nswindow/collectionbehavior-swift.struct
- Clicks through the stage are switched with setIgnoresMouseEvents: rather than a Qt window flag, which has
  Qt set up the whole window again each time.
- Chatmon becomes the active app only when you open the ask box, never when a bubble shows.
- Whether a full-screen app is over the chatmon's screen, from CoreGraphics' window list: bounds, layers and
  owners only, which need no Screen Recording permission (titles and contents would).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
from typing import NamedTuple

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
        self.long = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(send)  # -> NSInteger
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


# -- What's on screen: CoreGraphics' window list, each window's owner, layer, bounds and whether it's on screen.
#    https://developer.apple.com/documentation/coregraphics/cgwindowlistcopywindowinfo(_:_:)

_ON_SCREEN_ONLY, _INCLUDING_WINDOW, _EXCLUDE_DESKTOP = 1 << 0, 1 << 3, 1 << 4  # CGWindowListOption
_SINT32 = 3  # kCFNumberSInt32Type


class Window(NamedTuple):
    pid: int
    layer: int  # 0: an app's own windows; menus, the Dock and the menu bar are above
    on_screen: bool
    bounds: tuple[float, float, float, float]  # x, y, width, height: points, from the main screen's top left


class _Rect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double), ("w", ctypes.c_double), ("h", ctypes.c_double)]


class _WindowList:
    def __init__(self):
        cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
        cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        cg.CGRectMakeWithDictionaryRepresentation.restype = ctypes.c_bool
        cg.CGRectMakeWithDictionaryRepresentation.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Rect)]
        cf.CFArrayGetCount.restype = ctypes.c_long
        cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
        cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
        cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
        cf.CFDictionaryGetValue.restype = ctypes.c_void_p
        cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cf.CFNumberGetValue.restype = ctypes.c_bool
        cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p]
        cf.CFBooleanGetValue.restype = ctypes.c_bool
        cf.CFBooleanGetValue.argtypes = [ctypes.c_void_p]
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        self.cf, self.cg = cf, cg
        self.key = {name: ctypes.c_void_p.in_dll(cg, f"kCGWindow{name}").value for name in ("OwnerPID", "Layer", "IsOnscreen", "Bounds")}

    def _int(self, entry: int, name: str) -> int:
        value, number = self.cf.CFDictionaryGetValue(entry, self.key[name]), ctypes.c_int32()
        return number.value if value and self.cf.CFNumberGetValue(value, _SINT32, ctypes.byref(number)) else -1

    def windows(self, option: int, window: int = 0) -> list[Window]:
        listed = self.cg.CGWindowListCopyWindowInfo(option, window)
        if not listed:
            return []
        try:
            out = []
            for i in range(self.cf.CFArrayGetCount(listed)):
                entry = self.cf.CFArrayGetValueAtIndex(listed, i)
                on = self.cf.CFDictionaryGetValue(entry, self.key["IsOnscreen"])  # left out when it isn't
                rect = _Rect()
                if not self.cg.CGRectMakeWithDictionaryRepresentation(self.cf.CFDictionaryGetValue(entry, self.key["Bounds"]), ctypes.byref(rect)):
                    continue
                out.append(Window(self._int(entry, "OwnerPID"), self._int(entry, "Layer"), bool(on and self.cf.CFBooleanGetValue(on)),
                                  (rect.x, rect.y, rect.w, rect.h)))
            return out
        finally:
            self.cf.CFRelease(listed)


_window_list: _WindowList | None = None


def _windows() -> _WindowList | None:
    global _window_list
    if _window_list is None:
        try:
            _window_list = _WindowList()
        except (AttributeError, OSError, ValueError):
            return None
    return _window_list


def full_screen_over(view: int) -> bool:
    """Is another app full screen (or in Split View) on the screen of the window whose NSView `view` is: the
    stage's? Its bubbles would come and go unseen there, as macOS keeps the stage out of full-screen apps'
    Spaces. Then macOS has the stage off screen, and another app's window fills that screen from its very top
    edge (with no menu bar): the two things the window list says while it happens (checked on macOS 15)."""
    rt, listed = _rt(), _windows()
    if rt is None or listed is None or not view:
        return False
    try:
        window = rt.obj(view, rt.sel("window"))
        number = rt.long(window, rt.sel("windowNumber")) if window else 0
        if number <= 0:  # not on the window server
            return False
        mine = listed.windows(_INCLUDING_WINDOW, number)
        if not mine or mine[0].on_screen:
            return False
        me = os.getpid()
        return fills_from_top(mine[0].bounds, [w for w in listed.windows(_ON_SCREEN_ONLY | _EXCLUDE_DESKTOP) if w.pid != me])
    except (ctypes.ArgumentError, OSError):
        return False


def fills_from_top(screen: tuple[float, float, float, float], windows: list[Window]) -> bool:
    """Whether one of these is an app's window (layer 0) on `screen`, from its very top edge: a full-screen
    app's, or either half of Split View. With the menu bar showing, every window starts below it."""
    x, y, w, h = screen
    for win in windows:
        wx, wy, ww, wh = win.bounds
        if win.layer == 0 and ww > 0 and wh > 0 and abs(wy - y) <= 1 and wx >= x - 1 and wx + ww <= x + w + 1 and wy + wh <= y + h + 1:
            return True
    return False

