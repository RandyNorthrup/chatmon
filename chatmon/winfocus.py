"""Windows 11: whether Focus is on (a focus session, from the Clock app or the notification centre), which
SHQueryUserNotificationState doesn't say. WinRT's FocusSessionManager.IsFocusActive (Windows 11 build 23504
and later), asked through combase with ctypes: no WinRT package for Python needed. Imported on Windows alone.
https://learn.microsoft.com/en-us/uwp/api/windows.ui.shell.focussessionmanager
The interfaces' IDs and method order are the Windows SDK's (winrt/windows.ui.shell.h, 10.0.26100).

Each answer comes from the shell, in another process, and takes a tenth of a second or more: a thread of its
own asks, never the screen's, and `active` is its latest answer."""

from __future__ import annotations

import ctypes
import threading
import uuid
from ctypes import wintypes

CLASS = "Windows.UI.Shell.FocusSessionManager"
IID_STATICS = "834df764-cb9a-5d0a-aa9f-73df4f249395"  # IFocusSessionManagerStatics
# vtable slots: IUnknown's 3 and IInspectable's 3 come first
STATICS_GET_DEFAULT, STATICS_GET_IS_SUPPORTED = 6, 7
MANAGER_GET_IS_FOCUS_ACTIVE = 6  # IFocusSessionManager
COINIT_MULTITHREADED = 0x0
EVERY = 5.0  # seconds between asking, as often as the app looks at whether to keep quiet


class _GUID(ctypes.Structure):
    _fields_ = [("bytes", ctypes.c_ubyte * 16)]

    @classmethod
    def of(cls, text: str) -> "_GUID":
        return cls.from_buffer_copy(uuid.UUID(text).bytes_le)


def _method(obj: int, slot: int, *argtypes):
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)(table[slot])


def _release(obj: int) -> None:
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])(obj)


def manager() -> int | None:
    """Windows' FocusSessionManager (an IFocusSessionManager, released by the caller), or None: an older
    Windows, or one without Focus. On a thread that has joined COM."""
    combase = ctypes.WinDLL("combase")
    combase.WindowsCreateString.argtypes = [wintypes.LPCWSTR, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
    combase.WindowsDeleteString.argtypes = [ctypes.c_void_p]
    combase.RoGetActivationFactory.argtypes = [ctypes.c_void_p, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
    name = ctypes.c_void_p()
    if combase.WindowsCreateString(CLASS, len(CLASS), ctypes.byref(name)) != 0:
        return None
    statics = ctypes.c_void_p()
    try:
        found = combase.RoGetActivationFactory(name, ctypes.byref(_GUID.of(IID_STATICS)), ctypes.byref(statics))
    finally:
        combase.WindowsDeleteString(name)
    if found != 0 or not statics.value:  # REGDB_E_CLASSNOTREG: a Windows from before it
        return None
    try:
        supported, default = ctypes.c_bool(), ctypes.c_void_p()
        _method(statics.value, STATICS_GET_IS_SUPPORTED, ctypes.POINTER(ctypes.c_bool))(statics.value, ctypes.byref(supported))
        if not supported.value:
            return None
        _method(statics.value, STATICS_GET_DEFAULT, ctypes.POINTER(ctypes.c_void_p))(statics.value, ctypes.byref(default))
        return default.value or None
    finally:
        _release(statics.value)


def is_active(focus: int) -> bool:
    on = ctypes.c_bool()
    _method(focus, MANAGER_GET_IS_FOCUS_ACTIVE, ctypes.POINTER(ctypes.c_bool))(focus, ctypes.byref(on))  # OSError if it failed
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
                _release(focus)
            ole32.CoUninitialize()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(2.0)
