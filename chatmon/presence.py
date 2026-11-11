"""Whether you're there, and whether now is a time to keep quiet: each platform's own documented way.

- How long since you last touched the keyboard or mouse (away from the desk counts toward a break):
  Windows GetLastInputInfo; macOS CGEventSourceSecondsSinceLastEventType; on Linux, the Wayland overlay's
  ext-idle-notify-v1 (told to us by layer.py), GNOME's IdleMonitor, or X11's XScreenSaver extension.
- Whether to hold bubbles back: a full-screen app or a presentation (Windows SHQueryUserNotificationState,
  and a full-screen window in front on the chatmon's monitor), quiet hours, or Do Not Disturb (KDE's
  notification server, GNOME's show-banners). On the Wayland overlay and on macOS the system itself keeps
  the chatmon out of a full-screen app's way.
- Reduced motion and high contrast, which the chatmon follows unless you chose otherwise.

Every reading is best effort: one that can't be had says None (don't know), never raises.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import shutil
import subprocess
import sys
import time

AWAY_AFTER = 300  # seconds without input: away from the desk


# -- Windows


def _win_idle() -> float | None:
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint32)]

    try:
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        kernel32.GetTickCount.restype = ctypes.c_uint32
        return ((kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0  # ticks wrap every 49.7 days
    except (AttributeError, OSError):
        return None


# SHQueryUserNotificationState: https://learn.microsoft.com/en-us/windows/win32/api/shellapi/ne-shellapi-query_user_notification_state
_QUNS = {2: "a full-screen app", 3: "a full-screen game", 4: "a presentation", 6: "quiet hours", 7: "a full-screen app"}


def _win_quiet() -> str | None:
    try:
        state = ctypes.c_int(0)
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
            return None
        return _QUNS.get(state.value)
    except (AttributeError, OSError):
        return None


def _win_covered(stage_window: int) -> bool:
    """Is a full-screen window in front, on the chatmon's own monitor? (A video, a game, slides.)"""

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", ctypes.c_uint)]

    try:
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
        user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        front = user32.GetForegroundWindow()
        if not front or not stage_window:
            return False
        name = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(front, name, 64)
        if name.value in ("Progman", "WorkerW", "Shell_TrayWnd"):  # the desktop and the taskbar
            return False
        monitor = user32.MonitorFromWindow(front, 2)  # MONITOR_DEFAULTTONEAREST
        if monitor != user32.MonitorFromWindow(stage_window, 2):
            return False
        rect, info = RECT(), MONITORINFO(ctypes.sizeof(MONITORINFO))
        if not user32.GetWindowRect(front, ctypes.byref(rect)) or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False
        m = info.rcMonitor
        return rect.left <= m.left and rect.top <= m.top and rect.right >= m.right and rect.bottom >= m.bottom
    except (AttributeError, OSError):
        return False


_SPI_GETHIGHCONTRAST, _SPI_GETCLIENTAREAANIMATION, _SPI_GETMESSAGEDURATION = 0x42, 0x1042, 0x2016


def _win_setting(action: int) -> int | None:
    try:
        value = ctypes.c_uint(0)
        if not ctypes.windll.user32.SystemParametersInfoW(action, 0, ctypes.byref(value), 0):
            return None
        return value.value
    except (AttributeError, OSError):
        return None


def _win_high_contrast() -> bool | None:
    class HIGHCONTRASTW(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwFlags", ctypes.c_uint), ("lpszDefaultScheme", ctypes.c_wchar_p)]

    try:
        hc = HIGHCONTRASTW(ctypes.sizeof(HIGHCONTRASTW), 0, None)
        if not ctypes.windll.user32.SystemParametersInfoW(_SPI_GETHIGHCONTRAST, ctypes.sizeof(hc), ctypes.byref(hc), 0):
            return None
        return bool(hc.dwFlags & 1)  # HCF_HIGHCONTRASTON
    except (AttributeError, OSError):
        return None


# -- macOS (CoreGraphics, and AppKit through the Objective-C runtime: no PyObjC)


def _mac_idle() -> float | None:
    try:
        cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGEventSourceSecondsSinceLastEventType.restype = ctypes.c_double
        cg.CGEventSourceSecondsSinceLastEventType.argtypes = [ctypes.c_int32, ctypes.c_uint32]
        return float(cg.CGEventSourceSecondsSinceLastEventType(1, 0xFFFFFFFF))  # HID system state, any input
    except (AttributeError, OSError):
        return None


def _mac_reduce_motion() -> bool | None:
    """NSWorkspace.sharedWorkspace.accessibilityDisplayShouldReduceMotion."""
    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc") or "/usr/lib/libobjc.dylib")
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        send = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        obj = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)  # exact prototypes: arm64 needs them
        flag = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(send)
        workspace = obj(objc.objc_getClass(b"NSWorkspace"), objc.sel_registerName(b"sharedWorkspace"))
        if not workspace:
            return None
        return bool(flag(workspace, objc.sel_registerName(b"accessibilityDisplayShouldReduceMotion")))
    except (AttributeError, OSError, ValueError):
        return None


