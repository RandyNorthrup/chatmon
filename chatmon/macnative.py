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
- Starting at login as a login item of its own (SMAppService), not an unattributed LaunchAgent.
- Pasting that macOS counts as yours: Cmd+V through an Edit menu of its own, and the ask box's menus as native
  ones, so its pasteboard privacy doesn't ask whether Chatmon may paste what you just asked it to.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import re
from typing import Callable, NamedTuple

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
        self.text = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p)(send)  # -> const char *
        # -> BOOL, taking an NSError ** to fill in
        self.ok = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(send)
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


# -- Starting at login (macOS 13): Chatmon.app itself as a login item, through SMAppService. It's listed by name
#    in System Settings › General › Login Items, where turning it off is seen in Chatmon's menu too; a
#    LaunchAgent is only an unattributed background item there. It works with Chatmon's ad hoc signature, and a
#    registration outlasts an update to a newly signed build (both checked on macOS 15).
#    https://developer.apple.com/documentation/servicemanagement/smappservice/mainapp

NOT_REGISTERED, ENABLED, REQUIRES_APPROVAL, NOT_FOUND = 0, 1, 2, 3  # SMAppService.Status


def _main_app_service() -> tuple[_ObjC | None, int]:
    rt = _rt()
    if rt is None:
        return None, 0
    try:
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ServiceManagement.framework/ServiceManagement")
    except OSError:
        return None, 0
    cls = rt.cls("SMAppService")  # nil before macOS 13
    service = rt.obj(cls, rt.sel("mainAppService")) if cls else 0
    return (rt, service) if service else (None, 0)


def login_item() -> int | None:
    """The app's login item: one of the statuses above, or None where there's no SMAppService."""
    rt, service = _main_app_service()
    return rt.long(service, rt.sel("status")) if rt else None


def set_login_item(on: bool) -> str | None:
    """Make the app a login item, or stop it being one. None if done, else why it wasn't."""
    rt, service = _main_app_service()
    if rt is None:
        return "this macOS has no SMAppService"
    error = ctypes.c_void_p()
    if rt.ok(service, rt.sel("registerAndReturnError:" if on else "unregisterAndReturnError:"), ctypes.byref(error)):
        return None
    described = rt.obj(error.value, rt.sel("localizedDescription")) if error.value else 0
    text = rt.text(described, rt.sel("UTF8String")) if described else None
    return text.decode("utf-8", "replace") if text else "macOS didn't say why"


# -- Pasting that macOS counts as yours. Where its pasteboard privacy is on (macOS 15.4 and later with
#    EnablePasteboardPrivacyDeveloperPreview, and by default in a later release), an app that reads the clipboard
#    gets "“Chatmon” is trying to access the pasteboard" unless the read comes from a native menu item, chosen or
#    by its key equivalent: Cmd+V as a key press, a call of the app's own and a Qt-drawn menu all ask. And inside
#    a Qt menu's event loop macOS can't ask: NSPasteboard's assertion stopped Chatmon. So here Cmd+V comes
#    through an Edit menu of Chatmon's own (unseen, as Chatmon has no menu bar), and the ask box's menus are
#    native ones, with Qt's actions behind them (all checked on macOS 15.7, with real input).
#    https://developer.apple.com/documentation/appkit/nspasteboard/accessbehavior-swift.enum

_Action = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)  # -(void)name:(id)sender


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class _Menus:
    """An Objective-C class of Chatmon's own, the target of its native menu items, whose actions run Python."""

    def __init__(self, rt: _ObjC):
        lib = rt.lib
        lib.objc_allocateClassPair.restype = ctypes.c_void_p
        lib.objc_allocateClassPair.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
        lib.class_addMethod.restype = ctypes.c_bool
        lib.class_addMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
        lib.objc_registerClassPair.argtypes = [ctypes.c_void_p]
        send = ctypes.cast(lib.objc_msgSend, ctypes.c_void_p).value
        self.rt = rt
        self.string = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)(send)  # -> NSString
        self.make = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)  # (id) -> id
        self.put = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)  # (id) -> void
        self.set_long = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(send)
        self.index = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)  # (id) -> NSInteger
        # initWithTitle:action:keyEquivalent:
        self.item = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)
        # popUpMenuPositioningItem:atLocation:inView: -> BOOL
        self.pop = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, _Point, ctypes.c_void_p)(send)
        self.on_paste: Callable[[], None] | None = None
        self.actions: list = []  # the QActions of the menu showing, by their items' tags
        self.edit = 0  # the Edit menu's item in the menu bar
        self._paste, self._chosen = _Action(self._pasted), _Action(self._picked)  # kept: the class calls them
        name = b"ChatmonMenuTarget"
        cls = lib.objc_allocateClassPair(rt.cls("NSObject"), name, 0)
        if not cls:
            raise OSError("ChatmonMenuTarget exists already")
        lib.class_addMethod(cls, rt.sel("paste:"), ctypes.cast(self._paste, ctypes.c_void_p), b"v@:@")
        lib.class_addMethod(cls, rt.sel("chosen:"), ctypes.cast(self._chosen, ctypes.c_void_p), b"v@:@")
        lib.objc_registerClassPair(cls)
        self.target = rt.obj(rt.obj(cls, rt.sel("alloc")), rt.sel("init"))  # kept for good

    def _pasted(self, me, cmd, sender) -> None:
        # Only ever with one of Qt's windows in front: while a dialog of macOS's own is open (modal), AppKit turns
        # off an item whose target doesn't say it works then, so Cmd+V goes to the dialog as it always did.
        if self.on_paste is not None:
            self.on_paste()

    def _picked(self, me, cmd, sender) -> None:
        tag = self.rt.long(sender, self.rt.sel("tag"))
        if 0 <= tag < len(self.actions):
            self.actions[tag].trigger()

    def text(self, s: str) -> int:
        return self.string(self.rt.cls("NSString"), self.rt.sel("stringWithUTF8String:"), s.encode("utf-8"))

    def new_item(self, title: str, action: str | None, key: str = "") -> int:
        rt = self.rt
        item = self.item(rt.obj(rt.cls("NSMenuItem"), rt.sel("alloc")), rt.sel("initWithTitle:action:keyEquivalent:"),
                         self.text(title), rt.sel(action) if action else None, self.text(key))
        return rt.obj(item, rt.sel("autorelease"))

    def new_menu(self, title: str = "") -> int:
        rt = self.rt
        menu = self.make(rt.obj(rt.cls("NSMenu"), rt.sel("alloc")), rt.sel("initWithTitle:"), self.text(title))
        return rt.obj(menu, rt.sel("autorelease"))

    def mirror(self, menu) -> int:
        """A native menu with the QMenu's items (and submenus'), each choosing its QAction."""
        rt = self.rt
        ns = self.new_menu()
        rt.set_bool(ns, rt.sel("setAutoenablesItems:"), False)  # enabled as the actions are
        empty = True
        for action in menu.actions():
            if not action.isVisible():
                continue
            if action.isSeparator():
                if not empty:
                    self.put(ns, rt.sel("addItem:"), rt.obj(rt.cls("NSMenuItem"), rt.sel("separatorItem")))
                if action.text():  # a section's heading
                    heading = self.new_item(menu_text(action.text()), None)
                    rt.set_bool(heading, rt.sel("setEnabled:"), False)
                    self.put(ns, rt.sel("addItem:"), heading)
                    empty = False
                continue
            sub = action.menu()
            item = self.new_item(menu_text(action.text()), None if sub is not None else "chosen:")
            if sub is not None:
                self.put(item, rt.sel("setSubmenu:"), self.mirror(sub))
            else:
                self.put(item, rt.sel("setTarget:"), self.target)
                self.set_long(item, rt.sel("setTag:"), len(self.actions))
                self.actions.append(action)
            rt.set_bool(item, rt.sel("setEnabled:"), action.isEnabled())
            if action.isCheckable() and action.isChecked():
                self.set_long(item, rt.sel("setState:"), 1)  # NSControlStateValueOn: a tick
            self.put(ns, rt.sel("addItem:"), item)
            empty = False
        return ns


