"""Measure whether each bubble style's animation loops cleanly, through the app's own drawing code, at
real size and real speed, over a dark and a light desktop.

usage: python art/tools/loop-qc.py OUT_DIR [--only electric,fire] [--fps 30]

One full cycle (`BubbleArt.loop_period`) is rendered at the app's redraw rate. Per style and background:

  cycle   the loop's length. Limit 3 to 8 s (the leaf's cycle is the caterpillar's whole walk and rest, so
          it is allowed up to 60 s; its gait repeats every 1.4 s).
  step    the median mean change per pixel between neighbouring frames (0-255): how much moves.
  jump    the biggest step / the median step. A pop or a frame from a different drawing shows here.
  seam    the step from the last frame back to the first / the mean of the steps either side of it. A
          clean loop's seam is an ordinary step for that moment of the cycle (how much moves can change
          through a cycle, so the median would be the wrong yardstick).
  flash   the biggest step itself (mean change per pixel, 0-255). A small sprite appearing is well under 1;
          the whole border flashing at once would be several.
  closes  the mean difference between the frame at t = 0 and the frame one whole cycle later. Must be ~0:
          the loop comes back to exactly where it began.
  flicker the share of everything that changes that changes FAST: each pixel's distance from its own
          7-frame average (what is left above about 4 Hz), squared and summed, over its whole variation
          across the cycle. Things that drift, scroll, swell or fade score low; a picture redrawn every few
          frames, or anything that jitters or races, scores high. This is the gate for "boiling" and for
          "too fast". Limit 0.10.
  boil    the share of a 6-frame change NOT explained by shifting the whole picture by up to 4 px (the
          shift test from the content library's loop_qc.py). It suits a picture that slides as a whole.
          Here the bubble stands still and only its trim moves, in different directions on each edge, so no
          one shift explains anything and it reads 1.00 for every style: it is printed for the record and
          not gated. Flicker is the measure that catches a boiling loop here.
  pop     the 99.9th percentile of one step's per-pixel change (0-255): the hardest single-frame change.
  inside  the largest change, over the whole cycle, of any pixel inside the text area. Must be 0: the fill
          and the text never move and no effect covers them.
  light   the cycle's brightness swing: the standard deviation of the frames' mean brightness over its mean.

The electric style's lightning runs round the border and its arcs crackle where it has just passed, on
purpose, so it is measured twice: without them (`-run`: what is left must be as calm as the others) and
with them (`+run`: flicker, pop and jump are reported, not gated: a pulse passing a pixel is a fast change
for that pixel, and an arc striking is always a big step against a base this calm; flash is still gated,
so no frame lights the whole rim, and so are seam, closes, inside and light). The pulses' speed along the
border is printed: whether that speed looks right is judged by watching the preview, not here.

The limits are the same for every style. Checked against loops whose answer is known (a slow whole-tile
drift and a slow glow pass; a fast scroll, a 6-frame sheet played at 8 fps, a loop that does not close and a
one-frame flash each fail on the measures they should).

Writes OUT_DIR/<style>-strip.png (12 moments across the cycle, dark), <style>-seam.png (the last three and
first three frames at 2x), qc.json, and prints the table. Exit 1 if any gated value is over its limit.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bubble_preview", HERE / "bubble-preview.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)

from PyQt6.QtCore import QSizeF  # noqa: E402

BG = {"dark": (30, 33, 40), "light": (233, 235, 240)}
LIMITS = {"jump": 2.5, "seam": 1.5, "flash": 1.5, "closes": 0.05, "flicker": 0.10, "pop": 60.0, "inside": 0.0, "light": 0.08}
CYCLE = {"default": (3.0, 8.0), "leaf": (3.0, 60.0)}
UNGATED = {"electric+run": {"flicker", "pop", "jump"}}  # running pulses and their crackle move fast on purpose
MOVING = {"Arcs", "Runner", "Wake"}  # layers left out of a style's `-run` measurement
WINDOW = 7  # frames in the moving average the fast part is measured against
LAG = 6  # frames between the two pictures the shift test compares


def flat(rgba: np.ndarray, bg: tuple[int, int, int]) -> np.ndarray:
    a = rgba[..., 3:4].astype(np.float32) / 255
    return rgba[..., :3].astype(np.float32) * a + np.array(bg, np.float32) * (1 - a)


def residual(a: np.ndarray, b: np.ndarray, reach: int = 4) -> float:
    raw = float(np.abs(b - a).max(-1).mean())
    if raw < 0.02:
        return 0.0
    h, w = a.shape[:2]
    best = raw
    for dy in range(-reach, reach + 1):
        for dx in range(-reach, reach + 1):
            sa = a[max(0, -dy) : h - max(0, dy), max(0, -dx) : w - max(0, dx)]
            sb = b[max(0, dy) : h - max(0, -dy), max(0, dx) : w - max(0, -dx)]
            best = min(best, float(np.abs(sb - sa).max(-1).mean()))
    return best / raw


def measure(render, period: float, fps: float, text_box: tuple[int, int, int, int], bg: tuple[int, int, int]) -> tuple[dict, dict[int, np.ndarray]]:
    n = max(WINDOW + 2, round(period * fps))
    x0, y0, x1, y1 = text_box
    first = flat(render(0.0), bg)
    wanted = {round(i * (n - 1) / 11) for i in range(12)} | {n - 3, n - 2, n - 1, 0, 1, 2}
    keep, steps, pops, boils, lights = {}, [], [], [], []
    inside = 0.0
    total = np.zeros(first.shape[:2], np.float64)  # per pixel: sum and sum of squares over the cycle
    total2 = np.zeros(first.shape[:2], np.float64)
    fast = 0.0
    ring: list[np.ndarray] = []  # the last WINDOW grey frames, for the moving average
    lagged: list[np.ndarray] = []
    prev = None
    for i in range(n + WINDOW - 1):  # once round, then far enough again to finish the windows that wrap
        j = i % n
        cur = first if j == 0 else flat(render(j / fps), bg)
        g = cur.mean(-1).astype(np.float64)
        if i < n:
            if j in wanted:
                keep[j] = cur
            total += g
            total2 += g * g
            lights.append(float(cur.mean()))
            inside = max(inside, float(np.abs(cur[y0:y1, x0:x1] - first[y0:y1, x0:x1]).max()))
        if prev is not None and i <= n:  # n steps: 0>1 ... n-1>0
            mag = np.abs(cur - prev).max(-1)
            steps.append(float(mag.mean()))
            pops.append(float(np.percentile(mag, 99.9)))
        lagged.append(cur)
        if len(lagged) > LAG:
            old = lagged.pop(0)
            if i % max(1, n // 30) == 0:
                boils.append(residual(old, cur))
        ring.append(g)
        if len(ring) > WINDOW:
            ring.pop(0)
        if len(ring) == WINDOW:  # the middle frame of the window against the window's mean: n windows in all
            fast += float(((ring[WINDOW // 2] - np.mean(ring, axis=0)) ** 2).sum())
        prev = cur
    after = flat(render(period), bg)
    variation = float((total2 - total * total / n).sum())
    inner = steps[:-1]
    med = max(float(np.median(inner)), 0.05)
    m = {
        "cycle": period,
        "frames": n,
        "step": float(np.median(inner)),
        "jump": max(inner) / med,
        "seam": steps[-1] / max((steps[-2] + steps[0]) / 2, 0.05),
        "flash": max(steps),
        "closes": float(np.abs(after - first).mean()),
        "flicker": fast / variation if variation > 1e-6 else 0.0,
        "boil": float(np.median(boils)) if boils else 0.0,
        "pop": max(pops),
        "inside": inside,
        "light": float(np.std(lights) / max(np.mean(lights), 1e-6)),
    }
    return m, keep


def verdict(name: str, style: str, m: dict) -> list[str]:
    bad = []
    lo, hi = CYCLE.get(style, CYCLE["default"])
    if not lo <= m["cycle"] <= hi:
        bad.append("cycle")
    for key, limit in LIMITS.items():
        if key not in UNGATED.get(name, ()) and m[key] > limit:
            bad.append(key)
    return bad


def sheets(out: Path, name: str, frames: dict[int, np.ndarray], n: int, n_strip: int = 12) -> None:
    """`frames` holds the kept frames by number: 12 spread evenly over the cycle, the first 3 and the last 3."""
    imgs = {i: Image.fromarray(np.clip(f.round(), 0, 255).astype(np.uint8)) for i, f in frames.items()}
    w, h = imgs[0].size
    picks = [imgs[round(i * (n - 1) / (n_strip - 1))] for i in range(n_strip)]
    strip = Image.new("RGB", (w * 4, h * 3))
    for i, im in enumerate(picks):
        strip.paste(im, ((i % 4) * w, (i // 4) * h))
    strip.save(out / f"{name}-strip.png")
    seam = [imgs[i] for i in (n - 3, n - 2, n - 1, 0, 1, 2)]
    sheet = Image.new("RGB", (w * 2 * 3, h * 2 * 2))
    for i, im in enumerate(seam):
        sheet.paste(im.resize((w * 2, h * 2), Image.NEAREST), ((i % 3) * w * 2, (i // 3) * h * 2))
    ImageDraw.Draw(sheet).text((6, 4), "last 3 frames of the cycle (top) run into the first 3 (bottom)", fill=(235, 235, 235))
    sheet.save(out / f"{name}-seam.png")


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    fps = float(sys.argv[sys.argv.index("--fps") + 1]) if "--fps" in sys.argv else 30.0
    app = preview.start_app()  # noqa: F841 (kept alive while drawing)
    from chatmon import bubbleart, styles

    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else [s for s in styles.STYLES if s != "plain"]
    text = QSizeF(*preview.TEXT)
    results, failed = {}, False
    head = f"{'style':15} {'bg':5} {'cycle':>6} {'step':>5} {'jump':>5} {'seam':>5} {'flash':>5} {'closes':>6} {'flicker':>7} {'boil':>5} {'pop':>4} {'inside':>6} {'light':>6}  verdict"
    print(head)
    for style in only:
        art = bubbleart.art(style)
        if art is None:
            print(f"{style}: no art")
            failed = True
            continue
        frame = art.frame_for(text)
        box = (round(frame.text.left()) + 4, round(frame.text.top()) + 4, round(frame.text.right()) + 4, round(frame.text.bottom()) + 4)
        variants = [(style, art.layers)]
        if any(type(layer).__name__ in MOVING for layer in art.layers):
            variants = [(f"{style}-run", [layer for layer in art.layers if type(layer).__name__ not in MOVING]), (f"{style}+run", art.layers)]
            frame_rim = art.rim(round(text.width()), round(text.height()), round(art.tail_range(text.width())[0]))
            for layer in art.layers:
                if type(layer).__name__ == "Runner":
                    print(f"{style}: {layer.count} pulses, {abs(layer.laps) * frame_rim.length / layer.period:.0f} px/s along a {frame_rim.length:.0f} px border")
        every = art.layers
        look = styles.get(style)
        for name, layers in variants:
            art.layers = layers
            period = art.loop_period(text)

            def render(t: float, art=art, look=look) -> np.ndarray:
                return np.asarray(preview.layer(art, look, text, t, content=False))

            for bg_name, bg in BG.items():
                m, frames = measure(render, period, fps, box, bg)
                bad = verdict(name, style, m)
                failed |= bool(bad)
                results[f"{name}/{bg_name}"] = {**{k: round(v, 3) if isinstance(v, float) else v for k, v in m.items()}, "fail": bad}
                print(
                    f"{name:15} {bg_name:5} {m['cycle']:5.1f}s {m['step']:5.2f} {m['jump']:5.2f} {m['seam']:5.2f} {m['flash']:5.2f} {m['closes']:6.3f} {m['flicker']:7.3f} {m['boil']:5.2f}"
                    f" {m['pop']:4.0f} {m['inside']:6.1f} {m['light']:6.3f}  {'FAIL ' + ', '.join(bad) if bad else 'ok'}"
                )
                if bg_name == "dark":
                    sheets(out, name, frames, m["frames"])
        art.layers = every
    (out / "qc.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
