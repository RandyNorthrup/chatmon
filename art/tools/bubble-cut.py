"""Build the chat bubbles' art from the picked originals: a still bubble per style and the pieces its
border effect is made of. Nothing here is an animation frame drawn by a generator: motion is made in the
app (penguin_companion/bubbleart.py) by moving these pieces on a fixed period.

usage: python art/tools/bubble-cut.py RAW_DIR [--only electric,fire]

RAW_DIR holds, per style:
  <style>-anim.png        the approved bubble: a 3 x 2 sheet of the same bubble. Its per-pixel median is the
                          still; baked-in effect bits on the straight edges are removed.
and the effect sources:
  ghost-mist-a.png, ghost-mist-b.png   horizontal mist strips (made tileable here)
  electric-current.png                 horizontal current strip (made tileable here)
  electric-arcs.png                    4 x 2 sheet of single arc sprites (the two yellow ones are left out;
                                       the rest and the strip are turned from cyan to yellow here)
  fire-flames.png                      horizontal flame row on a baseline (made tileable, then baked into a
                                       loop here by moving it through periodic noise)
  fire-embers.png                      3 x 2 sheet of single ember sprites
  fairy-sparkles.png                   3 x 2 sheet of single sparkle sprites
  leaf-caterpillar.png                 4 x 2 sheet; only the last cell (the flat pose) is used, and its crawl
                                       is baked here by passing a wave along that one sprite

Writes into penguin_companion/bubbles/: <style>-still.png, the strips and sprite rows, fairy-still-b.png (the
same rim in shifted colours, transparent wherever nothing changes), fire-flames.png (the baked loop, frames
stacked top to bottom), leaf-crawler.png (the baked crawl, frames side by side), manifest.json,
and prints the measurements that prove each strip tiles (the wrap column's step against the other columns')
and each baked loop closes (the last-to-first frame step against the others).

Every original must have real transparency; the tool stops on one that doesn't. Needs Pillow and NumPy.
"""

from __future__ import annotations

import colorsys
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "penguin_companion" / "bubbles"
TEXT = 210.0  # display width of the text area in the art's own proportions; sets the still's scale
K = 0.5  # display px per art px: the art is kept at twice display size
STYLES = ["electric", "fire", "ghost", "fairy", "leaf"]
KEEP_EDGES = {"leaf"}  # styles whose straight edges carry painted detail that must stay (the ivy)


def alpha_ok(a: np.ndarray, name: str) -> None:
    h, w = a.shape
    corners = [a[0, 0], a[0, w - 1], a[h - 1, 0], a[h - 1, w - 1]]
    clear = float((a < 8).mean())
    if max(corners) > 8 or clear < 0.25:
        sys.exit(f"{name}: no real transparency (corners {corners}, {clear:.0%} clear); regenerate it")


