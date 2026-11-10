"""Measure the companions' animation strips and fail if any is out of limits.

Usage: python creature-qc.py [<creature> ...] [--anim-dir <dir>] [--size 120]
  creature    which to check (default: every creature in creatures.json)
  --anim-dir  where the strips are (default: ../../chatmon/anim)
  --size      the on-screen height the limits are judged at (the app's default, 120)
Prints one row per strip and exits 1 if any check fails. Needs Pillow and numpy.

What it measures, and the limit (limits are in screen pixels at --size, never in strip pixels):
  size    the strip is frames x w by h as its manifest entry says, and all twelve are there
  fringe  edge pixels (alpha above 32, within 2 px of a pixel that isn't) that still look keyed:
          within 100 RGB levels of the key colour, or the key's hue and more than 10 levels tinted
          its way. Limit: 0
  x       how far the animation's anchor (creatures.json: the body, the feet, a belly mark, the
          cut line...) moves left to right over the frames. Limit: 1 px spread
  y       how far the floor line (the lowest row of the body; floating: the tail tip) moves over
          the frames that stand on it. Frames in the air and animations kept as drawn (a float
          cycle) are not judged. Limit: 1 px spread
  head    the head's size against the idle strip's, as drawn on screen: the head is found by
          sliding idle's (or, for side views, turn's) over the frame at a range of sizes and taking
          the best match. Limit: within 3 percent
  border  pixels with alpha above 32 on a frame's outermost rows and columns (clipping). Limit: 0
  specks  loose pieces under 12 px, more than 6 px from the creature, that are not meant: any in an
          animation without loose effects, and faint ones (no pixel above half alpha) in one with
          them. Limit: 0. Loose pieces that are meant (sparkles, embers, leaves) are counted in
          the last column, for the eye to check.
What it cannot judge: whether the motion reads well, and whether a frame is drawn on-model.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import creaturespec as cs  # noqa: E402
import spritefix  # noqa: E402

DRIFT = 1.0  # screen px
HEAD = 3.0  # percent
WORK = 2.0  # px per screen px when matching heads


def spread(values: list[float]) -> float:
    return max(values) - min(values) if values else 0.0


def drift(frames: list[np.ndarray], a: dict, colours: dict, factor: float) -> tuple[float | None, float | None]:
    """The anchor's spread left to right and the floor's spread top to bottom, in screen px."""
    n = len(frames)
    how = a.get("check", a["x"])
    how = how if isinstance(how, dict) else {"by": how}
    x = None
    if how["by"] != "none":
        worst = 0.0
        for group in how.get("groups") or [list(range(1, n + 1))]:
            shifts = [cs.shift_between(frames[group[0] - 1], frames[g - 1], colours, how) for g in group]
            if any(s is None for s in shifts):
                return float("inf"), None
            worst = max(worst, spread(shifts))
        x = worst * factor
    y = a.get("y", {})
    floors = None
    if y.get("pin", "each") == "each":
        rows = [cs.floor_row(frames[g - 1], colours) for g in y.get("floor", range(1, n + 1))]
        floors = float("inf") if any(r is None for r in rows) else spread(rows) * factor
    return x, floors


# -- the head's size


def _grey(frame: np.ndarray, factor: float) -> np.ndarray:
    """A frame at WORK px per screen px, over mid grey, as luma."""
    size = (max(8, round(frame.shape[1] * factor * WORK)), max(8, round(frame.shape[0] * factor * WORK)))
    f = spritefix.resize_rgba(frame, size).astype(float)
    alpha = f[..., 3:4] / 255
    return ((f[..., :3] * alpha + 128 * (1 - alpha)) @ np.array([0.299, 0.587, 0.114])).astype(np.float32)


def _best_match(image: np.ndarray, templ: np.ndarray) -> float:
    """The highest normalised cross-correlation of `templ` anywhere in `image`."""
    h, w = templ.shape
    pad_y, pad_x = h // 3, w // 3
    image = np.pad(image, ((pad_y, pad_y), (pad_x, pad_x)), constant_values=128.0)
    big_h, big_w = image.shape
    if h > big_h or w > big_w:
        return -1.0
    t = templ - templ.mean()
    norm = float(np.sqrt((t**2).sum()))
    shape = (big_h, big_w)
    corr = np.fft.irfft2(np.fft.rfft2(image, shape) * np.conj(np.fft.rfft2(t, shape)), shape)[: big_h - h + 1, : big_w - w + 1]

    def box(values: np.ndarray) -> np.ndarray:
        c = np.pad(values.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        return c[h:, w:] - c[:-h, w:] - c[h:, :-w] + c[:-h, :-w]

    image = image.astype(np.float64)
    var = box(image**2) - box(image) ** 2 / (h * w)
    busy = var > 0.1 * norm**2  # a flat patch of background matches nothing
    return float(np.where(busy, corr / (norm * np.sqrt(np.maximum(var, 1e-6))), -1.0).max())


def relative_size(image: np.ndarray, templ: np.ndarray) -> float:
    """How large what `templ` shows is drawn in `image`, as a ratio: the template size that matches best."""
    sizes = np.arange(0.78, 1.2401, 0.01)
    scores = []
    for s in sizes:
        t = np.asarray(Image.fromarray(templ).resize((max(4, round(templ.shape[1] * s)), max(4, round(templ.shape[0] * s))), Image.LANCZOS))
        scores.append(_best_match(image, t))
    i = int(np.argmax(scores))
    if 0 < i < len(sizes) - 1:  # the top of the parabola through the best three
        a, b, c = scores[i - 1], scores[i], scores[i + 1]
        if a - 2 * b + c < 0:
            return float(sizes[i] + 0.01 * 0.5 * (a - c) / (a - 2 * b + c))
    return float(sizes[i])


def _box(frame_grey: np.ndarray, frame: np.ndarray, factor: float, box: dict) -> np.ndarray:
    """The part of a frame the table calls its head: a share of the creature's own box."""
    solid = spritefix.main_part(frame[..., 3] > cs.SOLID)
    rows, cols = np.nonzero(solid.any(1))[0], np.nonzero(solid.any(0))[0]
    k = factor * WORK
    top, left = rows.min() * k, cols.min() * k
    height, width = (rows.max() + 1 - rows.min()) * k, (cols.max() + 1 - cols.min()) * k
    y0, y1 = round(top + box["y"][0] * height), round(top + box["y"][1] * height)
    x0, x1 = round(left + box["x"][0] * width), round(left + box["x"][1] * width)
    return frame_grey[max(0, y0) : y1, max(0, x0) : x1]


