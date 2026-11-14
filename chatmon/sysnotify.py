"""The desktop's own notifications on Linux: org.freedesktop.Notifications, straight over D-Bus.

Qt's QSystemTrayIcon.showMessage goes through the tray: with no tray (stock GNOME, without the AppIndicator
extension) it shows nothing, though Qt says it can. Every Linux desktop has a notification service, tray or not.
https://specifications.freedesktop.org/notification-spec/latest/protocol.html

What a notification is for decides how it's sent (Notifier):
- Read aloud, for a screen reader Chatmon can't reach itself: transient, so it stays out of the notification
  history, and each one replaces the one before, so a busy afternoon doesn't fill the list.
- An alert waiting under a full-screen app: urgency 2 (critical), which the desktop shows until it's dismissed.
- A bubble's buttons: the notification's actions, so they can be pressed there; the server's ActionInvoked
  says which, and the button's own action runs.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, pyqtSlot

try:  # a slot taking the D-Bus message itself, where there's QtDBus (this module is imported where there isn't too)
    from PyQt6.QtDBus import QDBusMessage

    _message_slot = pyqtSlot(QDBusMessage)
except ImportError:
    def _message_slot(method):
        return method

SERVICE = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"
APP_ID = "io.github.RandyNorthrup.chatmon"  # the .desktop file's name, so the desktop knows whose it is
URGENCY_LOW, URGENCY_NORMAL, URGENCY_CRITICAL = 0, 1, 2  # the spec's urgency levels, sent as a byte


def message(title: str, body: str, *, replaces: int = 0, actions: list[str] | None = None, urgency: int | None = None,
            transient: bool = False):
    """Notify(app_name s, replaces_id u, app_icon s, summary s, body s, actions as, hints a{sv}, timeout i)."""
    from PyQt6.QtDBus import QDBusMessage

    msg = QDBusMessage.createMethodCall(SERVICE, PATH, SERVICE, "Notify")
    msg.setArguments(["Chatmon", _typed(replaces, "UInt"), APP_ID, title, body, _typed(list(actions or []), "QStringList"),
                      hints(urgency, transient), -1])
    return msg


def hints(urgency: int | None = None, transient: bool = False) -> dict:
    """The hints map (a{sv}): whose notification it is, and, if given, its urgency (a byte, as the spec has it)
    and whether it's transient (kept out of the history)."""
    out: dict = {"desktop-entry": APP_ID}
    if urgency is not None:
        out["urgency"] = _typed(urgency, "UChar")
    if transient:
        out["transient"] = True
    return out


def actions_for(buttons: list[str]) -> list[str]:
    """Buttons as the spec's actions: each one's key, its place ("0", "1"...), then the label shown."""
    out: list[str] = []
    for i, label in enumerate(buttons):
        out += [str(i), label]
    return out


def _typed(value, type_name: str):
    """`value` as D-Bus's own type (an unsigned int, a byte, a string list), not Python's nearest."""
    from PyQt6.QtCore import QMetaType, QVariant

    v = QVariant(value)
    v.convert(QMetaType(getattr(QMetaType.Type, type_name).value))
    return v


def send(title: str, body: str) -> bool:
    """Shown by the desktop (it keeps it, and follows your Do Not Disturb); False if there's no one to show it."""
    try:
        from PyQt6.QtDBus import QDBusConnection

        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            return False
        return bus.send(message(title, body))  # no waiting for the answer: the id it sends back isn't needed
    except (ImportError, RuntimeError, TypeError, AttributeError):
        return False


class Notifier(QObject):
    """Chatmon's notifications, one Notifier per app. `read_aloud` and `alert` return False if there's no
    notification service to show them. `pressed(index)`, if given, runs when one of the notification's buttons is
    pressed there, with that button's place in `buttons`. Nothing waits: the id each notification gets comes back
    in a moment (a read-aloud one sent before the last one's id is back can't replace it, and shows beside it)."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.read_aloud_id = 0  # the read-aloud notification showing, which the next replaces
        self._pressed: dict[int, Callable[[int], None]] = {}  # notification id: what its buttons do
        self._bus = None
        try:
            from PyQt6.QtDBus import QDBusConnection
        except ImportError:
            return
        bus = QDBusConnection.sessionBus()
        if bus.isConnected():
            self._bus = bus
            bus.connect(SERVICE, PATH, SERVICE, "ActionInvoked", self._action_invoked)
            bus.connect(SERVICE, PATH, SERVICE, "NotificationClosed", self._closed)

    def read_aloud(self, title: str, body: str, buttons: list[str] | None = None, pressed: Callable[[int], None] | None = None) -> bool:
        return self._send(message(title, body, replaces=self.read_aloud_id, actions=actions_for(buttons or []), transient=True), pressed, True)

    def alert(self, title: str, body: str, buttons: list[str] | None = None, pressed: Callable[[int], None] | None = None,
              urgency: int = URGENCY_CRITICAL) -> bool:
        return self._send(message(title, body, actions=actions_for(buttons or []), urgency=urgency), pressed, False)

    def _send(self, msg, pressed, read_aloud: bool) -> bool:
        if self._bus is None:
            return False
        from PyQt6.QtDBus import QDBusMessage, QDBusPendingCallWatcher, QDBusPendingReply

        watcher = QDBusPendingCallWatcher(self._bus.asyncCall(msg, 5000), self)

        def sent(w: QDBusPendingCallWatcher) -> None:
            reply = QDBusPendingReply(w).reply()
            w.deleteLater()
            if reply.type() == QDBusMessage.MessageType.ReplyMessage and reply.arguments():
                self.shown(int(reply.arguments()[0]), pressed, read_aloud)

        watcher.finished.connect(sent)
        return True

    def shown(self, notification: int, pressed: Callable[[int], None] | None, read_aloud: bool) -> None:
        """The server showed it, under this id."""
        if read_aloud:
            if self.read_aloud_id and self.read_aloud_id != notification:
                self._pressed.pop(self.read_aloud_id, None)  # replaced, or left beside it: its buttons are done
            self.read_aloud_id = notification
        if pressed is not None:
            self._pressed[notification] = pressed

    @_message_slot
    def _action_invoked(self, message) -> None:
        """ActionInvoked(id u, action_key s): sent for every app's notifications; only ours are answered."""
        args = message.arguments()
        if len(args) < 2:
            return
        pressed = self._pressed.get(int(args[0]))
        key = str(args[1])
        if pressed is not None and key.isdigit():  # "default" (the notification itself clicked) isn't a button
            pressed(int(key))

    @_message_slot
    def _closed(self, message) -> None:
        """NotificationClosed(id u, reason u): dismissed, timed out or replaced; its buttons are done with."""
        args = message.arguments()
        if not args:
            return
        notification = int(args[0])
        self._pressed.pop(notification, None)
        if notification == self.read_aloud_id:
            self.read_aloud_id = 0
