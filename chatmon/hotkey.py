"""A global shortcut: one key combination that reaches Chatmon from any app, to open the ask box.

A shortcut is written the way Qt writes one (QKeySequence's PortableText, what QKeySequenceEdit gives):
"Ctrl+Alt+Space", "Meta+Shift+F5". As in Qt, on macOS "Ctrl" is the Command key and "Meta" the Control key, so a
shortcut recorded there means the keys that were pressed. Each platform has its own way to claim it:

- Windows: RegisterHotKey, on a message-only window of its own, heard through a native event filter.
- macOS: Carbon's RegisterEventHotKey, which needs no Accessibility permission.
- X11: XGrabKey on the root window, over an X connection of its own.
- Wayland: the GlobalShortcuts portal, where the desktop has one (KDE Plasma, GNOME 48 and later, Hyprland). The
  desktop may ask you first, and has the last word on the keys: `bound` says what it chose.

A shortcut another app holds is reported, never taken. Imports anywhere; each platform's library is loaded only
when a shortcut is set there.
https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey
https://www.x.org/releases/current/doc/man/man3/XGrabKey.3.xhtml
https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html
https://specifications.freedesktop.org/shortcuts/latest/"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from collections.abc import Callable, Mapping
from typing import ClassVar, NamedTuple, Protocol

from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, QSocketNotifier, Qt, pyqtSignal

from .i18n import N_, _

# Windows' DLLs and last error; CDLL and errno elsewhere only so the module imports on every OS (the Windows backend
# is made on Windows alone).
_WinDLL = getattr(ctypes, "WinDLL", ctypes.CDLL)
_get_last_error = getattr(ctypes, "get_last_error", ctypes.get_errno)

MODIFIERS = ("ctrl", "alt", "shift", "meta")  # Qt's ControlModifier, AltModifier, ShiftModifier, MetaModifier
MODIFIER_NAMES = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "meta": "Meta"}
MODIFIER_ALIASES = {"ctrl": "ctrl", "control": "ctrl", "ctl": "ctrl", "alt": "alt", "option": "alt", "opt": "alt",
                    "shift": "shift", "meta": "meta", "win": "meta", "windows": "meta", "super": "meta", "logo": "meta"}
COMMAND = ("cmd", "command")  # the Command key: Qt's Ctrl on macOS, and the key in its place (Meta) elsewhere


class Key(NamedTuple):
    """One key: its Windows virtual-key code, its macOS virtual key code (None: Macs have no such key) and its X
    keysym name, which the XDG shortcuts format uses too."""

    windows: int
    mac: int | None
    x11: str


# Named keys, by Qt's PortableText name.
NAMED = {
    "Space": Key(0x20, 0x31, "space"), "Return": Key(0x0D, 0x24, "Return"), "Tab": Key(0x09, 0x30, "Tab"),
    "Esc": Key(0x1B, 0x35, "Escape"), "Backspace": Key(0x08, 0x33, "BackSpace"), "Ins": Key(0x2D, 0x72, "Insert"),
    "Del": Key(0x2E, 0x75, "Delete"), "Home": Key(0x24, 0x73, "Home"), "End": Key(0x23, 0x77, "End"),
    "PgUp": Key(0x21, 0x74, "Prior"), "PgDown": Key(0x22, 0x79, "Next"), "Left": Key(0x25, 0x7B, "Left"),
    "Right": Key(0x27, 0x7C, "Right"), "Up": Key(0x26, 0x7E, "Up"), "Down": Key(0x28, 0x7D, "Down"),
    "Pause": Key(0x13, None, "Pause"), "Print": Key(0x2C, None, "Print"),
}
KEY_ALIASES = {"enter": "Return", "escape": "Esc", "insert": "Ins", "delete": "Del", "pageup": "PgUp", "page up": "PgUp",
               "pagedown": "PgDown", "page down": "PgDown", "spacebar": "Space", "printscreen": "Print"}
# The punctuation keys of a US layout, by the character on them.
PUNCTUATION = {
    "`": Key(0xC0, 0x32, "grave"), "-": Key(0xBD, 0x1B, "minus"), "=": Key(0xBB, 0x18, "equal"),
    "[": Key(0xDB, 0x21, "bracketleft"), "]": Key(0xDD, 0x1E, "bracketright"), "\\": Key(0xDC, 0x2A, "backslash"),
    ";": Key(0xBA, 0x29, "semicolon"), "'": Key(0xDE, 0x27, "apostrophe"), ",": Key(0xBC, 0x2B, "comma"),
    ".": Key(0xBE, 0x2F, "period"), "/": Key(0xBF, 0x2C, "slash"),
}
# macOS's virtual key codes for letters and digits (kVK_ANSI_*), and for F1 to F20 (kVK_F*).
_MAC_LETTERS = dict(zip("ASDFHGZXCVBQWERYT123465", [*range(0x09 + 1), *range(0x0B, 0x17 + 1)], strict=True))
_MAC_LETTERS.update({"9": 0x19, "7": 0x1A, "8": 0x1C, "0": 0x1D, "O": 0x1F, "U": 0x20, "I": 0x22, "P": 0x23, "L": 0x25,
                     "J": 0x26, "K": 0x28, "N": 0x2D, "M": 0x2E})
_MAC_F = [0x7A, 0x78, 0x63, 0x76, 0x60, 0x61, 0x62, 0x64, 0x65, 0x6D, 0x67, 0x6F, 0x69, 0x6B, 0x71, 0x6A, 0x40, 0x4F, 0x50, 0x5A]
KEYS: dict[str, Key] = {**NAMED, **PUNCTUATION}
KEYS.update({c: Key(ord(c), _MAC_LETTERS[c], c.lower()) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"})
KEYS.update({f"F{n}": Key(0x70 + n - 1, _MAC_F[n - 1] if n <= len(_MAC_F) else None, f"F{n}") for n in range(1, 25)})
ALONE = {f"F{n}" for n in range(13, 25)}  # keys no app types with, which may be a shortcut by themselves

# Shown translated: _(CONFLICT).format(combo=...), _(NO_PORTAL).
CONFLICT = N_("{combo} is already used by another app. Pick another shortcut.")
# Translators: "chatmon ask" is a command to type, as it is.
NO_PORTAL = N_("This desktop doesn't let apps have shortcuts of their own (it has no GlobalShortcuts portal). You can set "
               "one in your desktop's keyboard settings that runs: chatmon ask")


class Combo(NamedTuple):
    modifiers: frozenset
    key: str

    def text(self) -> str:
        """As Qt would write it: "Ctrl+Alt+Space"."""
        return "+".join([MODIFIER_NAMES[m] for m in MODIFIERS if m in self.modifiers] + [self.key])


def _key_name(part: str) -> str | None:
    if part in PUNCTUATION:
        return part
    low = part.lower()
    if low in KEY_ALIASES:
        return KEY_ALIASES[low]
    for name in KEYS:
        if name.lower() == low:
            return name
    return None


def parse(sequence: str, platform: str = sys.platform) -> Combo:
    """The combination a shortcut names; ValueError, with a sentence to show, if it names none Chatmon can set."""
    text = (sequence or "").strip()
    if not text:
        # Translators: key names in a shortcut are written in English, as Chatmon reads them: Ctrl+Alt+Space.
        raise ValueError(_("A shortcut needs a key, such as Ctrl+Alt+Space."))
    parts = [p.strip() for p in text.split("+")]
    if not all(parts):
        raise ValueError(_('"{shortcut}" isn\'t a shortcut: write it like Ctrl+Alt+Space.').format(shortcut=text))
    modifiers: set[str] = set()
    key = None
    for part in parts:
        low = part.lower()
        if low in COMMAND:
            modifiers.add("ctrl" if platform == "darwin" else "meta")
            continue
        if low in MODIFIER_ALIASES:
            modifiers.add(MODIFIER_ALIASES[low])
            continue
        name = _key_name(part)
        if name is None:
            raise ValueError(_('Chatmon doesn\'t know the key "{key}".').format(key=part))
        if key is not None:
            raise ValueError(_("A shortcut has one key, not {key} and {other}.").format(key=key, other=name))
        key = name
    if key is None:
        raise ValueError(_('"{shortcut}" needs a key as well, such as Space.').format(shortcut=text))
    combo = Combo(frozenset(modifiers), key)
    if not modifiers & {"ctrl", "alt", "meta"} and key not in ALONE:
        raise ValueError(_("{shortcut} would take that key from every app you type in: add Ctrl, Alt or Meta.").format(shortcut=combo.text()))
    return combo


# -- Windows


class _Windows(QAbstractNativeEventFilter):
    """RegisterHotKey on a message-only window (never shown, never in any list of windows): WM_HOTKEY reaches it
    through Qt's event loop, where a native event filter hears it."""

    WM_HOTKEY = 0x0312
    FLAGS: ClassVar[dict[str, int]] = {"alt": 0x1, "ctrl": 0x2, "shift": 0x4, "meta": 0x8}  # MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN
    MOD_NOREPEAT = 0x4000  # held down, it's pressed once
    ERROR_HOTKEY_ALREADY_REGISTERED = 1409
    HWND_MESSAGE = -3

    def __init__(self, pressed: Callable[[], None]):
        super().__init__()
        from ctypes import wintypes

        user32 = _WinDLL("user32", use_last_error=True)
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self._user32, self._msg = user32, wintypes.MSG
        self._pressed = pressed
        # A system class: no window procedure of Chatmon's own to keep alive.
        self.hwnd = user32.CreateWindowExW(0, "STATIC", "Chatmon shortcut", 0, 0, 0, 0, 0, wintypes.HWND(self.HWND_MESSAGE), None, None, None)
        if not self.hwnd:
            raise OSError(_get_last_error(), _("Windows wouldn't make the shortcut's window"))
        self.id: int | None = None  # the registration in force
        app: QCoreApplication | None = QCoreApplication.instance()  # typed: PyQt6 6.12's stub says an unbound Self
        if app is not None:  # there is one: shortcuts are set from Qt's event loop
            app.installNativeEventFilter(self)

    def grab(self, combo: Combo) -> str | None:
        flags = sum(self.FLAGS[m] for m in combo.modifiers) | self.MOD_NOREPEAT
        new_id = 2 if self.id == 1 else 1  # the old one stays until the new one is in
        if not self._user32.RegisterHotKey(self.hwnd, new_id, flags, KEYS[combo.key].windows):
            error = _get_last_error()
            if error == self.ERROR_HOTKEY_ALREADY_REGISTERED:
                return _(CONFLICT).format(combo=combo.text())
            return _("Windows wouldn't set up {shortcut} (error {error}).").format(shortcut=combo.text(), error=error)
        self.release()
        self.id = new_id
        return None

    def release(self) -> None:
        if self.id is not None:
            self._user32.UnregisterHotKey(self.hwnd, self.id)
            self.id = None

    def nativeEventFilter(self, event_type, message):
        if message and bytes(event_type) == b"windows_generic_MSG":
            msg = self._msg.from_address(int(message))
            if msg.hWnd == self.hwnd and msg.message == self.WM_HOTKEY:
                if self.id is not None and msg.wParam == self.id:
                    self._pressed()
                return True, 0  # the shortcut's window's own: nobody else's business
        return False, 0

    def close(self) -> None:
        self.release()
        app: QCoreApplication | None = QCoreApplication.instance()
        if app is not None:  # gone only if Qt was shut down first
            app.removeNativeEventFilter(self)
        if self.hwnd:
            self._user32.DestroyWindow(self.hwnd)
            self.hwnd = None