def head_sizes(strips: dict, manifest: dict, c: dict, spec: dict, creature: str, size: float) -> dict[str, float]:
    """Each animation's head size on screen against idle's, in percent off (0: the same size)."""
    heads = c["heads"]

    def view(anim: str, frame: int) -> tuple[np.ndarray, np.ndarray, float]:
        f = cs.frames_of(strips[anim], manifest[anim])[frame - 1]
        factor = cs.screen_factor(manifest[anim], size)
        return _grey(f, factor), f, factor

    def against(ref: tuple, ref_box: dict, anim: str, frame: int, reverse: dict | None) -> float:
        grey, f, factor = view(anim, frame)
        if reverse:  # only part of the head shows: slide that over the reference instead
            return 1 / relative_size(ref[0], _box(grey, f, factor, reverse))
        return relative_size(grey, _box(ref[0], ref[1], ref[2], ref_box))

    front = view("idle", heads["front"].get("frame", 1))
    turn_front = against(front, heads["front"], "turn", heads["turn_front"], None)
    side = view("turn", heads["turn_side"])
    out = {}
    for anim in manifest:
        a = cs.anim_spec(spec, creature, anim)
        h = a.get("head", {})
        if anim == "idle":
            ratio = 1.0
        elif anim == "turn":
            ratio = turn_front
        elif h.get("view") == "side":
            ratio = turn_front * against(side, heads["side"], anim, h.get("frame", 1), None)
        else:
            ratio = against(front, heads["front"], anim, h.get("frame", 1), h.get("part"))
        out[anim] = (ratio - 1) * 100
    return out


# -- the table


