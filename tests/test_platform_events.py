"""What the platforms say and how Chatmon answers in kind (M4A): Linux notifications that stay out of the history and
carry buttons, screen-reader announcements on Windows and macOS, and macOS's sleep, wake and Low Power Mode.

The parts that need a platform's own services run where it is: a UI Automation client on Windows
(tests/uia_client.py, with comtypes), pretend notification servers on a private D-Bus on Linux
(tests/fake_notifications.py). The rest builds and reads the real D-Bus messages and Qt objects everywhere."""

import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
windows = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
linux_bus = pytest.mark.skipif(not sys.platform.startswith("linux") or not shutil.which("dbus-run-session"), reason="Linux with dbus-run-session")


# -- Linux notifications (sysnotify.Notifier, M4A-07)


def test_read_aloud_notifications_are_transient_and_alerts_urgent(qapp):
    pytest.importorskip("PyQt6.QtDBus")
    from chatmon import sysnotify

    hints = sysnotify.hints(transient=True)
    assert hints["transient"] is True and "urgency" not in hints
    urgent = sysnotify.hints(urgency=sysnotify.URGENCY_CRITICAL)
    assert urgent["urgency"].typeName() == "uchar" and urgent["urgency"].value() in (2, b"\x02")  # a byte, as the spec has it
    assert "transient" not in urgent and urgent["desktop-entry"] == sysnotify.APP_ID
    message = sysnotify.message("Reminder", "Stretch.", replaces=7, actions=sysnotify.actions_for(["Snooze 10 min", "Done"]), transient=True)
    name, replaces, icon, title, body, actions, sent_hints, timeout = message.arguments()
    assert (name, replaces, title, body, timeout) == ("Chatmon", 7, "Reminder", "Stretch.", -1)
    assert actions == ["0", "Snooze 10 min", "1", "Done"] and sent_hints["transient"] is True


def _invoked(notification: int, key: str):
    from PyQt6.QtDBus import QDBusMessage

    from chatmon import sysnotify

    signal = QDBusMessage.createSignal(sysnotify.PATH, sysnotify.SERVICE, "ActionInvoked")
    signal.setArguments([notification, key])
    return signal


def _closed(notification: int):
    from PyQt6.QtDBus import QDBusMessage

    from chatmon import sysnotify

    signal = QDBusMessage.createSignal(sysnotify.PATH, sysnotify.SERVICE, "NotificationClosed")
    signal.setArguments([notification, 1])
    return signal


def test_a_notifications_buttons_are_answered_for_ours_alone(qapp):
    pytest.importorskip("PyQt6.QtDBus")
    from chatmon import sysnotify

    notifier = sysnotify.Notifier()
    pressed = []
    notifier.shown(11, lambda i: pressed.append(("first", i)), read_aloud=True)
    assert notifier.read_aloud_id == 11
    notifier._action_invoked(_invoked(11, "1"))  # Done, on our notification
    notifier._action_invoked(_invoked(99, "0"))  # another app's notification
    notifier._action_invoked(_invoked(11, "default"))  # the notification itself clicked: not a button
    assert pressed == [("first", 1)]
    notifier.shown(12, lambda i: pressed.append(("second", i)), read_aloud=True)  # the next read-aloud one replaced it
    notifier._action_invoked(_invoked(11, "0"))
    notifier._action_invoked(_invoked(12, "0"))
    assert pressed == [("first", 1), ("second", 0)] and notifier.read_aloud_id == 12
    notifier.shown(20, lambda i: pressed.append(("alert", i)), read_aloud=False)
    notifier._closed(_closed(12))  # it timed out: the next read-aloud one replaces nothing
    notifier._action_invoked(_invoked(12, "0"))
    notifier._action_invoked(_invoked(20, "0"))
    assert notifier.read_aloud_id == 0 and pressed[-1] == ("alert", 0) and len(pressed) == 3


# -- Screen readers (a11y.announce, M4A-08 and M4A-09)