# -- macOS


def fourcc(code: str) -> int:
    return int.from_bytes(code.encode("ascii"), "big")


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


class _EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


class _Carbon:
    """Carbon's RegisterEventHotKey, with an event handler on the application's event target, which Qt's Cocoa
    event loop dispatches to. Exclusive, so a combination another app holds is refused rather than shared."""

    CARBON = "/System/Library/Frameworks/Carbon.framework/Carbon"
    FLAGS: ClassVar[dict[str, int]] = {"ctrl": 1 << 8, "shift": 1 << 9, "alt": 1 << 11, "meta": 1 << 12}  # cmdKey, shiftKey, optionKey, controlKey
    KEYBOARD, HOT_KEY_PRESSED = fourcc("keyb"), 5  # kEventClassKeyboard, kEventHotKeyPressed
    DIRECT_OBJECT, HOT_KEY_ID = fourcc("----"), fourcc("hkid")  # kEventParamDirectObject, typeEventHotKeyID
    SIGNATURE = fourcc("CHMN")
    EXCLUSIVE = 1 << 0  # kEventHotKeyExclusive
    HOT_KEY_EXISTS = -9878  # eventHotKeyExistsErr
    NOT_HANDLED = -9874  # eventNotHandledErr
    HANDLER = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

    def __init__(self, pressed: Callable[[], None]):
        carbon = ctypes.cdll.LoadLibrary(self.CARBON)
        carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
        carbon.GetApplicationEventTarget.argtypes = []
        carbon.InstallEventHandler.restype = ctypes.c_int32
        carbon.InstallEventHandler.argtypes = [ctypes.c_void_p, self.HANDLER, ctypes.c_ulong, ctypes.POINTER(_EventTypeSpec), ctypes.c_void_p,
                                               ctypes.POINTER(ctypes.c_void_p)]
        carbon.RemoveEventHandler.restype = ctypes.c_int32
        carbon.RemoveEventHandler.argtypes = [ctypes.c_void_p]
        carbon.RegisterEventHotKey.restype = ctypes.c_int32
        carbon.RegisterEventHotKey.argtypes = [ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID, ctypes.c_void_p, ctypes.c_uint32,
                                               ctypes.POINTER(ctypes.c_void_p)]
        carbon.UnregisterEventHotKey.restype = ctypes.c_int32
        carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
        carbon.GetEventParameter.restype = ctypes.c_int32
        carbon.GetEventParameter.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
                                             ctypes.POINTER(_EventHotKeyID)]
        self._carbon, self._pressed = carbon, pressed
        self.target = carbon.GetApplicationEventTarget()
        self._handler = self.HANDLER(self._on_event)  # kept: Carbon holds only its address
        self._handler_ref = ctypes.c_void_p()
        spec = _EventTypeSpec(self.KEYBOARD, self.HOT_KEY_PRESSED)
        status = carbon.InstallEventHandler(self.target, self._handler, 1, ctypes.byref(spec), None, ctypes.byref(self._handler_ref))
        if status != 0:
            raise OSError(status, _("Carbon wouldn't install the shortcut's handler"))
        self.id: int | None = None
        self._ref: int | None = None

    def grab(self, combo: Combo) -> str | None:
        code = KEYS[combo.key].mac
        if code is None:
            return _("Macs have no {key} key.").format(key=combo.key)
        new_id = 2 if self.id == 1 else 1
        ref = ctypes.c_void_p()
        status = self._carbon.RegisterEventHotKey(code, sum(self.FLAGS[m] for m in combo.modifiers), _EventHotKeyID(self.SIGNATURE, new_id),
                                                  self.target, self.EXCLUSIVE, ctypes.byref(ref))
        if status == self.HOT_KEY_EXISTS:
            return _(CONFLICT).format(combo=combo.text())
        if status != 0:
            return _("macOS wouldn't set up {shortcut} (error {error}).").format(shortcut=combo.text(), error=status)
        self.release()
        self.id, self._ref = new_id, ref.value
        return None

    def release(self) -> None:
        if self._ref:
            self._carbon.UnregisterEventHotKey(self._ref)
        self.id = self._ref = None

    def _on_event(self, next_handler, event, user_data) -> int:
        hot_key = _EventHotKeyID()
        found = self._carbon.GetEventParameter(event, self.DIRECT_OBJECT, self.HOT_KEY_ID, None, ctypes.sizeof(hot_key), None, ctypes.byref(hot_key))
        if found == 0 and hot_key.signature == self.SIGNATURE and self.id is not None and hot_key.id == self.id:
            self._pressed()
            return 0
        return self.NOT_HANDLED

    def close(self) -> None:
        self.release()
        if self._handler_ref.value:
            self._carbon.RemoveEventHandler(self._handler_ref)
            self._handler_ref = ctypes.c_void_p()


