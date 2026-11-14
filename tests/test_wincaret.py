"""Magnifier and new bubbles (wincaret.py): a hidden system caret over the bubble, as Windows itself reports it
(GetGUIThreadInfo) and the caret event Magnifier listens for (a WinEvent hook)."""

import ctypes
import os
import subprocess
import sys
import time
import uuid

import pytest

from chatmon import wincaret

windows = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

EVENT_OBJECT_LOCATIONCHANGE = 0x800B
OBJID_CARET = -8
WINEVENT_OUTOFCONTEXT = 0x0
WS_POPUP = 0x80000000


def _user32():
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.c_void_p]
    user32.SetWinEventHook.restype = wintypes.HANDLE
    user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
    return user32


def caret_of_this_thread():
    """(window, (left, top, right, bottom)) of this thread's caret, as Windows tells assistive tools."""
    from ctypes import wintypes

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                    ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND), ("hwndMoveSize", wintypes.HWND),
                    ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT)]

    info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    assert _user32().GetGUIThreadInfo(ctypes.WinDLL("kernel32").GetCurrentThreadId(), ctypes.byref(info))
    r = info.rcCaret
    return info.hwndCaret or None, (r.left, r.top, r.right, r.bottom)


@windows
def test_a_new_bubble_gets_the_caret_magnifier_follows(qapp):
    from ctypes import wintypes

    user32 = _user32()
    hwnd = user32.CreateWindowExW(0, "STATIC", "chatmon caret test", WS_POPUP, 100, 100, 400, 300, None, None, None, None)  # never shown
    assert hwnd
    heard = []
    WINEVENTPROC = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND, wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
    proc = WINEVENTPROC(lambda hook, event, window, obj, child, thread, when: heard.append((window, obj)))
    hook = user32.SetWinEventHook(EVENT_OBJECT_LOCATIONCHANGE, EVENT_OBJECT_LOCATIONCHANGE, None, proc, os.getpid(), 0, WINEVENT_OUTOFCONTEXT)
    caret = wincaret.Caret()
    try:
        assert caret.place(hwnd, 30, 40, 200, 60) and caret.window == hwnd
        assert caret_of_this_thread() == (hwnd, (30, 40, 230, 100))
        deadline = time.monotonic() + 3
        while (hwnd, OBJID_CARET) not in heard and time.monotonic() < deadline:
            qapp.processEvents()  # an out-of-context hook hears through this thread's messages
            time.sleep(0.01)
        assert (hwnd, OBJID_CARET) in heard  # what Magnifier listens for
        assert caret.place(hwnd, 5, 6, 0, 0)  # a degenerate bubble still gets a caret, one pixel square
        assert caret_of_this_thread() == (hwnd, (5, 6, 6, 7))
    finally:
        caret.clear()
        user32.UnhookWinEvent(hook)
    assert caret.window is None and caret_of_this_thread()[0] is None
    user32.DestroyWindow(hwnd)
    assert not caret.place(0, 1, 1, 1, 1)  # no window, no caret


def magnify_exe_running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Magnify.exe", "/NH"], capture_output=True, text=True, timeout=30)
    return "magnify.exe" in out.stdout.lower()


@windows
def test_the_caret_is_only_for_when_magnifier_runs():
    from ctypes import wintypes

    assert wincaret.magnifier_running() == magnify_exe_running()
    # A window of Magnifier's class, as Magnify.exe has while it runs.
    user32 = _user32()
    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    proc = WNDPROC(lambda h, m, w, l: user32.DefWindowProcW(h, m, w, l))
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE  # a pointer: never let it be cut down to an int
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    instance = kernel32.GetModuleHandleW(None)
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
    atom = user32.RegisterClassW(ctypes.byref(WNDCLASSW(lpfnWndProc=proc, hInstance=instance, lpszClassName=wincaret.MAGNIFIER_CLASS)))
    if not atom:
        pytest.skip("Magnifier's window class is taken in this process")
    hwnd = user32.CreateWindowExW(0, wincaret.MAGNIFIER_CLASS, f"test {uuid.uuid4().hex[:6]}", WS_POPUP, 0, 0, 10, 10, None, None, instance, None)
    try:
        assert hwnd and wincaret.magnifier_running()
    finally:
        user32.DestroyWindow(hwnd)
        user32.UnregisterClassW(wincaret.MAGNIFIER_CLASS, instance)
    assert wincaret.magnifier_running() == magnify_exe_running()


@pytest.mark.skipif(sys.platform == "win32", reason="elsewhere than Windows")
def test_elsewhere_there_is_no_caret_to_place():
    assert not wincaret.magnifier_running() and not wincaret.place(1, 1, 1, 1, 1)
    wincaret.clear()
