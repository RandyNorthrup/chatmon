"""The portal file chooser (portal.py) against a pretend portal on a private D-Bus (tests/fake_portal.py)."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent

needs_a_bus = pytest.mark.skipif(
    not sys.platform.startswith("linux") or not shutil.which("dbus-run-session") or os.environ.get("CHATMON_PORTAL_BUS"),
    reason="Linux with dbus-run-session",
)

CLIENT = r"""
import sys, json
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from PyQt6.QtCore import QCoreApplication, QTimer
app = QCoreApplication([])
from chatmon import portal
got = {"available": portal.available()}
chooser = portal.FileChooser()
def saved(paths):
    got["saved"] = paths
    app.quit()
def opened(paths):
    got["opened"] = paths
    chooser.save_file("Save the chat", Path("/tmp"), "chat.md", saved, lambda: (got.setdefault("fell back", True), app.quit()))
chooser.open_files("Attach to your question", Path("/home/me"), opened, lambda: (got.setdefault("fell back", True), app.quit()))
QTimer.singleShot(10_000, app.quit)
app.exec()
print(json.dumps(got))
"""


@needs_a_bus
def test_the_portal_is_asked_in_its_own_types_and_its_answer_read(tmp_path):
    pytest.importorskip("PyQt6.QtDBus")
    log, ready, fake = tmp_path / "asked.jsonl", tmp_path / "ready", HERE / "fake_portal.py"
    # The pretend portal says "ready" once it's on the bus; then the client asks it.
    script = (
        f'"{sys.executable}" "{fake}" "{log}" > "{ready}" 2>&1 & fake=$!; '
        f'for i in $(seq 100); do grep -q ready "{ready}" 2>/dev/null && break; sleep 0.1; done; '
        f'"{sys.executable}" -c "$CLIENT" "{HERE.parent}"; kill $fake'
    )
    env = dict(os.environ, CLIENT=CLIENT, QT_QPA_PLATFORM="offscreen", CHATMON_PORTAL_BUS="1")
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)  # a bus of its own: never the desktop's portal
    out = subprocess.run(["dbus-run-session", "--", "sh", "-c", script], capture_output=True, text=True, timeout=60, env=env)
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got == {"available": True, "opened": ["/tmp/picked one.txt"], "saved": ["/tmp/picked one.txt"]}, out.stderr
    asked = [json.loads(line) for line in log.read_text().splitlines()]
    assert [a["method"] for a in asked] == ["OpenFile", "SaveFile"] and all(a["signature"] == "ssa{sv}" for a in asked)
    assert asked[0]["options"] == {"current_folder": "QByteArray", "handle_token": "str", "modal": "bool", "multiple": "bool"}
    assert asked[0]["folder"] == "/home/me\x00" and asked[1]["options"]["current_name"] == "str"