# -- X11


class _XKeyEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int), ("display", ctypes.c_void_p),
                ("window", ctypes.c_ulong), ("root", ctypes.c_ulong), ("subwindow", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("x", ctypes.c_int), ("y", ctypes.c_int), ("x_root", ctypes.c_int), ("y_root", ctypes.c_int),
                ("state", ctypes.c_uint), ("keycode", ctypes.c_uint), ("same_screen", ctypes.c_int)]


class _XErrorEvent(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("display", ctypes.c_void_p), ("resourceid", ctypes.c_ulong), ("serial", ctypes.c_ulong),
                ("error_code", ctypes.c_ubyte), ("request_code", ctypes.c_ubyte), ("minor_code", ctypes.c_ubyte)]


_X_ERROR_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(_XErrorEvent))


class _X11:
    """XGrabKey on the root window over an X connection of Chatmon's own, read when a QSocketNotifier says it has
    something. A grab is made for each state of NumLock and CapsLock, which X counts as modifiers."""

    FLAGS: ClassVar[dict[str, int]] = {"shift": 1 << 0, "ctrl": 1 << 2, "alt": 1 << 3, "meta": 1 << 6}  # ShiftMask, ControlMask, Mod1Mask, Mod4Mask
    LOCK, NUM_LOCK = 1 << 1, 1 << 4  # LockMask, Mod2Mask
    LOCKS = (0, LOCK, NUM_LOCK, LOCK | NUM_LOCK)
    KEY_PRESS = 2
    BAD_ACCESS = 10  # another client holds the grab
    GRAB_MODE_ASYNC = 1

    def __init__(self, pressed: Callable[[], None], display: str | None = None):
        xlib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11") or "libX11.so.6")
        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        xlib.XDefaultRootWindow.restype = ctypes.c_ulong
        xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        xlib.XConnectionNumber.argtypes = [ctypes.c_void_p]
        xlib.XStringToKeysym.restype = ctypes.c_ulong
        xlib.XStringToKeysym.argtypes = [ctypes.c_char_p]
        xlib.XKeysymToKeycode.restype = ctypes.c_ubyte
        xlib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        xlib.XGrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        xlib.XUngrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong]
        xlib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        xlib.XPending.argtypes = [ctypes.c_void_p]
        xlib.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        xlib.XSetErrorHandler.restype = ctypes.c_void_p
        xlib.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self._x, self._pressed = xlib, pressed
        self.display = xlib.XOpenDisplay(display.encode() if display else None)
        if not self.display:
            raise OSError(_("There's no X display to set a shortcut on."))
        self.root = xlib.XDefaultRootWindow(self.display)
        self.grabbed: tuple[int, int] | None = None  # (keycode, modifiers) in force
        self._event = (ctypes.c_long * 24)()  # an XEvent: a union of 24 longs
        self._notifier = QSocketNotifier(xlib.XConnectionNumber(self.display), QSocketNotifier.Type.Read)
        self._notifier.activated.connect(self._read)

    def _grab_all(self, keycode: int, modifiers: int) -> list[int]:
        """Grab every lock state; the X errors that came back (BadAccess: someone else has it)."""
        errors: list[int] = []

        def heard(display, error) -> int:
            if display == self.display:
                errors.append(error.contents.error_code)
            return 0

        handler = _X_ERROR_HANDLER(heard)
        previous = self._x.XSetErrorHandler(ctypes.cast(handler, ctypes.c_void_p))
        try:
            for lock in self.LOCKS:
                self._x.XGrabKey(self.display, keycode, modifiers | lock, self.root, 0, self.GRAB_MODE_ASYNC, self.GRAB_MODE_ASYNC)
            self._x.XSync(self.display, 0)  # the errors arrive now, while this handler hears them
        finally:
            self._x.XSetErrorHandler(previous)
        return errors

    def _ungrab_all(self, keycode: int, modifiers: int) -> None:
        for lock in self.LOCKS:
            self._x.XUngrabKey(self.display, keycode, modifiers | lock, self.root)
        self._x.XSync(self.display, 0)

    def grab(self, combo: Combo) -> str | None:
        keycode = self._x.XKeysymToKeycode(self.display, self._x.XStringToKeysym(KEYS[combo.key].x11.encode()))
        if not keycode:
            return _("This keyboard has no {key} key.").format(key=combo.key)
        modifiers = sum(self.FLAGS[m] for m in combo.modifiers)
        if (keycode, modifiers) == self.grabbed:
            return None
        errors = self._grab_all(keycode, modifiers)
        if errors:
            self._ungrab_all(keycode, modifiers)  # whichever of the lock states it did get
            if self.BAD_ACCESS in errors:
                return _(CONFLICT).format(combo=combo.text())
            return _("X wouldn't set up {shortcut} (error {error}).").format(shortcut=combo.text(), error=errors[0])
        self.release()
        self.grabbed = (keycode, modifiers)
        return None

    def release(self) -> None:
        if self.grabbed is not None:
            self._ungrab_all(*self.grabbed)
            self.grabbed = None

    def _read(self) -> None:
        while self.display and self._x.XPending(self.display):
            self._x.XNextEvent(self.display, self._event)
            key = _XKeyEvent.from_buffer(self._event)
            if key.type == self.KEY_PRESS and self.grabbed == (key.keycode, key.state & ~(self.LOCK | self.NUM_LOCK)):
                self._pressed()

    def close(self) -> None:
        self.release()
        self._notifier.setEnabled(False)
        self._notifier.deleteLater()
        if self.display:
            self._x.XCloseDisplay(self.display)
            self.display = None


