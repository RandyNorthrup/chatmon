"""Whether you're there, and whether now is a time to keep quiet: each platform's own documented way.

- How long since you last touched the keyboard or mouse (away from the desk counts toward a break):
  Windows GetLastInputInfo; macOS CGEventSourceSecondsSinceLastEventType; on Linux, the Wayland overlay's
  ext-idle-notify-v1 (told to us by layer.py), GNOME's IdleMonitor, or X11's XScreenSaver extension.
- Whether to hold bubbles back: a full-screen app or a presentation (Windows SHQueryUserNotificationState,
  and a full-screen window in front on the chatmon's monitor; on macOS, a full-screen app over the chatmon's
  screen, from CoreGraphics' window list in macnative.py), quiet hours, Windows 11's Focus (winfocus.py), or
  Do Not Disturb (the notification server's own: KDE's, dunst's, mako's, SwayNotificationCenter's,
  xfce4-notifyd's; GNOME's show-banners). On the Wayland overlay and on macOS the system itself keeps the chatmon
  out of a full-screen app's way.
- Reduced motion and high contrast, which the chatmon follows unless you chose otherwise. On Linux: the desktop
  portal's settings, then GNOME's, then Qt's (6.10 and later); on macOS, AppKit's; on Windows, its own.

Every reading is best effort: one that can't be had says None (don't know), never raises. None of them waits on
the screen's thread: on Linux they're kept up to date by listeners (linuxsession.py), and Desk says when the
accessibility settings may have changed (settings_changed), so they needn't be asked again and again.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
import os
import shutil
import sys
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QProcess, pyqtSlot

from .qtsignal import pyqtSignal

if TYPE_CHECKING:
    from .winfocus import Focus

logger = logging.getLogger(__name__)

AWAY_AFTER = 300  # seconds without input: away from the desk


# -- Windows (each reading says None, or False, anywhere else)


def _win_idle() -> float | None:
    if sys.platform != "win32":
        return None

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint32)]

    try:
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        kernel32.GetTickCount.restype = ctypes.c_uint32
        return ((kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0  # ticks wrap every 49.7 days
    except (AttributeError, OSError) as exc:
        logger.debug("couldn't ask Windows how long since the last input: %s", exc)
        return None


# SHQueryUserNotificationState: https://learn.microsoft.com/en-us/windows/win32/api/shellapi/ne-shellapi-query_user_notification_state
_QUNS = {2: "a full-screen app", 3: "a full-screen game", 4: "a presentation", 6: "quiet hours", 7: "a full-screen app"}


def _win_quiet() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        state = ctypes.c_int(0)
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
            return None
        return _QUNS.get(state.value)
    except (AttributeError, OSError) as exc:
        logger.debug("couldn't ask Windows whether to keep quiet: %s", exc)
        return None


def _win_covered(stage_window: int) -> bool:
    """Is a full-screen window in front, on the chatmon's own monitor? (A video, a game, slides.)"""
    if sys.platform != "win32":
        return False

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
    except (AttributeError, OSError) as exc:
        logger.debug("couldn't tell whether a full-screen window is in front: %s", exc)
        return False


_SPI_GETHIGHCONTRAST, _SPI_GETCLIENTAREAANIMATION, _SPI_GETMESSAGEDURATION = 0x42, 0x1042, 0x2016
# What WM_SETTINGCHANGE says changed (its wParam): the settings above, and the screen reader flag, which NVDA,
# JAWS and others set as they start and clear as they stop.
SPI_SETHIGHCONTRAST, SPI_SETCLIENTAREAANIMATION, SPI_SETMESSAGEDURATION, SPI_SETSCREENREADER = 0x43, 0x1043, 0x2017, 0x47
ACCESSIBILITY_SETTINGS = (SPI_SETHIGHCONTRAST, SPI_SETCLIENTAREAANIMATION, SPI_SETMESSAGEDURATION)


