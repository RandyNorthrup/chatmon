"""Problem 3: Chatmon's own window reading Qt's clipboard after the overlay's ask box copied, on KWin.

    python kwin_qt_clipboard.py FOLDER"""

import subprocess
import sys

from common import chatmon_on

from test_compositors import DESK_WINDOW
from test_sway import centre, penguin

READ = ("import time; t = time.monotonic(); text = QtWidgets.QApplication.clipboard().text(); "
        "result = dict(qt_clipboard=text, read_took_s=round(time.monotonic() - t, 3), desk_window_active=desk.isActiveWindow(), overlay_has_keyboard=surface._kb_focus)")

with chatmon_on("kwin", sys.argv[1]) as (desk, probe, hands):
    probe.call(DESK_WINDOW)
    hands.click(*centre(penguin(probe)))
    probe.call("until(lambda: surface._kb_focus, 5)", settle=0.2)
    hands.type("mine")
    hands.key("a", mods=4)
    hands.key("c", mods=4)  # Ctrl+A, Ctrl+C in the box: the overlay's clipboard, and Qt's (LayerSurface.copy)
    probe.call("settled()", settle=0.2)
    pasted = subprocess.run(["wl-paste", "--no-newline"], env=desk.env, capture_output=True, text=True, timeout=10, check=False).stdout  # noqa: S607 - wl-paste, fixed
    print("another app pastes (wl-paste):", repr(pasted))
    print("box open, Qt's clipboard:", probe.call(READ))
    hands.key("Escape")
    for wait in (0.3, 1.0, 3.0):
        print(f"{wait} s after Esc:", probe.call(READ, settle=wait))
