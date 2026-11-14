"""Windows 11: whether Focus is on (a focus session, from the Clock app or the notification centre), which
SHQueryUserNotificationState doesn't say. WinRT's FocusSessionManager.IsFocusActive (Windows 11 build 23504
and later), asked through combase with ctypes (winrt.py): no WinRT package for Python needed. Used on Windows alone.
https://learn.microsoft.com/en-us/uwp/api/windows.ui.shell.focussessionmanager
The interfaces' IDs and method order are the Windows SDK's (winrt/windows.ui.shell.h, 10.0.26100).

Each answer comes from the shell, in another process, and takes a tenth of a second or more: a thread of its
own asks, never the screen's, and `active` is its latest answer."""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

from . import winrt

CLASS = "Windows.UI.Shell.FocusSessionManager"
IID_STATICS = "834df764-cb9a-5d0a-aa9f-73df4f249395"  # IFocusSessionManagerStatics
# vtable slots: IUnknown's 3 and IInspectable's 3 come first
STATICS_GET_DEFAULT, STATICS_GET_IS_SUPPORTED = 6, 7
MANAGER_GET_IS_FOCUS_ACTIVE = 6  # IFocusSessionManager
COINIT_MULTITHREADED = 0x0
EVERY = 5.0  # seconds between asking, as often as the app looks at whether to keep quiet


def manager() -> int | None:
    """Windows' FocusSessionManager (an IFocusSessionManager, released by the caller), or None: an older
    Windows, or one without Focus. On a thread that has joined COM."""
    statics = winrt.factory(CLASS, IID_STATICS)  # None: REGDB_E_CLASSNOTREG, a Windows from before it
    if statics is None:
        return None
    try:
        supported = ctypes.c_bool()
        winrt.method(statics, STATICS_GET_IS_SUPPORTED, ctypes.POINTER(ctypes.c_bool))(statics, ctypes.byref(supported))
        if not supported.value:
            return None
        return winrt.get_object(statics, STATICS_GET_DEFAULT)
    finally:
        winrt.release(statics)


def is_active(focus: int) -> bool:
    on = ctypes.c_bool()
    winrt.method(focus, MANAGER_GET_IS_FOCUS_ACTIVE, ctypes.POINTER(ctypes.c_bool))(focus, ctypes.byref(on))  # OSError if it failed
    return on.value


class Focus:
    """Whether Focus is on, kept up to date by a thread of its own. `active`: True, False, or None where it
    can't be told (an older Windows, one without Focus, or the shell not answering)."""

    def __init__(self, every: float = EVERY):
        self.active: bool | None = None
        self._every = every
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="chatmon-focus", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        ole32 = ctypes.WinDLL("ole32")
        ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        if ole32.CoInitializeEx(None, COINIT_MULTITHREADED) < 0:
            return
        focus = None
        try:
            focus = manager()
            while focus is not None and not self._stop.is_set():
                try:
                    self.active = is_active(focus)
                except OSError:
                    self.active = None
                self._stop.wait(self._every)
        except (OSError, AttributeError, ValueError):  # a failed HRESULT raises OSError
            pass
        finally:
            self.active = None
            if focus is not None:
                winrt.release(focus)
            ole32.CoUninitialize()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(2.0)