# -- Linux and the BSDs


def _dbus_call(bus, service: str, path: str, interface: str, method: str, *args):
    """One D-Bus call's first answer, or None (no such service, an error, or no answer within a moment)."""
    try:
        from PyQt6.QtDBus import QDBusInterface, QDBusMessage

        iface = QDBusInterface(service, path, interface, bus)
        if not iface.isValid():
            return None
        iface.setTimeout(500)
        reply = iface.call(method, *args)
        if reply.type() != QDBusMessage.MessageType.ReplyMessage or not reply.arguments():
            return None
        value = reply.arguments()[0]
        while hasattr(value, "variant"):  # QDBusVariant, as a property or a portal setting comes
            value = value.variant()
        return value
    except (ImportError, RuntimeError, TypeError):
        return None


def _session_bus():
    try:
        from PyQt6.QtDBus import QDBusConnection

        bus = QDBusConnection.sessionBus()
        return bus if bus.isConnected() else None
    except ImportError:
        return None


class _Xss(ctypes.Structure):
    _fields_ = [("window", ctypes.c_ulong), ("state", ctypes.c_int), ("kind", ctypes.c_int),
                ("til_or_since", ctypes.c_ulong), ("idle", ctypes.c_ulong), ("eventMask", ctypes.c_ulong)]


class _X11:
    """What the X server knows: idle time (the XScreenSaver extension) and whether the active window is
    full screen (_NET_WM_STATE_FULLSCREEN). Only for an X11 session: under XWayland, X sees X windows alone."""

    def __init__(self):
        self.ok = False
        try:
            self.x11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
            self.x11.XOpenDisplay.restype = ctypes.c_void_p
            self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            self.x11.XDefaultRootWindow.restype = ctypes.c_ulong
            self.x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
            self.x11.XInternAtom.restype = ctypes.c_ulong
            self.x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
            self.x11.XGetWindowProperty.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long, ctypes.c_int, ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p),
            ]
            self.x11.XFree.argtypes = [ctypes.c_void_p]
            self.display = self.x11.XOpenDisplay(None)
            if not self.display:
                return
            self.root = self.x11.XDefaultRootWindow(self.display)
            self.atoms = {name: self.x11.XInternAtom(self.display, name.encode(), 0)
                          for name in ("_NET_ACTIVE_WINDOW", "_NET_WM_STATE", "_NET_WM_STATE_FULLSCREEN")}
            self.ok = True
            self.xss = None
            path = ctypes.util.find_library("Xss")
            if path:
                xss = ctypes.CDLL(path)
                xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(_Xss)
                xss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_Xss)]
                self.xss, self.info = xss, xss.XScreenSaverAllocInfo()
        except (AttributeError, OSError):
            self.ok = False

    def _longs(self, window: int, prop: str) -> list[int]:
        kind, fmt, count, after, data = ctypes.c_ulong(), ctypes.c_int(), ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_void_p()
        if self.x11.XGetWindowProperty(self.display, window, self.atoms[prop], 0, 64, 0, 0, ctypes.byref(kind), ctypes.byref(fmt),
                                       ctypes.byref(count), ctypes.byref(after), ctypes.byref(data)) != 0 or not data.value:
            return []
        try:
            if fmt.value != 32:
                return []
            return list(ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))[: count.value])
        finally:
            self.x11.XFree(data)

    def idle(self) -> float | None:
        if not self.ok or self.xss is None or not self.xss.XScreenSaverQueryInfo(self.display, self.root, self.info):
            return None
        return self.info.contents.idle / 1000.0

    def fullscreen_in_front(self) -> bool:
        if not self.ok:
            return False
        active = self._longs(self.root, "_NET_ACTIVE_WINDOW")
        return bool(active and active[0]) and self.atoms["_NET_WM_STATE_FULLSCREEN"] in self._longs(active[0], "_NET_WM_STATE")


