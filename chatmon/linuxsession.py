"""Linux and the BSDs: hear the screen lock and unlock, and the computer sleep and wake, so time away counts as
a break, on whichever desktop.

- logind (the system bus): Manager.PrepareForSleep, and the session's LockedHint, which GNOME, KDE and the
  lockers that tell logind set. https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html
- org.freedesktop.ScreenSaver ActiveChanged (KDE) and org.gnome.ScreenSaver ActiveChanged (GNOME), on the
  session bus.

Imported where there's D-Bus alone; each part is tried, and one that isn't there is left out.
"""

from __future__ import annotations

import os
from typing import Callable

from PyQt6.QtCore import QMetaType, QObject, pyqtSlot
from PyQt6.QtDBus import QDBus, QDBusArgument, QDBusConnection, QDBusMessage

LOGIN1 = "org.freedesktop.login1"


def _value(v):
    while hasattr(v, "variant"):
        v = v.variant()
    return v


class SessionWatcher(QObject):
    """Calls `locked(bool)` as the screen locks and unlocks, and `slept(bool)` as it goes to sleep and wakes."""

    def __init__(self, locked: Callable[[bool], None], slept: Callable[[bool], None]):
        super().__init__()
        self._locked, self._slept = locked, slept
        self.heard: list[str] = []  # which sources it listens to, for the log and the tests
        session = QDBusConnection.sessionBus()
        if session.isConnected():
            if session.connect("org.freedesktop.ScreenSaver", "/ScreenSaver", "org.freedesktop.ScreenSaver", "ActiveChanged", self._active):
                self.heard.append("ScreenSaver")
            if session.connect("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver", "ActiveChanged", self._active):
                self.heard.append("GNOME ScreenSaver")
        system = QDBusConnection.systemBus()
        if system.isConnected():
            if system.connect(LOGIN1, "/org/freedesktop/login1", "org.freedesktop.login1.Manager", "PrepareForSleep", self._sleep):
                self.heard.append("logind sleep")
            path = self._session_path(system)
            if path and system.connect(LOGIN1, path, "org.freedesktop.DBus.Properties", "PropertiesChanged", self._session_changed):
                self.heard.append("logind lock")

    @staticmethod
    def _session_path(system: QDBusConnection) -> str | None:
        """Our session's object (signals never come from /session/auto): by our process, else XDG_SESSION_ID."""
        for method, arg in (("GetSessionByPID", os.getpid()), ("GetSession", os.environ.get("XDG_SESSION_ID"))):
            if arg is None:
                continue
            # One message with a timeout of its own: an interface object would ask logind to describe itself first.
            message = QDBusMessage.createMethodCall(LOGIN1, "/org/freedesktop/login1", "org.freedesktop.login1.Manager", method)
            message.setArguments([QDBusArgument(arg, QMetaType.Type.UInt.value) if method == "GetSessionByPID" else arg])
            reply = system.call(message, QDBus.CallMode.Block, 1000)
            if reply.type() == QDBusMessage.MessageType.ReplyMessage and reply.arguments():
                found = _value(reply.arguments()[0])
                if hasattr(found, "path"):  # a QDBusObjectPath
                    found = found.path()
                if found:
                    return str(found)
        return None

    @pyqtSlot(bool)
    def _active(self, on: bool) -> None:
        self._locked(bool(on))

    @pyqtSlot(bool)
    def _sleep(self, going: bool) -> None:
        self._slept(bool(going))

    @pyqtSlot(QDBusMessage)
    def _session_changed(self, message: QDBusMessage) -> None:
        args = message.arguments()
        if len(args) >= 2 and args[0] == "org.freedesktop.login1.Session":
            changed = args[1] or {}
            if "LockedHint" in changed:
                self._locked(bool(_value(changed["LockedHint"])))
