"""A pretend notification server, for tests/test_platform_events.py: run on a private session bus.

usage: fake_notifications.py LOG [--name NAME] [--dnd on|off|unset] [--press INDEX] [--not-own]

It answers as org.freedesktop.Notifications does, naming itself NAME in GetServerInformation (dunst, mako,
SwayNotificationCenter, Xfce Notify Daemon, Plasma), and answers that server's own Do Not Disturb question, where
the real one does: dunst's `paused` property, mako's ListModes, SwayNotificationCenter's GetDnd (on its own bus
name), xfconf's /do-not-disturb (on org.xfce.Xfconf; "unset" answers as xfconf does for a property never set), and
KDE's `Inhibited` property. Each call is written to LOG as a JSON line: a Notify with its arguments and each hint's
D-Bus type, and each question asked. With --press, the first notification that has actions gets ActionInvoked for
that action, as if its button were pressed. With --not-own, a server with a bus name of its own (swaync's,
xfconf's) leaves that name to whoever else may own or start it.
"""

import argparse
import json

from PyQt6.QtCore import QCoreApplication, QMetaType, QObject, QTimer, QVariant, pyqtClassInfo, pyqtSlot
from PyQt6.QtDBus import QDBusAbstractAdaptor, QDBusConnection, QDBusMessage, QDBusVariant

parser = argparse.ArgumentParser()
parser.add_argument("log")
parser.add_argument("--name", default="dunst")
parser.add_argument("--dnd", default="off", choices=["on", "off", "unset"])
parser.add_argument("--press", type=int, default=None)
parser.add_argument("--not-own", action="store_true")
args = parser.parse_args()
DND = args.dnd == "on"
PATH = "/org/freedesktop/Notifications"


def log(entry: dict) -> None:
    with open(args.log, "a", encoding="utf-8") as out:
        out.write(json.dumps(entry) + "\n")


def _uint(n: int) -> QVariant:
    v = QVariant(n)
    v.convert(QMetaType(QMetaType.Type.UInt.value))
    return v


def typed(value) -> list:
    """A hint as [D-Bus type, value], told from how QtDBus hands it over: a byte comes as bytes."""
    if isinstance(value, bool):
        return ["b", value]
    if isinstance(value, bytes) and len(value) == 1:
        return ["y", value[0]]
    if isinstance(value, int):
        return ["i", value]
    return ["s", str(value)]


def reply(message: QDBusMessage, *values) -> None:
    message.setDelayedReply(True)
    QDBusConnection.sessionBus().send(message.createReply(list(values)))


def asked(message: QDBusMessage, what: str) -> None:
    log({"asked": what})


next_id = [0]
pressed = [False]


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.Notifications")
class Notifications(QDBusAbstractAdaptor):
    @pyqtSlot(QDBusMessage)
    def GetServerInformation(self, message):
        asked(message, "GetServerInformation")
        reply(message, args.name, "test", "1.0", "1.2")

    @pyqtSlot(QDBusMessage)
    def GetCapabilities(self, message):
        reply(message, ["actions", "body", "persistence"])

    @pyqtSlot(str, "uint", str, str, str, "QStringList", "QVariantMap", int, QDBusMessage)
    def Notify(self, app, replaces, icon, summary, body, actions, hints, timeout, message):
        notification = replaces or next_id[0] + 1
        next_id[0] = max(next_id[0], notification)
        log({"method": "Notify", "signature": message.signature(), "id": notification, "replaces": replaces, "summary": summary,
             "actions": list(actions), "hints": {k: typed(v) for k, v in hints.items()}})
        reply(message, _uint(notification))
        if args.press is not None and actions and not pressed[0]:
            pressed[0] = True

            def press():
                signal = QDBusMessage.createSignal(PATH, "org.freedesktop.Notifications", "ActionInvoked")
                signal.setArguments([_uint(notification), str(args.press)])
                QDBusConnection.sessionBus().send(signal)

            QTimer.singleShot(150, press)

    @pyqtSlot("uint")
    def CloseNotification(self, notification):
        pass


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.DBus.Properties")
class Properties(QDBusAbstractAdaptor):
    """dunst's paused (org.dunstproject.cmd0) and KDE's Inhibited (org.freedesktop.Notifications)."""

    @pyqtSlot(str, str, QDBusMessage)
    def Get(self, interface, name, message):
        asked(message, f"Get {interface} {name}")
        if (args.name, interface, name) in (("dunst", "org.dunstproject.cmd0", "paused"), ("Plasma", "org.freedesktop.Notifications", "Inhibited")):
            reply(message, QDBusVariant(DND))
        else:
            message.setDelayedReply(True)
            QDBusConnection.sessionBus().send(message.createErrorReply("org.freedesktop.DBus.Error.UnknownProperty", name))


@pyqtClassInfo("D-Bus Interface", "fr.emersion.Mako")
class Mako(QDBusAbstractAdaptor):
    @pyqtSlot(QDBusMessage)
    def ListModes(self, message):
        asked(message, "ListModes")
        reply(message, ["default", "do-not-disturb"] if DND else ["default"])


@pyqtClassInfo("D-Bus Interface", "org.erikreider.swaync.cc")
class Swaync(QDBusAbstractAdaptor):
    @pyqtSlot(QDBusMessage)
    def GetDnd(self, message):
        asked(message, "GetDnd")
        reply(message, DND)


@pyqtClassInfo("D-Bus Interface", "org.xfce.Xfconf")
class Xfconf(QDBusAbstractAdaptor):
    @pyqtSlot(str, str, QDBusMessage)
    def GetProperty(self, channel, prop, message):
        asked(message, f"GetProperty {channel} {prop}")
        if args.dnd == "unset" or (channel, prop) != ("xfce4-notifyd", "/do-not-disturb"):
            message.setDelayedReply(True)
            QDBusConnection.sessionBus().send(message.createErrorReply("org.xfce.Xfconf.Error.PropertyNotFound", f"{prop} does not exist"))
        else:
            reply(message, QDBusVariant(DND))


app = QCoreApplication([])
bus = QDBusConnection.sessionBus()
objects = []


def serve(path: str, service: str, *adaptors) -> None:
    root = QObject()
    for adaptor in adaptors:
        adaptor(root)
    objects.append(root)
    assert bus.registerObject(path, root, QDBusConnection.RegisterOption.ExportAdaptors)
    assert bus.registerService(service) or service in bus.interface().registeredServiceNames().value()


serve(PATH, "org.freedesktop.Notifications", Notifications, Properties)
if args.name == "mako":
    serve("/fr/emersion/Mako", "org.freedesktop.Notifications", Mako)
if args.name == "SwayNotificationCenter" and not args.not_own:
    serve("/org/erikreider/swaync/cc", "org.erikreider.swaync.cc", Swaync)
if args.name == "Xfce Notify Daemon" and not args.not_own:
    serve("/org/xfce/Xfconf", "org.xfce.Xfconf", Xfconf)
print("ready", flush=True)
app.exec()
