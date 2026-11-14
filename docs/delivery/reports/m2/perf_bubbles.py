"""Timing for M2-13, M2-14 and M2-15: what drawing the painted bubbles costs.

usage: python docs/delivery/reports/m2/perf_bubbles.py [--seconds N] [--json PATH]

Run from the repository root. It uses only calls that exist before and after M2, so the same script measures
both. Numbers are wall-clock on this machine (QT_QPA_PLATFORM=offscreen), for comparing before with after, not
absolute budgets.

- M2-13: a speech bubble left showing for N seconds of its own clock, painted at the stage's 30 frames a second:
  how many frames needed drawing (its anim_key changed), and the time spent drawing them.
- M2-14: the animated ask box, open for one second of real time: paint events on the box and on its child widgets.
- M2-15: one painted bubble drawn 120 times with its notch moving one pixel each time, against 120 times with the
  notch still: milliseconds per draw.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.getcwd())

from PyQt6.QtCore import QEvent, QEventLoop, QObject, QPoint, QSizeF, QTimer  # noqa: E402
from PyQt6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from chatmon import bubbleart, styles  # noqa: E402
from chatmon.bubble import AskBox, SpeechBubble  # noqa: E402

PAINTED = ["electric", "fire", "ghost", "fairy", "leaf"]
TEXT = "Your build finished. Three tests were slow, and one of them timed out on the second run; have a look when you can."
FPS = 30


def bubble_lifetime(name: str, seconds: float) -> dict:
    bubble = SpeechBubble()
    bubble.set_style(styles.get(name), True)
    bubble.show("Build finished", TEXT, [("Show me", None), ("Later", None)], None, 0.0)
    img = QImage(600, 400, QImage.Format.Format_ARGB32_Premultiplied)
    frames, spent, last = 0, 0.0, None
    for i in range(round(seconds * FPS)):
        now = i / FPS
        bubble.tick(now)
        key = bubble.anim_key(now)
        if key == last and frames:
            continue  # the stage draws only when something changed
        last = key
        img.fill(QColor(0, 0, 0, 0))
        p = QPainter(img)
        start = time.perf_counter()
        bubble.paint(p, bubble.size.width() / 2, now)
        spent += time.perf_counter() - start
        p.end()
        frames += 1
    return {"style": name, "seconds": seconds, "frames_drawn": frames, "ms_total": round(spent * 1000, 1), "ms_per_frame": round(spent * 1000 / max(1, frames), 2)}


class Paints(QObject):
    def __init__(self, box):
        super().__init__()
        self.box, self.own, self.children = box, 0, 0

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Paint and obj.isWidgetType() and obj.window() is self.box:
            if obj is self.box:
                self.own += 1
            else:
                self.children += 1
        return False


def ask_box_second(name: str) -> dict:
    box = AskBox()
    box.set_style(styles.get(name), True)
    box.open(QPoint(600, 600), "Ask Sparky", "Enter to ask", "Ask anything", text="**You:** hello\n\nHi there! " + TEXT, activate=False)
    spin(0.3)
    paints = Paints(box)
    QApplication.instance().installEventFilter(paints)
    start = time.perf_counter()
    spin(1.0)
    elapsed = time.perf_counter() - start
    QApplication.instance().removeEventFilter(paints)
    box.dismiss()
    box.deleteLater()
    return {"style": name, "seconds": round(elapsed, 2), "box_paints": paints.own, "child_paints": paints.children}


def notch_moving(name: str, animate: bool) -> dict:
    art = bubbleart.art(name, "perf")
    text = QSizeF(300, 92)
    lo, hi = art.tail_range(text.width())
    frame = art.frame_for(text)
    img = QImage(round(frame.size.width()) * 2, round(frame.size.height()) * 2, QImage.Format.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(2.0)
    result = {"style": name, "animate": animate}
    for label, tips in (("still_notch", [lo + 20] * 120), ("moving_notch", [lo + (i % int(hi - lo)) for i in range(120)])):
        warm = QPainter(img)
        art.paint(warm, 0, 0, text, tips[0], 0.0, animate)  # warm the caches for the first place
        warm.end()
        start = time.perf_counter()
        for i, tip in enumerate(tips):
            img.fill(QColor(0, 0, 0, 0))
            p = QPainter(img)
            art.paint(p, 0, 0, text, tip, i / FPS, animate)
            p.end()
        result[f"{label}_ms_per_draw"] = round((time.perf_counter() - start) * 1000 / len(tips), 3)
    return result


def spin(seconds: float) -> None:
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=30.0, help="how long each speech bubble stays (its own clock)")
    parser.add_argument("--json", help="also write the results here")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    results = {
        "M2-13 bubble lifetime": [bubble_lifetime(n, args.seconds) for n in PAINTED],
        "M2-14 ask box, one second": [ask_box_second(n) for n in PAINTED],
        "M2-15 notch moving": [notch_moving(n, animate) for n in PAINTED for animate in (False, True)],
    }
    for section, rows in results.items():
        print(section)
        for row in rows:
            print("  " + ", ".join(f"{k}={v}" for k, v in row.items()))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
