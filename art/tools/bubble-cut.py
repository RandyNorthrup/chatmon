"""Cut the chat bubble art into what the app draws.

usage: python art/tools/bubble-cut.py RAW_DIR [--only electric,fire]

RAW_DIR holds the picked originals for each style:
  <style>-frame.png  the bubble: a wide rounded panel and, below it, its tail
  <style>-fx.png     the rim effect: a 4 x 2 sprite sheet (8 cells)
  <style>-fx2.png    a second sheet, for the styles that have one (leaf: the caterpillar)
  <style>-rim.png    a painted rim loop, for the styles that have one: a 4 x 3 sheet of 12 frames
  <style>-anim.png   an animated bubble (it replaces the frame, its tail and its effect): a 3 x 2 sheet,
                     every cell the same bubble with its tail as part of it, and its effect

Writes penguin_companion/bubbles/<style>-panel.png, <style>-tail.png and
<style>-fx.png (the effect's frames side by side), and the style's entry in
penguin_companion/bubbles/manifest.json:

  scale    display pixels per art pixel (the art is kept at twice display size)
  slice    the panel's 9-slice insets, in art pixels: left, top, right, bottom
  rim      the rim's thickness, in art pixels: left, top, right, bottom
  tail     the tail's size and how far it overlaps the panel's bottom edge, in art pixels
  fx, fx2  each effect sheet's frame count, frame size (art pixels) and whether it is one looping animation
  rim_fx   the painted rim loop: frame count and size, the clear hole its effect hugs (x0, y0, x1, y1) and its frame rate

Every original must have real transparency (no painted checkerboard); the tool
stops on one that doesn't. Needs Pillow and NumPy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "penguin_companion" / "bubbles"
CORNER = 30.0  # the panel's corner pieces at most this tall and wide on screen, so small bubbles still fit
# Each style's effect sheets: (sheet, display size of one frame's longer side, whether its cells are one
# looping animation). Sheet "fx" is <style>-fx.png; "fx2" is a second sheet, <style>-fx2.png.
FX = {
    "electric": [("fx", 60, False)],
    "fire": [("fx", 40, True)],
    "leaf": [("fx", 30, True), ("fx2", 46, True)],  # bees (row 1) and butterflies (row 2); the caterpillar
    "fairy": [("fx", 26, True)],
    "ghost": [("fx", 44, True)],
}
# Corner extents (x along the top and bottom, y down the sides, original pixels) measured by eye where the
# automatic measure is fooled: the leaf's braided vine changes all along its length, and its corner clusters
# reach well past the braid.
CORNERS = {"leaf": (235, 225)}


def alpha_ok(a: np.ndarray, name: str) -> None:
    h, w = a.shape
    corners = [a[0, 0], a[0, w - 1], a[h - 1, 0], a[h - 1, w - 1]]
    clear = float((a < 8).mean())
    if max(corners) > 8 or clear < 0.25:
        sys.exit(f"{name}: no real transparency (corners {corners}, {clear:.0%} clear); regenerate it")


def clean(img: np.ndarray, reach: int = 24) -> np.ndarray:
    """Clear the faint haze generators leave in "transparent" areas: keep
    only what lies within `reach` pixels of something solid."""
    a = img[..., 3]
    solid = Image.fromarray(((a > 60) * 255).astype(np.uint8)).resize((a.shape[1] // 4, a.shape[0] // 4), Image.BILINEAR)
    near = solid.filter(ImageFilter.MaxFilter(2 * (reach // 4) + 1)).resize((a.shape[1], a.shape[0]), Image.BILINEAR)
    keep = np.asarray(near) > 0
    out = img.copy()
    out[..., 3] = np.where(keep & (a >= 10), a, 0)
    return out


def bands(mask_rows: np.ndarray) -> list[tuple[int, int]]:
    """Runs of rows that hold something."""
    runs, start = [], None
    for y, on in enumerate(mask_rows):
        if on and start is None:
            start = y
        elif not on and start is not None:
            runs.append((start, y))
            start = None
    if start is not None:
        runs.append((start, len(mask_rows)))
    return runs


def crop(img: np.ndarray, pad: int = 2) -> np.ndarray:
    ys, xs = np.nonzero(img[..., 3] > 8)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad + 1, img.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad + 1, img.shape[1])
    return img[y0:y1, x0:x1]


def rim_thickness(panel: np.ndarray) -> tuple[int, int, int, int]:
    """How far in from each edge the fill starts, along the middle row and column."""
    h, w = panel.shape[:2]
    rgb = panel[..., :3].astype(int)
    fill = np.median(rgb[h * 2 // 5 : h * 3 // 5, w * 2 // 5 : w * 3 // 5].reshape(-1, 3), axis=0)

    def scan(line: np.ndarray, alpha: np.ndarray) -> int:
        """`line` runs from the middle out to the edge: from the rim's inner
        edge to the panel's outer edge (scanning from the inside, so a dark
        outer band the colour of the fill isn't mistaken for it)."""
        far = int(np.nonzero(alpha > 128)[0].max()) if (alpha > 128).any() else len(line) - 1
        off = np.abs(line - fill).sum(axis=1) > 45
        for i in range(len(line) - 3):
            if off[i : i + 3].all():
                return max(2, far - i + 1)
        return 2

    cy, cx = h // 2, w // 2
    row = np.median(rgb[cy - 5 : cy + 6], axis=0)  # a few rows and columns, so texture doesn't count
    col = np.median(rgb[:, cx - 5 : cx + 6], axis=1)
    ra, ca = panel[cy, :, 3], panel[:, cx, 3]
    return (
        scan(row[cx::-1], ra[cx::-1]),
        scan(col[cy::-1], ca[cy::-1]),
        scan(row[cx:], ra[cx:]),
        scan(col[cy:], ca[cy:]),
    )


