"""Linux and the BSDs: what the desktop says over D-Bus, heard as it happens rather than asked again and again.

- The screen locking and unlocking, and the computer sleeping and waking, so time away counts as a break and
  nothing is drawn while no one can see it: logind (the system bus) Manager.PrepareForSleep, and the session's
  LockedHint, which GNOME, KDE and the lockers that tell logind set; org.freedesktop.ScreenSaver ActiveChanged
  (KDE) and org.gnome.ScreenSaver ActiveChanged (GNOME), on the session bus.
  https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html
- Power saving, so the stage draws less often: power-profiles-daemon's power-saver profile, and UPower's
  OnBattery. https://upower.freedesktop.org/docs/UPower.html
- The desktop portal's appearance settings (high contrast, reduced motion), read once and then followed through
  its SettingChanged signal. https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Settings.html
- The notification server's own Do Not Disturb: KDE's, dunst's, mako's, SwayNotificationCenter's and
  xfce4-notifyd's.
- Whether a screen reader runs (ScreenReaders): Orca's remote controller (49 and later) on the session bus,
  AT-SPI's ScreenReaderEnabled where at-spi2-core still keeps it (it went in 2.62, which kept only IsEnabled: an
  assistive technology listens), GNOME's screen-reader-enabled setting, and a screen reader's own process.

Nothing here waits on the screen's thread but the session lookup at start: every other question is asked without
waiting, and its answer comes back as a signal. A service that isn't running is never started by a question
(NoAutoStart). Each listener can belong to the object that uses it (`parent`): an answer still on its way when that
object goes is never delivered. Imported where there's D-Bus alone; each part is tried, and one that isn't there is
left out.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QMetaType, QObject, pyqtSlot
from PyQt6.QtDBus import QDBus, QDBusArgument, QDBusConnection, QDBusMessage, QDBusPendingCallWatcher, QDBusPendingReply, QDBusServiceWatcher

from .qtsignal import pyqtSignal

LOGIN1 = "org.freedesktop.login1"
PROPERTIES = "org.freedesktop.DBus.Properties"
ASK_FOR_MS = 5000  # how long an answer may take before it counts as none


def _value(v):
    while hasattr(v, "variant"):
        v = v.variant()
    return v


def _call(service: str, path: str, interface: str, method: str, *args) -> QDBusMessage:
    """A method call that never starts a service which isn't running already."""
    message: QDBusMessage = QDBusMessage.createMethodCall(service, path, interface, method)  # typed: PyQt6 6.12.1's stubs give static constructors an unbound Self
    if args:
        message.setArguments(list(args))
    message.setAutoStartService(False)
    return message


def _ask(owner: QObject, bus: QDBusConnection, message: QDBusMessage, then: Callable[[QDBusMessage], None]) -> None:
    """Send `message` without waiting; `then(reply)` gets the answer (an error message, if it failed), unless `owner`
    has gone by then (the answer's watcher goes with it)."""
    watcher = QDBusPendingCallWatcher(bus.asyncCall(message, ASK_FOR_MS), owner)

    def answered(w: QDBusPendingCallWatcher) -> None:
        reply = QDBusPendingReply(w).reply()
        w.deleteLater()
        then(reply)

    watcher.finished.connect(answered)


def _answer(reply: QDBusMessage):
    """A reply's first value, unwrapped from its variants; None for an error or an empty reply."""
    if reply.type() != QDBusMessage.MessageType.ReplyMessage or not reply.arguments():
        return None
    return _value(reply.arguments()[0])


