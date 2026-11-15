"""Without Chatmon: Windows' notification state each second for 40 s, and, when it says busy, the visible windows as
big as a monitor (whose may be what it means). Silent."""

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32")
user32.GetWindowLongW.restype = ctypes.c_long
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def big() -> list[str]:
    found = []

    def each(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if rect.right - rect.left >= 1600 and rect.bottom - rect.top >= 899:
                pid, cls, title = wintypes.DWORD(0), ctypes.create_unicode_buffer(128), ctypes.create_unicode_buffer(128)
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                user32.GetClassNameW(hwnd, cls, 128)
                user32.GetWindowTextW(hwnd, title, 128)
                ex = user32.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF
                found.append(f"pid {pid.value} {cls.value!r} {title.value!r} {[rect.left, rect.top, rect.right, rect.bottom]} ex {ex:#x}")
        return True

    user32.EnumWindows(WNDENUMPROC(each), 0)
    return found


for _ in range(40):
    value = ctypes.c_int(0)
    ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(value))
    print(time.strftime("%H:%M:%S"), "state", value.value, "|", "; ".join(big()) if value.value == 2 else "", flush=True)
    time.sleep(1)
