"""testpc2, in Technician's signed-in desktop session, before the AC-03E drill: does a toast from Chatmon's Toaster
land in Windows' history (Action Center) under its tag here, and what is left after hide() and after clear()?

Run with the source tree on PYTHONPATH. It registers a throwaway app ID as tests/test_wintoast.py's fixture does, and
removes it, and the toast, after. Exit 0 only when the toast was in the history under its tag and nothing was left."""

import ctypes
import os
import sys
import time
import uuid
import winreg

from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
from PyQt6.QtWidgets import QApplication

from chatmon import winfocus, wintoast, winrt

QUNS = {1: "not present (locked, screen saver)", 2: "busy (full-screen app)", 3: "running a Direct3D full-screen app",
        4: "presentation mode", 5: "accepts notifications", 6: "quiet time", 7: "a Windows Store app full screen"}


def toast_enabled() -> str:
    """The value tests/test_wintoast.py's notifications_on() reads; absent means never turned off."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\PushNotifications") as key:
            return str(winreg.QueryValueEx(key, "ToastEnabled")[0])
    except FileNotFoundError:
        return "absent (notifications never turned off: on)"


def wait_for(app: QApplication, done, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while not done() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    return bool(done())


def main() -> int:
    session = ctypes.c_ulong()
    ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session))
    print(f"python {sys.version.split()[0]}, PyQt6 {PYQT_VERSION_STR}, Qt {QT_VERSION_STR}")
    print(f"user {os.environ.get('USERNAME')}, session {session.value}")
    print(f"ToastEnabled: {toast_enabled()}")
    state = ctypes.c_int(0)
    hr = ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state))
    print(f"SHQueryUserNotificationState: hr {hr}, state {state.value} ({QUNS.get(state.value, '?')})")
    winrt.join_com()
    focus = winfocus.manager()
    print(f"Focus session active: {winfocus.is_active(focus) if focus else 'no FocusSessionManager'}")
    winrt.release(focus)

    app = QApplication.instance() or QApplication([])
    app_id = f"RandyNorthrup.Chatmon.Test{uuid.uuid4().hex[:8]}"
    wintoast.register_app_id(app_id, "Chatmon test")
    toaster = wintoast.Toaster(app_id)
    heard: list[tuple] = []
    toaster.dismissed.connect(lambda tag, why: heard.append(("dismissed", tag, why)))
    toaster.failed.connect(lambda tag, code: heard.append(("failed", tag, code)))
    landed = False
    left: list[str] = []
    try:
        print(f"app ID {app_id}: NotificationSetting {toaster.setting()}")
        tag = toaster.show("Chatmon drill probe", "A toast from Chatmon's AC-03E drill on testpc2, removed at once.",
                           ["OK"], silent=True)
        print(f"show() -> tag {tag}, why_not {toaster.why_not}")
        if tag:
            start = time.monotonic()
            landed = wait_for(app, lambda: tag in toaster.in_action_center())
            print(f"in the history under its tag: {landed}, after {time.monotonic() - start:.2f} s; "
                  f"history {toaster.in_action_center()}")
            print(f"hide() -> {toaster.hide(tag)}")
            wait_for(app, lambda: ("dismissed", tag, wintoast.HIDDEN_BY_CHATMON) in heard)
            wait_for(app, lambda: False, 0.5)
            print(f"heard (HIDDEN_BY_CHATMON = {wintoast.HIDDEN_BY_CHATMON}, TIMED_OUT = {wintoast.TIMED_OUT}): {heard}")
            print(f"history after hide(), before clear(): {toaster.in_action_center()}")
    finally:
        toaster.clear()
        left = toaster.in_action_center()
        print(f"history after clear(): {left}")
        toaster.close()
        print(f"registration removed: {wintoast.unregister_app_id(app_id)}")
    ok = landed and not left
    print("PROBE", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
