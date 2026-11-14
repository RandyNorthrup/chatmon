"""A pretend GlobalShortcuts portal, for tests/test_hotkey_portal.py: run on a private session bus. It answers
CreateSession and BindShortcuts as xdg-desktop-portal does (a Request path at once, its Response signal after), sends
Activated for the shortcut it bound (and one for a session that isn't the client's), and writes what it was asked to
the log named on its command line.

QtDBus can't receive BindShortcuts' array of structs, so it talks through chatmon/libdbus.py; the test checks what went
over the wire independently, with dbus-monitor.

usage: fake_shortcuts_portal.py REPO LOG MODE, where MODE is accept, decline, garbled (a Response in the wrong shape)
or no-shortcuts (a portal without GlobalShortcuts)."""

import json
import sys
import time

sys.path.insert(0, sys.argv[1])

from chatmon import libdbus  # noqa: E402

LOG, MODE = sys.argv[2], sys.argv[3]
PATH = "/org/freedesktop/portal/desktop"
SHORTCUTS = "org.freedesktop.portal.GlobalShortcuts"
REQUEST = "org.freedesktop.portal.Request"

bus = libdbus.Bus()
assert bus.request_name("org.freedesktop.portal.Desktop")
later: list = []  # (when, what to do)


def log(entry: dict) -> None:
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def plain(value):
    """What came in, as JSON can hold it."""
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def handle(message: libdbus.Message) -> None:
    sender = message.sender.lstrip(":").replace(".", "_")
    now = time.monotonic()
    if (message.interface, message.member) == ("org.freedesktop.DBus.Properties", "Get"):
        if MODE == "no-shortcuts" or message.args[0] != SHORTCUTS:
            bus.reply_error(message, "org.freedesktop.DBus.Error.UnknownInterface", "No such interface")
        else:
            bus.reply(message, "v", [libdbus.Variant("u", 2)])
    elif message.member == "CreateSession":
        options = message.args[0]
        request = f"{PATH}/request/{sender}/{options['handle_token']}"
        session = f"{PATH}/session/{sender}/{options['session_handle_token']}"
        log({"method": "CreateSession", "signature": message.signature, "options": sorted(options)})
        bus.reply(message, "o", [libdbus.ObjectPath(request)])
        later.append((now + 0.1, lambda: bus.emit(request, REQUEST, "Response", "ua{sv}", [0, {"session_handle": libdbus.Variant("s", session)}])))
    elif message.member == "BindShortcuts":
        session, shortcuts, parent, options = message.args
        request = f"{PATH}/request/{sender}/{options['handle_token']}"
        log({"method": "BindShortcuts", "signature": message.signature, "session": session, "shortcuts": plain(shortcuts), "parent": parent})
        bus.reply(message, "o", [libdbus.ObjectPath(request)])
        if MODE == "decline":
            later.append((now + 0.1, lambda: bus.emit(request, REQUEST, "Response", "ua{sv}", [1, {}])))
            return
        bound = [(shortcut_id, {"description": libdbus.Variant("s", props["description"]), "trigger_description": libdbus.Variant("s", "Ctrl+Alt+Space")})
                 for shortcut_id, props in shortcuts]
        if MODE == "garbled":  # a portal answering in a shape the specification doesn't have
            later.append((now + 0.1, lambda: bus.emit(request, REQUEST, "Response", "ua{sv}", [0, {"shortcuts": libdbus.Variant("s", "nonsense")}])))
            return
        later.append((now + 0.1, lambda: bus.emit(request, REQUEST, "Response", "ua{sv}", [0, {"shortcuts": libdbus.Variant("a(sa{sv})", bound)}])))
        # Someone else's session pressing the same shortcut id: not the client's to hear.
        later.append((now + 0.3, lambda: bus.emit(PATH, SHORTCUTS, "Activated", "osta{sv}", [libdbus.ObjectPath(f"{PATH}/session/other/x"), "chatmon-ask", 1, {}])))
        later.append((now + 0.5, lambda: bus.emit(PATH, SHORTCUTS, "Activated", "osta{sv}", [libdbus.ObjectPath(session), "chatmon-ask", 2, {}])))
    elif (message.interface, message.member) == ("org.freedesktop.portal.Session", "Close"):
        log({"method": "Close", "path": message.path})
        bus.reply(message)
    else:
        bus.reply_error(message, "org.freedesktop.DBus.Error.UnknownMethod", message.member)


print("ready", flush=True)
while True:
    due = [item for item in later if item[0] <= time.monotonic()]
    for item in due:
        later.remove(item)
        item[1]()
    message = bus.next_message(50)
    if message is not None and message.kind == libdbus.METHOD_CALL:
        handle(message)
