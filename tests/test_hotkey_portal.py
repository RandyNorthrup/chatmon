"""The global shortcut on Wayland (shortcutportal.py, through libdbus.py) against a pretend GlobalShortcuts portal on
a private D-Bus (tests/fake_shortcuts_portal.py), with dbus-monitor reading what went over the wire on its own."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chatmon import hotkey, libdbus, shortcutportal

HERE = Path(__file__).resolve().parent

needs_a_bus = pytest.mark.skipif(
    not sys.platform.startswith("linux") or not shutil.which("dbus-run-session") or not shutil.which("dbus-monitor"),
    reason="Linux with dbus-run-session and dbus-monitor",
)


def test_the_keys_are_asked_for_in_the_xdg_shortcuts_format():
    trigger = shortcutportal.xdg_trigger
    assert trigger(hotkey.parse("Ctrl+Alt+Space")) == "CTRL+ALT+space"
    assert trigger(hotkey.parse("Meta+Shift+F5", "linux")) == "SHIFT+LOGO+F5"
    assert trigger(hotkey.parse("Ctrl+Shift+Return")) == "CTRL+SHIFT+Return"  # the spec's own example, CTRL+ALT+Return's kin
    assert trigger(hotkey.parse("Alt+/")) == "ALT+slash"


def test_signatures_split_into_their_complete_types():
    assert libdbus.complete_types("oa(sa{sv})sa{sv}") == ["o", "a(sa{sv})", "s", "a{sv}"]
    assert libdbus.complete_types("osta{sv}") == ["o", "s", "t", "a{sv}"]
    assert libdbus.complete_types("") == []
    with pytest.raises(ValueError):
        libdbus.complete_types("a(s")
    assert [libdbus.guess(v) for v in (True, 3, 2 ** 40, 1.5, "x", libdbus.ObjectPath("/x"), {"a": 1}, ["a"])] == ["b", "i", "x", "d", "s", "o", "a{sv}", "as"]


CLIENT = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from PyQt6.QtCore import QCoreApplication, QTimer
app = QCoreApplication([])
from chatmon import hotkey
hk = hotkey.Hotkey(kind="portal")
got = {"pressed": 0, "bound": [], "failed": []}
def bound(how):
    got["bound"].append(how)
    QTimer.singleShot(1500, finish)  # time for both presses the portal sends: another session's, then this one's
def finish():
    hk.unregister()  # closes the session
    QTimer.singleShot(500, app.quit)
def failed(why):
    got["failed"].append(why)
    if sys.argv[2:] == ["again"] and len(got["failed"]) == 1:
        got["again"] = hk.register("Ctrl+Alt+K")  # the portal's thread is still there to ask
        return
    QTimer.singleShot(300, app.quit)
hk.pressed.connect(lambda: got.update(pressed=got["pressed"] + 1))
hk.bound.connect(bound)
hk.failed.connect(failed)
got["register"] = hk.register("Ctrl+Alt+Space")
QTimer.singleShot(15000, app.quit)
app.exec()
hk.close()
print(json.dumps(got))
"""


def run_on_a_private_bus(tmp_path: Path, mode: str | None, again: bool = False) -> tuple[dict, list[dict], str]:
    """Pretend portal (unless mode is None: no portal at all), dbus-monitor and the client, on a bus of their own."""
    log, ready, monitor = tmp_path / "asked.jsonl", tmp_path / "ready", tmp_path / "monitor.txt"
    fake = HERE / "fake_shortcuts_portal.py"
    portal = (f'"{sys.executable}" "{fake}" "{HERE.parent}" "{log}" {mode} > "{ready}" 2>&1 & fake=$!; '
              f'for i in $(seq 100); do grep -q ready "{ready}" 2>/dev/null && break; sleep 0.1; done; ') if mode else "fake=; "
    script = (portal + f'dbus-monitor --session > "{monitor}" 2>&1 & watching=$!; sleep 0.5; '
              f'"{sys.executable}" -c "$CLIENT" "{HERE.parent}"{" again" if again else ""}; kill $watching $fake 2>/dev/null; true')
    env = dict(os.environ, CLIENT=CLIENT, QT_QPA_PLATFORM="offscreen", PYTHONDONTWRITEBYTECODE="1")
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)  # a bus of its own: never the desktop's portal
    out = subprocess.run(["dbus-run-session", "--", "sh", "-c", script], capture_output=True, text=True, timeout=90, env=env)
    lines = out.stdout.strip().splitlines()
    assert lines, out.stderr + (ready.read_text() if ready.exists() else "")
    asked = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return json.loads(lines[-1]), asked, monitor.read_text() if monitor.exists() else ""


def bind_call(monitor: str) -> str:
    """dbus-monitor's account of the BindShortcuts call: from its header to the next message."""
    start = monitor.index("member=BindShortcuts")
    following = [monitor.find(word, start + 1) for word in ("\nmethod call", "\nsignal", "\nmethod return", "\nerror")]
    return monitor[start:min([f for f in following if f > 0], default=len(monitor))]


@needs_a_bus
def test_the_portal_binds_it_and_its_presses_reach_chatmon(tmp_path):
    got, asked, monitor = run_on_a_private_bus(tmp_path, "accept")
    assert got == {"pressed": 1, "bound": ["Ctrl+Alt+Space"], "failed": [], "register": None}  # another session's press ignored
    assert [a["method"] for a in asked] == ["CreateSession", "BindShortcuts", "Close"]
    assert asked[0]["signature"] == "a{sv}" and asked[0]["options"] == ["handle_token", "session_handle_token"]
    bind = asked[1]
    assert bind["signature"] == "oa(sa{sv})sa{sv}" and bind["parent"] == ""
    assert bind["shortcuts"] == [["chatmon-ask", {"description": "Open Chatmon's ask box", "preferred_trigger": "CTRL+ALT+space"}]]
    assert asked[2]["path"] == bind["session"]  # unregistering closed the session it bound
    wire = bind_call(monitor)  # dbus-monitor's own reading of the call
    for part in ('object path "' + bind["session"] + '"', "array [", "struct {", 'string "chatmon-ask"', 'string "preferred_trigger"',
                 'string "CTRL+ALT+space"', 'string "handle_token"'):
        assert part in wire, wire


@needs_a_bus
def test_a_shortcut_the_desktop_turns_down_is_reported(tmp_path):
    got, asked, _ = run_on_a_private_bus(tmp_path, "decline")
    assert got["register"] is None and got["pressed"] == 0 and got["bound"] == []
    assert got["failed"] == [shortcutportal.DECLINED]
    assert [a["method"] for a in asked] == ["CreateSession", "BindShortcuts", "Close"]


@needs_a_bus
def test_a_portal_answering_nonsense_fails_that_shortcut_and_the_next_can_still_be_asked(tmp_path):
    got, asked, _ = run_on_a_private_bus(tmp_path, "garbled", again=True)
    assert got["failed"] == [shortcutportal.BROKEN, shortcutportal.BROKEN] and got["again"] is None and got["pressed"] == 0
    assert [a["method"] for a in asked] == ["CreateSession", "BindShortcuts", "Close"] * 2
    assert asked[4]["shortcuts"][0][1]["preferred_trigger"] == "CTRL+ALT+k"


@needs_a_bus
@pytest.mark.parametrize("mode", [None, "no-shortcuts"])
def test_a_desktop_without_the_portal_says_how_to_do_it_instead(tmp_path, mode):
    got, asked, _ = run_on_a_private_bus(tmp_path, mode)
    assert got["register"] is None and got["failed"] == [hotkey.NO_PORTAL] and asked == []
    assert "chatmon ask" in hotkey.NO_PORTAL
