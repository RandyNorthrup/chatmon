"""Cut the companions' sprite sheets into the app's animation strips.

Usage: python creature-cut.py <sheets-dir> [--only <creature>[/<anim>] ...] [--out <anim-dir>] [--cache <dir>] [--debug <dir>]
  sheets-dir  one folder per creature (fire-red-panda, ghost-rabbit, ...) holding its raw 1536 x 1024
              sheets, named as creatures.json names them (see ../README.md for where they are kept)
  --only      cut just these creatures, or one animation of one ("ghost-rabbit/idle"); the rest of
              that creature's manifest is kept
  --out       where the strips go: <anim-dir>/<creature>/<anim>.png and manifest.json
              (default: ../../chatmon/anim)
  --cache     keep the keyed sheets here, so a second run only repeats the slicing (keying a sheet
              takes a few seconds)
  --debug     also write <dir>/<creature>-<anim>.png: the aligned frames at sheet size on dark and
              light, with the floor line and the anchor drawn in
Then run creature-qc.py: it measures the strips and fails on anything out of limits.

This is penguin-slice.py made general: the same steps (key the sheet, cut the grid, line every frame
up, crop all frames of an animation to one box, scale to a 240 px strip, write the manifest), driven
by creatures.json, which says per creature and animation which sheet cells make the frames, what
stays put from frame to frame, and how large it is drawn. The key colour is measured from each sheet
(green or magenta), and glows are unmixed from it instead of cut (spritefix.chroma_key).
Needs Pillow and numpy.

creatures.json, per creature:
  key        "green" or "magenta": the family of its sheets' key colour
  screen_px  screen pixels per sheet pixel at the default size (120), for an animation of scale 1
  hover      screen px it floats above the floor (the ghost rabbit); without it, it stands
  colours    named colour rules such as "r>205 and b-g<48": "body" narrows what counts as the body,
             "effect" is left out of it (flames, mist), "mark" is a belly or a charm to anchor on
  heads      where the head is in the idle and turn frames (creature-qc.py compares sizes by it)
  defaults   animation fields that hold unless an animation says otherwise
and per animation:
  sheet      [file, columns, rows]; or sheets: {name: [file, columns, rows]}
  frames     the cells in order, counted from 1 ("b2" is cell 2 of sheet "b"; default: every cell);
             {"of": 1, "taller": 1.01} builds a frame from a cell, stretched upwards with its feet
             in place (a breath)
  scale      display scale against idle, so the head is one size on screen (default 1)
  x          what stays put left to right: "overlap" (the body's best overlap with frame 1),
             "centre", "feet", "mark", "cut" (peek) or "none" (as drawn); or {"by": one of those,
             "band": [from, to] as shares of the body's height, "top": only the n largest patches
             of a mark, "groups": frames lined up among themselves, "links": [[frame, with-frame,
             {another anchor}]] to join two groups}
  y          {"floor": the frames that stand on the floor line (default: all), "pin": "each" (each
             of them onto the line; the default), "rows" (a sheet row at a time) or "sheet" (as drawn)}
  gap        screen px from the floor line to the frame's bottom edge (default: floor_gap + hover)
  anchor     what the app pins to its spot on the floor: "feet" (default), "centre", "mark", "cut"
  check      the anchor creature-qc.py watches instead of x (where x is "none")
  loose      true if the sheet means to have loose effect pieces (sparkles, embers, leaves)
  soft       false for sheets with hard edges only (no glow to follow inwards)
  head       the frame, and the view ("side"), creature-qc.py takes the head's size from
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import creaturespec as cs  # noqa: E402
import spritefix  # noqa: E402

KEYER = 9  # bump when spritefix.chroma_key changes, so cached sheets are keyed again
MARGIN = 96  # canvas margin around a cell, so a shifted frame never clips
PAD = 6  # sheet px kept clear around an animation's frames (as penguin-slice.py)
SPECK = 36  # sheet px: a loose piece smaller than this is a speck (about 12 px in a strip)
FAINT = 96  # a speck whose strongest pixel is below this alpha is keying residue wherever it is
NEAR = 10  # sheet px: a speck this close to the creature belongs to it


def keyed_sheet(path: str, soft: bool, cache: str | None) -> np.ndarray:
    with open(path, "rb") as fh:
        digest = hashlib.sha1(fh.read()).hexdigest()
    saved = os.path.join(cache, f"{digest}-{int(soft)}-{KEYER}.npy") if cache else None
    if saved and os.path.exists(saved):
        return np.load(saved)
    rgb = np.asarray(Image.open(path).convert("RGB"))
    key, spread = spritefix.measure_key(rgb)
    rgba, _ = spritefix.chroma_key(rgb, key, spread, soft=soft)
    if saved:
        os.makedirs(cache, exist_ok=True)
        np.save(saved, rgba)
    return rgba


def clean(cell: np.ndarray, loose: bool) -> tuple[np.ndarray, int]:
    """Drop specks: small loose pieces that are faint (keying residue) or, unless the sheet means to
    have loose effect pieces, far from the creature. Returns the cell and how many it dropped."""
    labels, areas = spritefix.label(cell[..., 3] > 0)
    if len(areas) < 3:
        return cell, 0
    main = int(areas[1:].argmax()) + 1
    peak = np.zeros(len(areas), np.uint8)
    np.maximum.at(peak, labels.ravel(), cell[..., 3].ravel())
    close = np.zeros(len(areas), bool)
    close[np.unique(labels[spritefix.grow(labels == main, NEAR, diagonal=True)])] = True
    small = areas < SPECK
    small[0] = False
    drop = small & ((peak < FAINT) | (~close & (not loose)))
    if not drop.any():
        return cell, 0
    out = cell.copy()
    out[drop[labels]] = 0
    return out, int(drop.sum())


def taller(cell: np.ndarray, colours: dict, by: float) -> np.ndarray:
    """A breath: the frame stretched upwards by the factor `by`, its feet staying where they are."""
    floor = int(cs.floor_row(cell, colours))
    part = cell[: floor + 1]
    grown = spritefix.resize_rgba(part, (cell.shape[1], round(part.shape[0] * by)))
    out = np.zeros_like(cell)
    rise = grown.shape[0] - part.shape[0]
    out[: floor + 1] = grown[rise:]
    out[floor + 1 :] = cell[floor + 1 :]
    return out


def source_frames(creature: str, anim: str, a: dict, colours: dict, sheets_dir: str, cache: str | None) -> list[tuple[np.ndarray, tuple]]:
    """The animation's frames as keyed sheet cells, each with the (sheet, row) it came from."""
    sheets = a.get("sheets") or {"": a["sheet"]}
    keyed = {}

    def cell(ref) -> tuple[np.ndarray, tuple]:
        ref = str(ref)
        name = ref.rstrip("0123456789")
        file, cols, rows = sheets[name]
        if name not in keyed:
            path = os.path.join(sheets_dir, creature, file)
            if not os.path.exists(path):
                sys.exit(f"{creature}/{anim}: {path} is missing")
            keyed[name] = keyed_sheet(path, bool(a.get("soft", True)), cache)
        sheet = keyed[name]
        h, w = sheet.shape[0] // rows, sheet.shape[1] // cols
        n = int(ref[len(name) :]) - 1
        r, c = divmod(n, cols)
        return sheet[r * h : (r + 1) * h, c * w : (c + 1) * w], (name, r)

    refs = a.get("frames") or list(range(1, sheets[""][1] * sheets[""][2] + 1))
    out = []
    for ref in refs:
        if isinstance(ref, dict):
            base, where = cell(ref["of"])
            out.append((taller(base, colours, ref["taller"]), where))
        else:
            out.append(cell(ref))
    return out


