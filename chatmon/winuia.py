"""Windows: have the screen reader say something through UI Automation's notification event, which Narrator, NVDA
and JAWS read: UiaRaiseNotificationEvent, Windows 10 1709 and later.
https://learn.microsoft.com/en-us/windows/win32/api/uiautomationcoreapi/nf-uiautomationcoreapi-uiaraisenotificationevent

What UI Automation passes on, as checked on Windows 11 with a UI Automation client listening: an event raised from a
provider of the app's own (IRawElementProviderSimple, here in ctypes) that says it's server-side, on a window that's
been shown a moment. One raised on UiaHostProviderFromHwnd's provider, from a provider that says it's client-side,
on a window that hands out another provider (a Qt window with a line edit in it), or right after the window is
shown, is dropped without a word. So the notifications come from a window of their own (one pixel, see-through,
never taking a click or the keyboard) that hands out this provider itself, for WM_GETOBJECT, whatever Qt would
answer for it. (Qt's
QAccessibleAnnouncementEvent does all this for Qt's own windows, but no PyQt6 has a binding for it.)

NVDA reads a notification only from the app in front (event_UIA_notification in its NVDAObjects/UIA), so
`in_front()` says whether Chatmon is, and the caller has another way to say it while it isn't.
Imported on Windows alone.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import time
import uuid
from ctypes import wintypes

from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication, Qt
from PyQt6.QtGui import QGuiApplication

from .i18n import N_, _

logger = logging.getLogger(__name__)

WM_GETOBJECT = 0x003D
UIA_ROOT_OBJECT_ID = -25  # UiaRootObjectId: WM_GETOBJECT's lParam when UI Automation asks for a window's provider
SERVER_SIDE_PROVIDER = 0x1 << 1  # ProviderOptions_ServerSideProvider: the app's own (client-side ones are dropped)
UIA_NAME = 30005  # UIA_NamePropertyId; every other property is the window's own (its host provider's)
NOTIFICATION_KIND_OTHER = 4  # NotificationKind_Other
IMPORTANT_ALL, ALL = 0, 2  # NotificationProcessing: an important one is said even over others
VT_EMPTY, VT_BSTR = 0, 8
S_OK, E_NOINTERFACE = 0, -2147467262  # 0x80004002
IID_IUNKNOWN = uuid.UUID("00000000-0000-0000-c000-000000000046")
IID_IRAW_ELEMENT_PROVIDER_SIMPLE = uuid.UUID("d6dd68d1-86fd-4332-8666-9abedea2d24c")
NAME = N_("Chatmon announcements")  # what a screen reader exploring the desktop finds the window called
READY_AFTER = 3.0  # seconds from showing the window to its first notification: UI Automation loses one raised at once


# Windows' calling convention; CFUNCTYPE elsewhere only so the module imports on every OS (nothing here runs there).
_FUNCTYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)


class _Value(ctypes.Union):
    _fields_ = [("bstrVal", ctypes.c_void_p), ("record", ctypes.c_void_p * 2)]  # BRECORD, the widest member, sets the size


class VARIANT(ctypes.Structure):
    _fields_ = [("vt", ctypes.c_ushort), ("reserved1", ctypes.c_ushort), ("reserved2", ctypes.c_ushort), ("reserved3", ctypes.c_ushort),
                ("value", _Value)]


_QueryInterface = _FUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
_Count = _FUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)  # AddRef, Release
_Options = _FUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int))
_Pattern = _FUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))
_Property = _FUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(VARIANT))
_Host = _FUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))


class _Vtable(ctypes.Structure):
    _fields_ = [("QueryInterface", _QueryInterface), ("AddRef", _Count), ("Release", _Count), ("get_ProviderOptions", _Options),
                ("GetPatternProvider", _Pattern), ("GetPropertyValue", _Property), ("get_HostRawElementProvider", _Host)]


class _Object(ctypes.Structure):
    _fields_ = [("vtable", ctypes.POINTER(_Vtable))]


def _libraries():
    uia = ctypes.WinDLL("uiautomationcore")
    uia.UiaHostProviderFromHwnd.restype = ctypes.c_long
    uia.UiaHostProviderFromHwnd.argtypes = [wintypes.HWND, ctypes.POINTER(ctypes.c_void_p)]
    uia.UiaReturnRawElementProvider.restype = ctypes.c_ssize_t
    uia.UiaReturnRawElementProvider.argtypes = [wintypes.HWND, wintypes.WPARAM, wintypes.LPARAM, ctypes.c_void_p]
    uia.UiaClientsAreListening.restype = wintypes.BOOL
    uia.UiaRaiseNotificationEvent.restype = ctypes.c_long  # AttributeError before Windows 10 1709
    uia.UiaRaiseNotificationEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
    oleaut = ctypes.WinDLL("oleaut32")
    oleaut.SysAllocString.restype = ctypes.c_void_p
    oleaut.SysAllocString.argtypes = [wintypes.LPCWSTR]
    oleaut.SysFreeString.argtypes = [ctypes.c_void_p]
    return uia, oleaut


class Provider:
    """The announcer window's UI Automation provider: a COM object (IRawElementProviderSimple) made in ctypes. It
    names itself and has the window's own host provider for everything else. UI Automation calls it from threads
    of its own; it only ever answers with constants. Kept for the life of the process: COM may hold it to the end."""

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self.refs = 1
        self._uia, self._oleaut = _libraries()
        self._vtable = _Vtable(_QueryInterface(self._query_interface), _Count(self._add_ref), _Count(self._release),
                               _Options(self._options), _Pattern(self._pattern), _Property(self._property), _Host(self._host))
        self._object = _Object(ctypes.pointer(self._vtable))
        self.pointer = ctypes.addressof(self._object)

    def _query_interface(self, this, iid, out) -> int:
        asked = uuid.UUID(bytes_le=ctypes.string_at(iid, 16))
        if asked in (IID_IUNKNOWN, IID_IRAW_ELEMENT_PROVIDER_SIMPLE):
            out[0] = self.pointer
            self.refs += 1
            return S_OK
        out[0] = None
        return E_NOINTERFACE

    def _add_ref(self, this) -> int:
        self.refs += 1
        return self.refs

    def _release(self, this) -> int:
        self.refs = max(1, self.refs - 1)  # never freed: Python keeps it
        return self.refs

    def _options(self, this, out) -> int:
        out[0] = SERVER_SIDE_PROVIDER
        return S_OK

    def _pattern(self, this, pattern, out) -> int:
        out[0] = None  # no control patterns: nothing to click or read in it
        return S_OK

    def _property(self, this, prop, out) -> int:
        value = out.contents
        value.vt = VT_EMPTY
        if prop == UIA_NAME:
            value.vt, value.value.bstrVal = VT_BSTR, self._oleaut.SysAllocString(_(NAME))  # the caller frees it
        return S_OK

    def _host(self, this, out) -> int:
        return self._uia.UiaHostProviderFromHwnd(self.hwnd, out)


class Announcer(QAbstractNativeEventFilter):
    """The window notifications come from, and its provider, handed out for WM_GETOBJECT by a native event filter
    put in place before the window is first shown (UI Automation asks then)."""

    def __init__(self):
        super().__init__()
        from PyQt6.QtWidgets import QWidget

        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowTransparentForInput
                 | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.window = QWidget(None, flags)
        self.window.setWindowTitle("Chatmon")
        self.window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # nothing drawn: nothing seen
        self.window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        screen = QGuiApplication.primaryScreen().geometry()
        self.window.setGeometry(screen.x(), screen.y(), 1, 1)
        self.hwnd = int(self.window.winId())
        self.provider = Provider(self.hwnd)
        self._uia, self._oleaut = self.provider._uia, self.provider._oleaut
        QCoreApplication.instance().installNativeEventFilter(self)
        self.window.show()
        self.shown_at = time.monotonic()

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG" and message:
            msg = wintypes.MSG.from_address(int(message))
            if msg.hWnd == self.hwnd and msg.message == WM_GETOBJECT and (msg.lParam or 0) & 0xFFFFFFFF == UIA_ROOT_OBJECT_ID & 0xFFFFFFFF:
                return True, self._uia.UiaReturnRawElementProvider(self.hwnd, msg.wParam, msg.lParam, self.provider.pointer)
        return False, 0

    def say(self, text: str, important: bool = False) -> bool:
        """Raise the notification; False if no UI Automation client (no screen reader) is listening, the window is
        too new for UI Automation to have taken it in yet, or it failed."""
        if time.monotonic() - self.shown_at < READY_AFTER or not self._uia.UiaClientsAreListening():
            return False
        words, activity = self._oleaut.SysAllocString(text), self._oleaut.SysAllocString("chatmon.announcement")
        try:
            result = self._uia.UiaRaiseNotificationEvent(self.provider.pointer, NOTIFICATION_KIND_OTHER,
                                                         IMPORTANT_ALL if important else ALL, words, activity)
        finally:
            self._oleaut.SysFreeString(words)
            self._oleaut.SysFreeString(activity)
        return result == S_OK


_announcer: Announcer | None = None
_unavailable = False


def prepare() -> bool:
    """Make the announcer's window now, so it's ready by the time something is to be said (a screen reader was
    found). False if UI Automation notifications can't be had here: Qt's offscreen platform (no real windows), or
    a Windows before 1709."""
    global _announcer, _unavailable
    if _announcer is None and not _unavailable:
        if QGuiApplication.platformName() != "windows":
            _unavailable = True
        else:
            try:
                _announcer = Announcer()
            except (AttributeError, OSError) as exc:
                logger.debug("UI Automation's notifications can't be had: %s", exc)
                _unavailable = True
    return _announcer is not None


def say(text: str, important: bool = False) -> bool:
    """Have the screen reader say `text` through UI Automation; False if it can't be done now (see `prepare` and
    Announcer.say), and the caller says it another way."""
    prepare()
    return _announcer is not None and _announcer.say(text, important)


def in_front() -> bool:
    """Whether the window in front is one of Chatmon's (its ask box, its menu): then Chatmon is the app in front."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
        front = user32.GetForegroundWindow()
        if not front:
            return False
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(front, ctypes.byref(pid))
        return pid.value == os.getpid()
    except (AttributeError, OSError) as exc:
        logger.debug("couldn't tell which app is in front: %s", exc)
        return False
