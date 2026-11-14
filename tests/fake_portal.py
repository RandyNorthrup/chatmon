"""A pretend xdg-desktop-portal, for tests/test_portal_bus.py: run on a private session bus.

Its FileChooser answers OpenFile and SaveFile as the portal does (a Request path, then its Response signal), and
writes what it was sent, with each option's D-Bus type, to the file named on its command line.

Its Settings answer org.freedesktop.appearance's contrast and reduced-motion, from FAKE_CONTRAST and FAKE_MOTION
(unset: the portal has no such setting), with ReadOne and Read (FAKE_SETTINGS_VERSION 2, the default) or Read
alone (1, as portals before 1.15). Each read is written to the same file. With FAKE_FLIP_CONTRAST, once both have
been read, contrast changes to that value, told by SettingChanged."""

import json
import os
import sys

from PyQt6.QtCore import QCoreApplication, QTimer, pyqtClassInfo, pyqtSlot
from PyQt6.QtDBus import QDBusAbstractAdaptor, QDBusConnection, QDBusMessage, QDBusObjectPath, QDBusVariant
from PyQt6.QtCore import QObject

LOG = sys.argv[1]


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.portal.FileChooser")
class Chooser(QDBusAbstractAdaptor):
    def _answer(self, method, parent, title, options, message):
        sender = message.service().lstrip(":").replace(".", "_")
        path = f"/org/freedesktop/portal/desktop/request/{sender}/{options.get('handle_token', 'x')}"
        typed = {k: type(v).__name__ for k, v in options.items()}
        with open(LOG, "a") as log:
            log.write(json.dumps({"method": method, "signature": message.signature(), "title": title, "options": typed,
                                  "folder": bytes(options.get("current_folder", b"")).decode("utf-8", "replace")}) + "\n")

        def respond():
            signal = QDBusMessage.createSignal(path, "org.freedesktop.portal.Request", "Response")
            signal.setArguments([_uint(0), {"uris": ["file:///tmp/picked%20one.txt"]}])
            QDBusConnection.sessionBus().send(signal)

        QTimer.singleShot(200, respond)
        return QDBusObjectPath(path)

    @pyqtSlot(str, str, "QVariantMap", QDBusMessage, result=QDBusObjectPath)
    def OpenFile(self, parent, title, options, message):
        return self._answer("OpenFile", parent, title, options, message)

    @pyqtSlot(str, str, "QVariantMap", QDBusMessage, result=QDBusObjectPath)
    def SaveFile(self, parent, title, options, message):
        return self._answer("SaveFile", parent, title, options, message)


SETTINGS = {"contrast": os.environ.get("FAKE_CONTRAST"), "reduced-motion": os.environ.get("FAKE_MOTION")}
read = set()


def _setting(method, namespace, key, message, wrap):
    with open(LOG, "a") as log:
        log.write(json.dumps({"settings": method, "key": key}) + "\n")
    value = SETTINGS.get(key) if namespace == "org.freedesktop.appearance" else None
    message.setDelayedReply(True)
    bus = QDBusConnection.sessionBus()
    if value is None:
        bus.send(message.createErrorReply("org.freedesktop.portal.Error.NotFound", "Requested setting not found"))
        return
    answer = QDBusVariant(_uint(int(value)))
    bus.send(message.createReply([QDBusVariant(answer) if wrap else answer]))
    read.add(key)
    flip = os.environ.get("FAKE_FLIP_CONTRAST")
    if flip is not None and read == set(SETTINGS) and SETTINGS["contrast"] != flip:
        SETTINGS["contrast"] = flip

        def changed():
            signal = QDBusMessage.createSignal("/org/freedesktop/portal/desktop", "org.freedesktop.portal.Settings", "SettingChanged")
            signal.setArguments(["org.freedesktop.appearance", "contrast", QDBusVariant(_uint(int(flip)))])
            bus.send(signal)

        QTimer.singleShot(300, changed)


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.portal.Settings")
class SettingsBefore115(QDBusAbstractAdaptor):
    @pyqtSlot(str, str, QDBusMessage)
    def Read(self, namespace, key, message):
        _setting("Read", namespace, key, message, wrap=True)  # one variant more: Read's old way


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.portal.Settings")
class Settings(SettingsBefore115):
    @pyqtSlot(str, str, QDBusMessage)
    def ReadOne(self, namespace, key, message):
        _setting("ReadOne", namespace, key, message, wrap=False)


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.DBus.Properties")
class Props(QDBusAbstractAdaptor):
    @pyqtSlot(str, str, result=QDBusVariant)
    def Get(self, interface, name):
        return QDBusVariant(_uint(4))


def _uint(n):
    from PyQt6.QtCore import QMetaType, QVariant

    v = QVariant(n)
    v.convert(QMetaType(QMetaType.Type.UInt.value))
    return v


app = QCoreApplication([])
root = QObject()
Chooser(root)
Props(root)
(SettingsBefore115 if os.environ.get("FAKE_SETTINGS_VERSION") == "1" else Settings)(root)
bus = QDBusConnection.sessionBus()
assert bus.registerObject("/org/freedesktop/portal/desktop", root, QDBusConnection.RegisterOption.ExportAdaptors)
assert bus.registerService("org.freedesktop.portal.Desktop")
print("ready", flush=True)
app.exec()