def place(frames: list[np.ndarray], wheres: list[tuple], a: dict, colours: dict) -> tuple[list[int], list[int], int]:
    """How far to move each frame right and down so the animation's anchor stays put, and the floor
    line they then share."""
    n = len(frames)
    # left to right: every frame against the first of its group
    how = a["x"] if isinstance(a["x"], dict) else {"by": a["x"]}
    groups = how.get("groups") or [list(range(1, n + 1))]
    dx = [0.0] * n
    for group in groups:
        first = group[0] - 1
        for i in (g - 1 for g in group):
            s = cs.shift_between(frames[first], frames[i], colours, how)
            if s is None:
                sys.exit(f"no anchor ({how['by']}) in frame {i + 1}")
            dx[i] = s
    for later, earlier, link in how.get("links", []):  # a later group against an earlier one, by another anchor
        s = cs.shift_between(_moved(frames[earlier - 1], dx[earlier - 1]), _moved(frames[later - 1], dx[later - 1]), colours, link)
        for group in groups:
            if later in group:
                for g in group:
                    dx[g - 1] += s
    # top to bottom: grounded frames by their own floor; the rest go with their row of the sheet
    y = a.get("y", {})
    grounded = [g - 1 for g in y.get("floor", range(1, n + 1))]
    floors = {i: cs.floor_row(frames[i], colours) for i in grounded}
    pin = y.get("pin", "each")
    line = float(np.median(list(floors.values())))
    dy = [0.0] * n
    if pin != "sheet":
        for i in range(n):
            if pin == "each" and i in floors:
                dy[i] = line - floors[i]
            else:
                mates = [line - f for j, f in floors.items() if wheres[j] == wheres[i]] or [line - f for f in floors.values()]
                dy[i] = float(np.median(mates))
    return [round(v) for v in dx], [round(v) for v in dy], round(line)


