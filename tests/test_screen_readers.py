"""Whether a screen reader runs on Linux (linuxsession.ScreenReaders, a11y.reader): Orca's remote controller,
AT-SPI's ScreenReaderEnabled where at-spi2-core still keeps it (before 2.62), GNOME's setting, and a screen reader's
own process. The way each is heard is checked everywhere with real D-Bus messages; on Linux, against at-spi2-core's
own bus launcher and gsettings, and a pretend launcher of the kind before 2.62 (tests/fake_a11y_bus.py)."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PyQt6.QtDBus")

HERE = Path(__file__).resolve().parent
ORCA1 = ("org.gnome.Orca1.Service", "/org/gnome/Orca1/Service")


def _proc(tmp_path: Path, **processes: str) -> Path:
    """A /proc with these processes (pid: its name), and the entries that aren't processes."""
    proc = tmp_path / "proc"
    for pid, name in processes.items():
        (proc / pid.lstrip("p")).mkdir(parents=True)
        (proc / pid.lstrip("p") / "comm").write_text(name + "\n", encoding="utf-8")
    (proc / "self").mkdir(parents=True, exist_ok=True)  # not a process's number: passed over
    (proc / "uptime").write_text("1.0 1.0\n", encoding="utf-8")
    return proc


def test_a_screen_readers_process_is_found_by_its_name(tmp_path):
    from chatmon import linuxsession

    proc = _proc(tmp_path, p101="bash", p102="orca", p103="odilia", p104="orca-helper", p105="fenrir")
    (proc / "106").mkdir()  # gone between the listing and the read: no comm
    assert linuxsession.running_readers(proc) == ["Fenrir", "Odilia", "Orca"]
    assert linuxsession.running_readers(proc, uid=-1) == []  # another user's readers aren't this session's
    assert linuxsession.running_readers(tmp_path / "no-proc") == []


@pytest.fixture
def readers(qapp, tmp_path):
    from chatmon import linuxsession

    made = linuxsession.ScreenReaders(proc=_proc(tmp_path, p101="bash"), gnome=False)
    told = []
    made.changed.connect(lambda: told.append(made.found()))
    yield made, told
    made.close()


def _status_signal(changed: dict):
    from PyQt6.QtDBus import QDBusMessage

    signal = QDBusMessage.createSignal("/org/a11y/bus", "org.freedesktop.DBus.Properties", "PropertiesChanged")
    signal.setArguments(["org.a11y.Status", changed, []])
    return signal


def test_orcas_remote_controller_is_the_reader_to_speak_through(readers):
    made, told = readers
    assert made.found() is None
    made.owned("org.gnome.Orca.Service", True)  # Orca 49 or 50
    made.owned(ORCA1[0], True)  # Orca 51's name too: the newer one is spoken through
    assert made.found() == ("Orca", ORCA1)
    made.owned(ORCA1[0], False)
    made.owned("org.gnome.Orca.Service", False)
    assert told == [("Orca", ("org.gnome.Orca.Service", "/org/gnome/Orca/Service")), ("Orca", ORCA1),
                    ("Orca", ("org.gnome.Orca.Service", "/org/gnome/Orca/Service")), None]


def test_before_at_spi2_core_262_screen_reader_enabled_says_one_runs(readers):
    made, told = readers
    made._status_changed(_status_signal({"ScreenReaderEnabled": True, "IsEnabled": True}))
    assert made.found() == ("a screen reader", None) and made.accessibility is True
    made._status_changed(_status_signal({"ScreenReaderEnabled": False}))
    made._status_changed(_status_signal({"Something": True}))  # not one of these
    assert told == [("a screen reader", None), None]


def test_from_at_spi2_core_262_is_enabled_alone_isnt_a_screen_reader_but_its_process_is(readers, tmp_path):
    """2.62 keeps IsEnabled only: something listens (a magnifier, an on-screen keyboard, Accerciser...). As it turns
    on, the reader's own process is looked for."""
    made, told = readers
    made._status_changed(_status_signal({"IsEnabled": True}))
    assert made.found() is None and told == []
    (made._proc / "202").mkdir()
    (made._proc / "202" / "comm").write_text("odilia\n", encoding="utf-8")
    made._status_changed(_status_signal({"IsEnabled": True}))  # a reader registering for events says so again
    assert made.found() == ("Odilia", None)
    (made._proc / "202" / "comm").unlink()
    (made._proc / "202").rmdir()
    made.rescan()  # as a11y.reader() looks again
    assert told == [("Odilia", None), None]


def test_at_spis_bus_going_forgets_what_it_said(readers):
    made, told = readers
    made.status({"ScreenReaderEnabled": True})
    made.owned("org.a11y.Bus", False)  # the launcher stopped (the session's ending, or it crashed)
    assert made.screen_reader_enabled is None and made.found() is None and told == [("a screen reader", None), None]


def test_gnomes_screen_reader_setting_says_one_runs(qapp, tmp_path):
    from chatmon import linuxsession

    made = linuxsession.ScreenReaders(proc=_proc(tmp_path), gnome=True)
    try:
        assert made._gnome_setting is not None and made.found() is None
        made._gnome_setting._set("true")  # `gsettings get` answers, or `gsettings monitor` hears it turned on
        assert made.gnome is True and made.found() == ("a screen reader", None)
        made._gnome_setting._set("false")
        assert made.found() is None
    finally:
        made.close()