class SessionWatcher(QObject):
    """Calls `locked(bool)` as the screen locks and unlocks, `slept(bool)` as it goes to sleep and wakes, and
    `seen(bool)`: False while the screen is locked (nothing on it can be seen, so nothing need be drawn), True once
    it's unlocked. Each source can say the same thing (logind and the screen saver both tell of a lock): each
    change is told once."""

    def __init__(self, locked: Callable[[bool], None], slept: Callable[[bool], None], seen: Callable[[bool], None] | None = None,
                 parent: QObject | None = None):
        super().__init__(parent)  # type: ignore[arg-type]  # PyQt6 6.12.1's stubs type QObject's parent as Self, this class
        self._locked, self._slept, self._seen = locked, slept, seen
        self.locked = False  # as last told
        self.heard: list[str] = []  # which sources it listens to, for the log and the tests
        session: QDBusConnection = QDBusConnection.sessionBus()
        if session.isConnected():
            if session.connect("org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver", "ActiveChanged", self._active):
                self.heard.append("ScreenSaver")
            if session.connect("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver", "ActiveChanged", self._active):
                self.heard.append("GNOME ScreenSaver")
        system: QDBusConnection = QDBusConnection.systemBus()
        if system.isConnected():
            if system.connect(LOGIN1, "/org/freedesktop/login1", "org.freedesktop.login1.Manager", "PrepareForSleep", self._sleep):
                self.heard.append("logind sleep")
            path = self._session_path(system)
            if path and system.connect(LOGIN1, path, PROPERTIES, "PropertiesChanged", self._session_changed):
                self.heard.append("logind lock")

    @staticmethod
    def _session_path(system: QDBusConnection) -> str | None:
        """Our session's object (signals never come from /session/auto): by our process, else XDG_SESSION_ID."""
        for method, arg in (("GetSessionByPID", os.getpid()), ("GetSession", os.environ.get("XDG_SESSION_ID"))):
            if arg is None:
                continue
            # One message with a timeout of its own: an interface object would ask logind to describe itself first.
            message: QDBusMessage = QDBusMessage.createMethodCall(LOGIN1, "/org/freedesktop/login1", "org.freedesktop.login1.Manager", method)
            message.setArguments([QDBusArgument(arg, QMetaType.Type.UInt.value) if method == "GetSessionByPID" else arg])  # type: ignore[call-overload]  # PyQt6's stub types the member's int value as the enum
            reply = system.call(message, QDBus.CallMode.Block, 1000)
            if reply.type() == QDBusMessage.MessageType.ReplyMessage and reply.arguments():
                found = _value(reply.arguments()[0])
                if hasattr(found, "path"):  # a QDBusObjectPath
                    found = found.path()
                if found:
                    return str(found)
        return None

    def _lock(self, on: bool) -> None:
        if on == self.locked:
            return
        self.locked = on
        self._locked(on)
        if self._seen is not None:
            self._seen(not on)

    @pyqtSlot(bool)
    def _active(self, on: bool) -> None:
        self._lock(bool(on))

    @pyqtSlot(bool)
    def _sleep(self, going: bool) -> None:
        self._slept(bool(going))

    @pyqtSlot(QDBusMessage)
    def _session_changed(self, message: QDBusMessage) -> None:
        args = message.arguments()
        if len(args) >= 2 and args[0] == "org.freedesktop.login1.Session":
            changed = args[1] or {}
            if "LockedHint" in changed:
                self._lock(bool(_value(changed["LockedHint"])))


# power-profiles-daemon, by its name since 0.20, then its first. https://upower.pages.freedesktop.org/power-profiles-daemon/
PROFILES = (("org.freedesktop.UPower.PowerProfiles", "/org/freedesktop/UPower/PowerProfiles"), ("net.hadess.PowerProfiles", "/net/hadess/PowerProfiles"))
UPOWER = ("org.freedesktop.UPower", "/org/freedesktop/UPower")