class Desk:
    """Readings of the person at the computer and their desktop's settings. One per app."""

    def __init__(self, platform: str = ""):
        self.platform = platform  # Qt's platform name: "xcb", "wayland", "windows", "cocoa"...
        self.overlay_idle_since: float | None = None  # told by the Wayland overlay (ext-idle-notify-v1)
        self._x11: _X11 | None = None
        self._desktop = (os.environ.get("XDG_CURRENT_DESKTOP") or "").lower()

    def _x(self) -> _X11 | None:
        if self.platform != "xcb" or os.environ.get("WAYLAND_DISPLAY"):  # XWayland sees X windows alone
            return None
        if self._x11 is None:
            self._x11 = _X11()
        return self._x11 if self._x11.ok else None

    def idle_seconds(self) -> float | None:
        """Seconds since the last keyboard or mouse input anywhere on the desktop; None if it can't be told."""
        if sys.platform == "win32":
            return _win_idle()
        if sys.platform == "darwin":
            return _mac_idle()
        if self.overlay_idle_since is not None:
            return max(AWAY_AFTER, time.monotonic() - self.overlay_idle_since + AWAY_AFTER)
        if "gnome" in self._desktop:
            bus = _session_bus()
            ms = _dbus_call(bus, "org.gnome.Mutter.IdleMonitor", "/org/gnome/Mutter/IdleMonitor/Core", "org.gnome.Mutter.IdleMonitor", "GetIdletime") if bus else None
            if isinstance(ms, int):
                return ms / 1000.0
        x = self._x()
        return x.idle() if x else None

    def quiet(self) -> str | None:
        """Why bubbles should wait (a full-screen app, a presentation, Do Not Disturb), or None."""
        if sys.platform == "win32":
            return _win_quiet()
        if sys.platform == "darwin":
            return None  # full-screen apps have their own Space, which the chatmon stays out of
        if "kde" in self._desktop:
            bus = _session_bus()
            if bus and _dbus_call(bus, "org.freedesktop.Notifications", "/org/freedesktop/Notifications",
                                  "org.freedesktop.DBus.Properties", "Get", "org.freedesktop.Notifications", "Inhibited") is True:
                return "Do Not Disturb"
        if "gnome" in self._desktop and shutil.which("gsettings"):
            try:
                out = subprocess.run(["gsettings", "get", "org.gnome.desktop.notifications", "show-banners"], capture_output=True, text=True, timeout=2)
                if out.stdout.strip() == "false":
                    return "Do Not Disturb"
            except (OSError, subprocess.SubprocessError):
                pass
        x = self._x()
        if x and x.fullscreen_in_front():
            return "a full-screen app"
        return None

    def covered(self, stage_window: int) -> bool:
        """Is a full-screen window in front, over the chatmon's own screen? Then it stays out of the way."""
        if sys.platform == "win32":
            return _win_covered(stage_window)
        x = self._x()
        return bool(x and x.fullscreen_in_front())

    def reduce_motion(self) -> bool:
        if sys.platform == "win32":
            return _win_setting(_SPI_GETCLIENTAREAANIMATION) == 0
        if sys.platform == "darwin":
            return bool(_mac_reduce_motion())
        bus = _session_bus()
        portal = _dbus_call(bus, "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop", "org.freedesktop.portal.Settings",
                            "ReadOne", "org.freedesktop.appearance", "reduced-motion") if bus else None
        if isinstance(portal, int):
            return portal == 1
        if "gnome" in self._desktop and shutil.which("gsettings"):
            try:
                out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "enable-animations"], capture_output=True, text=True, timeout=2)
                return out.stdout.strip() == "false"
            except (OSError, subprocess.SubprocessError):
                return False
        return False

    def high_contrast(self) -> bool:
        if sys.platform == "win32":
            return bool(_win_high_contrast())
        try:
            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QGuiApplication

            hints = QGuiApplication.styleHints().accessibility()  # Qt 6.10 and later
            return hints.contrastPreference() == Qt.ContrastPreference.HighContrast
        except (AttributeError, ImportError, RuntimeError):
            return False

    def notice_seconds(self) -> float | None:
        """How long you've asked notifications to stay up (Windows' Accessibility setting); None if not set."""
        if sys.platform == "win32":
            seconds = _win_setting(_SPI_GETMESSAGEDURATION)
            return float(seconds) if seconds else None
        return None