def check(creature: str, spec: dict, anim_dir: str, size: float) -> bool:
    c = spec["creatures"][creature]
    colours = c.get("colours", {})
    key = cs.KEYS[c.get("key", "green")]
    folder = os.path.join(anim_dir, creature)
    try:
        with open(os.path.join(folder, "manifest.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
    except OSError as exc:
        print(f"{creature}: no manifest ({exc})")
        return False
    ok = list(manifest) == list(spec["playback"])
    if not ok:
        print(f"{creature}: the manifest has {list(manifest)}, not the twelve animations in order")
    strips, sized = {}, {}
    for anim, m in manifest.items():
        try:
            strips[anim] = np.asarray(Image.open(os.path.join(folder, f"{anim}.png")).convert("RGBA"))
        except OSError:
            strips[anim] = np.zeros((1, 1, 4), np.uint8)
        fps, loop = spec["playback"].get(anim, (None, None))
        sized[anim] = strips[anim].shape[:2] == (m["h"], m["frames"] * m["w"]) and m["h"] == spec["frame_height"] and (m["fps"], m["loop"]) == (fps, loop)
    usable = {k: v for k, v in strips.items() if sized[k]}
    heads = head_sizes(usable, manifest, c, spec, creature, size) if len(usable) == len(manifest) and "heads" in c else {}
    print(f"\n{creature} (at {size:g} px; limits: fringe 0, x and y {DRIFT:g} px, head {HEAD:g}%, border 0, specks 0)")
    print(f"  {'anim':7}{'frames':>7}{'size':>6}{'fringe':>8}{'x px':>7}{'y px':>7}{'head %':>8}{'border':>8}{'specks':>8}{'loose':>7}  verdict")
    for anim, m in manifest.items():
        if not sized[anim]:
            print(f"  {anim:7}{m['frames']:>7}{'BAD':>6}{'':>52}  FAIL (strip and manifest disagree)")
            ok = False
            continue
        a = cs.anim_spec(spec, creature, anim)
        frames = cs.frames_of(strips[anim], m)
        factor = cs.screen_factor(m, size)
        fringe = sum(int(spritefix.key_spill(f, key).sum()) for f in frames)
        x, y = drift(frames, a, colours, factor)
        border = sum(int((f[0, :, 3] > cs.SHOWN).sum() + (f[-1, :, 3] > cs.SHOWN).sum() + (f[:, 0, 3] > cs.SHOWN).sum() + (f[:, -1, 3] > cs.SHOWN).sum()) for f in frames)
        counted = [cs.stray_specks(f, bool(a.get("loose")))[1:] for f in frames]
        bad, meant = sum(b for b, _ in counted), sum(g for _, g in counted)
        head = heads.get(anim)
        fails = []
        if fringe:
            fails.append("fringe")
        if x is not None and x > DRIFT:
            fails.append("x")
        if y is not None and y > DRIFT:
            fails.append("y")
        if head is None or abs(head) > HEAD:
            fails.append("head")
        if border:
            fails.append("border")
        if bad:
            fails.append("specks")
        ok = ok and not fails

        def cell(v: float | None, digits: int = 2) -> str:
            return "-" if v is None else f"{v:.{digits}f}"

        print(f"  {anim:7}{m['frames']:>7}{'ok':>6}{fringe:>8}{cell(x):>7}{cell(y):>7}{cell(head, 1):>8}{border:>8}{bad:>8}{meant:>7}  " + ("ok" if not fails else "FAIL " + ", ".join(fails)))
    return ok


def main(argv: list[str]) -> int:
    args = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] not in ("--anim-dir", "--size"))]
    anim_dir = argv[argv.index("--anim-dir") + 1] if "--anim-dir" in argv else str(cs.ANIM_ROOT)
    size = float(argv[argv.index("--size") + 1]) if "--size" in argv else 120.0
    spec = cs.load()
    unknown = [a for a in args if a not in spec["creatures"]]
    if unknown:
        sys.exit(f"{', '.join(unknown)}: not in creatures.json (the penguin's strips are checked by tests/test_anim_strips.py)")
    results = [check(creature, spec, anim_dir, size) for creature in (args or list(spec["creatures"]))]
    print("\n" + ("all strips within limits" if all(results) else "FAILED: see the rows marked FAIL"))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
