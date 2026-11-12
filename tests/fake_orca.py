"""A pretend Orca remote controller (Orca 51's names), for tests/test_a11y.py: run on a private session bus.
Each PresentMessage it's sent goes to the file named on its command line, a line each."""

import sys

from PyQt6.QtCore import QCoreApplication, QObject, pyqtClassInfo, pyqtSlot
from PyQt6.QtDBus import QDBusAbstractAdaptor, QDBusConnection

LOG = sys.argv[1]


@pyqtClassInfo("D-Bus Interface", "org.gnome.Orca1.Service")
class Service(QDBusAbstractAdaptor):
    @pyqtSlot(str, result=bool)
    def PresentMessage(self, message):
        with open(LOG, "a", encoding="utf-8") as log:
            log.write(message + "\n")
        return True


app = QCoreApplication([])
root = QObject()
Service(root)
bus = QDBusConnection.sessionBus()
assert bus.registerObject("/org/gnome/Orca1/Service", root, QDBusConnection.RegisterOption.ExportAdaptors)
assert bus.registerService("org.gnome.Orca1.Service")
print("ready", flush=True)
app.exec()
