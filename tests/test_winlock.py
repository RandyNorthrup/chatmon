"""Windows: system setting changes heard through winlock's native event filter (WM_SETTINGCHANGE), so high contrast,
animations and a screen reader starting are followed at once (M4A-04)."""

import ctypes
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

HERE = Path(__file__).resolve().parent


def test_a_setting_change_is_passed_on_once_from_its_own_window(qapp):
    from ctypes import wintypes

    from PyQt6 import sip

    from chatmon import presence, winlock

    changed = []
    watcher = winlock.LockWatcher(lambda away: None, settings=changed.append)
    try:
        def tell(action, hwnd=watcher.hwnd, message=winlock.WM_SETTINGCHANGE):
            msg = wintypes.MSG(hwnd, message, action, 0)
            return watcher.nativeEventFilter(b"windows_generic_MSG", sip.voidptr(ctypes.addressof(msg)))

        assert tell(presence.SPI_SETHIGHCONTRAST) == (False, 0)  # never kept from Qt, which follows it too
        tell(presence.SPI_SETCLIENTAREAANIMATION, hwnd=12345)  # the copy sent to another of Chatmon's windows
        tell(presence.SPI_SETSCREENREADER)
        tell(0)  # a change that names no action: passed on, for Desk to judge
        tell(presence.SPI_SETHIGHCONTRAST, message=0x0015)  # WM_SYSCOLORCHANGE: not this
        assert changed == [presence.SPI_SETHIGHCONTRAST, presence.SPI_SETSCREENREADER, 0]
    finally:
        watcher.close()


def test_without_a_settings_callback_setting_changes_are_left_alone(qapp):
    from ctypes import wintypes

    from PyQt6 import sip

    from chatmon import winlock

    away = []
    watcher = winlock.LockWatcher(away.append)
    try:
        msg = wintypes.MSG(watcher.hwnd, winlock.WM_SETTINGCHANGE, 0x43, 0)
        assert watcher.nativeEventFilter(b"windows_generic_MSG", sip.voidptr(ctypes.addressof(msg))) == (False, 0)
        assert away == []
    finally:
        watcher.close()


SENT = r"""
import ctypes, sys
sys.path.insert(0, sys.argv[1])
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from chatmon import presence, winlock
desk = presence.Desk("windows")
heard = []
desk.settings_changed.connect(lambda: heard.append("settings"))
desk.screen_reader_changed.connect(lambda: heard.append("screen reader"))
watcher = winlock.LockWatcher(lambda away: None, settings=desk.windows_setting_changed)
send = ctypes.windll.user32.SendMessageW
send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
send(watcher.hwnd, winlock.WM_SETTINGCHANGE, presence.SPI_SETHIGHCONTRAST, 0)
send(watcher.hwnd, winlock.WM_SETTINGCHANGE, presence.SPI_SETSCREENREADER, 0)
watcher.close()
print(",".join(heard), flush=True)
"""


def test_a_sent_wm_settingchange_reaches_desk_through_qts_window_procedure():
    """As Windows delivers it: sent (not posted) to the window, through Qt's window procedure and native event
    filters, on Qt's real Windows platform (the suite's offscreen one has no real windows)."""
    env = dict(os.environ, QT_QPA_PLATFORM="windows")
    out = subprocess.run([sys.executable, "-c", SENT, str(HERE.parent)], capture_output=True, text=True, timeout=60, env=env)
    assert out.stdout.strip() == "settings,screen reader", out.stderr