class PowerProfile(QObject):
    """Calls `saving(bool)`: whether to save power, as it stands and as it changes. It's True while
    power-profiles-daemon's power-saver profile is on, or while the computer runs on its battery (UPower's
    OnBattery), and each change is told once."""

    def __init__(self, saving: Callable[[bool], None], parent: QObject | None = None):
        super().__init__(parent)  # type: ignore[arg-type]  # PyQt6 6.12.1's stubs type QObject's parent as Self, this class
        self._saving = saving
        self.heard: list[str] = []  # the services it listens to
        self.profile_saver = False
        self.on_battery = False
        self.told: bool | None = None
        self._bus: QDBusConnection = QDBusConnection.systemBus()
        if not self._bus.isConnected():
            return
        self._ask_profile(0)
        service, path = UPOWER
        _ask(self, self._bus, _call(service, path, PROPERTIES, "Get", service, "OnBattery"), self._battery_read)

    def _ask_profile(self, i: int) -> None:
        service, path = PROFILES[i]

        def read(reply: QDBusMessage) -> None:
            value = _answer(reply)
            if value is None:
                if i + 1 < len(PROFILES):
                    self._ask_profile(i + 1)
                return
            if self._bus.connect(service, path, PROPERTIES, "PropertiesChanged", self._changed):
                self.heard.append(service)
            self.profile_saver = value == "power-saver"
            self._tell()

        _ask(self, self._bus, _call(service, path, PROPERTIES, "Get", service, "ActiveProfile"), read)

    def _battery_read(self, reply: QDBusMessage) -> None:
        value = _answer(reply)
        if not isinstance(value, bool):
            return
        service, path = UPOWER
        if self._bus.connect(service, path, PROPERTIES, "PropertiesChanged", self._changed):
            self.heard.append(service)
        self.on_battery = value
        self._tell()

    def _tell(self) -> None:
        saving = self.profile_saver or self.on_battery
        if saving != self.told:
            self.told = saving
            self._saving(saving)

    @pyqtSlot(QDBusMessage)
    def _changed(self, message: QDBusMessage) -> None:
        args = message.arguments()
        if len(args) < 2 or not isinstance(args[1], dict):
            return
        changed = args[1]
        if "ActiveProfile" in changed:
            self.profile_saver = _value(changed["ActiveProfile"]) == "power-saver"
        if args[0] == UPOWER[0] and "OnBattery" in changed:
            self.on_battery = bool(_value(changed["OnBattery"]))
        self._tell()


# -- The desktop portal's appearance settings

PORTAL = ("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop", "org.freedesktop.portal.Settings")
APPEARANCE = "org.freedesktop.appearance"
APPEARANCE_KEYS = ("contrast", "reduced-motion")  # each: 1 asks for it (higher contrast, less motion), 0 has no preference


def portal_flag(value) -> bool | None:
    """An appearance setting as yes or no: 1 asks for it, 0 has no preference, anything else isn't known."""
    value = _value(value)
    if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
        return None
    return value == 1


class PortalSettings(QObject):
    """The portal's high-contrast and reduced-motion settings: read once without waiting, then kept up to date by
    its SettingChanged signal, so they're read from `values` at once. `changed` is emitted when one is first known
    and whenever it changes."""

    changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)  # type: ignore[arg-type]  # PyQt6 6.12.1's stubs type QObject's parent as Self, this class
        self.values: dict[str, bool | None] = {}
        self._bus: QDBusConnection = QDBusConnection.sessionBus()
        if not self._bus.isConnected():
            return
        self._bus.connect(PORTAL[0], PORTAL[1], PORTAL[2], "SettingChanged", self._setting_changed)
        for key in APPEARANCE_KEYS:
            self._read(key, "ReadOne")

    def _read(self, key: str, method: str) -> None:
        def answered(reply: QDBusMessage) -> None:
            if reply.type() == QDBusMessage.MessageType.ReplyMessage:
                self.set(key, _answer(reply))
            elif method == "ReadOne" and reply.errorName() == "org.freedesktop.DBus.Error.UnknownMethod":
                self._read(key, "Read")  # a portal before version 2: the same value, in one variant more

        _ask(self, self._bus, _call(*PORTAL, method, APPEARANCE, key), answered)

    def set(self, key: str, value) -> None:
        flag = portal_flag(value)
        if key in self.values and self.values[key] == flag:
            return
        self.values[key] = flag
        self.changed.emit()

    @pyqtSlot(QDBusMessage)
    def _setting_changed(self, message: QDBusMessage) -> None:
        args = message.arguments()
        if len(args) >= 3 and args[0] == APPEARANCE and args[1] in APPEARANCE_KEYS:
            self.set(args[1], args[2])

    def close(self) -> None:
        if self._bus.isConnected():
            self._bus.disconnect(PORTAL[0], PORTAL[1], PORTAL[2], "SettingChanged", self._setting_changed)