def test_a11y_reads_what_was_last_heard(qapp, tmp_path, monkeypatch):
    from chatmon import a11y, linuxsession

    monkeypatch.setattr(a11y.sys, "platform", "linux")
    made = linuxsession.ScreenReaders(proc=_proc(tmp_path), gnome=False)
    monkeypatch.setattr(linuxsession, "_screen_readers", made)
    assert a11y.reader() is None
    made.status({"ScreenReaderEnabled": True})
    found = a11y.reader()
    assert found is not None and found.name == "a screen reader" and found.speak is None  # the notification says it
    made.owned(ORCA1[0], True)
    found = a11y.reader()
    assert found is not None and found.name == "Orca" and found.speak is not None  # through its remote controller


def test_desk_passes_a_screen_reader_starting_on(qapp, tmp_path, monkeypatch):
    from chatmon import linuxsession, presence

    monkeypatch.setattr(presence.sys, "platform", "linux")
    made = linuxsession.ScreenReaders(proc=_proc(tmp_path), gnome=False)
    monkeypatch.setattr(linuxsession, "_screen_readers", made)
    desk = presence.Desk("wayland")
    heard = []
    desk.screen_reader_changed.connect(lambda: heard.append(True))
    made.owned(ORCA1[0], True)
    made.owned(ORCA1[0], True)  # the same news: once
    made.owned(ORCA1[0], False)
    assert heard == [True, True]
    desk.close()


# -- Linux: real D-Bus, at-spi2-core's own launcher, gsettings

linux_bus = pytest.mark.skipif(not sys.platform.startswith("linux") or not shutil.which("dbus-run-session"), reason="Linux with dbus-run-session")

CLIENT = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from PyQt6.QtCore import QCoreApplication, QTimer
app = QCoreApplication([])
from chatmon import a11y, presence
desk = presence.Desk("offscreen")  # starts listening, as the app does at its start
def look(why):
    found = a11y.reader()
    print(json.dumps([why, found.name if found else None, bool(found and found.speak)]), flush=True)
desk.screen_reader_changed.connect(lambda: look("changed"))
QTimer.singleShot(800, lambda: look("start"))
QTimer.singleShot(int(sys.argv[2]) * 1000, app.quit)
app.exec()
"""


def _session(tmp_path, steps: str, seconds: int = 12, env: dict | None = None) -> tuple[list, str]:
    """The client on a bus of its own, and the shell `steps` run once it has looked at the start ($OUT is what it
    printed, `until_seen TEXT` waits for it to print TEXT). What it printed, a list each, and the shell's output."""
    out = tmp_path / "client.out"
    script = (
        'until_seen() { for i in $(seq 100); do grep -q "$1" "$OUT" 2>/dev/null && return 0; sleep 0.1; done; return 1; }; '
        f'"{sys.executable}" -c "$CLIENT" "{HERE.parent}" {seconds} > "$OUT" 2>&1 & client=$!; '
        f'until_seen start; {steps}; wait $client'
    )
    full = dict(os.environ, CLIENT=CLIENT, OUT=str(out), QT_QPA_PLATFORM="offscreen", XDG_CURRENT_DESKTOP="")
    full.update(env or {})
    full.pop("DBUS_SESSION_BUS_ADDRESS", None)  # a bus of its own: never the desktop's screen reader
    done = subprocess.run(["dbus-run-session", "--", "sh", "-c", script], capture_output=True, text=True, timeout=90, env=full)
    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.startswith("[")] if out.exists() else []
    return lines, done.stdout + done.stderr + (out.read_text(encoding="utf-8") if out.exists() else "")


def _launcher() -> str | None:
    sys.path.insert(0, str(HERE))
    import sway_session

    return sway_session._atspi_launcher()


@linux_bus
def test_with_at_spi2_cores_own_launcher_a_reader_registering_is_heard(tmp_path):
    """As 2.62 has it (and the at-spi2-core before it): a reader that isn't Orca 49+ starts, and accessibility turns on
    as it registers; it stops, and accessibility turns off. Asking about AT-SPI never starts its launcher."""
    if _launcher() is None:
        pytest.skip("AT-SPI's bus launcher isn't installed (at-spi2-core)")
    has = ("dbus-send --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus "
           "org.freedesktop.DBus.NameHasOwner string:org.a11y.Bus | grep -q 'boolean true'")
    enabled = ("dbus-send --session --print-reply --dest=org.a11y.Bus /org/a11y/bus org.freedesktop.DBus.Properties.Set "
               "string:org.a11y.Status string:IsEnabled variant:boolean:{}")
    steps = (
        f'if {has}; then echo "a11y bus before: up"; else echo "a11y bus before: down"; fi; '
        "dbus-send --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus "
        "org.freedesktop.DBus.StartServiceByName string:org.a11y.Bus uint32:0 >/dev/null; "
        f'cp "$(command -v sleep)" "{tmp_path}/odilia"; "{tmp_path}/odilia" 60 & reader=$!; sleep 0.3; '
        f'{enabled.format("true")} >/dev/null; until_seen Odilia; '
        f'kill $reader; wait $reader 2>/dev/null; {enabled.format("false")} >/dev/null; until_seen "changed.*null" || true'
    )
    seen, out = _session(tmp_path, steps, seconds=10)
    assert "a11y bus before: down" in out, out  # the client asked, and nothing started it
    assert seen[0] == ["start", None, False], out
    assert ["changed", "Odilia", False] in seen and seen[-1] == ["changed", None, False], out


