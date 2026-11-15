"""The global shortcut on Wayland: the GlobalShortcuts portal (xdg-desktop-portal), where the desktop has one.

An app can't grab keys on Wayland; it asks the desktop. CreateSession makes a session, BindShortcuts asks for the
shortcut with the keys Chatmon would like (the desktop may ask you, and has the last word on the keys), and the
portal sends Activated while it's held. Each request is answered later, with a Response signal on a Request object.
https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html
https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Request.html

QtDBus can't send BindShortcuts' array of structs from Python, so this talks through libdbus (libdbus.py), on a
thread of its own: nothing here ever waits on the screen's thread. What it hears goes to `tell(what, detail)` from
that thread: ("pressed", ""), ("bound", how to press it) or ("failed", why)."""

from __future__ import annotations

import queue
import secrets
import threading
from collections.abc import Callable

from . import libdbus
from .hotkey import KEYS, NO_PORTAL, Combo
from .i18n import N_, _

SERVICE = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
SHORTCUTS = "org.freedesktop.portal.GlobalShortcuts"
REQUEST = "org.freedesktop.portal.Request"
SESSION = "org.freedesktop.portal.Session"
SHORTCUT_ID = "chatmon-ask"
# What the desktop lists the shortcut as, and why it failed: each shown translated, _(DESCRIPTION) and so on.
DESCRIPTION = N_("Open Chatmon's ask box")
OK, CANCELLED = 0, 1  # Response codes; 2: it ended some other way
DECLINED = N_("Your desktop didn't set the shortcut: it was turned down, or those keys are taken.")
BROKEN = N_("Your desktop couldn't set the shortcut.")
CLOSED = N_("Your desktop took Chatmon's shortcut away.")
NO_BUS = N_("Chatmon couldn't reach your desktop's session bus.")
XDG_MODIFIERS = (("ctrl", "CTRL"), ("alt", "ALT"), ("shift", "SHIFT"), ("meta", "LOGO"))
WAIT_MS = 200  # how long the thread waits for a message before looking for work from the screen's thread


def xdg_trigger(combo: Combo) -> str:
    """The keys in the XDG shortcuts format the portal takes: "CTRL+ALT+space"."""
    return "+".join([name for modifier, name in XDG_MODIFIERS if modifier in combo.modifiers] + [KEYS[combo.key].x11])


def _variant_text(value) -> str:
    return value if isinstance(value, str) else ""


