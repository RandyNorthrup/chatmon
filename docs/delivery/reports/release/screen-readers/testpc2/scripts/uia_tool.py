"""Small UI Automation and desktop helpers for the probe, run in testpc2's console session (job.ps1).

usage: uia_tool.py windows                      visible top-level windows: pid, class, title, rectangle
       uia_tool.py fg                           the foreground window
       uia_tool.py tree CLASS [DEPTH]           the UI Automation tree of the top-level window of that class
       uia_tool.py invoke CLASS ID|NAME         invoke (or toggle, or select) the element of that automation id or name
       uia_tool.py start EXE [ARGS...]          start a program and leave it running
       uia_tool.py close CLASS                  WM_CLOSE to each visible top-level window of that class
       uia_tool.py shot PATH                    a PNG of the whole desktop (Qt's screen grab)
"""

import sys

sys.coinit_flags = 0

import ctypes  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402
from ctypes import wintypes  # noqa: E402

import comtypes  # noqa: E402
import comtypes.client  # noqa: E402

UIA = comtypes.client.GetModule("UIAutomationCore.dll")
automation = comtypes.client.CreateObject(UIA.CUIAutomation8, interface=UIA.IUIAutomation5)
user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetForegroundWindow.restype = wintypes.HWND
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
CONTROL_TYPES = {v: k for k, v in vars(UIA).items() if k.startswith("UIA_") and k.endswith("ControlTypeId")}


def info(hwnd) -> str:
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    title, cls, rect = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(256), wintypes.RECT()
    user32.GetWindowTextW(hwnd, title, 256)
    user32.GetClassNameW(hwnd, cls, 256)
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return f"hwnd {hwnd} pid {pid.value} class {cls.value!r} title {title.value!r} rect {[rect.left, rect.top, rect.right, rect.bottom]}"


def top(cls: str):
    return automation.GetRootElement().FindFirst(UIA.TreeScope_Children, automation.CreatePropertyCondition(UIA.UIA_ClassNamePropertyId, cls))


def dump(element, depth: int, indent: int = 0) -> None:
    r = element.CurrentBoundingRectangle
    kind = CONTROL_TYPES.get(element.CurrentControlType, element.CurrentControlType)
    print(f"{'  ' * indent}{kind} name={element.CurrentName!r} id={element.CurrentAutomationId!r} class={element.CurrentClassName!r} "
          f"rect={[r.left, r.top, r.right, r.bottom]} enabled={element.CurrentIsEnabled}")
    if indent >= depth:
        return
    walker = automation.ControlViewWalker
    child = walker.GetFirstChildElement(element)
    while child:
        dump(child, depth, indent + 1)
        child = walker.GetNextSiblingElement(child)


def walk_find(element, key: str, depth: int = 0):
    """The first element under `element` (the control view, as the tree shows it) whose automation id or name is `key`."""
    if depth and key in (element.CurrentAutomationId, element.CurrentName):
        return element
    if depth > 14:
        return None
    walker = automation.ControlViewWalker
    child = walker.GetFirstChildElement(element)
    while child:
        found = walk_find(child, key, depth + 1)
        if found:
            return found
        child = walker.GetNextSiblingElement(child)
    return None


def main() -> int:
    what = sys.argv[1]
    if what == "windows":
        def each(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                print(info(hwnd))
            return True

        user32.EnumWindows(WNDENUMPROC(each), 0)
    elif what == "fg":
        print(info(user32.GetForegroundWindow()))
    elif what == "tree":
        window = top(sys.argv[2])
        if not window:
            print(f"no top-level window of class {sys.argv[2]!r}")
            return 1
        dump(window, int(sys.argv[3]) if len(sys.argv) > 3 else 8)
    elif what == "invoke":
        window = top(sys.argv[2])
        if not window:
            print(f"no top-level window of class {sys.argv[2]!r}")
            return 1
        found = walk_find(window, sys.argv[3])  # walked, not FindFirst: that doesn't reach into a XAML island's content
        if not found:
            print(f"no element named {sys.argv[3]!r}")
            return 1
        for pattern, iface, call in ((UIA.UIA_InvokePatternId, UIA.IUIAutomationInvokePattern, "Invoke"),
                                     (UIA.UIA_TogglePatternId, UIA.IUIAutomationTogglePattern, "Toggle"),
                                     (UIA.UIA_SelectionItemPatternId, UIA.IUIAutomationSelectionItemPattern, "Select")):
            got = found.GetCurrentPattern(pattern)
            if got:
                getattr(got.QueryInterface(iface), call)()
                print(f"{call} on {sys.argv[3]!r}")
                return 0
        print(f"{sys.argv[3]!r} has no invoke, toggle or select pattern")
        return 1
    elif what == "captest":
        # A sentence said through SAPI to the speakers, then the text Live captions shows, as UI Automation reads it.
        voice = comtypes.client.CreateObject("SAPI.SpVoice")
        voice.Speak("Testing live captions on this computer: one, two, three.")
        time.sleep(3)
        window = top("LiveCaptionsDesktopWindow")
        texts = []

        def gather(element, depth=0):
            if element.CurrentControlType == UIA.UIA_TextControlTypeId:
                texts.append((element.CurrentAutomationId, element.CurrentName))
            walker = automation.ControlViewWalker
            child = walker.GetFirstChildElement(element)
            while child and depth < 14:
                gather(child, depth + 1)
                child = walker.GetNextSiblingElement(child)

        if window:
            gather(window)
        for automation_id, name in texts:
            print(f"text id={automation_id!r}: {name!r}")
    elif what == "quiet":
        # What Chatmon asks Windows before showing a bubble that came on its own (presence._win_quiet), as this session sees it.
        sys.path.insert(0, r"W:\chatmon-sr\src")
        from chatmon import presence

        state = ctypes.c_int(0)
        hr = ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state))
        duration = ctypes.c_uint(0)
        ctypes.windll.user32.SystemParametersInfoW(0x2016, 0, ctypes.byref(duration), 0)  # SPI_GETMESSAGEDURATION
        print(f"SHQueryUserNotificationState: hr {hr}, state {state.value}; Chatmon reads it as {presence._win_quiet()!r}")
        print(f"message duration (s): {duration.value}")
        print("foreground: " + info(user32.GetForegroundWindow()))
    elif what == "start":
        process = subprocess.Popen(sys.argv[2:], close_fds=True, creationflags=0x00000008)  # DETACHED_PROCESS
        print(f"started pid {process.pid}: {sys.argv[2:]}")
        time.sleep(3)
    elif what == "close":
        def close(hwnd, _):
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if user32.IsWindowVisible(hwnd) and cls.value == sys.argv[2]:
                print("WM_CLOSE to " + info(hwnd))
                user32.PostMessageW(hwnd, 0x0010, 0, 0)
            return True

        user32.EnumWindows(WNDENUMPROC(close), 0)
    elif what == "shot":
        from PyQt6.QtWidgets import QApplication

        app = QApplication([])
        image = app.primaryScreen().grabWindow(0)
        print(f"saved {sys.argv[2]}: {image.save(sys.argv[2], 'PNG')}, {image.width()}x{image.height()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