def _win_setting(action: int) -> int | None:
    if sys.platform != "win32":
        return None
    try:
        value = ctypes.c_uint(0)
        if not ctypes.windll.user32.SystemParametersInfoW(action, 0, ctypes.byref(value), 0):
            return None
        return value.value
    except (AttributeError, OSError) as exc:
        logger.debug("couldn't read Windows' setting %#x: %s", action, exc)
        return None


def _win_high_contrast() -> bool | None:
    if sys.platform != "win32":
        return None

    class HIGHCONTRASTW(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwFlags", ctypes.c_uint), ("lpszDefaultScheme", ctypes.c_wchar_p)]

    try:
        hc = HIGHCONTRASTW(ctypes.sizeof(HIGHCONTRASTW), 0, None)
        if not ctypes.windll.user32.SystemParametersInfoW(_SPI_GETHIGHCONTRAST, ctypes.sizeof(hc), ctypes.byref(hc), 0):
            return None
        return bool(hc.dwFlags & 1)  # HCF_HIGHCONTRASTON
    except (AttributeError, OSError) as exc:
        logger.debug("couldn't read Windows' high contrast setting: %s", exc)
        return None


# -- macOS (CoreGraphics, and AppKit through the Objective-C runtime: no PyObjC)


def _mac_idle() -> float | None:
    try:
        cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGEventSourceSecondsSinceLastEventType.restype = ctypes.c_double
        cg.CGEventSourceSecondsSinceLastEventType.argtypes = [ctypes.c_int32, ctypes.c_uint32]
        return float(cg.CGEventSourceSecondsSinceLastEventType(1, 0xFFFFFFFF))  # HID system state, any input
    except (AttributeError, OSError) as exc:
        logger.debug("couldn't ask macOS how long since the last input: %s", exc)
        return None


def _mac_reduce_motion() -> bool | None:
    return _mac_workspace_flag(b"accessibilityDisplayShouldReduceMotion")


def _mac_increase_contrast() -> bool | None:
    return _mac_workspace_flag(b"accessibilityDisplayShouldIncreaseContrast")


def _mac_workspace_flag(name: bytes) -> bool | None:
    """One of NSWorkspace.sharedWorkspace's accessibility display options (System Settings › Accessibility ›
    Display), or None where it can't be read."""
    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc") or "/usr/lib/libobjc.dylib")
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        send = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        if not send:  # a loaded function always has an address
            raise OSError("objc_msgSend has no address")
        obj = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(send)  # exact prototypes: arm64 needs them
        flag = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(send)
        workspace = obj(objc.objc_getClass(b"NSWorkspace"), objc.sel_registerName(b"sharedWorkspace"))
        if not workspace:
            return None
        return bool(flag(workspace, objc.sel_registerName(name)))
    except (AttributeError, OSError, ValueError) as exc:
        logger.debug("couldn't read macOS's %s: %s", name.decode(), exc)
        return None


# -- Linux and the BSDs


def _dbus_call(bus, service: str, path: str, interface: str, method: str, *args):
    """One D-Bus call's first answer, or None (no such service, an error, or no answer within half a second).
    One message, not an interface object, which would ask the service to describe itself first, and wait."""
    try:
        from PyQt6.QtDBus import QDBus, QDBusMessage
    except ImportError:  # no QtDBus here
        return None
    try:
        message: QDBusMessage = QDBusMessage.createMethodCall(service, path, interface, method)  # typed: PyQt6 6.12.1's stubs give static constructors an unbound Self
        if args:
            message.setArguments(list(args))
        reply = bus.call(message, QDBus.CallMode.Block, 500)
        if reply.type() != QDBusMessage.MessageType.ReplyMessage or not reply.arguments():
            return None
        value = reply.arguments()[0]
        while hasattr(value, "variant"):  # QDBusVariant, as a property or a portal setting comes
            value = value.variant()
        return value
    except (RuntimeError, TypeError) as exc:
        logger.debug("the D-Bus call %s.%s failed: %s", interface, method, exc)
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
            uint, i = ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_int)
            self.x11.XGetGeometry.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), i, i, uint, uint, uint, uint]
            self.x11.XTranslateCoordinates.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, i, i,
                                                       ctypes.POINTER(ctypes.c_ulong)]
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
        except (AttributeError, OSError) as exc:
            logger.debug("couldn't reach the X server's libraries: %s", exc)
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

    def fullscreen_window(self) -> int:
        """The window in front, if it's full screen; else 0."""
        if not self.ok:
            return 0
        active = self._longs(self.root, "_NET_ACTIVE_WINDOW")
        if active and active[0] and self.atoms["_NET_WM_STATE_FULLSCREEN"] in self._longs(active[0], "_NET_WM_STATE"):
            return active[0]
        return 0

    def rect(self, window: int) -> tuple[int, int, int, int] | None:
        """Where a window is on the whole X screen: (x, y, width, height), or None if it can't be told."""
        root, x, y = ctypes.c_ulong(), ctypes.c_int(), ctypes.c_int()
        width, height, border, depth = ctypes.c_uint(), ctypes.c_uint(), ctypes.c_uint(), ctypes.c_uint()
        if not self.x11.XGetGeometry(self.display, window, ctypes.byref(root), ctypes.byref(x), ctypes.byref(y), ctypes.byref(width),
                                     ctypes.byref(height), ctypes.byref(border), ctypes.byref(depth)):
            return None
        child = ctypes.c_ulong()
        if not self.x11.XTranslateCoordinates(self.display, window, self.root, 0, 0, ctypes.byref(x), ctypes.byref(y), ctypes.byref(child)):
            return None
        return x.value, y.value, width.value, height.value


