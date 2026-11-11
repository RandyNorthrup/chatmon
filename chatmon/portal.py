"""The desktop's own file chooser on Linux, through xdg-desktop-portal: the one your desktop shows everywhere.

Qt's QFileDialog uses the portal only in Flatpak and Snap, or with QT_QPA_PLATFORMTHEME=xdgdesktopportal; on
Hyprland, Sway and other compositors without a Qt theme of their own it falls back to Qt's own dialog. The
portal's FileChooser asks over D-Bus and answers with a Request's Response signal.
https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.FileChooser.html
https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Request.html
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlsplit

from PyQt6.QtCore import QByteArray, QObject, pyqtSlot
from PyQt6.QtDBus import QDBus, QDBusConnection, QDBusMessage, QDBusPendingCallWatcher, QDBusPendingReply

SERVICE = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
CHOOSER = "org.freedesktop.portal.FileChooser"
REQUEST = "org.freedesktop.portal.Request"
OK, CANCELLED = 0, 1  # Response's codes; 2: it ended some other way (no chooser, an error)


def available() -> bool:
    """A FileChooser to ask: the portal is there and has one (a backend that implements it)."""
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return False
    message = QDBusMessage.createMethodCall(SERVICE, PATH, "org.freedesktop.DBus.Properties", "Get")
    message.setArguments([CHOOSER, "version"])
    reply = bus.call(message, QDBus.CallMode.Block, 1000)
    return reply.type() == QDBusMessage.MessageType.ReplyMessage


def request_path(bus: QDBusConnection, token: str) -> str:
    """Where the portal will put the Request: known before asking, so its answer can't come first."""
    sender = bus.baseService().lstrip(":").replace(".", "_")
    return f"{PATH}/request/{sender}/{token}"


def paths_from(uris) -> list[str]:
    """Local files from the chooser's file:// URIs (anything else, a remote location, is left out)."""
    out = []
    for uri in uris or []:
        parts = urlsplit(str(uri))
        if parts.scheme == "file" and parts.path:
            out.append(unquote(parts.path))
    return out


class FileChooser(QObject):
    """One question to the portal's FileChooser at a time. `then(paths)` gets the chosen files ([] when you
    cancel); `fallback()` runs instead when the portal couldn't show one."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._bus = QDBusConnection.sessionBus()
        self._path: str | None = None
        self._then: Callable[[list[str]], None] | None = None
        self._fallback: Callable[[], None] | None = None
        self._watcher: QDBusPendingCallWatcher | None = None

    def open_files(self, title: str, folder: Path, then, fallback) -> None:
        self._ask("OpenFile", title, {"multiple": True, "current_folder": _bytes(folder)}, then, fallback)

    def save_file(self, title: str, folder: Path, name: str, then, fallback) -> None:
        self._ask("SaveFile", title, {"current_name": name, "current_folder": _bytes(folder)}, then, fallback)

    def _ask(self, method: str, title: str, options: dict, then, fallback) -> None:
        self._forget()
        token = "chatmon_" + secrets.token_hex(8)
        self._path, self._then, self._fallback = request_path(self._bus, token), then, fallback
        self._bus.connect(SERVICE, self._path, REQUEST, "Response", self._response)
        message = QDBusMessage.createMethodCall(SERVICE, PATH, CHOOSER, method)
        message.setArguments(["", title, {**options, "handle_token": token, "modal": True}])
        self._watcher = QDBusPendingCallWatcher(self._bus.asyncCall(message, 30_000), self)
        self._watcher.finished.connect(self._asked)

    def _asked(self, watcher: QDBusPendingCallWatcher) -> None:
        reply = QDBusPendingReply(watcher).reply()
        watcher.deleteLater()
        self._watcher = None
        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
            self._give_up()
            return
        handle = reply.arguments()[0] if reply.arguments() else None
        handle = handle.path() if hasattr(handle, "path") else str(handle or "")
        if handle and handle != self._path:  # an older portal makes its own path: listen there instead
            self._bus.disconnect(SERVICE, self._path, REQUEST, "Response", self._response)
            self._path = handle
            self._bus.connect(SERVICE, self._path, REQUEST, "Response", self._response)

    @pyqtSlot(QDBusMessage)
    def _response(self, message: QDBusMessage) -> None:
        args = message.arguments()
        code = args[0] if args else 2
        results = args[1] if len(args) > 1 and isinstance(args[1], dict) else {}
        then = self._then
        if code not in (OK, CANCELLED):
            self._give_up()
            return
        self._forget()
        if then is not None:
            then(paths_from(_value(results.get("uris"))) if code == OK else [])

    def _give_up(self) -> None:
        fallback = self._fallback
        self._forget()
        if fallback is not None:
            fallback()

    def _forget(self) -> None:
        if self._path:
            self._bus.disconnect(SERVICE, self._path, REQUEST, "Response", self._response)
        self._path = self._then = self._fallback = None


def _bytes(folder: Path) -> QByteArray:
    """A folder as the portal takes it: its bytes, ending in a NUL."""
    return QByteArray(os.fsencode(str(folder)) + b"\0")


def _value(v):
    while hasattr(v, "variant"):
        v = v.variant()
    return v
