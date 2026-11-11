"""Updates waiting, as PackageKit knows them: for a system whose package manager Chatmon doesn't ask itself.

A transaction on the system bus: CreateTransaction, then GetUpdates, which answers from what PackageKit already
knows (no download, no administrator: only installing asks for one), a Package signal for each update, and then
Finished. https://www.freedesktop.org/software/PackageKit/gtk-doc/api-reference.html
"""

from __future__ import annotations

from PyQt6.QtCore import QMetaType, QObject, QTimer, QVariant, pyqtSignal, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher, QDBusPendingReply

SERVICE = "org.freedesktop.PackageKit"
PATH = "/org/freedesktop/PackageKit"
TRANSACTION = "org.freedesktop.PackageKit.Transaction"
FILTER_NONE = 1 << 1  # a bitfield of PkFilterEnum: PK_FILTER_ENUM_NONE is 1
EXIT_SUCCESS = 1  # PkExitEnum
INFO_BLOCKED = 17  # PkInfoEnum: held back (a dependency can't be met), so not installable now
TIMEOUT_MS = 120_000


def present() -> bool:
    """PackageKit is on this system: running, or one the system bus starts when asked."""
    bus = QDBusConnection.systemBus()
    if not bus.isConnected():
        return False
    for method in ("ListNames", "ListActivatableNames"):
        reply = bus.call(QDBusMessage.createMethodCall("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", method))
        if reply.type() == QDBusMessage.MessageType.ReplyMessage and reply.arguments() and SERVICE in reply.arguments()[0]:
            return True
    return False


class UpdateCount(QObject):
    """Counts the updates waiting, once: `counted` says how many, or None if PackageKit couldn't tell."""

    counted = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._bus = QDBusConnection.systemBus()
        self._path: str | None = None
        self._count = 0
        self._done = False
        self._watchers: list[QDBusPendingCallWatcher] = []
        self._timer = QTimer(self, singleShot=True, interval=TIMEOUT_MS)
        self._timer.timeout.connect(lambda: self._finish(None))

    def start(self) -> None:
        if not self._bus.isConnected():
            QTimer.singleShot(0, lambda: self._finish(None))
            return
        self._timer.start()
        self._call(QDBusMessage.createMethodCall(SERVICE, PATH, SERVICE, "CreateTransaction"), self._created)

    def stop(self) -> None:
        """Not wanted any more (Chatmon is quitting): no answer comes."""
        self._done = True
        self._timer.stop()
        self._unlisten()

    def _call(self, message: QDBusMessage, then) -> None:
        watcher = QDBusPendingCallWatcher(self._bus.asyncCall(message, TIMEOUT_MS), self)
        self._watchers.append(watcher)
        watcher.finished.connect(lambda w: self._answered(w, then))

    def _answered(self, watcher: QDBusPendingCallWatcher, then) -> None:
        reply = QDBusPendingReply(watcher).reply()  # PyQt's watcher is the call: its answer, as a message
        watcher.deleteLater()
        if watcher in self._watchers:
            self._watchers.remove(watcher)
        if self._done:
            return
        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
            self._finish(None)
            return
        then(reply)

    def _created(self, reply: QDBusMessage) -> None:
        path = reply.arguments()[0] if reply.arguments() else None
        path = path.path() if hasattr(path, "path") else path  # a QDBusObjectPath
        if not path:
            self._finish(None)
            return
        self._path = str(path)
        # Listening before asking: the signals can't come before we hear them.
        for name, slot in (("Package", self._package), ("Finished", self._finished), ("ErrorCode", self._error)):
            self._bus.connect(SERVICE, self._path, TRANSACTION, name, slot)
        message = QDBusMessage.createMethodCall(SERVICE, self._path, TRANSACTION, "GetUpdates")
        message.setArguments([_uint64(FILTER_NONE)])
        self._call(message, lambda _reply: None)  # the answer is the signals

    @pyqtSlot(QDBusMessage)
    def _package(self, message: QDBusMessage) -> None:
        args = message.arguments()
        if args and args[0] != INFO_BLOCKED:
            self._count += 1

    @pyqtSlot(QDBusMessage)
    def _finished(self, message: QDBusMessage) -> None:
        args = message.arguments()
        self._finish(self._count if args and args[0] == EXIT_SUCCESS else None)

    @pyqtSlot(QDBusMessage)
    def _error(self, _message: QDBusMessage) -> None:
        self._finish(None)

    def _finish(self, count: int | None) -> None:
        if self._done:
            return
        self._done = True
        self._timer.stop()
        self._unlisten()
        self.counted.emit(count)

    def _unlisten(self) -> None:
        if self._path:
            for name, slot in (("Package", self._package), ("Finished", self._finished), ("ErrorCode", self._error)):
                self._bus.disconnect(SERVICE, self._path, TRANSACTION, name, slot)
            self._path = None


def _uint64(n: int) -> QVariant:
    v = QVariant(n)
    v.convert(QMetaType(QMetaType.Type.ULongLong.value))
    return v
