"""Does Chatmon's own overlay make Windows say a full-screen app is running? No screen reader runs, so nothing is
spoken. Windows' notification state (SHQueryUserNotificationState) is read every second: before Chatmon starts, while
it runs (with its windows' rectangles and styles), and after it quits.

usage: quns_check.py OUT_DIR SOURCE_TREE SHIM [inset]
  inset: the shim's hypothesis, the stage one pixel short of the monitor's bottom edge
"""

import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

OUT, SRC, SHIM = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
user32 = ctypes.WinDLL("user32")
user32.GetWindowLongW.restype = ctypes.c_long
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
NAMES = {1: "not present", 2: "busy (full-screen app)", 3: "Direct3D full screen", 4: "presentation", 5: "accepts notifications",
         6: "quiet time", 7: "app"}
log = open(OUT / "quns.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115


def say(text: str) -> None:
    line = time.strftime("%H:%M:%S ") + text
    print(line, flush=True)
    log.write(line + "\n")


def state() -> str:
    value = ctypes.c_int(0)
    ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(value))
    fg = user32.GetForegroundWindow()
    pid, title = wintypes.DWORD(0), ctypes.create_unicode_buffer(128)
    user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
    user32.GetWindowTextW(fg, title, 128)
    return f"state {value.value} ({NAMES.get(value.value, '?')}); foreground pid {pid.value} {title.value!r}"


def windows(pid: int) -> list[str]:
    found = []

    def each(hwnd, _):
        owner = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            ex = user32.GetWindowLongW(hwnd, -20) & 0xFFFFFFFF  # GWL_EXSTYLE
            found.append(f"hwnd {hwnd} rect {[rect.left, rect.top, rect.right, rect.bottom]} exstyle {ex:#010x}"
                         f"{' TOPMOST' if ex & 0x8 else ''}{' TRANSPARENT' if ex & 0x20 else ''}{' LAYERED' if ex & 0x80000 else ''}"
                         f"{' NOACTIVATE' if ex & 0x08000000 else ''}{' TOOLWINDOW' if ex & 0x80 else ''}")
        return True

    user32.EnumWindows(WNDENUMPROC(each), 0)
    return found


for _ in range(10):
    say("before Chatmon: " + state())
    time.sleep(1)
env = dict(os.environ, PROBE_SRC=str(SRC), PROBE_TRACE=str(OUT / "chatmon-trace.jsonl"), PROBE_QUEUE="1",
           PROBE_STAGE_INSET="1" if "inset" in sys.argv[4:] else "")
say(f"hypothesis, the stage 1 px short of the monitor: {bool(env['PROBE_STAGE_INSET'])}")
app = subprocess.Popen([sys.executable, str(SHIM)], cwd=SRC, env=env, stdout=open(OUT / "chatmon-stdout.log", "w"), stderr=subprocess.STDOUT,  # noqa: SIM115
                       creationflags=0x4000)
say(f"Chatmon started (launcher pid {app.pid})")
pid = None
for i in range(25):
    time.sleep(1)
    if pid is None and (OUT / "chatmon-trace.jsonl").exists():
        starts = [json.loads(line) for line in (OUT / "chatmon-trace.jsonl").read_text(encoding="utf-8").splitlines()]
        pid = next((e["pid"] for e in starts if e["event"] == "start"), None)
    say("Chatmon running: " + state())
    if pid and i in (5, 15):
        for line in windows(pid):
            say(f"  Chatmon's window: {line}")
subprocess.run([sys.executable, "-m", "chatmon", "quit"], cwd=SRC, capture_output=True, timeout=60)
app.wait(30)
say("Chatmon quit")
for _ in range(10):
    time.sleep(1)
    say("after Chatmon: " + state())
