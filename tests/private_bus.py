"""Running a pretend D-Bus service and a client together on a bus of their own (Linux, dbus-run-session), for the
tests that talk to UPower: the private bus stands in for the system bus too, so this machine's own services are
never asked."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def needs_dbus_run_session() -> None:
    if not sys.platform.startswith("linux") or not shutil.which("dbus-run-session"):
        pytest.skip("Linux with dbus-run-session")
    pytest.importorskip("PyQt6.QtDBus")


def as_system_bus(tmp_path: Path, fake: str, fake_args: list[str], client: str) -> tuple[str, list[dict]]:
    """Start tests/`fake` (which writes a JSON line per question to the log it's given first, and prints "ready"),
    then run `client` (Python source, given the repository's folder as its first argument): the output, and the
    questions the fake was asked."""
    log, ready = tmp_path / "asked.jsonl", tmp_path / "ready"
    script = (
        'export DBUS_SYSTEM_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS"; '
        f'"{sys.executable}" "{HERE / fake}" "{log}" {" ".join(fake_args)} > "{ready}" 2>&1 & fake=$!; '
        f'for i in $(seq 100); do grep -q ready "{ready}" 2>/dev/null && break; sleep 0.1; done; '
        f'"{sys.executable}" -c "$CLIENT" "{HERE.parent}"; kill $fake'
    )
    env = dict(os.environ, CLIENT=client, QT_QPA_PLATFORM="offscreen")
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)
    env.pop("DBUS_SYSTEM_BUS_ADDRESS", None)
    out = subprocess.run(["dbus-run-session", "--", "sh", "-c", script], capture_output=True, text=True, timeout=60, env=env)
    asked = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    return out.stdout + out.stderr, asked