# -- choosing, and the shortcut itself


def backend_kind(platform: str = sys.platform, env: Mapping[str, str] | None = None) -> str | None:
    """Which way to set a shortcut here: "windows", "carbon", "portal" (any Wayland session: an X grab there only
    hears keys while an X app has focus), "x11", or None where there's no display at all."""
    env = os.environ if env is None else env
    if platform == "win32":
        return "windows"
    if platform == "darwin":
        return "carbon"
    if env.get("WAYLAND_DISPLAY"):
        return "portal"
    if env.get("DISPLAY"):
        return "x11"
    return None


class _Backend(Protocol):
    """What each platform's way of claiming a shortcut does."""

    def grab(self, combo: Combo) -> str | None: ...
    def release(self) -> None: ...
    def close(self) -> None: ...


class Hotkey(QObject):
    """One global shortcut. `pressed` when it's pressed; `failed(sentence)` when a desktop turns it down after
    register() returned (the portal asks the user); `bound(description)` with how to press it, in the desktop's
    own words where it has them. All on the Qt thread."""

    pressed = pyqtSignal()
    failed = pyqtSignal(str)
    bound = pyqtSignal(str)
    _heard = pyqtSignal(str, str)  # (what, detail), from any thread to this object's

    def __init__(self, kind: str | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.kind = kind if kind is not None else backend_kind()
        self.combo: Combo | None = None
        self.on_pressed: Callable[[], None] | None = None
        self.on_failed: Callable[[str], None] | None = None
        self._backend: _Backend | None = None
        # Queued even from this thread: never inside another library's event dispatch (Carbon's, Windows').
        self._heard.connect(self._hear, Qt.ConnectionType.QueuedConnection)  # type: ignore[call-arg]  # PyQt6 6.11's stub leaves out connect's type, which it takes

    def _tell(self, what: str = "pressed", detail: str = "") -> None:
        """What a backend heard, from whichever thread it heard it on."""
        self._heard.emit(what, detail)

    def _make_backend(self) -> _Backend:
        tell = self._tell
        if self.kind == "windows":
            return _Windows(tell)
        if self.kind == "carbon":
            return _Carbon(tell)
        if self.kind == "x11":
            return _X11(tell)
        if self.kind == "portal":
            from .shortcutportal import PortalShortcut

            return PortalShortcut(tell)
        raise OSError(_("There's no display to set a shortcut on."))

    def register(self, sequence: str) -> str | None:
        """Claim the shortcut, in place of any this one had; a sentence saying why it couldn't, or None. A failed
        change keeps the shortcut already set."""
        try:
            combo = parse(sequence)
        except ValueError as exc:
            return str(exc)
        if combo == self.combo:
            return None
        try:
            if self._backend is None:
                self._backend = self._make_backend()
            error = self._backend.grab(combo)
        except (AttributeError, OSError) as exc:  # the platform's library isn't there, or refused outright
            return getattr(exc, "strerror", None) or str(exc) or _("Shortcuts can't be set here.")
        if error is None:
            self.combo = combo
            if self.kind != "portal":  # the portal says what the desktop chose, once it has
                self.bound.emit(combo.text())
        return error

    def unregister(self) -> None:
        if self._backend is not None:
            self._backend.release()
        self.combo = None

    def _hear(self, what: str, detail: str) -> None:
        if what == "pressed" and self.combo is not None:
            self.pressed.emit()
            if self.on_pressed is not None:
                self.on_pressed()
        elif what == "failed":
            self.combo = None
            self.failed.emit(detail)
            if self.on_failed is not None:
                self.on_failed(detail)
        elif what == "bound":
            self.bound.emit(detail)

    def close(self) -> None:
        self.unregister()
        if self._backend is not None:
            self._backend.close()
            self._backend = None


_hotkey: Hotkey | None = None


def register(sequence: str, callback: Callable[[], None], failed: Callable[[str], None] | None = None) -> str | None:
    """The app's one shortcut: `callback()` runs on the Qt thread when it's pressed. A sentence saying why it
    couldn't be set, or None; `failed(sentence)` hears a refusal that comes later (a desktop asking first)."""
    global _hotkey
    if _hotkey is None:
        _hotkey = Hotkey()
    _hotkey.on_pressed, _hotkey.on_failed = callback, failed
    return _hotkey.register(sequence)


def unregister() -> None:
    if _hotkey is not None:
        _hotkey.unregister()


def current() -> str | None:
    """The shortcut in force, as Qt would write it, or None."""
    return _hotkey.combo.text() if _hotkey is not None and _hotkey.combo is not None else None