def clean(img: np.ndarray, reach: int = 24) -> np.ndarray:
    """Clear the faint haze generators leave in "transparent" areas: keep only what lies within `reach`
    pixels of something solid."""
    a = img[..., 3]
    solid = Image.fromarray(((a > 60) * 255).astype(np.uint8)).resize((a.shape[1] // 4, a.shape[0] // 4), Image.BILINEAR)
    near = solid.filter(ImageFilter.MaxFilter(2 * (reach // 4) + 1)).resize((a.shape[1], a.shape[0]), Image.BILINEAR)
    keep = np.asarray(near) > 0
    out = img.copy()
    out[..., 3] = np.where(keep & (a >= 10), a, 0)
    return out


def load(path: Path, reach: int = 40) -> np.ndarray:
    img = np.asarray(Image.open(path).convert("RGBA"))
    alpha_ok(img[..., 3], path.name)
    return clean(img, reach)


def premult(img: np.ndarray) -> np.ndarray:
    f = img.astype(np.float32)
    f[..., :3] *= f[..., 3:4] / 255
    return f


def unpremult(f: np.ndarray) -> np.ndarray:
    out = f.copy()
    a = np.maximum(out[..., 3:4], 1e-3)
    out[..., :3] = np.where(out[..., 3:4] > 0.5, out[..., :3] * 255 / a, 0)
    return np.clip(out.round(), 0, 255).astype(np.uint8)


def resize(img: np.ndarray, w: int, h: int) -> np.ndarray:
    """Resize straight-alpha RGBA through premultiplied alpha, so soft edges keep their colour."""
    planes = [Image.fromarray(premult(img)[..., c]).resize((w, h), Image.LANCZOS) for c in range(4)]
    return unpremult(np.stack([np.asarray(p) for p in planes], axis=-1))


def save(img: np.ndarray, name: str) -> None:
    Image.fromarray(img, "RGBA").save(OUT / name, optimize=True)


# -- the still bubble and its geometry


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

    rights = [run(near[y], cx) for y in range(cy - 6, cy + 7, 3)]
    lefts = [cx - run(near[y, cx::-1], 0) for y in range(cy - 6, cy + 7, 3)]
    downs = [run(near[:, x], cy) for x in range(cx - 30, cx + 31, 15)]
    ups = [cy - run(near[cy::-1, x], 0) for x in range(cx - 30, cx + 31, 15)]
    return int(np.median(lefts)), int(np.median(ups)), int(np.median(rights)), int(np.median(downs))


def align_cells(cells: list[np.ndarray]) -> list[np.ndarray]:
    """Shift every cell so its bubble sits where the first cell's does (the generator doesn't place it
    the same in every cell). Matched by the solid shape's cross-correlation, so effects don't pull it."""
    ref = (cells[0][..., 3] > 200).astype(np.float32)
    F = np.fft.rfft2(ref)
    out = [cells[0]]
    for c in cells[1:]:
        m = (c[..., 3] > 200).astype(np.float32)
        corr = np.fft.irfft2(F * np.conj(np.fft.rfft2(m)), s=ref.shape)
        dy, dx = np.unravel_index(int(np.argmax(corr)), corr.shape)
        dy = dy - ref.shape[0] if dy > ref.shape[0] // 2 else dy
        dx = dx - ref.shape[1] if dx > ref.shape[1] // 2 else dx
        shifted = np.zeros_like(c)
        h, w = c.shape[:2]
        ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
        xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
        shifted[yd, xd] = c[ys, xs]
        out.append(shifted)
    return out


def _weight(px: np.ndarray, fill: np.ndarray) -> np.ndarray:
    """How much a pixel looks like the border line: opaque, and unlike the fill."""
    px = px.astype(float)
    return (px[..., 3] / 255) ** 2 * np.abs(px[..., :3] - fill).sum(axis=-1)


def _ridge(line: np.ndarray, hi: int, fill: np.ndarray) -> float:
    """Where the border line is along a profile running from outside the bubble into its fill: the middle
    of the strongest run within the first `hi` pixels."""
    weight = _weight(line[:hi], fill)
    top = np.nonzero(weight >= weight.max() * 0.85)[0]
    return float(top.mean())


def cut_still(style: str, path: Path) -> dict:
    """The still bubble from the approved 3 x 2 sheet (the per-pixel median of its six cells), with its
    straight edges made even, and the measurements the app draws by."""
    img = load(path)
    h, w = img.shape[:2]
    cw, ch = w // 3, h // 2
    cells = align_cells([img[r * ch : (r + 1) * ch, c * cw : (c + 1) * cw] for r in range(2) for c in range(3)])
    boxes = [np.nonzero(c[..., 3] > 8) for c in cells]
    y0, y1 = max(min(b[0].min() for b in boxes) - 2, 0), min(max(b[0].max() for b in boxes) + 3, ch)
    x0, x1 = max(min(b[1].min() for b in boxes) - 2, 0), min(max(b[1].max() for b in boxes) + 3, cw)
    still = np.median(np.stack([c[y0:y1, x0:x1] for c in cells]).astype(np.float32), axis=0).round().astype(np.uint8)
    ix0, iy0, ix1, iy1 = _interior(still)
    ih = iy1 - iy0
    solid = still[..., 3] > 200
    band = min(iy1 + max(8, ih // 5), solid.shape[0] - 1)
    runs, start = [], None
    for x, on in enumerate(solid[band]):  # the notch: the solid run just below the bottom edge
        if on and start is None:
            start = x
        elif not on and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, solid.shape[1]))
    runs = [r for r in runs if ix0 < (r[0] + r[1]) / 2 < ix1]
    tl, tr = max(runs, key=lambda r: r[1] - r[0]) if runs else ((ix0 + ix1) // 2 - 10, (ix0 + ix1) // 2 + 10)
    cx = (tl + tr) // 2
    notch = (max(ix0, tl - max(14, ih // 4)), min(ix1, tr + max(14, ih // 4)))
    tail_bottom = int(np.nonzero(solid[:, cx])[0].max())
    corner = max(12, ih // 4)
    art = 2 * TEXT / (ix1 - ix0)  # art px per original px
    fh, fw = still.shape[:2]
    tw, th = round(fw * art), round(fh * art)
    out = resize(still, tw, th)
    a = lambda v: round(v * art)  # noqa: E731
    text = [a(ix0), a(iy0), a(ix1), a(iy1)]
    c, n, tip = a(corner), [a(notch[0]), a(notch[1])], a(cx)
    # Every measure the app cuts the still by is made even, so at half size each piece lands on whole
    # display pixels: a piece that ends on half a pixel shows as a faint line where two pieces meet.
    text = [text[0] + text[0] % 2, text[1] + text[1] % 2, text[2] - (tw - text[2]) % 2, text[3] - (th - text[3]) % 2]
    c += c % 2
    n = [n[0] - (tip - n[0]) % 2, n[1] + (n[1] - tip) % 2]
    tx0, ty0, tx1, ty1 = text
    L, R, T, B = tx0 + c, tw - tx1 + c, ty0 + c, th - ty1 + c
    if style not in KEEP_EDGES:
        # The straight edges are stretched by the app, so anything painted on them would smear: make each
        # one the median of its own columns (or rows). This also takes out the effect bits baked into the
        # sheet (a flame, a crackle, a glint), which the app now draws moving. The corner pieces are eased
        # into the same profile over their last few pixels, so no step shows where a corner meets an edge.
        src = out.astype(np.float32)
        ease = 18  # art px inside each corner piece over which it turns into the edge's profile

        def even(block: np.ndarray, axis: int, core: np.ndarray) -> np.ndarray:
            """`block` with every line along `axis` replaced by the median over the `core` lines, eased in at both ends."""
            profile = np.median(np.take(block, core, axis=axis), axis=axis, keepdims=True)
            n = block.shape[axis]
            pos = np.arange(n, dtype=np.float32)
            weight = np.clip(np.minimum(pos - (core.min() - ease), (core.max() + ease) - pos) / ease, 0, 1)
            shape = [1, 1, 1]
            shape[axis] = n
            weight = weight.reshape(shape)
            return block * (1 - weight) + profile * weight

        out_f = src.copy()
        out_f[:ty0] = even(src[:ty0], 1, np.arange(L, tw - R))
        bottom_block = even(src[ty1:], 1, np.r_[L : n[0], n[1] : tw - R])
        cols = np.ones(tw, bool)
        cols[n[0] : n[1]] = False  # the notch's own columns keep their painting
        out_f[ty1:, cols] = bottom_block[:, cols]
        out_f[:, :tx0] = even(out_f[:, :tx0], 0, np.arange(T, th - B))
        out_f[:, tx1:] = even(out_f[:, tx1:], 0, np.arange(T, th - B))
        out = np.clip(out_f.round(), 0, 255).astype(np.uint8)
    save(out, f"{style}-still.png")
    # The border's centre line: how far in from each side of the frame it runs, and the corner's radius.
    cy, cxm, clear = (ty0 + ty1) // 2, (tx0 + tx1) // 2, tx1 - c  # `clear`: a column right of the notch
    if style in KEEP_EDGES:  # a painted, uneven border: halfway between the outer edge and the fill
        op = out[..., 3] > 200
        left = (int(np.nonzero(op[cy])[0].min()) + tx0) / 2
        right = tw - 1 - (int(np.nonzero(op[cy])[0].max()) + tx1) / 2
        top = (int(np.nonzero(op[:, cxm])[0].min()) + ty0) / 2
        bottom = th - 1 - (int(np.nonzero(op[:, clear])[0].max()) + ty1) / 2
        radius = c * 0.6
        half = ty0 - top + 1
    else:
        fill = np.median(out[ty0 + 8 : ty1 - 8, tx0 + 8 : tx1 - 8, :3].reshape(-1, 3).astype(float), axis=0)
        left = _ridge(out[cy], tx0 + 2, fill)
        right = _ridge(out[cy, ::-1], tw - tx1 + 2, fill)
        top = _ridge(out[:, cxm], ty0 + 2, fill)
        bottom = _ridge(out[::-1, clear], th - ty1 + 2, fill)
        # Radius: the border line crosses the corner's diagonal r * (1 - 1/sqrt 2) in from the corner point.
        diag = _weight(np.array([out[int(round(top + d)), int(round(left + d))] for d in range(1, c)]), fill)
        run = np.nonzero(diag >= diag.max() * 0.85)[0] + 1
        radius = float(run.mean()) / (1 - 1 / np.sqrt(2))
        half = max(2.0, min(tx0 - left, ty0 - top) + 1)
    return {
        "scale": K,
        "w": tw,
        "h": th,
        "text": text,  # the plain fill: where text may go
        "corner": c,  # how far the corner pieces reach past the text area
        "notch": n,  # the strip of the bottom edge that holds the notch (x range)
        "tail": [tip, a(tail_bottom)],  # the notch's tip
        "rim": {"inset": [round(float(v), 1) for v in (left, top, right, bottom)], "radius": round(float(radius), 1), "half": round(float(half), 1)},
    }


def swap_colours(style: str, entry: dict, turn: float) -> str:
    """The still's rim with its colours turned round the colour wheel, for the app to fade in and out over
    the still: the outline is the same, so only the colour drifts. Where the colours do not change (the
    fill, the shadow) it is transparent, so the text area is never drawn over."""
    img = np.asarray(Image.open(OUT / f"{style}-still.png").convert("RGBA")).copy()
    x0, y0, x1, y1 = entry["text"]
    rgb = img[..., :3].astype(float)
    fill = np.median(rgb[y0 + 10 : y1 - 10, x0 + 10 : x1 - 10].reshape(-1, 3), axis=0)
    weight = np.clip((np.abs(rgb - fill).sum(axis=2) - 30) / 50, 0, 1)
    weight[y0:y1, x0:x1] = 0  # the fill itself is identical in both, to the pixel
    hsv = np.array([colorsys.rgb_to_hsv(*(px / 255)) for px in rgb.reshape(-1, 3)])
    hsv[:, 0] = (hsv[:, 0] + turn) % 1.0
    turned = np.array([colorsys.hsv_to_rgb(*px) for px in hsv]).reshape(rgb.shape) * 255
    img[..., :3] = (rgb * (1 - weight[..., None]) + turned * weight[..., None]).round().astype(np.uint8)
    img[weight == 0] = 0  # nothing at all where the two are the same: the app never draws over the fill
    name = f"{style}-still-b.png"
    save(img, name)
    return name


# -- tileable strips


def band_of(img: np.ndarray, pad: int) -> tuple[int, int]:
    rows = np.nonzero((img[..., 3] > 14).mean(axis=1) > 0.01)[0]
    return max(int(rows.min()) - pad, 0), min(int(rows.max()) + pad + 1, img.shape[0])


def smooth_noise(w: int, h: int, cell: int, seed: int, wrap_x: bool = True, wrap_y: bool = False, cell_y: int | None = None) -> np.ndarray:
    """Smooth noise in 0..1, w x h, that tiles along x (and y when asked)."""
    rng = np.random.default_rng(seed)
    gw, gh = max(2, round(w / cell)), max(2, round(h / (cell_y or cell)))
    g = rng.random((gh, gw)).astype(np.float32)
    px, py = (3 if wrap_x else 0), (3 if wrap_y else 0)
    g = np.pad(g, ((py, py), (px, px)), mode="wrap")
    big = np.asarray(Image.fromarray(g).resize((round(g.shape[1] * w / gw), round(g.shape[0] * h / gh)), Image.BICUBIC))
    ox, oy = round(px * w / gw), round(py * h / gh)
    out = big[oy : oy + h, ox : ox + w]
    return np.clip((out - out.min()) / max(1e-6, float(out.max() - out.min())), 0, 1)


def make_tileable(img: np.ndarray, overlap: int, seed: int) -> np.ndarray:
    """Join the strip's two ends: the last `overlap` columns are folded over the first, mixed across a
    ramp whose edge wanders with smooth noise, so the join has no straight line to see."""
    f = premult(img)
    h, w = f.shape[:2]
    n = w - overlap
    out = f[:, :n].copy()
    ramp = (np.arange(overlap, dtype=np.float32) + 0.5) / overlap
    jitter = smooth_noise(overlap, h, 28, seed, wrap_x=False)
    weight = np.clip((ramp[None, :] - 0.5) * 2.2 + 0.5 + (jitter - 0.5) * 0.9, 0, 1)[..., None]  # 0: the tail end, 1: the head
    out[:, :overlap] = f[:, n:] * (1 - weight) + f[:, :overlap] * weight
    return unpremult(out)


def wrap_ratio(img: np.ndarray) -> float:
    """The step from the last column back to the first, against the 99th percentile of the steps between
    neighbouring columns: at or under 1 means the join is no worse than the strip itself."""
    f = premult(img)
    steps = np.abs(np.diff(f, axis=1)).mean(axis=(0, 2))
    wrap = float(np.abs(f[:, 0] - f[:, -1]).mean())
    return wrap / max(1e-6, float(np.percentile(steps, 99)))


def soften_rows(img: np.ndarray, top: int, bottom: int) -> np.ndarray:
    """Fade the strip's top and bottom rows to nothing, so its crop never shows as a line."""
    out = img.astype(np.float32)
    h = img.shape[0]
    ramp = np.ones(h, np.float32)
    if top:
        ramp[:top] = (np.arange(top) + 0.5) / top
    if bottom:
        ramp[h - bottom :] = (np.arange(bottom)[::-1] + 0.5) / bottom
    out[..., 3] *= ramp[:, None]
    return out.round().astype(np.uint8)


def cut_strip(path: Path, name: str, height: float, overlap: int, seed: int, part: float = 1.0, stretch: float = 1.0) -> dict:
    """A tileable strip `height` display px tall, from a generated horizontal band. Only the first `part`
    of the band is used, drawn `stretch` times longer than painted: at border size a painted band's
    features are a few pixels apart and read as a ruffle, so fewer, longer ones are wanted."""
    img = load(path, reach=60)
    y0, y1 = band_of(img, 6)
    band = make_tileable(img[y0:y1, : round(img.shape[1] * part)], overlap, seed)
    scale = (height / K) / band.shape[0]
    w, h = max(8, round(band.shape[1] * scale * stretch)), max(4, round(height / K))
    out = soften_rows(resize(band, w, h), 3, 3)
    save(out, name)
    ratio = wrap_ratio(out)
    print(f"  {name}: {w} x {h} art px, tile {w * K:.0f} display px, wrap step x{ratio:.2f} of the strip's own 99th percentile: {'ok' if ratio <= 1.0 else 'FAIL'}")
    if ratio > 1.0:
        sys.exit(f"{name}: the join shows; raise the overlap or regenerate the strip")
    return {"file": name, "wrap": round(ratio, 2)}


# -- the baked flame loop


def sample(f: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Bilinear sample of premultiplied `f` at float coordinates, wrapping in x and clamping in y."""
    h, w = f.shape[:2]
    x0 = np.floor(x).astype(int)
    y0 = np.clip(np.floor(y).astype(int), 0, h - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    fx, fy = (x - x0)[..., None], np.clip(y - np.floor(y), 0, 1)[..., None]
    xa, xb = x0 % w, (x0 + 1) % w
    top = f[y0, xa] * (1 - fx) + f[y0, xb] * fx
    bot = f[y1, xa] * (1 - fx) + f[y1, xb] * fx
    return top * (1 - fy) + bot * fy


def bake_flames(path: Path, name: str, above: float, below: float, frames: int, period: float, overlap: int, seed: int, part: float = 1.0, stretch: float = 1.0) -> dict:
    """A loop of a tileable flame row: every frame is the same painted row pushed through smooth noise
    that climbs by exactly one of its own heights per loop, so the flames lick upward and the last frame
    runs straight into the first. The push is nothing at the baseline and grows toward the tips, where the
    noise also eats the flames away. Only the first `part` of the painted row is used, drawn `stretch`
    times wider than painted: at border size the painted tongues are a few pixels wide and read as a
    fringe, so fewer, broader ones are wanted."""
    img = load(path, reach=60)
    y0, y1 = band_of(img, 10)
    band = make_tileable(img[y0:y1, : round(img.shape[1] * part)], overlap, seed)
    base = int(np.argmax((band[..., 3] > 200).mean(axis=1)))  # the ember line
    tall = base - int(np.nonzero((band[..., 3] > 30).mean(axis=1) > 0.01)[0].min())
    scale = 2 * (above / K) / tall  # worked at twice the final size, then reduced
    w = round(band.shape[1] * scale * stretch)
    top_rows, low_rows = round(2 * (above + 4) / K), round(2 * below / K)
    src = resize(band, w, round(band.shape[0] * scale))
    b = round(base * scale)
    canvas = np.zeros((top_rows + low_rows, w, 4), np.uint8)
    take0 = max(0, b - top_rows)
    piece = src[take0 : min(src.shape[0], b + low_rows)]
    canvas[top_rows - (b - take0) : top_rows - (b - take0) + piece.shape[0]] = piece
    f = premult(canvas)
    h = f.shape[0]
    period_rows = h * 2  # the noise's height: it climbs this far per loop
    n1 = smooth_noise(w, period_rows, 34, seed + 1, wrap_y=True)
    n2 = smooth_noise(w, period_rows, 26, seed + 2, wrap_y=True)
    n3 = smooth_noise(w, period_rows, 20, seed + 3, wrap_y=True)
    # How tall the fire stands along the row, drifting slowly: patches of taller flames between stretches
    # where it only smoulders. One row per moment of the loop, tiling in x and in time.
    swell = smooth_noise(w, 240, round(2 * 26 / K), seed + 4, wrap_y=True, cell_y=80)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    height = np.clip((top_rows - yy) / (2 * above / K), 0, 1.2)  # 0 at the baseline, 1 at the tallest tip
    out = []
    xi = xx.astype(int)
    for i in range(frames):
        climb = yy + i / frames * period_rows  # the pattern moves up as i grows, by part-rows (no stepping)
        r0 = np.floor(climb).astype(int)
        part_row = (climb - r0).astype(np.float32)

        def at(noise: np.ndarray, r0=r0, part_row=part_row) -> np.ndarray:
            return noise[r0 % period_rows, xi] * (1 - part_row) + noise[(r0 + 1) % period_rows, xi] * part_row

        s = i / frames * 240
        s0 = int(s)
        row = swell[s0 % 240] * (1 - (s - s0)) + swell[(s0 + 1) % 240] * (s - s0)
        stand = np.clip(0.3 + 1.2 * row, 0.3, 1.0)[None, :]  # share of full height
        dx = (at(n1) - 0.5) * 2 * (2 * 4.0 / K) * height**1.3
        dy = (at(n2) - 0.5) * 2 * (2 * 2.5 / K) * height
        ys = np.where(yy < top_rows, top_rows - (top_rows - yy) / stand, yy)  # squash the flames to their height here
        g = sample(f, xx + dx, ys + dy)
        g = np.where((ys < 0)[..., None], 0, g)
        eat = np.clip(1.25 - 1.5 * (height / stand) * at(n3), 0, 1)[..., None]
        out.append(g * eat)
    fw, fh = round(w / 2), round(h / 2)
    small = [soften_rows(resize(unpremult(g), fw, fh), 2, 0) for g in out]
    save(np.concatenate(small, axis=0), name)
    steps = [float(np.abs(premult(small[(i + 1) % frames]) - premult(small[i])).mean()) for i in range(frames)]
    seam = steps[-1] / max(1e-6, (steps[-2] + steps[0]) / 2)  # against the steps either side of it
    wrap = wrap_ratio(small[0])
    ok = seam <= 1.25 and wrap <= 1.0
    print(
        f"  {name}: {frames} frames of {fw} x {fh} art px, tile {fw * K:.0f} display px, loop seam x{seam:.2f} of the steps either side, wrap x{wrap:.2f}: {'ok' if ok else 'FAIL'}"
    )
    if not ok:
        sys.exit(f"{name}: the baked loop does not close cleanly")
    return {
        "type": "flames",
        "file": name,
        "frames": frames,
        "w": fw,
        "h": fh,
        "period": period,
        "base": round(top_rows / 2),
        "seam": round(seam, 2),
        "wrap": round(wrap, 2),
    }


# -- single sprites


def cut_sprites(path: Path, name: str, cols: int, rows: int, size: float, skip: tuple[int, ...] = ()) -> dict:
    """The sheet's separate sprites (all but the cells in `skip`), each centred in its own box, side by
    side; the longer side `size` display px."""
    img = load(path)
    h, w = img.shape[:2]
    cw, ch = w // cols, h // rows
    crops = []
    for i, cell in enumerate(img[r * ch : (r + 1) * ch, c * cw : (c + 1) * cw] for r in range(rows) for c in range(cols)):
        if i in skip:
            continue
        ys, xs = np.nonzero(cell[..., 3] > 8)
        crops.append(cell[max(ys.min() - 2, 0) : ys.max() + 3, max(xs.min() - 2, 0) : xs.max() + 3])
    fh, fw = max(c.shape[0] for c in crops), max(c.shape[1] for c in crops)
    scale = (size / K) / max(fh, fw)
    tw, th = max(2, round(fw * scale)), max(2, round(fh * scale))
    strip = np.zeros((th, tw * len(crops), 4), np.uint8)
    for i, c in enumerate(crops):
        box = np.zeros((fh, fw, 4), np.uint8)
        oy, ox = (fh - c.shape[0]) // 2, (fw - c.shape[1]) // 2
        box[oy : oy + c.shape[0], ox : ox + c.shape[1]] = c
        strip[:, i * tw : (i + 1) * tw] = resize(box, tw, th)
    save(strip, name)
    return {"file": name, "count": len(crops), "w": tw, "h": th}


def tone(img: np.ndarray, hue: float, sat: float, val: float) -> np.ndarray:
    """The picture with its hue turned and its saturation and brightness scaled (alpha untouched)."""
    rgb = img[..., :3].astype(np.float32) / 255
    hsv = np.array([colorsys.rgb_to_hsv(*px) for px in rgb.reshape(-1, 3)])
    hsv[:, 0] = (hsv[:, 0] + hue) % 1.0
    hsv[:, 1] = np.clip(hsv[:, 1] * sat, 0, 1)
    hsv[:, 2] = np.clip(hsv[:, 2] * val, 0, 1)
    out = img.copy()
    out[..., :3] = (np.array([colorsys.hsv_to_rgb(*px) for px in hsv]).reshape(rgb.shape) * 255).round().astype(np.uint8)
    return out


ELECTRIC_HUE = 47.0  # degrees: the electric style's lightning is yellow (it was painted cyan, like the border)


def set_hue(img: np.ndarray, hue: float, amount: np.ndarray | float = 1.0) -> np.ndarray:
    """The picture with every colour's hue set to `hue` (degrees, 0 to 60: red to yellow), keeping its
    saturation and brightness, so a white core stays white and a soft glow stays as see-through as it
    was. `amount` (0..1, per pixel or one number) is how much of the change each pixel takes."""
    rgb = img[..., :3].astype(np.float32)
    hi, lo = rgb.max(-1), rgb.min(-1)
    turned = np.stack([hi, hi - (hi - lo) * (1 - hue / 60.0), lo], axis=-1)
    a = np.asarray(amount, np.float32)[..., None] if np.ndim(amount) else float(amount)
    out = img.copy()
    out[..., :3] = np.clip(rgb + (turned - rgb) * a, 0, 255).round().astype(np.uint8)
    return out


def retint(name: str, hue: float) -> None:
    img = np.asarray(Image.open(OUT / name).convert("RGBA"))
    save(set_hue(img, hue), name)


def cut_crawler(path: Path, name: str, width: float, frames: int, lift: float, toned: tuple[float, float, float] = (0.0, 1.0, 1.0)) -> dict:
    """The caterpillar's crawl, made from ONE painted sprite (the sheet's last cell, the flat pose): each
    column of the sprite is lifted by a wave that runs from tail to head, one whole wave per loop, so the
    gait is smooth and its last frame runs into its first. Frames are written side by side."""
    img = load(path)
    h, w = img.shape[:2]
    cell = img[h // 2 :, 3 * (w // 4) :]
    ys, xs = np.nonzero(cell[..., 3] > 8)
    crop = cell[max(ys.min() - 2, 0) : ys.max() + 3, max(xs.min() - 2, 0) : xs.max() + 3]
    scale = (width / K) / crop.shape[1]
    flat = tone(resize(crop, round(crop.shape[1] * scale), round(crop.shape[0] * scale)), *toned)
    room = round(lift / K) + 2  # rows above the sprite for the hump to rise into
    fh, fw = flat.shape[0] + room, flat.shape[1]
    base = np.zeros((fh, fw, 4), np.float32)
    base[room:] = premult(flat)
    u = (np.arange(fw) + 0.5) / fw  # 0 at the tail, 1 at the head
    body = np.sin(np.pi * np.minimum(1.0, u / 0.82)) ** 0.6  # the head and the tail tip barely lift
    yy = np.broadcast_to(np.arange(fh, dtype=np.float32)[:, None], (fh, fw))
    xx = np.broadcast_to(np.arange(fw, dtype=np.float32)[None, :], (fh, fw))
    out = []
    for i in range(frames):
        wave = np.maximum(0.0, np.sin(2 * np.pi * (u * 1.15 - i / frames))) ** 1.5
        up = (lift / K) * wave * body
        out.append(unpremult(sample(base, xx, yy + up[None, :])))
    save(np.concatenate(out, axis=1), name)
    steps = [float(np.abs(premult(out[(i + 1) % frames]) - premult(out[i])).mean()) for i in range(frames)]
    seam = steps[-1] / max(1e-6, (steps[-2] + steps[0]) / 2)  # against the steps either side of it
    feet = float(np.nonzero((flat[..., 3] > 128).any(axis=1))[0].max() + 1 + room) / fh
    print(f"  {name}: {frames} frames of {fw} x {fh} art px, gait seam x{seam:.2f} of the steps either side: {'ok' if seam <= 1.25 else 'FAIL'}")
    if seam > 1.25:
        sys.exit(f"{name}: the gait does not close")
    return {"file": name, "frames": frames, "w": fw, "h": fh, "feet": round(feet, 3)}


# -- each style's effect: what it is built from and how it moves (see art/bubbles/README.md)


def effects(style: str, raw: Path, entry: dict) -> list[dict]:
    if style == "ghost":
        a = cut_strip(raw / "ghost-mist-a.png", "ghost-mist-a.png", height=19, overlap=260, seed=11, part=0.62, stretch=2.4)
        b = cut_strip(raw / "ghost-mist-b.png", "ghost-mist-b.png", height=14, overlap=260, seed=12, part=0.62, stretch=2.0)
        return [
            {"type": "glow", "period": 6.0, "amount": 0.16, "beats": [1]},
            {"type": "scroll", "file": a["file"], "period": 6.0, "speed": 11.0, "offset": 0.5, "opacity": 0.5, "breathe": 0.35},
            {"type": "scroll", "file": b["file"], "period": 6.0, "speed": -7.0, "offset": 0.0, "opacity": 0.7, "breathe": 0.3, "phase": 0.5},
        ]
    if style == "electric":
        cur = cut_strip(raw / "electric-current.png", "electric-current.png", height=12, overlap=220, seed=21)
        arcs = cut_sprites(raw / "electric-arcs.png", "electric-arcs.png", 4, 2, size=58, skip=(3, 7))  # the two painted yellow are left out
        retint(cur["file"], ELECTRIC_HUE)
        retint(arcs["file"], ELECTRIC_HUE)
        run = {"period": 8.0, "count": 2, "laps": 1}  # two pulses, each once round the border in 8 s
        return [
            {"type": "glow", "period": 4.0, "amount": 0.14, "beats": [1, 3]},
            {"type": "runner", "file": cur["file"], **run, "speed": 10.0, "offset": 0.0, "opacity": 1.0, "tail": 190.0, "lead": 12.0, "glow": 0.9, "halo": 22.0, "head": 6.0, "colour": "#ffd93b", "plus": False},
            {"type": "wake", **arcs, **run, "spacing": 80.0, "life": 0.6, "seed": 7, "offset": 2.0, "plus": False},
        ]
    if style == "fire":
        flames = bake_flames(raw / "fire-flames.png", "fire-flames.png", above=15, below=2, frames=36, period=3.0, overlap=200, seed=31, part=0.6, stretch=1.7)
        embers = cut_sprites(raw / "fire-embers.png", "fire-embers.png", 3, 2, size=7)
        return [
            flames,
            {"type": "glow", "period": 3.0, "amount": 0.22, "beats": [1, 2]},
            {"type": "embers", **embers, "period": 3.0, "slots": 5, "life": 1.5, "seed": 3, "plus": True},
        ]
    if style == "fairy":
        b = swap_colours("fairy", entry, turn=0.42)
        sparkles = cut_sprites(raw / "fairy-sparkles.png", "fairy-sparkles.png", 3, 2, size=22)
        return [
            {"type": "swap", "file": b, "period": 6.0, "amount": 0.9},
            {"type": "sheen", "period": 6.0, "count": 2, "life": 2.6, "speed": 34.0, "reach": 40.0, "amount": 0.8, "seed": 4},
            {"type": "sparkles", **sparkles, "period": 6.0, "slots": 4, "life": 1.3, "seed": 5, "plus": True},
        ]
    if style == "leaf":
        crawler = cut_crawler(raw / "leaf-caterpillar.png", "leaf-crawler.png", width=34, frames=42, lift=2.6, toned=(0.035, 0.86, 0.8))
        return [{"type": "crawler", **crawler, "speed": 10.0, "stride": 1.4, "rest": 2.8}]
    return []


def main() -> None:
    raw = Path(sys.argv[1])
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else STYLES
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    for style in only:
        print(style)
        entry = cut_still(style, raw / f"{style}-anim.png")
        entry["fx"] = effects(style, raw, entry)
        manifest[style] = entry
        print("  rim", entry["rim"], "text", entry["text"], "notch", entry["notch"])
    manifest_path.write_text(json.dumps(dict(sorted(manifest.items())), indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
