"""CI's fedora:44 crash (run 43700807137), forced: two short companion tests through tests/app_harness.py, then a
collection made to run inside Qt's loop over the top-level windows (QApplication.setWindowIcon), as Qt reaches a
window of this script's own, while the first quit Companion turns to garbage (its timers going off). Python's own
collections are off, so that is the only collection there is until the end.

Base harness: the first Companion's windows are freed inside the loop; on glibc the loop then crashes (Fatal Python
error: Segmentation fault, in QApplicationPrivate::notifyWindowIconChanged). Fixed harness: it's still held by the
harness then, nothing is freed inside the loop, and the harness frees it itself afterwards.

usage: python3 -X faulthandler forced_repro.py REPO_ROOT
"""

import gc
import os
import sys
import tempfile
import time
import weakref
from pathlib import Path

root = sys.argv[1]
sys.path[:0] = [root, os.path.join(root, "tests")]
home = tempfile.mkdtemp()
for var in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_STATE_HOME"):
    os.environ[var] = home  # what outlives a test's stand-ins finds no one's own files
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("CHATMON_INSTANCE", f"repro-{os.getpid()}")
gc.disable()

import pytest
from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget

app = QApplication([])
from chatmon import agents

agents._run_json = lambda argv, what: []  # for good: no agent's command line, whatever goes off after a test
import app_harness

start = time.monotonic()


def companion_test() -> weakref.ref:
    with pytest.MonkeyPatch.context() as mp:
        folder = Path(tempfile.mkdtemp(dir=home))
        mp.setenv("LOCALAPPDATA", str(folder))
        fixture = app_harness.make_companion(folder, mp)
        c = next(fixture)
        app_harness.spin(0.2)
        fixture.close()
    return weakref.ref(c)


first = companion_test()
companion_test()
print(f"{time.monotonic() - start:5.2f} s: two companion tests done; top-level windows {len(QApplication.topLevelWidgets())}", flush=True)


class CollectsInside(QObject):
    freed = 0

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ApplicationWindowIconChange:
            before = len(QApplication.topLevelWidgets())
            gc.collect()
            freed = before - len(QApplication.topLevelWidgets())
            if freed:
                print(f"{time.monotonic() - start:5.2f} s: {freed} windows freed by a collection inside setWindowIcon's loop; "
                      f"Qt goes on through its list", flush=True)
            self.freed += freed
        return False


inside, window = CollectsInside(), QWidget()
window.installEventFilter(inside)
deadline = time.monotonic() + 7
while time.monotonic() < deadline and not inside.freed:
    app_harness.spin(0.25)
    app.setWindowIcon(QIcon(QPixmap(16, 16)))
window.removeEventFilter(inside)
print(f"{time.monotonic() - start:5.2f} s: setWindowIcon's loops done; windows freed inside them: {inside.freed}", flush=True)
let_go = getattr(app_harness, "let_go_of_the_quit", None)
if let_go is not None:  # the fixed harness
    deadline = time.monotonic() + 15
    while first() is not None and time.monotonic() < deadline:
        app_harness.spin(0.25)
        let_go()
    print(f"{time.monotonic() - start:5.2f} s: the first freed by the harness, between tests: {first() is None}", flush=True)