class PortalShortcut:
    """One shortcut through the portal. grab() and release() hand work to the thread and return at once."""

    def __init__(self, tell: Callable[[str, str], None]):
        self._tell = tell
        self._work: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="chatmon-shortcut", daemon=True)
        self._thread.start()

    # -- the screen's thread

    def grab(self, combo: Combo) -> str | None:
        """Ask for the shortcut; the answer comes through `tell`. A new one replaces the old: the desktop binds a
        session's shortcuts once, so it's a new session."""
        self._work.put(("bind", combo))
        return None

    def release(self) -> None:
        self._work.put(("release", None))

    def close(self) -> None:
        self._work.put(("close", None))
        self._thread.join(5)

    # -- the portal's thread

    def _run(self) -> None:
        try:
            self._bus = libdbus.Bus()
        except (OSError, libdbus.Failure):
            self._fail_all(_(NO_BUS))
            return
        self._session: str | None = None  # the session bound, or being bound
        self._waiting: dict[str, Callable[[int, dict], None]] = {}  # Request path -> what to do with its Response
        self._pending: Combo | None = None
        try:
            self._bus.add_match(f"type='signal',sender='{SERVICE}',interface='{SHORTCUTS}'")
            self._bus.add_match(f"type='signal',sender='{SERVICE}',interface='{SESSION}',member='Closed'")
            while True:
                try:
                    what, combo = self._work.get_nowait()
                except queue.Empty:
                    what = combo = None
                if what == "close":
                    self._close_session()
                    return
                message = None
                try:
                    if what == "release":
                        self._close_session()
                    elif what == "bind":
                        self._close_session()
                        self._start(combo)
                    message = self._bus.next_message(WAIT_MS)
                    if message is not None:
                        self._heard(message)
                except (libdbus.Failure, TypeError, ValueError, KeyError, IndexError, AttributeError):
                    # The portal refused a call, or answered in a shape it shouldn't: this shortcut failed, but the
                    # thread carries on for the next one.
                    self._close_session()
                    self._tell("failed", _(BROKEN))
                finally:
                    if message is not None:
                        message.free()
        except (ConnectionError, libdbus.Failure):
            self._tell("failed", _(NO_BUS))
        finally:
            self._bus.close()

    def _fail_all(self, why: str) -> None:
        """Without a bus, every request fails: say so for each, until closed."""
        while True:
            what, _ = self._work.get()
            if what == "close":
                return
            if what == "bind":
                self._tell("failed", why)

    def _request(self, method: str, signature: str, args: list, options: dict, then: Callable[[int, dict], None]) -> None:
        """Call one of the portal's request methods, listening on its Request first so its Response can't come
        before the listening does (its path is known from the token)."""
        token = "chatmon_" + secrets.token_hex(8)
        sender = self._bus.unique_name.lstrip(":").replace(".", "_")
        expected = f"{PATH}/request/{sender}/{token}"
        self._bus.add_match(f"type='signal',sender='{SERVICE}',interface='{REQUEST}',member='Response',path='{expected}'")
        self._waiting[expected] = then
        options = {**options, "handle_token": libdbus.Variant("s", token)}
        handle = self._bus.call(SERVICE, PATH, SHORTCUTS, method, signature + "a{sv}", [*args, options])
        path = str(handle[0]) if handle else expected
        if path != expected:  # an older portal makes its own path: listen there instead
            self._waiting[path] = self._waiting.pop(expected)
            self._bus.add_match(f"type='signal',sender='{SERVICE}',interface='{REQUEST}',member='Response',path='{path}'")

    def _start(self, combo: Combo) -> None:
        try:
            version = self._bus.call(SERVICE, PATH, "org.freedesktop.DBus.Properties", "Get", "ss", [SHORTCUTS, "version"], 2000)
        except libdbus.Failure:  # no portal, or one without GlobalShortcuts
            self._tell("failed", _(NO_PORTAL))
            return
        if not version:
            self._tell("failed", _(NO_PORTAL))
            return
        self._pending = combo
        token = "chatmon_" + secrets.token_hex(8)
        self._request("CreateSession", "", [], {"session_handle_token": libdbus.Variant("s", token)}, self._session_made)

    def _session_made(self, code: int, results: dict) -> None:
        combo, self._pending = self._pending, None
        session = _variant_text(results.get("session_handle"))  # typed 's' for old portals' sake; an object path
        if code != OK or not session or combo is None:
            self._tell("failed", _(BROKEN))
            return
        self._session = session
        shortcut = (SHORTCUT_ID, {"description": libdbus.Variant("s", _(DESCRIPTION)), "preferred_trigger": libdbus.Variant("s", xdg_trigger(combo))})
        self._request("BindShortcuts", "oa(sa{sv})s", [libdbus.ObjectPath(session), [shortcut], ""], {},
                      lambda code, results: self._bound(combo, code, results))

    def _bound(self, combo: Combo, code: int, results: dict) -> None:
        if code != OK:
            self._close_session()
            self._tell("failed", _(DECLINED) if code == CANCELLED else _(BROKEN))
            return
        ours = [props for shortcut_id, props in results.get("shortcuts") or [] if shortcut_id == SHORTCUT_ID]
        if not ours:  # bound, but without Chatmon's: turned down
            self._close_session()
            self._tell("failed", _(DECLINED))
            return
        self._tell("bound", _variant_text(ours[0].get("trigger_description")) or combo.text())

    def _heard(self, message: libdbus.Message) -> None:
        if message.kind != libdbus.SIGNAL:
            return
        if message.interface == REQUEST and message.member == "Response" and message.path in self._waiting:
            then = self._waiting.pop(message.path)
            code = message.args[0] if message.args else 2
            results = message.args[1] if len(message.args) > 1 and isinstance(message.args[1], dict) else {}
            then(code, results)
        elif message.interface == SHORTCUTS and message.member == "Activated" and len(message.args) >= 2:
            if self._session and str(message.args[0]) == self._session and message.args[1] == SHORTCUT_ID:
                self._tell("pressed", "")
        elif message.interface == SHORTCUTS and message.member == "ShortcutsChanged" and len(message.args) >= 2:
            if self._session and str(message.args[0]) == self._session:
                for shortcut_id, props in message.args[1]:
                    if shortcut_id == SHORTCUT_ID and _variant_text(props.get("trigger_description")):
                        self._tell("bound", props["trigger_description"])
        elif message.interface == SESSION and message.member == "Closed" and self._session and message.path == self._session:
            self._session = None
            self._tell("failed", _(CLOSED))

    def _close_session(self) -> None:
        self._waiting.clear()
        self._pending = None
        if self._session:
            session, self._session = self._session, None
            try:
                self._bus.call(SERVICE, session, SESSION, "Close", "", [], 2000)
            except libdbus.Failure:
                pass  # already gone