def _moved(frame: np.ndarray, dx: float) -> np.ndarray:
    return np.roll(frame, round(dx), axis=1)


def cut(creature: str, anim: str, spec: dict, sheets_dir: str, cache: str | None, debug: str | None) -> tuple[np.ndarray, dict]:
    c = spec["creatures"][creature]
    a = cs.anim_spec(spec, creature, anim)
    colours = c.get("colours", {})
    cells = source_frames(creature, anim, a, colours, sheets_dir, cache)
    wheres = [w for _, w in cells]
    frames, dropped = [], 0
    for cell, _ in cells:
        canvas = np.zeros((cell.shape[0] + 2 * MARGIN, cell.shape[1] + 2 * MARGIN, 4), np.uint8)
        cleaned, n = clean(cell, bool(a.get("loose")))
        cut_off = [side for side, edge in (("top", cleaned[0]), ("bottom", cleaned[-1]), ("left", cleaned[:, 0]), ("right", cleaned[:, -1])) if edge[:, 3].max() > cs.SHOWN]
        if cut_off:  # the sheet itself clips the drawing: no cutting can mend that
            print(f"  ! {creature}/{anim} frame {len(frames) + 1}: the drawing reaches the cell's {', '.join(cut_off)} edge")
        dropped += n
        canvas[MARGIN:-MARGIN, MARGIN:-MARGIN] = cleaned
        frames.append(canvas)
    dx, dy, line = place(frames, wheres, a, colours)
    if max(map(abs, dx + dy)) > MARGIN - PAD:
        sys.exit(f"{creature}/{anim}: a frame has to move {max(map(abs, dx + dy))} px, more than the margin")
    frames = [np.roll(f, (y, x), (0, 1)) for f, x, y in zip(frames, dx, dy, strict=True)]

    # one box for the whole animation, its bottom edge a fixed distance under the floor line
    per_px = c["screen_px"] * a.get("scale", 1.0)  # sheet px to screen px at the reference size
    shown = np.any([f[..., 3] > 8 for f in frames], axis=0)
    rows, cols = np.nonzero(shown.any(1))[0], np.nonzero(shown.any(0))[0]
    gap = a.get("gap", c.get("hover", 0) + spec["floor_gap"])  # screen px under the floor line
    bottom = line + 1 + round(gap / per_px)
    if rows.max() + 2 > bottom:  # something hangs lower than the gap: keep it, and say so if it shows
        if (rows.max() + 2 - bottom) * per_px > 0.75:
            print(f"  ! {creature}/{anim}: the drawing reaches {(rows.max() + 2 - bottom) * per_px:.1f} screen px under its floor gap; the box is lowered to fit")
        bottom = rows.max() + 2
    top, left, right = rows.min() - PAD, cols.min() - PAD, cols.max() + 1 + PAD
    height = bottom - top
    fh = spec["frame_height"]
    fw = max(1, round((right - left) * fh / height))
    key = cs.KEYS[c.get("key", "green")]
    scaled = [spritefix.despill_edge(spritefix.resize_rgba(f[top:bottom, left:right], (fw, fh)), key) for f in frames]
    for f in scaled:  # what scaling down left of a mote too small to draw is a speck now
        stray, n, _ = cs.stray_specks(f, bool(a.get("loose")))
        f[stray] = 0
        dropped += n
    strip = spritefix.join(scaled)

    how = a.get("anchor") or ({"by": "feet"} if not c.get("hover") else {"by": "centre"})
    how = how if isinstance(how, dict) else {"by": how}
    ax = cs.anchor_x(frames[how.get("frame", 1) - 1], colours, how)
    fps, loop = spec["playback"][anim]
    entry = {
        "frames": len(frames),
        "w": fw,
        "h": fh,
        "fps": fps,
        "loop": loop,
        "scale": round(height * per_px / spec["screen_size"], 4),
        "anchor": round((ax - left) * fh / height, 1),
    }
    print(f"{creature}/{anim}: {len(frames)} x {fw}x{fh}, scale {entry['scale']}, moved x {dx} y {dy}" + (f", {dropped} specks dropped" if dropped else ""))
    if debug:
        os.makedirs(debug, exist_ok=True)
        _debug_sheet(frames, (top, bottom, left, right), line, ax, os.path.join(debug, f"{creature}-{anim}.png"))
    return strip, entry