# -- The notification server's own Do Not Disturb, by the name GetServerInformation gives it. Each question is the
#    one that server's own tool asks (dunstctl is-paused, makoctl mode, swaync-client --get-dnd, xfconf-query).

NOTIFICATIONS = ("org.freedesktop.Notifications", "/org/freedesktop/Notifications")
DND_QUESTIONS: dict[str, tuple] = {
    "Plasma": (*NOTIFICATIONS, PROPERTIES, "Get", NOTIFICATIONS[0], "Inhibited"),
    "dunst": (*NOTIFICATIONS, PROPERTIES, "Get", "org.dunstproject.cmd0", "paused"),
    "mako": (NOTIFICATIONS[0], "/fr/emersion/Mako", "fr.emersion.Mako", "ListModes"),
    "SwayNotificationCenter": ("org.erikreider.swaync.cc", "/org/erikreider/swaync/cc", "org.erikreider.swaync.cc", "GetDnd"),
    "Xfce Notify Daemon": ("org.xfce.Xfconf", "/org/xfce/Xfconf", "org.xfce.Xfconf", "GetProperty", "xfce4-notifyd", "/do-not-disturb"),
}
MAKO_DND_MODE = "do-not-disturb"  # the mode mako's own documentation sets up to hide notifications


def dnd_on(server: str, answer) -> bool | None:
    """Whether that server's answer means Do Not Disturb is on: mako's modes include do-not-disturb; the others
    answer yes or no. None if the answer isn't one."""
    answer = _value(answer)
    if server == "mako":
        return MAKO_DND_MODE in answer if isinstance(answer, list) else None
    return answer if isinstance(answer, bool) else None


class NotificationDnd(QObject):
    """Whether the notification server's own Do Not Disturb is on, asked without waiting: `state` is the last
    answer (None: not known), and `refresh()` asks again (once at a time). The server is named by
    GetServerInformation, asked again (at most once a minute) after a question fails: it may have gone, or another
    server taken over."""

    IDENTIFY_AGAIN_AFTER = 60.0  # seconds

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)  # type: ignore[arg-type]  # PyQt6 6.12.1's stubs type QObject's parent as Self, this class
        self.server: str | None = None
        self.state: bool | None = None
        self._asking = False
        self._failed_at = float("-inf")
        self._bus: QDBusConnection = QDBusConnection.sessionBus()

    def refresh(self) -> None:
        if self._asking or not self._bus.isConnected():
            return
        if self.server is None and time.monotonic() - self._failed_at < self.IDENTIFY_AGAIN_AFTER:
            return
        self._asking = True
        if self.server is None:
            _ask(self, self._bus, _call(*NOTIFICATIONS, NOTIFICATIONS[0], "GetServerInformation"), self._identified)
        elif self.server in DND_QUESTIONS:
            _ask(self, self._bus, _call(*DND_QUESTIONS[self.server]), self._answered)
        else:
            self._asking = False  # a server with no Do Not Disturb of its own to ask (GNOME's is a setting)

    def _identified(self, reply: QDBusMessage) -> None:
        self._asking = False
        name = _answer(reply)
        if isinstance(name, str) and name:
            self.server = name
            self.refresh()

    def _answered(self, reply: QDBusMessage) -> None:
        self._asking = False
        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
            self.server, self.state, self._failed_at = None, None, time.monotonic()
            return
        self.heard(_answer(reply))

    def heard(self, answer) -> None:
        self.state = dnd_on(self.server or "", answer)


