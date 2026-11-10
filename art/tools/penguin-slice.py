"""Slice the generated green-screen sprite sheets into keyed animation strips.

Usage: python penguin-slice.py <sheets-dir> [out-dir] [--only name ...]
  sheets-dir  the raw sheets, one <name>.png per animation (kept outside the
              repository; see ../README.md)
  out-dir     where the strips and manifest.json go
              (default: ../../chatmon/anim)
  --only      slice just these animations and update their manifest entries,
              keeping the rest (for re-making one sheet)
Then run penguin-touchup.py over the out-dir for the pixel fixes.
Needs Pillow and numpy.
"""

import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spritefix  # noqa: E402

# name: (cols, rows, fps, loop, scale)
# scale is the display scale that keeps the penguin one size on screen, matched
# by standing height against `idle` (peek by head width).
SPEC = {
    "walk": (4, 2, 10, True, 1.0),
    "idle": (3, 2, 5, True, 1.0),
    "peek": (3, 2, 4, False, 0.47),
    "talk": (3, 2, 8, True, 1.0),
    "wave": (3, 2, 7, True, 1.0),
    "think": (3, 2, 4, True, 1.0),
    "hop": (3, 2, 9, True, 1.13),
    "sleep": (3, 2, 3, True, 1.0),
    "charge": (3, 2, 9, True, 1.17),
    "alert": (3, 2, 8, True, 1.05),
    "turn": (3, 2, 6, False, 1.0),
    "beam": (3, 2, 8, False, 1.0),
}
FRAME_H = 240  # output frame height in px (2x for ~120 px on screen)
MARGIN = 160  # canvas margin so shifted content never clips


def key_image(img):
    px = img.load()
    w, h = img.size
    out = Image.new("RGBA", (w, h))
    op = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]
            dom = g - max(r, b)
            if g > 90 and dom > 55:
                op[x, y] = (0, 0, 0, 0)
            elif g > 70 and dom > 16:
                a = max(0, min(255, int(255 * (1 - (dom - 16) / 39))))
                op[x, y] = (r, max(r, b), b, a)
            else:
                op[x, y] = (r, g, b, 255)
    alpha = out.getchannel("A").filter(ImageFilter.MedianFilter(3))
    out.putalpha(alpha)
    return out


def bbox_of(img):
    return img.getchannel("A").point(lambda v: 255 if v > 48 else 0).getbbox()


def slice_sheet(path, name):
    cols, rows, fps, loop, display_scale = SPEC[name]
    keyed = key_image(Image.open(path).convert("RGB"))
    W, H = keyed.size
    cw, ch = W / cols, H / rows
    raw = []
    for r in range(rows):
        for c in range(cols):
            box = (round(c * cw), round(r * ch), round((c + 1) * cw), round((r + 1) * ch))
            raw.append((r, keyed.crop(box)))
    # Rows: the generator places each row at its own height, so shift every row so its lowest
    # point (feet, or the peek cut line) matches row 0. Within a row the feet share a baseline.
    rows_bb = {}
    for r, cell in raw:
        bb = bbox_of(cell)
        if bb:
            rows_bb.setdefault(r, []).append(bb)
    ref_bottom = max(b[3] for b in rows_bb[0])
    dy = {r: round(ref_bottom - max(b[3] for b in bbs)) for r, bbs in rows_bb.items()}
    cells = []
    for r, cell in raw:
        canvas = Image.new("RGBA", (cell.width + 2 * MARGIN, cell.height + 2 * MARGIN), (0, 0, 0, 0))
        canvas.paste(cell, (MARGIN, MARGIN + dy.get(r, 0)), cell)
        cells.append(np.asarray(canvas).copy())
    # Columns: the generator doesn't centre the character in every cell either, so line each frame's
    # body up with frame 1's (spritefix.ALIGN says how), or the penguin slides about as it plays.
    cells = [spritefix.despill(c) for c in cells]
    cells, _ = spritefix.realign(cells, spritefix.ALIGN[name], pad=0)
    # One shared crop for the whole animation keeps motion (bob, hop) relative to the cell.
    union = None
    for cell in cells:
        bb = bbox_of(Image.fromarray(cell))
        if bb is not None:
            union = bb if union is None else (min(union[0], bb[0]), min(union[1], bb[1]), max(union[2], bb[2]), max(union[3], bb[3]))
    pad = 6
    cw0, ch0 = cells[0].shape[1], cells[0].shape[0]
    union = (max(0, union[0] - pad), max(0, union[1] - pad), min(cw0, union[2] + pad), min(ch0, union[3] + pad))
    frames = [Image.fromarray(c).crop(union) for c in cells]
    fw0, fh0 = frames[0].size
    scale = FRAME_H / fh0
    fw = max(1, round(fw0 * scale))
    strip = Image.new("RGBA", (fw * len(frames), FRAME_H), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(f.resize((fw, FRAME_H), Image.LANCZOS), (i * fw, 0))
    entry = {"frames": len(frames), "w": fw, "h": FRAME_H, "fps": fps, "loop": loop, "scale": display_scale}
    return strip, entry


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    only = argv[argv.index("--only") + 1 :] if "--only" in argv else None
    if only:
        args = args[: len(args) - len(only)]
    if not args:
        sys.exit(__doc__)
    sheets = args[0]
    out = args[1] if len(args) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "chatmon", "anim")
    os.makedirs(out, exist_ok=True)
    manifest_path = os.path.join(out, "manifest.json")
    manifest = {}
    if only and os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    for name in only or SPEC:
        strip, entry = slice_sheet(os.path.join(sheets, f"{name}.png"), name)
        path = os.path.join(out, f"{name}.png")
        strip.save(path, optimize=True)
        manifest[name] = entry
        print(name, entry["frames"], entry["w"], FRAME_H, os.path.getsize(path))
    ordered = {k: manifest[k] for k in SPEC if k in manifest}
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(ordered, fh, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