def test_announcements_fall_back_to_the_notification(qapp, monkeypatch):
    """Without UI Automation (Qt's offscreen platform has no real windows) or with Chatmon behind other apps, the
    notification says it; a reader with a way of its own uses it; no reader, nothing."""
    from chatmon import a11y

    notified = []
    assert a11y.announce(None, "Stretch.", notify=lambda: notified.append(True)) == "" and notified == []
    assert a11y.announce(a11y.Reader("Narrator"), "Stretch.", notify=lambda: notified.append(True)) == "notification"
    assert notified == [True]
    said = []
    orca = a11y.Reader("Orca", lambda words, important: said.append((words, important)))
    assert a11y.announce(orca, "Stretch.", important=True, notify=lambda: notified.append(True)) == "spoken"
    assert said == [("Stretch.", True)] and notified == [True]
    assert a11y.announce(a11y.Reader("a screen reader"), "Stretch.") == ""  # nothing to say it with


@windows
def test_on_windows_announcements_need_chatmon_in_front(qapp, monkeypatch):
    from chatmon import a11y, winuia

    raised = []
    monkeypatch.setattr(winuia, "say", lambda words, important: raised.append(words) or True)
    notified = []
    monkeypatch.setattr(winuia, "in_front", lambda: False)  # NVDA would ignore it: the notification instead
    assert a11y.announce(a11y.Reader("Narrator"), "Stretch.", notify=lambda: notified.append(True)) == "notification"
    assert raised == [] and notified == [True]
    monkeypatch.setattr(winuia, "in_front", lambda: True)
    assert a11y.announce(a11y.Reader("Narrator"), "Stretch.", notify=lambda: notified.append(True)) == "uia"
    assert raised == ["Stretch."] and notified == [True]


@windows
def test_chatmon_in_front_is_told_by_the_foreground_windows_process():
    from chatmon import winuia

    assert winuia.in_front() in (True, False)  # the console or another app is in front while tests run
    assert isinstance(winuia.in_front(), bool)


@windows
def test_the_uia_provider_answers_as_ui_automation_asks(qapp):
    """The COM object itself, called through its vtable as UI Automation calls it."""
    from chatmon import winuia

    provider = winuia.Provider(0)
    vtable = provider._object.vtable.contents
    me = provider.pointer
    out = ctypes.c_void_p()
    simple = (ctypes.c_ubyte * 16).from_buffer_copy(winuia.IID_IRAW_ELEMENT_PROVIDER_SIMPLE.bytes_le)
    assert vtable.QueryInterface(me, ctypes.addressof(simple), ctypes.byref(out)) == winuia.S_OK and out.value == me
    fragment = (ctypes.c_ubyte * 16).from_buffer_copy(bytes.fromhex("f7063da8e8590e4fa6aeb65fa5f8f2a8"))  # another interface
    assert vtable.QueryInterface(me, ctypes.addressof(fragment), ctypes.byref(out)) == winuia.E_NOINTERFACE and not out.value
    options = ctypes.c_int()
    assert vtable.get_ProviderOptions(me, ctypes.byref(options)) == winuia.S_OK and options.value == winuia.SERVER_SIDE_PROVIDER
    value = winuia.VARIANT()
    vtable.GetPropertyValue(me, winuia.UIA_NAME, ctypes.byref(value))
    assert value.vt == winuia.VT_BSTR and ctypes.wstring_at(value.value.bstrVal) == "Chatmon announcements"
    provider._oleaut.SysFreeString(value.value.bstrVal)
    vtable.GetPropertyValue(me, 30003, ctypes.byref(value))  # ControlType: left to the window's host provider
    assert value.vt == winuia.VT_EMPTY
    pattern = ctypes.c_void_p(1)
    assert vtable.GetPatternProvider(me, 10000, ctypes.byref(pattern)) == winuia.S_OK and not pattern.value