# -- Whether a screen reader runs. Each way is asked without waiting and followed as it changes; a reading says what
#    was last heard. at-spi2-core 2.62 dropped org.a11y.Status ScreenReaderEnabled (2.61 reworked IsEnabled, which
#    the bus launcher now sets as an assistive technology registers for events): there IsEnabled says something
#    listens, not what, so the reader itself is looked for, by its remote controller or its process.
#    https://gitlab.gnome.org/GNOME/at-spi2-core/-/blob/main/NEWS

# Orca's remote controller, which speaks (and brailles) what it's sent: org.gnome.Orca.Service in 49 and 50,
# org.gnome.Orca1.Service from 51. https://gitlab.gnome.org/GNOME/orca/-/blob/main/docs/remote-controller.md
ORCA = (("org.gnome.Orca1.Service", "/org/gnome/Orca1/Service"), ("org.gnome.Orca.Service", "/org/gnome/Orca/Service"))
A11Y_BUS = ("org.a11y.Bus", "/org/a11y/bus")
A11Y_STATUS = "org.a11y.Status"
# Linux screen readers by their process name (/proc/PID/comm), as each one's own launcher names it.
READER_PROCESSES = {"orca": "Orca", "odilia": "Odilia", "fenrir": "Fenrir"}
GNOME_SCREEN_READER = ("org.gnome.desktop.a11y.applications", "screen-reader-enabled")
PROC = Path("/proc")


def running_readers(proc: Path = PROC, uid: int | None = None) -> list[str]:
    """The screen readers running as this user (`uid`; None: whoever), by their processes: names, sorted."""
    found = set()
    try:
        entries = list(proc.iterdir())
    except OSError:  # no /proc: not Linux, or hidden from this process
        return []
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            name = READER_PROCESSES.get((entry / "comm").read_text(encoding="utf-8", errors="replace").strip())
            if name and (uid is None or entry.stat().st_uid == uid):
                found.add(name)
        except OSError:  # gone since it was listed, or not ours to read
            continue
    return sorted(found)


