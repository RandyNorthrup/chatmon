"""Windows: hear when you step away and come back, so time away counts as a break: the screen locking and
unlocking, a Remote Desktop or console session disconnecting (which doesn't lock), and sleep and resume.

Windows tells a window that asked (WTSRegisterSessionNotification) with WM_WTSSESSION_CHANGE, and every
top-level window WM_POWERBROADCAST; a native event filter hears them. Imported on Windows alone.
https://learn.microsoft.com/en-us/windows/win32/termserv/wm-wtssession-change
https://learn.microsoft.com/en-us/windows/win32/power/wm-powerbroadcast"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable

from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QTimer
from PyQt6.QtGui import QWindow

WM_WTSSESSION_CHANGE = 0x02B1
WTS_CONSOLE_CONNECT, WTS_CONSOLE_DISCONNECT, WTS_REMOTE_CONNECT, WTS_REMOTE_DISCONNECT = 0x1, 0x2, 0x3, 0x4
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
WM_POWERBROADCAST = 0x0218
PBT_APMSUSPEND, PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC = 0x4, 0x7, 0x12
NOTIFY_FOR_THIS_SESSION = 0
AWAY = {WTS_SESSION_LOCK: True, WTS_SESSION_UNLOCK: False, WTS_CONSOLE_DISCONNECT: True, WTS_REMOTE_DISCONNECT: True,
        WTS_CONSOLE_CONNECT: False, WTS_REMOTE_CONNECT: False}
ASLEEP = {PBT_APMSUSPEND: True, PBT_APMRESUMESUSPEND: False, PBT_APMRESUMEAUTOMATIC: False}

_wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)
_Register = _wtsapi32.WTSRegisterSessionNotification
_Register.restype, _Register.argtypes = wintypes.BOOL, [wintypes.HWND, wintypes.DWORD]
_Unregister = _wtsapi32.WTSUnRegisterSessionNotification
_Unregister.restype, _Unregister.argtypes = wintypes.BOOL, [wintypes.HWND]


class LockWatcher(QAbstractNativeEventFilter):
    """Calls `changed(True)` when you step away (the screen locks, the session disconnects) and
    `changed(False)` when you're back; `slept(True)` as the computer goes to sleep, `slept(False)` on waking."""

    RETRIES = 12  # registering can fail early in a login, before Remote Desktop Services is ready: try again

    def __init__(self, changed: Callable[[bool], None], slept: Callable[[bool], None] | None = None):
        super().__init__()
        self._changed, self._slept = changed, slept
        self.locked = False
        self.asleep = False
        self._window = QWindow()  # never shown: only there to be told
        self.hwnd = int(self._window.winId())
        QCoreApplication.instance().installNativeEventFilter(self)  # sleep and resume reach every top-level window
        self.listening = False
        self._tries = 0
        self._register()

    def _register(self) -> None:
        self.listening = bool(_Register(self.hwnd, NOTIFY_FOR_THIS_SESSION))
        self._tries += 1
        if not self.listening and self._tries < self.RETRIES:
            QTimer.singleShot(10_000, self._register)

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG" and message:
            msg = wintypes.MSG.from_address(int(message))
            if msg.hWnd == self.hwnd and msg.message == WM_WTSSESSION_CHANGE and msg.wParam in AWAY:
                away = AWAY[msg.wParam]
                if away != self.locked:  # Qt shows filters a posted message twice: once queued, once dispatched
                    self.locked = away
                    self._changed(away)
            elif msg.hWnd == self.hwnd and msg.message == WM_POWERBROADCAST and msg.wParam in ASLEEP and self._slept is not None:
                asleep = ASLEEP[msg.wParam]
                if asleep != self.asleep:
                    self.asleep = asleep
                    self._slept(asleep)
        return False, 0

    def close(self) -> None:
        QCoreApplication.instance().removeNativeEventFilter(self)
        self._tries = self.RETRIES
        if self.listening:
            _Unregister(self.hwnd)
            self.listening = False