def _debug_sheet(frames: list[np.ndarray], box: tuple[int, int, int, int], line: int, ax: float, path: str) -> None:
    top, bottom, left, right = box
    rows = []
    for bg in ((30, 33, 40), (233, 235, 240)):
        tiles = []
        for f in frames:
            crop = f[top:bottom, left:right].astype(float)
            alpha = crop[..., 3:4] / 255
            tile = (crop[..., :3] * alpha + np.array(bg) * (1 - alpha)).astype(np.uint8)
            tile[line - top] = (255, 0, 0)
            tile[:, round(ax) - left] = (0, 160, 255)
            tile[:, -1] = (128, 128, 128)
            tiles.append(tile)
        rows.append(np.concatenate(tiles, 1))
    Image.fromarray(np.concatenate(rows, 0)).save(path)


def main(argv: list[str]) -> None:
    opts = {"--only": [], "--out": [], "--cache": [], "--debug": []}
    args, current = [], None
    for arg in argv:
        if arg in opts:
            current = opts[arg]
        elif current is not None:
            current.append(arg)
            current = current if current is opts["--only"] else None
        else:
            args.append(arg)
    if not args:
        sys.exit(__doc__)
    spec = cs.load()
    out = opts["--out"][0] if opts["--out"] else str(cs.ANIM_ROOT)
    cache = opts["--cache"][0] if opts["--cache"] else None
    debug = opts["--debug"][0] if opts["--debug"] else None
    wanted = {}
    for only in opts["--only"] or list(spec["creatures"]):
        creature, _, anim = only.partition("/")
        if creature not in spec["creatures"]:
            sys.exit(f"{creature}: not in creatures.json")
        wanted.setdefault(creature, []).extend([anim] if anim else list(spec["playback"]))
    for creature, anims in wanted.items():
        folder = os.path.join(out, creature)
        os.makedirs(folder, exist_ok=True)
        manifest_path = os.path.join(folder, "manifest.json")
        manifest = {}
        if os.path.exists(manifest_path):
            with open(manifest_path, encoding="utf-8") as fh:
                manifest = json.load(fh)
        for anim in anims:
            strip, entry = cut(creature, anim, spec, args[0], cache, debug)
            Image.fromarray(strip).save(os.path.join(folder, f"{anim}.png"), optimize=True)
            manifest[anim] = entry
        with open(manifest_path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({k: manifest[k] for k in spec["playback"] if k in manifest}, fh, indent=1)
            fh.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
