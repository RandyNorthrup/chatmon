"""A pretend Secret Service (org.freedesktop.secrets), for tests/test_keychain.py: run on a private session bus.
It keeps items in memory and answers as GNOME Keyring does, in the specification's own types, and writes each call
it gets, with the call's D-Bus signature, to the file named on its command line. `--locked`: its collection is
locked, so reading finds nothing unlocked and saving needs a prompt. https://specifications.freedesktop.org/secret-service/"""

import json
import sys

from PyQt6.QtCore import QByteArray, QCoreApplication, QMetaType, QObject, pyqtClassInfo, pyqtSlot
from PyQt6.QtDBus import QDBusAbstractAdaptor, QDBusArgument, QDBusConnection, QDBusMessage, QDBusObjectPath, QDBusVariant

LOG = sys.argv[1]
LOCKED = "--locked" in sys.argv
ROOT = "/org/freedesktop/secrets"
COLLECTION = ROOT + "/collection/login"
PROMPT = ROOT + "/prompt/1"
NO_PROMPT = "/"

items: dict[str, dict] = {}
sessions: set[str] = set()
kept: list[QObject] = []  # every object on the bus, held so Python doesn't free it
made = [0]


def log(message: QDBusMessage, **more) -> None:
    with open(LOG, "a") as out:
        out.write(json.dumps({"member": message.member(), "path": message.path(), "signature": message.signature(), **more}) + "\n")


def paths(found: list[str]) -> QDBusArgument:
    out = QDBusArgument()
    out.beginArray(QMetaType.fromName(b"QDBusObjectPath"))
    for p in found:
        out.add(QDBusObjectPath(p))
    out.endArray()
    return out


def answer(message: QDBusMessage, *args) -> None:
    QDBusConnection.sessionBus().send(message.createReply(list(args)))


def expose(path: str, adaptor) -> None:
    holder = QObject()
    holder.path = path
    adaptor(holder)
    kept.append(holder)
    assert QDBusConnection.sessionBus().registerObject(path, holder, QDBusConnection.RegisterOption.ExportAdaptors)


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.Secret.Service")
class Service(QDBusAbstractAdaptor):
    @pyqtSlot(QDBusMessage)
    def OpenSession(self, message):
        algorithm = message.arguments()[0]
        log(message, algorithm=algorithm)
        made[0] += 1
        path = f"{ROOT}/session/{made[0]}"
        sessions.add(path)
        expose(path, Session)
        answer(message, QDBusVariant(""), QDBusObjectPath(path))

    @pyqtSlot(QDBusMessage)
    def SearchItems(self, message):
        wanted = message.arguments()[0]
        log(message, attributes=wanted)
        found = [p for p, item in items.items() if all(item["attributes"].get(k) == v for k, v in wanted.items())]
        answer(message, paths([] if LOCKED else found), paths(found if LOCKED else []))

    @pyqtSlot(QDBusMessage)
    def Unlock(self, message):
        log(message, objects=message.arguments()[0])
        if LOCKED:
            answer(message, paths([]), QDBusObjectPath(PROMPT))
        else:
            answer(message, paths(message.arguments()[0]), QDBusObjectPath(NO_PROMPT))

    @pyqtSlot(QDBusMessage)
    def ReadAlias(self, message):
        log(message, alias=message.arguments()[0])
        answer(message, QDBusObjectPath(COLLECTION))


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.Secret.Collection")
class Collection(QDBusAbstractAdaptor):
    @pyqtSlot(QDBusMessage)
    def CreateItem(self, message):
        properties, secret, replace = message.arguments()
        attributes = properties.get("org.freedesktop.Secret.Item.Attributes")
        session, parameters, value, kind = secret
        log(message, attributes=attributes, label=properties.get("org.freedesktop.Secret.Item.Label"), session_open=session in sessions,
            content_type=kind, replace=replace)
        if LOCKED:
            answer(message, QDBusObjectPath(NO_PROMPT), QDBusObjectPath(PROMPT))
            return
        path = next((p for p, i in items.items() if i["attributes"] == attributes), None) if replace else None
        if path is None:
            made[0] += 1
            path = f"{COLLECTION}/{made[0]}"
            expose(path, Item)
        items[path] = {"attributes": dict(attributes), "secret": bytes(value), "type": kind}
        answer(message, QDBusObjectPath(path), QDBusObjectPath(NO_PROMPT))


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.Secret.Item")
class Item(QDBusAbstractAdaptor):
    @pyqtSlot(QDBusMessage)
    def GetSecret(self, message):
        session = message.arguments()[0]
        log(message, session_open=session in sessions)
        item = items[self.parent().path]
        out = QDBusArgument()
        out.beginStructure()
        out.add(QDBusObjectPath(session))
        out.add(QByteArray(b""))
        out.add(QByteArray(item["secret"]))
        out.add(item["type"])
        out.endStructure()
        answer(message, out)

    @pyqtSlot(QDBusMessage)
    def Delete(self, message):
        log(message)
        items.pop(self.parent().path, None)
        answer(message, QDBusObjectPath(NO_PROMPT))


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.Secret.Session")
class Session(QDBusAbstractAdaptor):
    @pyqtSlot(QDBusMessage)
    def Close(self, message):
        log(message)
        sessions.discard(self.parent().path)
        answer(message)


@pyqtClassInfo("D-Bus Interface", "org.freedesktop.Secret.Prompt")
class Prompt(QDBusAbstractAdaptor):
    @pyqtSlot(QDBusMessage)
    def Prompt(self, message):
        log(message)
        answer(message)


app = QCoreApplication([])
expose(ROOT, Service)
expose(COLLECTION, Collection)
expose(PROMPT, Prompt)
assert QDBusConnection.sessionBus().registerService("org.freedesktop.secrets")
print("ready", flush=True)
app.exec()