def covers(full: tuple[int, int, int, int], stage: tuple[int, int, int, int]) -> bool:
    """Whether a full-screen window (x, y, width, height) is on the stage's screen. The stage spans its whole
    screen, so its middle is that screen's: the full-screen window covers it there, or is on another monitor."""
    fx, fy, fw, fh = full
    sx, sy, sw, sh = stage
    mx, my = sx + sw / 2, sy + sh / 2
    return fx <= mx < fx + fw and fy <= my < fy + fh


class _GSetting(QObject):
    """A GNOME setting, kept up to date by `gsettings monitor` (which says each change as it happens), read at
    once from here: never a wait on the screen's thread. `changed` is emitted when it's first known and whenever it
    changes."""

    changed = pyqtSignal()

    def __init__(self, schema: str, key: str, parent: QObject | None = None):
        super().__init__(parent)  # type: ignore[arg-type]  # PyQt6 6.12.1's stubs type QObject's parent as Self, this class
        self.value: str | None = None
        self._key = key
        self._first: QProcess | None = None
        self._monitor: QProcess | None = None
        if not shutil.which("gsettings"):
            return
        self._first = QProcess(self)
        self._first.finished.connect(self._read_first)
        self._first.start("gsettings", ["get", schema, key])
        self._monitor = QProcess(self)
        self._monitor.readyReadStandardOutput.connect(self._heard)
        self._monitor.start("gsettings", ["monitor", schema, key])

    @pyqtSlot()
    def _read_first(self) -> None:
        if self._first is not None:  # it is: only its own finished signal calls this
            self._set(self._first.readAllStandardOutput().data().decode(errors="replace"))

    def _set(self, text: str) -> None:
        text = text.strip()
        if text and text != self.value:
            self.value = text
            self.changed.emit()

    @pyqtSlot()
    def _heard(self) -> None:
        if self._monitor is None:  # it isn't: only its own signal calls this
            return
        for line in self._monitor.readAllStandardOutput().data().decode(errors="replace").splitlines():
            name, _, value = line.partition(":")
            if name.strip() == self._key:
                self._set(value)

    def close(self) -> None:
        """Stop both commands, and hear nothing more from them: a command still running is ended as it's
        deleted, and what it said then must not reach a setting that's going."""
        for process in (self._first, self._monitor):
            if process is None:
                continue
            for signal in (process.finished, process.readyReadStandardOutput):
                try:
                    signal.disconnect()
                except TypeError:  # nothing connected to it
                    pass
            process.kill()
            process.waitForFinished(500)