@linux_bus
@pytest.mark.parametrize("screen_reader, expected", [("on", "a screen reader"), ("gone", None)])
def test_a_launcher_before_262_says_so_and_262s_is_enabled_alone_doesnt(tmp_path, screen_reader, expected):
    """A launcher of the kind before at-spi2-core 2.62, with ScreenReaderEnabled; and one as 2.62 has it, with
    IsEnabled on (something listens) but no screen reader's process to be found."""
    log, ready = tmp_path / "asked.jsonl", tmp_path / "ready"
    start = (f'"{sys.executable}" "{HERE / "fake_a11y_bus.py"}" "{log}" --screen-reader {screen_reader} --enabled on > "{ready}" 2>&1 & '
             f'for i in $(seq 100); do grep -q ready "{ready}" 2>/dev/null && break; sleep 0.1; done')
    off = ("dbus-send --session --print-reply --dest=org.a11y.Bus /org/a11y/bus org.freedesktop.DBus.Properties.Set "
           "string:org.a11y.Status string:ScreenReaderEnabled variant:boolean:false >/dev/null 2>&1; sleep 1")
    out = tmp_path / "client.out"
    script = (
        f'{start}; until_seen() {{ for i in $(seq 100); do grep -q "$1" "$OUT" 2>/dev/null && return 0; sleep 0.1; done; return 1; }}; '
        f'"{sys.executable}" -c "$CLIENT" "{HERE.parent}" 6 > "$OUT" 2>&1 & client=$!; until_seen start; {off}; wait $client'
    )
    env = dict(os.environ, CLIENT=CLIENT, OUT=str(out), QT_QPA_PLATFORM="offscreen", XDG_CURRENT_DESKTOP="")
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)
    done = subprocess.run(["dbus-run-session", "--", "sh", "-c", script], capture_output=True, text=True, timeout=90, env=env)
    text = out.read_text(encoding="utf-8") if out.exists() else done.stdout + done.stderr
    seen = [json.loads(line) for line in text.splitlines() if line.startswith("[")]
    assert ["start", expected, False] in seen, text
    if expected:
        assert seen[-1] == ["changed", None, False], text  # turned off: told, and no reader now
    else:
        assert all(name is None for _, name, _ in seen), text
    assert any(json.loads(line)["asked"] == "GetAll" for line in log.read_text(encoding="utf-8").splitlines())


@linux_bus
def test_gnomes_setting_turns_the_screen_reader_on_and_off(tmp_path):
    """GNOME's org.gnome.desktop.a11y.applications screen-reader-enabled, through gsettings itself (a keyfile of the
    test's own, never the desktop's settings)."""
    gsettings = shutil.which("gsettings")
    schema = subprocess.run([gsettings, "list-keys", "org.gnome.desktop.a11y.applications"], capture_output=True, text=True, check=False) if gsettings else None
    if schema is None or "screen-reader-enabled" not in schema.stdout:
        pytest.skip("gsettings with GNOME's accessibility schema (gsettings-desktop-schemas) isn't installed")
    env = {"GSETTINGS_BACKEND": "keyfile", "XDG_CONFIG_HOME": str(tmp_path / "config"), "XDG_CURRENT_DESKTOP": "GNOME"}
    set_to = "gsettings set org.gnome.desktop.a11y.applications screen-reader-enabled {}"
    subprocess.run(set_to.format("true").split(), env=dict(os.environ, **env), check=True, timeout=30)
    seen, out = _session(tmp_path, f'{set_to.format("false")}; until_seen "changed.*null" || true', seconds=8, env=env)
    assert ["start", "a screen reader", False] in seen, out
    assert seen[-1] == ["changed", None, False], out


@linux_bus
def test_orca_starting_and_stopping_while_chatmon_runs_is_heard(tmp_path):
    """Orca's remote controller registering after Chatmon started, then going (tests/fake_orca.py, as Orca 51 names
    itself): heard as it happens, and spoken through while it's there."""
    said = tmp_path / "said.txt"
    steps = (f'"{sys.executable}" "{HERE / "fake_orca.py"}" "{said}" > "{tmp_path}/orca.out" 2>&1 & orca=$!; '
             'until_seen "changed.*Orca"; kill $orca; wait $orca 2>/dev/null; until_seen "changed.*null" || true')
    seen, out = _session(tmp_path, steps, seconds=8)
    assert seen[0] == ["start", None, False], out
    assert ["changed", "Orca", True] in seen and seen[-1] == ["changed", None, False], out