ANNOUNCER = r"""
import os, sys, time
sys.path.insert(0, sys.argv[1])
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from chatmon import a11y, winuia

def pump(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)

print("prepared", winuia.prepare(), flush=True)
print("window", winuia._announcer.hwnd, flush=True)
print("too soon", winuia.say("Too soon.", False), flush=True)  # UI Automation hasn't taken the window in yet
pump(winuia.READY_AFTER + 0.3)
winuia.in_front = lambda: True  # as with the ask box open: Chatmon is the app in front
notified, routes = [], set()
for attempt in range(4):  # a client just started may take a moment to listen to a new process: again until heard
    routes.add(a11y.announce(a11y.Reader("Narrator"), sys.argv[2], important=True, notify=lambda: notified.append(1)))
    pump(1.5)
    if os.path.exists(sys.argv[3]) and os.path.getsize(sys.argv[3]):
        break
print("routes", sorted(routes), notified, flush=True)
pump(2)  # still answering UI Automation while the test asks the window's name
"""


@windows
def test_a_ui_automation_client_hears_the_announcement(tmp_path):
    """End to end, as Narrator, NVDA or JAWS hear it: a UI Automation client in another process gets the
    notification event with the words, from the announcer window on Qt's real Windows platform."""
    pytest.importorskip("comtypes")
    log, words = tmp_path / "heard.jsonl", "Reminder. Stretch your legs."
    client = subprocess.Popen([sys.executable, str(HERE / "uia_client.py"), "listen", str(log), "40"], stdout=subprocess.PIPE, text=True)
    env = dict(os.environ, QT_QPA_PLATFORM="windows")
    announcer = None
    try:
        assert client.stdout.readline().strip() == "ready"
        announcer = subprocess.Popen([sys.executable, "-c", ANNOUNCER, str(HERE.parent), words, str(log)], stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, env=env)
        said = [announcer.stdout.readline().strip() for _ in range(4)]
        assert said[0] == "prepared True" and said[1].startswith("window ") and said[2:] == ["too soon False", "routes ['uia'] []"], said
        # The window's element is the announcer's own provider (it names itself), not Qt's or the bare window's.
        name = subprocess.run([sys.executable, str(HERE / "uia_client.py"), "name", said[1].split()[1]], capture_output=True, text=True, timeout=30)
        announcer.wait(30)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not (log.exists() and log.read_text(encoding="utf-8").strip()):
            time.sleep(0.1)
        heard = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    finally:
        client.kill()
        client.wait(10)
        if announcer is not None:
            announcer.kill()
    assert name.stdout.strip() == "Chatmon announcements", name.stderr
    assert heard and all(h == {"kind": 4, "processing": 0, "words": words, "activity": "chatmon.announcement"} for h in heard), heard  # Other, ImportantAll


def test_voiceover_holds_announcements_until_chatmon_is_in_front(qapp, monkeypatch):
    from PyQt6.QtCore import Qt

    from chatmon import a11y

    active, posted, spoken = [False], [], []
    queue = a11y.VoiceOver(post=lambda text, important: posted.append((text, important)), active=lambda: active[0], speak=spoken.append)
    for i in range(7):
        queue.say(f"Message {i}.", important=(i == 3))
    assert posted == [] and len(queue.held) == a11y.VoiceOver.HELD  # the last few, not a backlog
    queue.state_changed(Qt.ApplicationState.ApplicationInactive)
    assert posted == []
    active[0] = True
    queue.state_changed(Qt.ApplicationState.ApplicationActive)  # you came to Chatmon
    assert posted == [("Message 2. Message 3. Message 4. Message 5. Message 6.", True)] and queue.held == []
    queue.say("Now.", False)  # in front: said at once
    assert posted[-1] == ("Now.", False)
    queue.state_changed(Qt.ApplicationState.ApplicationActive)  # nothing held: nothing again
    assert len(posted) == 2 and spoken == []


def test_the_speech_fallback_says_it_at_once_instead(qapp, monkeypatch):
    from chatmon import a11y

    monkeypatch.setattr(a11y, "_speech_fallback", False)
    posted, spoken = [], []
    queue = a11y.VoiceOver(post=lambda text, important: posted.append(text), active=lambda: False, speak=spoken.append)
    a11y.set_speech_fallback(True)
    queue.say("Reminder. Stretch.", True)
    assert spoken == ["Reminder. Stretch."] and queue.held == [] and posted == []
    a11y.set_speech_fallback(False)
    queue.say("Later.", False)
    assert spoken == ["Reminder. Stretch."] and queue.held == [("Later.", False)]


