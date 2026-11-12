"""Screen readers (a11y.py): what's read out, and each platform's way to have it said."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chatmon import a11y

HERE = Path(__file__).resolve().parent


def test_a_bubble_is_read_as_plain_words_with_its_buttons():
    assert a11y.spoken("Reminder", "**Stretch** your [legs](https://x) and run `ls`", ["Snooze 10 min", "Done"]) == (
        "Reminder. Stretch your legs and run ls. To answer, type “Snooze 10 min” or “Done” in the chat."
    )
    assert a11y.spoken("Saved!", "") == "Saved!"
    assert a11y.plain("- one\n- **two**") == "one two"


def test_a_typed_button_is_its_label_or_the_start_only_it_has():
    labels = ["Snooze 10 min", "Done", "Snore"]
    assert a11y.typed_button(labels, "done") == 1 and a11y.typed_button(labels, " Snooze 10 MIN. ") == 0
    assert a11y.typed_button(labels, "snoo") == 0 and a11y.typed_button(labels, "sno") is None  # two start so
    assert a11y.typed_button(labels, "do") is None  # too short to tell from a question


CLIENT = r"""
import sys
sys.path.insert(0, sys.argv[1])
from PyQt6.QtCore import QCoreApplication, QTimer
app = QCoreApplication([])
from chatmon import a11y
reader = a11y.reader()
print(reader.name if reader else "none", flush=True)
if reader and reader.speak:
    reader.speak("Reminder. Stretch.", True)
QTimer.singleShot(500, app.quit)
app.exec()
"""


@pytest.mark.skipif(not sys.platform.startswith("linux") or not shutil.which("dbus-run-session"), reason="Linux with dbus-run-session")
def test_orca_is_found_and_asked_to_present_the_message(tmp_path):
    pytest.importorskip("PyQt6.QtDBus")
    log, ready, fake = tmp_path / "said.txt", tmp_path / "ready", HERE / "fake_orca.py"
    script = (
        f'"{sys.executable}" "{fake}" "{log}" > "{ready}" 2>&1 & fake=$!; '
        f'for i in $(seq 100); do grep -q ready "{ready}" 2>/dev/null && break; sleep 0.1; done; '
        f'"{sys.executable}" -c "$CLIENT" "{HERE.parent}"; sleep 0.3; kill $fake'
    )
    env = dict(os.environ, CLIENT=CLIENT, QT_QPA_PLATFORM="offscreen")
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)  # a bus of its own: never the desktop's screen reader
    out = subprocess.run(["dbus-run-session", "--", "sh", "-c", script], capture_output=True, text=True, timeout=60, env=env)
    assert out.stdout.split() == ["Orca"], out.stderr
    assert log.read_text(encoding="utf-8") == "Reminder. Stretch.\n"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows")
def test_windows_asks_whether_a_screen_reader_or_narrator_is_running():
    assert a11y._running("python.exe") or a11y._running("pythonw.exe")  # the look at what's running works
    assert not a11y._running("no-such-program.exe")
    found = a11y.reader()
    assert found is None or found.name in ("a screen reader", "Narrator")


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS")
def test_macos_asks_voiceover_and_can_post_an_announcement():
    found = a11y.reader()
    assert found is None or found.name == "VoiceOver"
    a11y._voiceover("Reminder. Stretch.", True)  # with VoiceOver off, macOS just doesn't say it
