"""Windows: hear when you step away and come back, so time away counts as a break: the screen locking and
unlocking, a Remote Desktop or console session disconnecting (which doesn't lock), and sleep and resume. And
whether anything on screen can be seen at all (the session unlocked, its display on), which Microsoft asks
apps to stop drawing without, and Energy Saver (battery saver), which asks them to draw less.

Windows tells a window that asked (WTSRegisterSessionNotification) with WM_WTSSESSION_CHANGE, every
top-level window WM_POWERBROADCAST, and a window that registered for a power setting
(RegisterPowerSettingNotification) PBT_POWERSETTINGCHANGE, first with the setting as it stands, then as it
changes. A native event filter hears them. Imported on Windows alone.
https://learn.microsoft.com/en-us/windows/win32/termserv/wm-wtssession-change
https://learn.microsoft.com/en-us/windows/win32/power/wm-powerbroadcast
https://learn.microsoft.com/en-us/windows/win32/power/power-setting-guids"""

from __future__ import annotations

import ctypes
import uuid
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
PBT_POWERSETTINGCHANGE = 0x8013
NOTIFY_FOR_THIS_SESSION = 0
DEVICE_NOTIFY_WINDOW_HANDLE = 0
AWAY = {WTS_SESSION_LOCK: True, WTS_SESSION_UNLOCK: False, WTS_CONSOLE_DISCONNECT: True, WTS_REMOTE_DISCONNECT: True,
        WTS_CONSOLE_CONNECT: False, WTS_REMOTE_CONNECT: False}
ASLEEP = {PBT_APMSUSPEND: True, PBT_APMRESUMESUSPEND: False, PBT_APMRESUMEAUTOMATIC: False}

# The power settings listened for (winnt.h). This session's display: 0 off, 1 on, 2 dimmed (on). Energy Saver
# from Windows 11 24H2: 0 off, 1 standard, 2 high savings; before it, battery saver: 0 off, 1 on.
SESSION_DISPLAY_STATUS = uuid.UUID("2b84c20e-ad23-4ddf-93db-05ffbd7efca5")
ENERGY_SAVER_STATUS = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")
POWER_SAVING_STATUS = uuid.UUID("e00958c0-c213-4ace-ac77-fecced2eeea5")
DISPLAY_OFF = 0


class POWERBROADCAST_SETTING(ctypes.Structure):
    _fields_ = [("PowerSetting", ctypes.c_ubyte * 16), ("DataLength", wintypes.DWORD), ("Data", ctypes.c_ubyte * 4)]


_wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)
_Register = _wtsapi32.WTSRegisterSessionNotification
_Register.restype, _Register.argtypes = wintypes.BOOL, [wintypes.HWND, wintypes.DWORD]
_Unregister = _wtsapi32.WTSUnRegisterSessionNotification
_Unregister.restype, _Unregister.argtypes = wintypes.BOOL, [wintypes.HWND]
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_RegisterPower = _user32.RegisterPowerSettingNotification
_RegisterPower.restype, _RegisterPower.argtypes = ctypes.c_void_p, [wintypes.HANDLE, ctypes.c_char_p, wintypes.DWORD]
_UnregisterPower = _user32.UnregisterPowerSettingNotification
_UnregisterPower.restype, _UnregisterPower.argtypes = wintypes.BOOL, [ctypes.c_void_p]


def power_setting(address: int) -> tuple[uuid.UUID, int] | None:
    """(which setting, its value) from a PBT_POWERSETTINGCHANGE's POWERBROADCAST_SETTING; None if it has no
    DWORD's worth of data."""
    if not address:
        return None
    setting = POWERBROADCAST_SETTING.from_address(address)
    if setting.DataLength < 4:
        return None
    return uuid.UUID(bytes_le=bytes(setting.PowerSetting)), int.from_bytes(bytes(setting.Data), "little")


class LockWatcher(QAbstractNativeEventFilter):
    """Calls `changed(True)` when you step away (the screen locks, the session disconnects) and
    `changed(False)` when you're back; `slept(True)` as the computer goes to sleep, `slept(False)` on waking;
    `seen(False)` when nothing on screen can be seen (locked, disconnected, or the display off) and
    `seen(True)` when it can again; `saving(True)` while Energy Saver is on."""

    RETRIES = 12  # registering can fail early in a login, before Remote Desktop Services is ready: try again

    def __init__(self, changed: Callable[[bool], None], slept: Callable[[bool], None] | None = None,
                 seen: Callable[[bool], None] | None = None, saving: Callable[[bool], None] | None = None):
        super().__init__()
        self._changed, self._slept, self._seen, self._saving = changed, slept, seen, saving
        self.locked = False
        self.asleep = False
        self.display_on = True
        self.visible = True  # what `seen` was last told
        self.power_saving = False
        self._settings: dict[uuid.UUID, int] = {}
        self._window = QWindow()  # never shown: only there to be told
        self.hwnd = int(self._window.winId())
        QCoreApplication.instance().installNativeEventFilter(self)  # sleep and resume reach every top-level window
        self.listening = False
        self._tries = 0
        self._register()
        # Each is told at once as it stands, then as it changes.
        self._power = [handle for handle in (_RegisterPower(self.hwnd, guid.bytes_le, DEVICE_NOTIFY_WINDOW_HANDLE)
                                             for guid in (SESSION_DISPLAY_STATUS, ENERGY_SAVER_STATUS, POWER_SAVING_STATUS)) if handle]

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
                    self._tell_seen()
            elif msg.hWnd == self.hwnd and msg.message == WM_POWERBROADCAST and msg.wParam in ASLEEP and self._slept is not None:
                asleep = ASLEEP[msg.wParam]
                if asleep != self.asleep:
                    self.asleep = asleep
                    self._slept(asleep)
            elif msg.hWnd == self.hwnd and msg.message == WM_POWERBROADCAST and msg.wParam == PBT_POWERSETTINGCHANGE:
                setting = power_setting(msg.lParam or 0)
                if setting is not None:
                    self._setting(*setting)
        return False, 0

    def _setting(self, guid: uuid.UUID, value: int) -> None:
        self._settings[guid] = value
        if guid == SESSION_DISPLAY_STATUS:
            self.display_on = value != DISPLAY_OFF  # dimmed is still on
            self._tell_seen()
        elif guid in (ENERGY_SAVER_STATUS, POWER_SAVING_STATUS):
            # Energy Saver's own word where Windows has it (24H2 on); battery saver's before it.
            on = self._settings.get(ENERGY_SAVER_STATUS, self._settings.get(POWER_SAVING_STATUS, 0)) != 0
            if on != self.power_saving:
                self.power_saving = on
                if self._saving is not None:
                    self._saving(on)

    def _tell_seen(self) -> None:
        visible = self.display_on and not self.locked
        if visible != self.visible:
            self.visible = visible
            if self._seen is not None:
                self._seen(visible)

    def close(self) -> None:
        QCoreApplication.instance().removeNativeEventFilter(self)
        self._tries = self.RETRIES
        for handle in self._power:
            _UnregisterPower(handle)
        self._power = []
        if self.listening:
            _Unregister(self.hwnd)
            self.listening = False