def corner_extent(panel: np.ndarray, rim: tuple[int, int, int, int]) -> tuple[int, int]:
    """How far the corner decoration reaches along the edges (x along the top and bottom, y down the sides)."""
    h, w = panel.shape[:2]
    a = panel.astype(int)

    def along(strip: np.ndarray) -> int:
        """`strip` runs from a corner along an edge: where does it settle into the plain edge?"""
        ref = strip[len(strip) // 2 - 6 : len(strip) // 2 + 6].mean(axis=0)
        diffs = np.abs(strip - ref).sum(axis=(1, 2)) / strip.shape[1]
        limit = np.percentile(diffs[len(strip) // 3 : 2 * len(strip) // 3], 95) * 1.6 + 12
        for i in range(len(strip) // 2):
            if (diffs[i : i + 8] <= limit).all():
                return i
        return len(strip) // 3

    top_band = a[: max(rim[1], 4) + 6].transpose(1, 0, 2)  # columns along the top
    bottom_band = a[h - max(rim[3], 4) - 6 :].transpose(1, 0, 2)
    left_band = a[:, : max(rim[0], 4) + 6]  # rows down the left side
    right_band = a[:, w - max(rim[2], 4) - 6 :]
    x = max(along(top_band), along(top_band[::-1]), along(bottom_band), along(bottom_band[::-1]))
    y = max(along(left_band), along(left_band[::-1]), along(right_band), along(right_band[::-1]))
    return x, y


def cut_frame(style: str, path: Path) -> dict:
    img = np.asarray(Image.open(path).convert("RGBA"))
    alpha_ok(img[..., 3], path.name)
    img = clean(img)
    runs = [r for r in bands((img[..., 3] > 8).any(axis=1)) if r[1] - r[0] > 6]
    if len(runs) < 2:
        sys.exit(f"{path.name}: expected the panel and, below it, the tail; found {len(runs)} piece(s)")
    runs.sort(key=lambda r: r[1] - r[0], reverse=True)
    panel_run, tail_run = runs[0], max(runs[1:], key=lambda r: r[0])
    panel = crop(img[panel_run[0] : panel_run[1]])
    tail = crop(img[tail_run[0] : tail_run[1]])
    rim = rim_thickness(panel)
    ext_x, ext_y = CORNERS.get(style) or corner_extent(panel, rim)
    inset = (max(ext_x, rim[0]) + 4, max(ext_y, rim[1]) + 4, max(ext_x, rim[2]) + 4, max(ext_y, rim[3]) + 4)
    display = CORNER / max(inset)  # display px per original px
    art = 2 * display  # keep twice display size, for high-density screens

    def shrink(a: np.ndarray) -> Image.Image:
        im = Image.fromarray(a, "RGBA")
        return im.resize((max(1, round(im.width * art)), max(1, round(im.height * art))), Image.LANCZOS)

    p, t = shrink(panel), shrink(tail)
    p.save(OUT / f"{style}-panel.png", optimize=True)
    t.save(OUT / f"{style}-tail.png", optimize=True)
    s = lambda v: round(v * art)  # noqa: E731
    return {
        "scale": 0.5,
        "slice": [s(v) for v in inset],
        "rim": [s(v) for v in rim],
        "panel": [p.width, p.height],
        "tail": [t.width, t.height, s(max(rim[3], 2)) + 2],
    }


def cut_fx(style: str, sheet: str, size: float, loop: bool, path: Path) -> dict:
    img = np.asarray(Image.open(path).convert("RGBA"))
    alpha_ok(img[..., 3], path.name)
    img = clean(img, reach=40)
    h, w = img.shape[:2]
    cw, ch = w // 4, h // 2
    cells = [img[r * ch : (r + 1) * ch, c * cw : (c + 1) * cw] for r in range(2) for c in range(4)]
    if loop:  # one animation: keep every frame in the same box so it doesn't jump
        boxes = [np.nonzero(c[..., 3] > 8) for c in cells]
        y0 = min(b[0].min() for b in boxes)
        y1 = max(b[0].max() for b in boxes) + 1
        x0 = min(b[1].min() for b in boxes)
        x1 = max(b[1].max() for b in boxes) + 1
        frames = [c[max(y0 - 2, 0) : y1 + 2, max(x0 - 2, 0) : x1 + 2] for c in cells]
    else:  # separate sprites: each centred on itself
        frames = [crop(c) for c in cells]
        fh, fw = max(f.shape[0] for f in frames), max(f.shape[1] for f in frames)
        padded = []
        for f in frames:
            canvas = np.zeros((fh, fw, 4), np.uint8)
            oy, ox = (fh - f.shape[0]) // 2, (fw - f.shape[1]) // 2
            canvas[oy : oy + f.shape[0], ox : ox + f.shape[1]] = f
            padded.append(canvas)
        frames = padded
    fh, fw = frames[0].shape[:2]
    art = 2 * size / max(fh, fw)
    tw, th = max(1, round(fw * art)), max(1, round(fh * art))
    strip = Image.new("RGBA", (tw * len(frames), th), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(Image.fromarray(f, "RGBA").resize((tw, th), Image.LANCZOS), (i * tw, 0))
    strip.save(OUT / f"{style}-{sheet}.png", optimize=True)
    return {"frames": len(frames), "w": tw, "h": th, "loop": loop}


RIMS = {"fire": 12.0, "electric": 14.0}  # styles with a painted rim loop, and its frame rate


def cut_rim(style: str, path: Path) -> dict:
    """A painted rim loop: a 4 x 3 sheet, every cell the same effect round the
    same invisible bubble outline. Keeps every frame in one box, and finds the
    outline (the clear hole in the middle) so the app can lay it on the bubble."""
    img = np.asarray(Image.open(path).convert("RGBA"))
    alpha_ok(img[..., 3], path.name)
    img = clean(img, reach=40)
    h, w = img.shape[:2]
    cw, ch = w // 4, h // 3
    cells = [img[r * ch : (r + 1) * ch, c * cw : (c + 1) * cw] for r in range(3) for c in range(4)]
    boxes = [np.nonzero(c[..., 3] > 8) for c in cells]
    y0, y1 = max(min(b[0].min() for b in boxes) - 2, 0), min(max(b[0].max() for b in boxes) + 3, ch)
    x0, x1 = max(min(b[1].min() for b in boxes) - 2, 0), min(max(b[1].max() for b in boxes) + 3, cw)
    frames = [c[y0:y1, x0:x1] for c in cells]
    stack = np.median(np.stack([f[..., 3] for f in frames]).astype(float), axis=0)  # the ring, steady across frames
    fh, fw = stack.shape
    cy, cx = fh // 2, fw // 2
    solid = stack > 60

    def first(line) -> int:
        hits = np.nonzero(line)[0]
        return int(hits[0]) if len(hits) else len(line) // 2

    # The hole: from the middle out to where the effect starts, along the middle row and column.
    hole = [cx - first(solid[cy, cx::-1]), cy - first(solid[cy::-1, cx]), cx + first(solid[cy, cx:]), cy + first(solid[cy:, cx])]
    strip = Image.new("RGBA", (fw * len(frames), fh), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(Image.fromarray(np.ascontiguousarray(f), "RGBA"), (i * fw, 0))
    strip.save(OUT / f"{style}-rim.png", optimize=True)
    return {"frames": len(frames), "w": fw, "h": fh, "hole": hole, "fps": RIMS[style]}


ANIM_FPS = {"fire": 10.0, "electric": 12.0, "ghost": 8.0, "fairy": 8.0, "leaf": 5.0}
ANIM_TEXT = 210.0  # display width of the text area in the art's own proportions; sets the art's scale


def _interior(med: np.ndarray) -> tuple[int, int, int, int]:
    """The plain fill inside the panel: grown from the centre over pixels close to the fill's colour."""
    h, w = med.shape[:2]
    rgb = med[..., :3].astype(int)
    fill = np.median(rgb[h // 2 - 4 : h // 2 + 5, w // 2 - 4 : w // 2 + 5].reshape(-1, 3), axis=0)
    near = (np.abs(rgb - fill).sum(axis=2) < 60) & (med[..., 3] > 200)
    cy, cx = h // 2, w // 2

    def run(line: np.ndarray, start: int) -> int:
        i = start
        while 0 <= i < len(line) and line[i]:
            i += 1
        return i

    # The fill's extent along the middle row and column (a few of each, so texture doesn't stop it early).
    rights = [run(near[y], cx) for y in range(cy - 6, cy + 7, 3)]
    lefts = [cx - run(near[y, cx::-1], 0) for y in range(cy - 6, cy + 7, 3)]
    downs = [run(near[:, x], cy) for x in range(cx - 30, cx + 31, 15)]
    ups = [cy - run(near[cy::-1, x], 0) for x in range(cx - 30, cx + 31, 15)]
    return int(np.median(lefts)), int(np.median(ups)), int(np.median(rights)), int(np.median(downs))


def cut_anim(style: str, path: Path) -> dict:
    """An animated bubble: a 3 x 2 sheet, every cell the same bubble (its tail part of it) with its effect.

    The box is steadied: a per-pixel median across the frames is the still bubble, and each frame keeps
    only the pixels that really move (the effect), so the box never wobbles from frame to frame."""
    img = np.asarray(Image.open(path).convert("RGBA"))
    alpha_ok(img[..., 3], path.name)
    img = clean(img, reach=40)
    h, w = img.shape[:2]
    cw, ch = w // 3, h // 2
    cells = [img[r * ch : (r + 1) * ch, c * cw : (c + 1) * cw] for r in range(2) for c in range(3)]
    boxes = [np.nonzero(c[..., 3] > 8) for c in cells]
    y0, y1 = max(min(b[0].min() for b in boxes) - 2, 0), min(max(b[0].max() for b in boxes) + 3, ch)
    x0, x1 = max(min(b[1].min() for b in boxes) - 2, 0), min(max(b[1].max() for b in boxes) + 3, cw)
    frames = np.stack([c[y0:y1, x0:x1] for c in cells]).astype(np.float32)
    still = np.median(frames, axis=0)
    moving = np.abs(frames - still).max(axis=3)  # how far each pixel strays from the still bubble
    keep = np.clip((moving - 18) / 30, 0, 1)[..., None]  # 0: the still bubble, 1: the frame's own pixel
    steady = (still * (1 - keep) + frames * keep).round().astype(np.uint8)
    still8 = still.round().astype(np.uint8)
    ix0, iy0, ix1, iy1 = _interior(still8)
    ih = iy1 - iy0
    # The tail: the solid run round the middle column just below the panel's bottom rim.
    solid = still8[..., 3] > 200
    cx = (ix0 + ix1) // 2
    below = iy1 + max(6, ih // 6)
    row = solid[min(below, solid.shape[0] - 1)]
    tl, tr = cx, cx
    while tl > 0 and row[tl - 1]:
        tl -= 1
    while tr < len(row) - 1 and row[tr + 1]:
        tr += 1
    notch = (tl - max(10, ih // 5), tr + max(10, ih // 5))  # the strip of the bottom edge that holds the tail
    tail_bottom = int(np.nonzero(solid[:, cx])[0].max())
    corner = max(12, ih // 4)  # how far the corner pieces reach past the text area
    scale = ANIM_TEXT / (ix1 - ix0)  # display px per original px, before keeping the art at twice display size
    art = 2 * scale
    fh, fw = steady.shape[1:3]
    tw, th = round(fw * art), round(fh * art)
    strip = Image.new("RGBA", (tw * len(steady), th), (0, 0, 0, 0))
    for i, f in enumerate(steady):
        strip.paste(Image.fromarray(f, "RGBA").resize((tw, th), Image.LANCZOS), (i * tw, 0))
    strip.save(OUT / f"{style}-anim.png", optimize=True)
    Image.fromarray(still8, "RGBA").resize((tw, th), Image.LANCZOS).save(OUT / f"{style}-still.png", optimize=True)
    a = lambda v: round(v * art)  # noqa: E731
    return {
        "scale": 0.5,
        "frames": len(steady),
        "w": tw,
        "h": th,
        "fps": ANIM_FPS[style],
        "text": [a(ix0), a(iy0), a(ix1), a(iy1)],  # the plain fill: where text may go
        "corner": a(corner),
        "notch": [a(notch[0]), a(notch[1])],  # the bottom strip holding the tail (x range)
        "tail": [a(cx), a(tail_bottom)],  # the tail's tip
    }


def main() -> None:
    raw = Path(sys.argv[1])
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else list(FX)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    for style in only:
        if (raw / f"{style}-anim.png").exists():  # an animated bubble, its tail part of it
            entry = {"anim": cut_anim(style, raw / f"{style}-anim.png")}
            for sheet, size, loop in FX.get(style, []):
                if sheet != "fx" or style == "leaf":
                    entry[sheet] = cut_fx(style, sheet, size, loop, raw / f"{style}-{sheet}.png")
            manifest[style] = entry
            print(style, json.dumps(entry))
            continue
        entry = cut_frame(style, raw / f"{style}-frame.png")
        for sheet, size, loop in FX[style]:
            entry[sheet] = cut_fx(style, sheet, size, loop, raw / f"{style}-{sheet}.png")
        if style in RIMS and (raw / f"{style}-rim.png").exists():
            entry["rim_fx"] = cut_rim(style, raw / f"{style}-rim.png")
        manifest[style] = entry
        print(style, json.dumps(entry))
    manifest_path.write_text(json.dumps(dict(sorted(manifest.items())), indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
