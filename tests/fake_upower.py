"""A pretend UPower, for tests/test_heads_up.py and tests/test_linuxsession.py: run on a private bus that stands in
for the system bus (DBUS_SYSTEM_BUS_ADDRESS pointed at it).

usage: fake_upower.py LOG PERCENT STATE ON_BATTERY [ON_BATTERY_LATER]

The DisplayDevice has a battery at PERCENT with UPower's State STATE (1 charging, 2 discharging, 4 full...);
UPower's OnBattery is ON_BATTERY ("true" or "false"), and, if given, changes to ON_BATTERY_LATER a moment after
it's first asked, told by PropertiesChanged. Each question is written to LOG, a JSON line each.
"""

import json
import sys

from PyQt6.QtCore import QCoreApplication, QMetaType, QObject, QTimer, QVariant, pyqtClassInfo, pyqtSlot
from PyQt6.QtDBus import QDBusAbstractAdaptor, QDBusConnection, QDBusMessage, QDBusVariant

LOG, PERCENT, STATE, ON_BATTERY = sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), sys.argv[4] == "true"
LATER = sys.argv[5] == "true" if len(sys.argv) > 5 else None
DEVICE = "org.freedesktop.UPower.Device"


def log(entry: dict) -> None:
    with open(LOG, "a", encoding="utf-8") as out:
        out.write(json.dumps(entry) + "\n")


def _uint(n: int) -> QVariant:
    v = QVariant(n)
    v.convert(QMetaType(QMetaType.Type.UInt.value))
    return v


def device() -> dict:
    return {"IsPresent": True, "Percentage": PERCENT, "State": _uint(STATE), "Type": _uint(2), "Model": ""}


def answer(message: QDBusMessage, value) -> None:
    message.setDelayedReply(True)
    QDBusConnection.systemBus().send(message.createReply([value]))


def fail(message: QDBusMessage) -> None:
    message.setDelayedReply(True)
    QDBusConnection.systemBus().send(message.createErrorReply("org.freedesktop.DBus.Error.InvalidArgs", "No such property"))


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.DBus.Properties")
class DisplayDevice(QDBusAbstractAdaptor):
    @pyqtSlot(str, QDBusMessage)
    def GetAll(self, interface, message):
        log({"path": "DisplayDevice", "method": "GetAll", "interface": interface})
        answer(message, device()) if interface == DEVICE else fail(message)

    @pyqtSlot(str, str, QDBusMessage)
    def Get(self, interface, name, message):
        log({"path": "DisplayDevice", "method": "Get", "name": name})
        props = device()
        answer(message, QDBusVariant(props[name])) if interface == DEVICE and name in props else fail(message)


state = {"on battery": ON_BATTERY, "asked": False}


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.DBus.Properties")
class Daemon(QDBusAbstractAdaptor):
    @pyqtSlot(str, str, QDBusMessage)
    def Get(self, interface, name, message):
        log({"path": "UPower", "method": "Get", "name": name})
        if (interface, name) != ("org.freedesktop.UPower", "OnBattery"):
            fail(message)
            return
        answer(message, QDBusVariant(state["on battery"]))
        if LATER is not None and not state["asked"]:
            state["asked"] = True

            def change():
                state["on battery"] = LATER
                signal = QDBusMessage.createSignal("/org/freedesktop/UPower", "org.freedesktop.DBus.Properties", "PropertiesChanged")
                signal.setArguments(["org.freedesktop.UPower", {"OnBattery": LATER}, []])
                QDBusConnection.systemBus().send(signal)

            QTimer.singleShot(300, change)


app = QCoreApplication([])
bus = QDBusConnection.systemBus()
roots = []
for path, adaptor in (("/org/freedesktop/UPower/devices/DisplayDevice", DisplayDevice), ("/org/freedesktop/UPower", Daemon)):
    root = QObject()
    adaptor(root)
    roots.append(root)
    assert bus.registerObject(path, root, QDBusConnection.RegisterOption.ExportAdaptors)
assert bus.registerService("org.freedesktop.UPower")
print("ready", flush=True)
app.exec()
