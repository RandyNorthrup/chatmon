"""M3-04's measurement: the overlay's buffers on a real sway, headless, at a 4K output with a scale of 2.

Run in WSL (or any Linux with sway, grim and the test requirements) with the checkout to measure as its argument:

    python docs/delivery/reports/m3/memory.py /path/to/checkout [--window] > memory-<which>.json

The checkout's own tests/sway_session.py starts sway and a whole Chatmon (tests/app_harness) on it. For each
moment below it reads, inside Chatmon, the overlay's buffers (count, pixel size, bytes) and its shared-memory
mappings (/proc/self/smaps, the "memfd:chatmon" ones: size, resident, proportional; and RssShmem), how many frames
the overlay drew in the 2 s before, and sway's resident shared memory (/proc/<sway>/status RssShmem: sway maps every
buffer it's given; its smaps aren't readable, as sway isn't dumpable).

`--window` first opens a plain window, which sway tiles over the whole output under the overlay, as on a desktop
with a window open. Without one, sway shows a full-output overlay buffer directly ("direct scan-out", in its log)
instead of compositing into its own: its own memory then looks smaller than on any real desktop.
"""

import json
import sys
import tempfile
import time
from pathlib import Path

root = Path(sys.argv[1]).resolve()
window = "--window" in sys.argv[2:]
sys.path.insert(0, str(root / "tests"))
sys.path.insert(0, str(root))

import os  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
import sway_session  # noqa: E402

COUNT_FRAMES = r"""
import time
frames = []
done = surface._frame_done
def counted(opcode, args):
    frames.append(time.monotonic())
    done(opcode, args)
surface._frame_done = counted  # each frame callback the compositor answers: one frame drawn
"""

MEASURE = r"""
import re, time
def shmem(pid):
    with open(f"/proc/{pid}/status") as f:
        return next(int(line.split()[1]) for line in f if line.startswith("RssShmem:"))
def smaps(pid):
    total = {"mappings": 0, "size_kb": 0, "rss_kb": 0, "pss_kb": 0}
    mine = False
    with open(f"/proc/{pid}/smaps") as f:
        for line in f:
            if re.match(r"^[0-9a-f]+-[0-9a-f]+ ", line):
                mine = "memfd:chatmon" in line
                total["mappings"] += mine
            elif mine and line.split(":")[0] in ("Size", "Rss", "Pss"):
                total[line.split(":")[0].lower() + "_kb"] += int(line.split()[1])
    return total
bufs = list(surface._buffers)
now = time.monotonic()
result = {
    "buffers": [[b.width, b.height] for b in bufs],
    "buffer_bytes": sum(b.width * b.height * 4 for b in bufs),
    "backdrop_pixel": bool(getattr(surface, "_backdrop", None)),
    "box": getattr(surface, "_box", None) and list(surface._box.getRect()),
    "output": list(surface._size), "scale": surface._scale(),
    "bubble": stage.bubble.drawn(), "ask_box": box.isVisible(), "menu": stage.menu.is_open(),
    "frames_last_2s": sum(1 for t in frames if now - t < 2),
    "chatmon": {**smaps("self"), "rss_shmem_kb": shmem("self")},
}
"""

DESKTOP_WINDOW = r"""
desk = QtWidgets.QWidget()
desk.setWindowTitle("a window under the overlay")
desk.setStyleSheet("background: #336")
desk.show()
until(lambda: desk.windowHandle() is not None and desk.windowHandle().isExposed(), 5)
"""


def measure(probe, session, label):
    probe.call("settled()", settle=0.3)
    found = probe.call(MEASURE)
    with open(f"/proc/{session.sway.pid}/status", encoding="utf-8") as f:
        found["sway"] = {"rss_shmem_kb": next(int(line.split()[1]) for line in f if line.startswith("RssShmem:"))}
    found["moment"] = label
    return found


folder = Path(tempfile.mkdtemp(prefix="m3-memory-"))
session = sway_session.Session(folder, mode="3840x2160", scale=2)
results = []
try:
    probe = sway_session.Probe(session)
    try:
        probe.call(COUNT_FRAMES)
        if window:
            probe.call(DESKTOP_WINDOW, settle=0.5)
        # Standing still (not walking about), so the moments compare; the greeting comes 1.5 s in.
        probe.call("import time; c.behavior.set_walk(False, time.monotonic()); until(lambda: stage.bubble.drawn(), 2.5)")
        results.append(measure(probe, session, "its greeting bubble showing"))
        probe.call("stage.dismiss_message(); until(lambda: not stage.bubble.drawn(), 5)")
        time.sleep(5)
        results.append(measure(probe, session, "nothing showing but the chatmon, 5 s on"))
        probe.call("stage.show_message('A reminder', 'Stretch your legs: it has been an hour since you last stood up. ' * 3)")
        results.append(measure(probe, session, "a bubble just shown"))
        probe.call("c.open_ask()", settle=0.5)
        results.append(measure(probe, session, "the ask box open on the overlay"))
        probe.call("c.show_menu(stage.head_point())", settle=0.5)
        results.append(measure(probe, session, "the penguin's menu open over the ask box"))
        probe.call("stage.close_menu(); box.dismiss(); stage.dismiss_message()")
        time.sleep(5)
        results.append(measure(probe, session, "everything closed, 5 s on"))
    finally:
        probe.close()
    swaylog = session.log("sway")
finally:
    session.close()
scanout = [line.split("] ")[-1] for line in swaylog.splitlines() if "Direct scan-out" in line]  # sway's own word, each time it changed
print(json.dumps({"checkout": str(root), "window_under_it": window, "sway_scanout_changes": scanout, "results": results}, indent=1))