class ScreenReaders(QObject):
    """Whether a screen reader runs, and which, as last heard: `found()`. `changed` is emitted when that changes
    (Orca's remote controller comes or goes, AT-SPI's status changes, GNOME's setting changes, `rescan()` finds a
    reader's process started or stopped). Nothing waits, and nothing is started: AT-SPI's bus isn't launched by
    asking about it. One per app: `screen_readers()`."""

    changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None, proc: Path = PROC, gnome: bool | None = None):
        super().__init__(parent)  # type: ignore[arg-type]  # PyQt6 6.12.1's stubs type QObject's parent as Self, this class
        self.orca: tuple[str, str] | None = None  # Orca's remote controller, (service, path), while it's registered
        self.screen_reader_enabled: bool | None = None  # AT-SPI's ScreenReaderEnabled, before at-spi2-core 2.62
        self.accessibility: bool | None = None  # AT-SPI's IsEnabled: an assistive technology listens
        self.gnome: bool | None = None  # GNOME's screen-reader-enabled setting, on GNOME
        self.running: list[str] = []
        self._proc = proc
        self._uid = os.getuid() if hasattr(os, "getuid") else None
        self._owned: dict[str, bool] = {}
        self._told: tuple[str, tuple[str, str] | None] | None = None
        self._gnome_setting = None
        if gnome is None:
            gnome = "gnome" in (os.environ.get("XDG_CURRENT_DESKTOP") or "").lower()
        if gnome:
            from .presence import _GSetting

            self._gnome_setting = _GSetting(*GNOME_SCREEN_READER, self)
            self._gnome_setting.changed.connect(self._gnome_changed)
        self._bus: QDBusConnection = QDBusConnection.sessionBus()
        if self._bus.isConnected():
            services = [service for service, _ in ORCA] + [A11Y_BUS[0]]
            self._watcher = QDBusServiceWatcher(services[0], self._bus, QDBusServiceWatcher.WatchModeFlag.WatchForOwnerChange, self)
            for service in services[1:]:  # one at a time: setWatchedServices never returned here (Qt 6.12.0, Linux)
                self._watcher.addWatchedService(service)
            self._watcher.serviceOwnerChanged.connect(self._owner_changed)
            self._bus.connect(A11Y_BUS[0], A11Y_BUS[1], PROPERTIES, "PropertiesChanged", self._status_changed)
            for service in services:
                _ask(self, self._bus, _call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner", service),
                     self._owner_answer(service))
        self.rescan()

    def found(self) -> tuple[str, tuple[str, str] | None] | None:
        """(the screen reader's name, Orca's remote controller to speak through or None), or None if none runs."""
        if self.orca is not None:
            return "Orca", self.orca
        if self.screen_reader_enabled or self.gnome:
            return (self.running[0] if self.running else "a screen reader"), None
        if self.running:
            return self.running[0], None
        return None

    def rescan(self) -> None:
        """Look again for a screen reader's process (a quick read of /proc, no question to anyone)."""
        self.running = running_readers(self._proc, self._uid)
        self._tell()

    def owned(self, service: str, owned: bool) -> None:
        """Whether that bus name has an owner now (asked at start, then told as it changes)."""
        self._owned[service] = owned
        self.orca = next(((name, path) for name, path in ORCA if self._owned.get(name)), None)
        if service == A11Y_BUS[0]:
            if owned:  # AT-SPI's bus is up (again): what does it say?
                _ask(self, self._bus, _call(*A11Y_BUS, PROPERTIES, "GetAll", A11Y_STATUS), self._status_read)
            else:
                self.screen_reader_enabled = self.accessibility = None
        self.rescan()

    def status(self, changed: dict) -> None:
        """AT-SPI's org.a11y.Status properties, as read or as changed."""
        if "ScreenReaderEnabled" in changed:
            self.screen_reader_enabled = bool(_value(changed["ScreenReaderEnabled"]))
        if "IsEnabled" in changed:
            self.accessibility = bool(_value(changed["IsEnabled"]))
        self.rescan()  # something started or stopped listening: is it a screen reader?

    def _owner_answer(self, service: str) -> Callable[[QDBusMessage], None]:
        def answered(reply: QDBusMessage) -> None:
            self.owned(service, _answer(reply) is True)

        return answered

    def _owner_changed(self, service: str, old: str, new: str) -> None:
        self.owned(service, bool(new))

    def _status_read(self, reply: QDBusMessage) -> None:
        answer = _answer(reply)
        if isinstance(answer, dict):
            self.status(answer)

    @pyqtSlot(QDBusMessage)
    def _status_changed(self, message: QDBusMessage) -> None:
        args = message.arguments()
        if len(args) >= 2 and args[0] == A11Y_STATUS and isinstance(args[1], dict):
            self.status(args[1])

    def _gnome_changed(self) -> None:
        value = self._gnome_setting.value if self._gnome_setting is not None else None
        self.gnome = None if value is None else value == "true"
        self.rescan()

    def _tell(self) -> None:
        found = self.found()
        if found != self._told:
            self._told = found
            self.changed.emit()

    def close(self) -> None:
        if self._gnome_setting is not None:
            self._gnome_setting.close()


_screen_readers: ScreenReaders | None = None


def screen_readers() -> ScreenReaders:
    """The app's one ScreenReaders, made on first use and kept: a11y.reader() reads it, presence.Desk passes on its
    changes as screen_reader_changed."""
    global _screen_readers
    if _screen_readers is None:
        _screen_readers = ScreenReaders()
    return _screen_readers
