"""What the app's tests share: a whole Companion, headless, of the test's own (`make_companion`), the desktop's readings
set by the test (`PretendDesk`), a brain that answers when told to (`PretendBrain`), and the event loop run for a while
(`spin`, `until`). Imported by the test files that build a Companion; not a test file itself."""

import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEventLoop, QTimer  # noqa: E402
from PyQt6.QtNetwork import QLocalServer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402


def spin(seconds: float) -> None:
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()


class PretendDesk:
    """The platform's readings, set by the test."""

    def __init__(self):
        self.idle, self.why_quiet, self.is_covered, self.motion, self.contrast, self.notice = 0.0, None, False, False, False, None
        self.overlay_idle_since = None

    def idle_seconds(self):
        return self.idle

    def quiet(self, _window=0):
        return self.why_quiet

    def covered(self, _window):
        return self.is_covered

    def reduce_motion(self):
        return self.motion

    def high_contrast(self):
        return self.contrast

    def notice_seconds(self):
        return self.notice

    def close(self):
        pass


def make_companion(tmp_path, monkeypatch):
    """A whole Companion of its own, headless, for a test: its own settings, state, chats and address, a desk of
    the test's own, a keychain in memory, and no agent's command line ever run. A test file's `companion` fixture
    yields from this; it's quit afterwards."""
    for var in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "APPDATA"):
        monkeypatch.setenv(var, str(tmp_path / var))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    # socket paths are limited to ~100 characters, so keep this one short
    run = tempfile.mkdtemp(prefix="pc-", dir=None if sys.platform == "win32" else "/tmp")
    monkeypatch.setenv("XDG_RUNTIME_DIR", run)
    from chatmon import agents, app as appmod, paths
    from chatmon.settings import State

    monkeypatch.setattr(agents, "_run_json", lambda argv, what: [])  # never run a real agent's command line

    from chatmon import __version__

    # Seen this version already (no what's new), asked about every agent already (no offer to connect them),
    # and never looking for updates (no network in tests).
    seen = {"name": "Sparky", "x": 600, "seen_version": __version__, "check_updates": False, "agent_status": {a.name: "found" for a in agents.AGENTS}}
    State(paths.state_file(), seen).save()
    qapp = QApplication.instance() or QApplication([])
    qapp.setQuitOnLastWindowClosed(False)
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    QLocalServer.removeServer(paths.server_name())
    assert server.listen(paths.server_name()), server.errorString()
    from chatmon import keychain

    real_keychain = keychain.use(keychain.InMemory())  # no test reads or writes the keychain of the computer it runs on
    c = appmod.Companion(qapp, server)
    c._file_chooser = None  # Qt's dialogs, which the tests stand in for: never the desktop's portal
    c._reader_seen = float("inf")  # no screen reader, never looked for: tests never talk to the desktop's
    # The desktop's own readings (full screen, presentation, Focus, reduced motion, idle time) are the test's to
    # set, never the computer's it runs on: a CI runner's desktop says "quiet", which held every bubble from
    # the background from the first look on (five seconds in).
    c.desk.close()
    c.desk = PretendDesk()
    c._check_accessibility()  # what it read of reduced motion and high contrast as it started, read again from it
    try:
        yield c
    finally:
        c.quit()
        server.close()
        keychain.use(real_keychain)


def until(condition, seconds=5.0):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        spin(0.02)
    return condition()


class PretendBrain:
    """Stands in for asking a brain: records each question, and answers when told to. The brain it stands for is in the
    companion's brains, and is the one found for every question (as when nothing needs looking at)."""

    def __init__(self, c, monkeypatch, kind="anthropic", tools_off=True, name="pretend", label="Pretend API"):
        from chatmon import brains

        self.c, self.asked = c, []
        self.brain = brains.Brain(
            name, kind, label=label, model="m", api_key="k", command=["pretend"] if kind == "command" else [], tools_off=tools_off
        )
        monkeypatch.setattr(c, "_brain", lambda wait=True: self.brain)
        monkeypatch.setattr(c, "_find_brain", lambda then: then(self.brain))  # found at once, as with nothing unsure
        monkeypatch.setitem(c.brains, name, self.brain)
        monkeypatch.setattr(c.asker, "ask", lambda brain, system, history, question, timeout, attached=(): self.asked.append((history, question, list(attached))))

    def answer(self, text):
        self.c._answered(text)