_menus_made: _Menus | None = None


def _menus() -> _Menus | None:
    global _menus_made
    if _menus_made is None:
        rt = _rt()
        try:
            _menus_made = _Menus(rt) if rt else None
        except (AttributeError, OSError):
            return None
    return _menus_made


def menu_text(text: str) -> str:
    """A Qt menu item's text as macOS shows it: no & marking a mnemonic (&& is an &), no shortcut after a tab."""
    return re.sub(r"&(.)", r"\1", text.split("\t")[0])


def edit_menu(paste: Callable[[], None]) -> bool:
    """An Edit menu with Paste (Cmd+V), which calls `paste`, so Cmd+V comes from a menu item, which macOS counts
    as you pasting, not to Qt as a key press. Chatmon has no menu bar, so it's never seen. Adds it again if the
    menu bar's been replaced. True if it's there."""
    menus = _menus()
    if menus is None:
        return False
    rt = menus.rt
    menus.on_paste = paste
    app = rt.obj(rt.cls("NSApplication"), rt.sel("sharedApplication"))
    bar = rt.obj(app, rt.sel("mainMenu")) if app else 0
    if not bar:
        return False
    if menus.edit:
        if menus.index(bar, rt.sel("indexOfItem:"), menus.edit) >= 0:
            return True
        rt.obj(menus.edit, rt.sel("release"))  # the one that was in the menu bar before it was made again
    edit = menus.new_menu("Edit")
    item = menus.new_item("Paste", "paste:", "v")  # with Command, a key equivalent's own
    menus.put(item, rt.sel("setTarget:"), menus.target)
    menus.put(edit, rt.sel("addItem:"), item)
    holder = menus.new_item("Edit", None)
    menus.put(holder, rt.sel("setSubmenu:"), edit)
    menus.put(bar, rt.sel("addItem:"), holder)
    menus.edit = rt.obj(holder, rt.sel("retain"))  # kept, to look for it in the menu bar next time
    return True


def popup(menu, pos, opener) -> bool:
    """Show the QMenu as a native menu with its top left at `pos` (a QPoint on screen), until an item's chosen
    or it's closed; `opener` is the widget clicked to open it. A chosen item triggers its QAction from the
    native item's own action, so a paste there is yours to macOS. False if it couldn't be shown (Qt can show it
    instead)."""
    from PyQt6.QtGui import QGuiApplication

    menus, screen = _menus(), QGuiApplication.primaryScreen()
    if menus is None or screen is None:
        return False
    rt = menus.rt
    menus.actions = []
    ns = menus.mirror(menu)
    # Cocoa's screen coordinates go up from the bottom of the main screen, which is Qt's primary one.
    at = _Point(pos.x(), screen.geometry().height() - pos.y())
    try:  # the chosen item's action is sent before this returns
        menus.pop(ns, rt.sel("popUpMenuPositioningItem:atLocation:inView:"), None, at, None)
    finally:
        menus.actions = []
        # The menu kept the mouse events while it was open, so Qt's view of the opener's window still has the
        # button down, and takes no more clicks: let it go, as Qt does after a native menu of its own
        # (QCocoaMenu::showPopup).
        view = int(opener.window().winId())
        if view and rt.responds(view, rt.sel("respondsToSelector:"), rt.sel("resetMouseButtons")):
            rt.obj(view, rt.sel("resetMouseButtons"))
    return True