# -- macOS: sleep, wake, displays, accessibility options and Low Power Mode (macnative.WorkspaceWatcher, M4A-03, -06)


def test_each_workspace_notification_is_its_own_signal(qapp, monkeypatch):
    """What each of the observer's methods says (here without AppKit: on macOS, tests/test_macnative.py posts the
    real notifications)."""
    from chatmon import macnative

    monkeypatch.setattr(macnative, "low_power_mode", lambda: True)
    watcher = macnative.WorkspaceWatcher()
    heard = []
    watcher.slept.connect(lambda on: heard.append(("slept", on)))
    watcher.screens_slept.connect(lambda on: heard.append(("screens", on)))
    watcher.accessibility_changed.connect(lambda: heard.append(("accessibility",)))
    watcher.low_power_changed.connect(lambda on: heard.append(("low power", on)))
    for selector, _, _ in macnative.WORKSPACE_EVENTS:
        watcher.deliver(selector)
    assert heard == [("slept", True), ("slept", False), ("screens", True), ("screens", False), ("accessibility",), ("low power", True)]
    assert watcher.listening == (sys.platform == "darwin")
    watcher.close()


# -- Linux, against pretend notification servers on a private bus (tests/fake_notifications.py)


def _on_a_private_bus(tmp_path, fake_args: list[str], client: str, config: Path | None = None, after: str = "") -> tuple[str, str]:
    """Run the pretend server, then `client`, then the shell command `after`, in a D-Bus session of their own (with
    the bus configuration `config`, if given); the output, and the server's log."""
    log, ready = tmp_path / "server.jsonl", tmp_path / "ready"
    fake = " ".join(f'"{a}"' for a in [sys.executable, str(HERE / "fake_notifications.py"), str(log), *fake_args])
    script = (
        f'{fake} > "{ready}" 2>&1 & fake=$!; '
        f'for i in $(seq 100); do grep -q ready "{ready}" 2>/dev/null && break; sleep 0.1; done; '
        f'"{sys.executable}" -c "$CLIENT" "{HERE.parent}"; {after or "true"}; kill $fake'
    )
    env = dict(os.environ, CLIENT=client, QT_QPA_PLATFORM="offscreen")
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)  # a bus of its own: never the desktop's notifications
    command = ["dbus-run-session", *([f"--config-file={config}"] if config else []), "--", "sh", "-c", script]
    out = subprocess.run(command, capture_output=True, text=True, timeout=90, env=env)
    return out.stdout + out.stderr, log.read_text(encoding="utf-8") if log.exists() else ""


NOTIFY_CLIENT = r"""
import sys
sys.path.insert(0, sys.argv[1])
from PyQt6.QtCore import QCoreApplication, QTimer
app = QCoreApplication([])
from chatmon import sysnotify
notifier = sysnotify.Notifier()
pressed = []
notifier.read_aloud("Reminder", "Stretch.", ["Snooze 10 min", "Done"], pressed.append)
QTimer.singleShot(400, lambda: notifier.read_aloud("Agent", "Claude needs you.", ["Open"], pressed.append))
QTimer.singleShot(800, lambda: notifier.alert("Battery almost empty", "Chatmon has something for you."))
QTimer.singleShot(2500, app.quit)
app.exec()
print("pressed", pressed, "read aloud id", notifier.read_aloud_id, flush=True)
"""


