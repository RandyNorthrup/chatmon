"""Windows: hear when the screen locks and unlocks, as D-Bus tells Linux desktops, so a locked
screen counts as a break there too.

Windows says so to a window that asked (WTSRegisterSessionNotification), with
WM_WTSSESSION_CHANGE; a native event filter hears it. Imported on Windows alone."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable

from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication
from PyQt6.QtGui import QWindow

WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
NOTIFY_FOR_THIS_SESSION = 0

_wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)
_Register = _wtsapi32.WTSRegisterSessionNotification
_Register.restype, _Register.argtypes = wintypes.BOOL, [wintypes.HWND, wintypes.DWORD]
_Unregister = _wtsapi32.WTSUnRegisterSessionNotification
_Unregister.restype, _Unregister.argtypes = wintypes.BOOL, [wintypes.HWND]


class LockWatcher(QAbstractNativeEventFilter):
    """Calls `changed(True)` when the screen locks and `changed(False)` when it unlocks."""

    def __init__(self, changed: Callable[[bool], None]):
        super().__init__()
        self._changed = changed
        self.locked = False
        self._window = QWindow()  # never shown: only there to be told
        self.hwnd = int(self._window.winId())
        self.listening = bool(_Register(self.hwnd, NOTIFY_FOR_THIS_SESSION))
        if self.listening:
            QCoreApplication.instance().installNativeEventFilter(self)

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG" and message:
            msg = wintypes.MSG.from_address(int(message))
            if msg.hWnd == self.hwnd and msg.message == WM_WTSSESSION_CHANGE and msg.wParam in (WTS_SESSION_LOCK, WTS_SESSION_UNLOCK):
                locked = msg.wParam == WTS_SESSION_LOCK
                if locked != self.locked:  # Qt shows filters a posted message twice: once queued, once dispatched
                    self.locked = locked
                    self._changed(locked)
        return False, 0

    def close(self) -> None:
        if self.listening:
            QCoreApplication.instance().removeNativeEventFilter(self)
            _Unregister(self.hwnd)
            self.listening = False