class Desk(QObject):
    """Readings of the person at the computer and their desktop's settings. One per app.

    `settings_changed` says reduced motion or high contrast may have changed (read them again): from the portal's
    SettingChanged and GNOME's settings on Linux, Qt's contrastPreferenceChanged (Qt 6.10 and later), and Windows'
    WM_SETTINGCHANGE, which winlock.LockWatcher hears and passes to `windows_setting_changed`.
    `screen_reader_changed` says a screen reader started or stopped (Windows says so for NVDA, JAWS and others)."""

    settings_changed = pyqtSignal()
    screen_reader_changed = pyqtSignal()

    def __init__(self, platform: str = ""):
        super().__init__()
        self.platform = platform  # Qt's platform name: "xcb", "wayland", "windows", "cocoa"...
        self.overlay_idle_since: float | None = None  # told by the Wayland overlay (ext-idle-notify-v1)
        self._x11: _X11 | None = None
        self._desktop = (os.environ.get("XDG_CURRENT_DESKTOP") or "").lower()
        self._gnome: dict[tuple[str, str], _GSetting] = {}  # (schema, key): its setting
        self._focus: Focus | None = None  # Windows 11's Focus, asked on a thread of its own
        # The listeners belong to the Desk (they go with it) and say changes with Qt signals: nothing they hear later
        # reaches a Desk that's gone.
        self._portal = None  # linuxsession.PortalSettings, from the first reading on; False: no D-Bus here
        self._dnd = None  # linuxsession.NotificationDnd, likewise
        self._watch_qt_contrast()

    def _watch_qt_contrast(self) -> None:
        """Qt 6.10 and later say when the system's contrast preference changes, on every platform. PyQt6 6.11
        wraps that signal as a method, so there the platforms' own signals alone say so (6.12 has it right)."""
        try:
            from PyQt6.QtGui import QGuiApplication

            if QGuiApplication.instance() is None:
                return
            hints = QGuiApplication.styleHints()
            accessibility = hints.accessibility() if hints is not None else None  # AttributeError before Qt 6.10
            if accessibility is None:
                return
            changed = accessibility.contrastPreferenceChanged
            if not hasattr(changed, "connect"):  # PyQt6 6.11's method
                return
            changed.connect(self.settings_changed)
        except (AttributeError, ImportError, RuntimeError, TypeError):
            pass

    def windows_setting_changed(self, action: int) -> None:
        """Windows changed a system setting (WM_SETTINGCHANGE's wParam, from winlock.LockWatcher)."""
        if action == SPI_SETSCREENREADER:
            self.screen_reader_changed.emit()
        elif action in ACCESSIBILITY_SETTINGS:
            self.settings_changed.emit()

    def _linux(self, kind: str):
        """The D-Bus listener of that kind ("portal", "dnd"), started on first use; None without D-Bus."""
        if sys.platform in ("win32", "darwin"):
            return None
        attr = "_" + kind
        made = getattr(self, attr)
        if made is None:
            try:
                from . import linuxsession
            except ImportError:  # no QtDBus
                made = False
            else:
                if kind == "portal":
                    made = linuxsession.PortalSettings(self)
                    made.changed.connect(self.settings_changed)
                else:
                    made = linuxsession.NotificationDnd(self)
            setattr(self, attr, made)
        return made or None

    def _portal_flag(self, key: str) -> bool | None:
        portal = self._linux("portal")
        return portal.values.get(key) if portal is not None else None

    def _gsetting(self, schema: str, key: str) -> str | None:
        if "gnome" not in self._desktop or sys.platform in ("win32", "darwin"):
            return None
        if (schema, key) not in self._gnome:
            setting = self._gnome[(schema, key)] = _GSetting(schema, key, self)
            setting.changed.connect(self.settings_changed)
        return self._gnome[(schema, key)].value

    def close(self) -> None:
        for setting in self._gnome.values():
            setting.close()
        if self._focus is not None:
            self._focus.close()
        if self._portal:
            self._portal.close()

    def _win_focus(self) -> bool:
        """Windows 11's Focus is on, as of the last time its thread asked (a moment ago)."""
        if self._focus is None:
            try:
                from . import winfocus

                self._focus = winfocus.Focus()
            except (ImportError, OSError, RuntimeError) as exc:
                logger.debug("couldn't start asking Windows about Focus: %s", exc)
                return False
        return self._focus.active is True

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

    def quiet(self, stage_window: int = 0) -> str | None:
        """Why bubbles should wait (a full-screen app, a presentation, Do Not Disturb), or None. `stage_window`
        is the stage's native window, which macOS needs: its full-screen apps are on one screen at a time. A
        full-screen app on any monitor holds bubbles, as Windows' own notification state does."""
        if sys.platform == "win32":
            return _win_quiet() or ("Focus" if self._win_focus() else None)
        if sys.platform == "darwin":
            # A full-screen app has a Space of its own, which the chatmon stays out of: bubbles there go unseen.
            return "a full-screen app" if self.covered(stage_window) else None
        dnd = self._linux("dnd")
        if dnd is not None:
            dnd.refresh()  # the answer comes back in a moment, for next time
            if dnd.state:
                return "Do Not Disturb"
        if self._gsetting("org.gnome.desktop.notifications", "show-banners") == "false":
            return "Do Not Disturb"
        x = self._x()
        if x and x.fullscreen_window():
            return "a full-screen app"
        return None

    def covered(self, stage_window: int) -> bool:
        """Is a full-screen window in front, over the chatmon's own screen? Then it stays out of the way. One on
        another monitor doesn't count."""
        if sys.platform == "win32":
            return _win_covered(stage_window)
        if sys.platform == "darwin":
            if self.platform != "cocoa":  # only Qt's cocoa windows are NSViews to ask AppKit about
                return False
            from . import macnative

            return macnative.full_screen_over(stage_window)
        x = self._x()
        if x is None:
            return False
        full = x.fullscreen_window()
        if not full:
            return False
        area, stage = x.rect(full), (x.rect(stage_window) if stage_window else None)
        return covers(area, stage) if area and stage else True  # where the stage is can't be told: as before

    def reduce_motion(self) -> bool:
        if sys.platform == "win32":
            return _win_setting(_SPI_GETCLIENTAREAANIMATION) == 0
        if sys.platform == "darwin":
            return bool(_mac_reduce_motion())
        portal = self._portal_flag("reduced-motion")
        if portal is not None:
            return portal
        return self._gsetting("org.gnome.desktop.interface", "enable-animations") == "false"

    def high_contrast(self) -> bool:
        if sys.platform == "win32":
            return bool(_win_high_contrast())
        if sys.platform == "darwin":
            return bool(_mac_increase_contrast())
        portal = self._portal_flag("contrast")
        if portal is not None:
            return portal
        gnome = self._gsetting("org.gnome.desktop.a11y.interface", "high-contrast")
        if gnome is not None:
            return gnome == "true"
        return _qt_high_contrast()

    def notice_seconds(self) -> float | None:
        """How long you've asked notifications to stay up (Windows' Accessibility setting); None if not set."""
        if sys.platform == "win32":
            seconds = _win_setting(_SPI_GETMESSAGEDURATION)
            return float(seconds) if seconds else None
        return None


def _qt_high_contrast() -> bool:
    """Qt's own word (6.10 and later), from the platform's theme."""
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication

        hints = QGuiApplication.styleHints()
        accessibility = hints.accessibility() if hints is not None else None  # AttributeError before Qt 6.10
        if accessibility is None:
            return False
        return accessibility.contrastPreference() == Qt.ContrastPreference.HighContrast
    except (AttributeError, ImportError, RuntimeError):
        return False