@linux_bus
def test_the_notification_server_gets_transient_replacing_and_urgent_notifications(tmp_path):
    pytest.importorskip("PyQt6.QtDBus")
    out, log = _on_a_private_bus(tmp_path, ["--name", "dunst", "--press", "1"], NOTIFY_CLIENT)
    sent = [json.loads(line) for line in log.splitlines() if '"Notify"' in line]
    assert len(sent) == 3, out
    first, second, alert = sent
    assert first["signature"] == "susssasa{sv}i" and first["replaces"] == 0 and first["hints"]["transient"] == ["b", True]
    assert first["actions"] == ["0", "Snooze 10 min", "1", "Done"]
    assert second["replaces"] == first["id"] and second["hints"]["transient"] == ["b", True]  # one replaces the other
    assert alert["hints"]["urgency"] == ["y", 2] and "transient" not in alert["hints"] and alert["replaces"] == 0
    assert "urgency" not in first["hints"]
    # The server pressed "Done" on the first: reported, with that button's place.
    assert f"pressed [1] read aloud id {second['id']}" in out, out


DND_CLIENT = r"""
import sys
sys.path.insert(0, sys.argv[1])
from PyQt6.QtCore import QCoreApplication, QTimer
app = QCoreApplication([])
from chatmon import presence
desk = presence.Desk("offscreen")
said = []
def ask():
    said.append(desk.quiet())
    if len(said) < 8:
        QTimer.singleShot(150, ask)
    else:
        app.quit()
ask()
app.exec()
print("quiet", said[-1], flush=True)
"""


@linux_bus
@pytest.mark.parametrize("server, dnd, expected", [
    ("dunst", "on", "Do Not Disturb"),
    ("dunst", "off", "None"),
    ("mako", "on", "Do Not Disturb"),
    ("mako", "off", "None"),
    ("SwayNotificationCenter", "on", "Do Not Disturb"),
    ("Xfce Notify Daemon", "on", "Do Not Disturb"),
    ("Xfce Notify Daemon", "unset", "None"),
    ("Plasma", "on", "Do Not Disturb"),
])
def test_each_servers_do_not_disturb_is_read_from_the_server(tmp_path, server, dnd, expected):
    pytest.importorskip("PyQt6.QtDBus")
    out, log = _on_a_private_bus(tmp_path, ["--name", server, "--dnd", dnd], DND_CLIENT)
    assert f"quiet {expected}" in out, out
    asked = [json.loads(line)["asked"] for line in log.splitlines() if '"asked"' in line]
    assert asked[0] == "GetServerInformation" and len(asked) >= 2, asked  # who, then that server's own question


@linux_bus
def test_asking_about_do_not_disturb_never_starts_a_service(tmp_path):
    """SwayNotificationCenter named as the server, but its own bus name not running, and startable (a D-Bus
    service file, as the swaync package installs): asking doesn't start it; an ordinary call would."""
    pytest.importorskip("PyQt6.QtDBus")
    services, started = tmp_path / "services", tmp_path / "started"
    services.mkdir()
    (services / "org.erikreider.swaync.cc.service").write_text(
        f"[D-BUS Service]\nName=org.erikreider.swaync.cc\nExec=/bin/sh -c 'touch {started}; sleep 5'\n", encoding="utf-8")
    config = tmp_path / "session.conf"
    config.write_text(
        "<!DOCTYPE busconfig PUBLIC \"-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN\" "
        "\"http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd\">\n"
        f"<busconfig><type>session</type><listen>unix:tmpdir={tmp_path}</listen><servicedir>{services}</servicedir>"
        "<policy context=\"default\"><allow send_destination=\"*\" eavesdrop=\"true\"/><allow eavesdrop=\"true\"/><allow own=\"*\"/></policy>"
        "</busconfig>\n", encoding="utf-8")
    check = f'echo "started before: $(test -e {started} && echo yes || echo no)"'
    ordinary = ("dbus-send --session --print-reply --dest=org.erikreider.swaync.cc /org/erikreider/swaync/cc "
                "org.erikreider.swaync.cc.GetDnd >/dev/null 2>&1; sleep 0.5")
    out, log = _on_a_private_bus(tmp_path, ["--name", "SwayNotificationCenter", "--dnd", "on", "--not-own"], DND_CLIENT, config,
                                 after=f'{check}; {ordinary}; echo "started after: $(test -e {started} && echo yes || echo no)"')
    assert "quiet None" in out and "started before: no" in out, out  # not known, and not started
    assert "started after: yes" in out, out  # the service file works: an ordinary call starts it
