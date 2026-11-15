"""What the probes share: the worktree's tests and Chatmon on the path, a QApplication, and a session of a compositor
with a whole Chatmon on it (tests/compositor_session.py, tests/sway_session.py's Probe)."""

import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]  # probes, compositors, release, reports, delivery, docs: the worktree
for path in (ROOT / "tests", ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from PyQt6.QtWidgets import QApplication  # after the path, as every import below

APP = QApplication.instance() or QApplication([])

import compositor_session
from sway_session import Probe
from test_sway import SETUP


@contextmanager
def chatmon_on(name: str, folder: str, env: dict | None = None, **session):
    """(session, probe, hands): a compositor of the probe's own, Chatmon on it set up as the checks set it up."""
    where = Path(folder)
    where.mkdir(parents=True, exist_ok=True)
    desk = compositor_session.start(name, where, **session)
    probe = hands = None
    try:
        probe = Probe(desk, env=env)
        probe.call(SETUP)
        hands = compositor_session.devices(desk)
        yield desk, probe, hands
    finally:
        if hands is not None:
            hands.close()
        if probe is not None:
            probe.close()
        desk.close()
