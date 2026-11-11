"""The desktop's own notifications on Linux: org.freedesktop.Notifications, straight over D-Bus.

Qt's QSystemTrayIcon.showMessage goes through the tray: with no tray (stock GNOME, without the AppIndicator
extension) it shows nothing, though Qt says it can. Every Linux desktop has a notification service, tray or not.
https://specifications.freedesktop.org/notification-spec/latest/protocol.html
"""

from __future__ import annotations

SERVICE = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"
APP_ID = "io.github.RandyNorthrup.chatmon"  # the .desktop file's name, so the desktop knows whose it is


def message(title: str, body: str):
    """Notify(app_name s, replaces_id u, app_icon s, summary s, body s, actions as, hints a{sv}, timeout i)."""
    from PyQt6.QtDBus import QDBusMessage

    msg = QDBusMessage.createMethodCall(SERVICE, PATH, SERVICE, "Notify")
    hints = {"desktop-entry": APP_ID}  # a map of variants: a{sv}
    msg.setArguments(["Chatmon", _typed(0, "UInt"), APP_ID, title, body, _typed([], "QStringList"), hints, -1])
    return msg


def _typed(value, type_name: str):
    """`value` as D-Bus's own type (an unsigned int, a string list), not Python's nearest."""
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
