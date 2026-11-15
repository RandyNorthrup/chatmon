"""A pretend AT-SPI bus launcher (org.a11y.Bus), for tests/test_screen_readers.py: run on a private session bus.

usage: fake_a11y_bus.py LOG [--screen-reader on|off|gone] [--enabled on|off]

Its org.a11y.Status has IsEnabled, and ScreenReaderEnabled as at-spi2-core kept it before 2.62 ("gone": as 2.62
has it, without). Each question it's asked is written to LOG, a JSON line each. A Set changes the property and says
so with PropertiesChanged, as the real launcher does.
"""

import argparse
import json

from PyQt6.QtCore import QCoreApplication, QObject, pyqtClassInfo, pyqtSlot
from PyQt6.QtDBus import QDBusAbstractAdaptor, QDBusConnection, QDBusMessage, QDBusVariant

parser = argparse.ArgumentParser()
parser.add_argument("log")
parser.add_argument("--screen-reader", default="on", choices=["on", "off", "gone"])
parser.add_argument("--enabled", default="on", choices=["on", "off"])
args = parser.parse_args()
PATH = "/org/a11y/bus"
STATUS = "org.a11y.Status"
props: dict[str, bool] = {"IsEnabled": args.enabled == "on"}
if args.screen_reader != "gone":
    props["ScreenReaderEnabled"] = args.screen_reader == "on"


def log(entry: dict) -> None:
    with open(args.log, "a", encoding="utf-8") as out:
        out.write(json.dumps(entry) + "\n")


def reply(message: QDBusMessage, *values) -> None:
    message.setDelayedReply(True)
    QDBusConnection.sessionBus().send(message.createReply(list(values)))


def fail(message: QDBusMessage, name: str) -> None:
    message.setDelayedReply(True)
    QDBusConnection.sessionBus().send(message.createErrorReply("org.freedesktop.DBus.Error.InvalidArgs", f"No such property “{name}”"))


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.DBus.Properties")
class Properties(QDBusAbstractAdaptor):
    @pyqtSlot(str, QDBusMessage)
    def GetAll(self, interface, message):
        log({"asked": "GetAll", "interface": interface})
        reply(message, dict(props) if interface == STATUS else {})

    @pyqtSlot(str, str, QDBusMessage)
    def Get(self, interface, name, message):
        log({"asked": "Get", "name": name})
        if interface == STATUS and name in props:
            reply(message, QDBusVariant(props[name]))
        else:
            fail(message, name)

    @pyqtSlot(str, str, QDBusVariant, QDBusMessage)
    def Set(self, interface, name, value, message):
        log({"asked": "Set", "name": name})
        if interface != STATUS or name not in props:
            fail(message, name)
            return
        props[name] = bool(value.variant())
        reply(message)
        signal = QDBusMessage.createSignal(PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged")
        signal.setArguments([STATUS, {name: props[name]}, []])
        QDBusConnection.sessionBus().send(signal)


app = QCoreApplication([])
root = QObject()
Properties(root)
bus = QDBusConnection.sessionBus()
assert bus.registerObject(PATH, root, QDBusConnection.RegisterOption.ExportAdaptors)
assert bus.registerService("org.a11y.Bus")
print("ready", flush=True)
app.exec()
