"""A pretend xdg-desktop-portal FileChooser, for tests/test_portal_bus.py: run on a private session bus.
It answers OpenFile and SaveFile as the portal does (a Request path, then its Response signal), and writes
what it was sent, with each option's D-Bus type, to the file named on its command line."""

import json
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
bus = QDBusConnection.sessionBus()
assert bus.registerObject("/org/freedesktop/portal/desktop", root, QDBusConnection.RegisterOption.ExportAdaptors)
assert bus.registerService("org.freedesktop.portal.Desktop")
print("ready", flush=True)
app.exec()
