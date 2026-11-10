"""Pixel fixes and per-frame alignment shared by penguin-slice.py and penguin-touchup.py.

Frames are RGBA numpy arrays (height x width x 4, uint8). Needs Pillow and numpy.
"""

from __future__ import annotations

import re

import numpy as np
from PIL import Image, ImageFilter

# How each animation keeps its body still from frame to frame (see ../README.md):
#   body   best overlap of the body's own colours with frame 1 (effects, glows and sparks left out)
#   torso  the same, using only the middle band of the body, so swinging feet or a beam don't pull it
#   foot   the mean x of the feet (the bottom quarter), the point the app pins to the floor
#   belly  the centre of the white penguin mark on the belly (hop and alert: spread flippers pull "body" off)
#   cut    the centre of what shows at the cut line (peek is only a head over the taskbar)
ALIGN = {
    "walk": "torso",
    "idle": "body",
    "peek": "cut",
    "talk": "body",
    "wave": "body",
    "think": "body",
    "hop": "belly",
    "sleep": "body",
    "charge": "body",
    "alert": "belly",
    "turn": "foot",
    "beam": "foot",
}
MAX_SHIFT = 80  # px searched either way when matching frames


def _hue(rgb: np.ndarray) -> np.ndarray:
    r, g, b = (rgb[..., i].astype(float) / 255 for i in range(3))
    mx = np.maximum(np.maximum(r, g), b)
    c = mx - np.minimum(np.minimum(r, g), b)
    h = np.zeros_like(mx)
    m = c > 1e-6
    rr = m & (mx == r)
    gg = m & (mx == g) & ~rr
    bb = m & ~rr & ~gg
    h[rr] = (60 * ((g - b)[rr] / c[rr])) % 360
    h[gg] = 60 * ((b - r)[gg] / c[gg]) + 120
    h[bb] = 60 * ((r - g)[bb] / c[bb]) + 240
    return h


def despill(frame: np.ndarray) -> np.ndarray:
    """Pull the chroma-key green out of edge and gap pixels: green-hued pixels (hue 85-170) get their
    green channel clamped to the larger of red and blue. The penguin has no green of its own; the
    yellow bolts (hue < 85) and the cyan nodes and glows (hue > 170) are left alone."""
    out = frame.copy()
    rgb = out[..., :3].astype(int)
    h = _hue(rgb)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    m = (out[..., 3] > 0) & (g > np.maximum(r, b)) & (h >= 85) & (h <= 170)
    out[..., 1] = np.where(m, np.maximum(r, b), g).astype(np.uint8)
    return out


def body_mask(frame: np.ndarray) -> np.ndarray:
    """Opaque pixels in the penguin's own colours: charcoal, orange, cream and the blue plates."""
    r, g, b, a = (frame[..., i].astype(int) for i in range(4))
    charcoal = (r + g + b) / 3 < 95
    orange = (r > 170) & (g > 70) & (g < 185) & (b < 100) & (r - g > 50)
    cream = (r > 200) & (g > 185) & (b > 150) & (r - b < 50) & (r >= g - 3)
    armour = (b > r + 40) & (b > 120) & (g < 190)
    return (a > 200) & (charcoal | orange | cream | armour)


def effect_mask(frame: np.ndarray) -> np.ndarray:
    """Lightning, sparks and glow: bright yellow, cyan or near-white pixels that are not cream."""
    r, g, b, a = (frame[..., i].astype(int) for i in range(4))
    yellow = (r > 190) & (g > 170) & (b < 200) & (r - b > 55)
    cyan = (b > 170) & (g > 170) & (r < 200)
    white = (r > 235) & (g > 235) & (b > 220)
    return (a > 40) & (yellow | cyan | white) & ~body_mask(frame)


def _torso(mask: np.ndarray) -> np.ndarray:
    rows = np.nonzero(mask.any(1))[0]
    if len(rows) == 0:
        return mask
    top, bottom = rows.min(), rows.max()
    out = np.zeros_like(mask)
    lo, hi = top + int((bottom - top) * 0.3), top + int((bottom - top) * 0.78)
    out[lo:hi] = mask[lo:hi]
    return out


def _shifted(mask: np.ndarray, dx: int) -> np.ndarray:
    out = np.zeros_like(mask)
    if dx > 0:
        out[:, dx:] = mask[:, :-dx]
    elif dx < 0:
        out[:, :dx] = mask[:, -dx:]
    else:
        out[:] = mask
    return out


def _best_overlap(ref: np.ndarray, mask: np.ndarray) -> int:
    best, best_dx = -1.0, 0
    for dx in range(-MAX_SHIFT, MAX_SHIFT + 1):
        s = _shifted(mask, dx)
        union = (ref | s).sum()
        score = (ref & s).sum() / union if union else 0.0
        if score > best:
            best, best_dx = score, dx
    return best_dx


def _foot_x(frame: np.ndarray) -> float:
    a = frame[..., 3]
    ys, xs = np.nonzero(a[a.shape[0] * 3 // 4 :] > 40)
    return float(xs.mean()) if len(xs) else a.shape[1] / 2


def _belly_x(frame: np.ndarray) -> float:
    r, g, b, a = (frame[..., i].astype(int) for i in range(4))
    ys, xs = np.nonzero((a > 200) & (r > 245) & (g > 245) & (b > 245))
    return float(xs.mean()) if len(xs) else _foot_x(frame)


def _cut_x(frame: np.ndarray) -> float:
    a = frame[..., 3]
    rows = np.nonzero((a > 40).any(1))[0]
    if len(rows) == 0:
        return a.shape[1] / 2
    band = a[max(0, rows.max() - 11) : rows.max() + 1] > 40
    xs = np.nonzero(band.any(0))[0]
    return (xs.min() + xs.max()) / 2


def frame_shifts(frames: list[np.ndarray], mode: str) -> list[int]:
    """How far to move each frame right so its body sits where frame 1's does."""
    if mode in ("body", "torso"):
        masks = [body_mask(f) for f in frames]
        if mode == "torso":
            masks = [_torso(m) for m in masks]
        return [0] + [_best_overlap(masks[0], m) for m in masks[1:]]
    anchor = {"foot": _foot_x, "belly": _belly_x, "cut": _cut_x}[mode]
    ref = anchor(frames[0])
    return [round(ref - anchor(f)) for f in frames]


def realign(frames: list[np.ndarray], mode: str, pad: int = 6) -> tuple[list[np.ndarray], list[int]]:
    """Shift every frame so the body stays put, then crop all frames to one shared width.
    Heights and vertical positions are kept (a hop or a bob is real motion)."""
    shifts = frame_shifts(frames, mode)
    h, w = frames[0].shape[:2]
    margin = MAX_SHIFT + pad
    wide = []
    for f, dx in zip(frames, shifts, strict=True):
        canvas = np.zeros((h, w + 2 * margin, 4), np.uint8)
        canvas[:, margin + dx : margin + dx + w] = f
        wide.append(canvas)
    cols = np.nonzero(np.any([c[..., 3] > 0 for c in wide], axis=(0, 1)))[0]
    left, right = max(0, cols.min() - pad), min(wide[0].shape[1], cols.max() + 1 + pad)
    return [c[:, left:right] for c in wide], shifts


def fade_cut_edges(frame: np.ndarray, span: int = 90, near: int = 10, min_run: int = 12) -> tuple[np.ndarray, bool]:
    """An effect (a beam, a bolt) cut off by the sheet's cell edge ends in a hard vertical line. If the
    outermost effect column within `near` px of the left or right edge holds at least `min_run` effect
    pixels, fade everything there to zero over `span` px towards that edge, except what touches the
    penguin's dark outline, so the body is never cut. Meant for effect animations only
    (penguin-touchup.py runs it on charge): a glowing outline would trip it elsewhere."""
    out = frame.copy()
    eff = effect_mask(frame)
    w = frame.shape[1]
    changed = False
    cols = np.nonzero(eff.any(0))[0]
    if len(cols) == 0:
        return out, False
    # Everything in the fade zone fades (a beam's pale core reads as cream to body_mask), except
    # pixels next to the penguin's charcoal outline, so a flipper reaching into the zone stays whole.
    rgb = frame[..., :3].astype(int)
    charcoal = (frame[..., 3] > 200) & (rgb.sum(-1) / 3 < 95)
    near_body = np.asarray(Image.fromarray((charcoal * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) > 0
    soft = ~near_body & (frame[..., 3] > 0)
    for side, col in (("right", cols.max()), ("left", cols.min())):
        dist = w - 1 - col if side == "right" else col
        if dist > near or eff[:, col].sum() < min_run:
            continue
        x = np.arange(w, dtype=float)
        ramp = np.clip((col - x) / span, 0, 1) if side == "right" else np.clip((x - col) / span, 0, 1)
        factor = np.where(soft, (ramp**1.6)[None, :], 1.0)
        out[..., 3] = (out[..., 3] * factor).round().astype(np.uint8)
        changed = True
    return out, changed


def recolour_feet(frame: np.ndarray, box: tuple[int, int, int, int]) -> tuple[np.ndarray, int]:
    """Turn olive or brown foot pixels inside `box` (x0, y0, x1, y1) charcoal, keeping their shading.
    The orange toe claws (red well above green) and the yellow bolts (bright green) are kept."""
    out = frame.copy()
    x0, y0, x1, y1 = box
    sub = out[y0:y1, x0:x1].astype(int)
    r, g, b, a = (sub[..., i] for i in range(4))
    olive = (a > 0) & (b < np.minimum(r, g) - 12) & (r - g < 42) & (g < 150)
    lum = 0.3 * r + 0.59 * g + 0.11 * b
    v = lum * 0.5
    sub[..., 0] = np.where(olive, v, r)
    sub[..., 1] = np.where(olive, v, g)
    sub[..., 2] = np.where(olive, np.minimum(255, v * 1.15 + 3), b)
    out[y0:y1, x0:x1] = np.clip(sub, 0, 255).astype(np.uint8)
    return out, int(olive.sum())


def bolt_halo(frame: np.ndarray, colour=(18, 26, 46), strength: float = 0.5, radius: int = 2) -> np.ndarray:
    """A thin dark halo behind lightning and sparks that stick out past the body, so pale bolts still
    read on a light taskbar. Opaque pixels are unchanged; the halo only fills in behind see-through ones."""
    eff = effect_mask(frame) & (frame[..., 3] > 120)
    if not eff.any():
        return frame
    m = Image.fromarray((eff * 255).astype(np.uint8))
    m = m.filter(ImageFilter.MaxFilter(2 * radius + 1)).filter(ImageFilter.GaussianBlur(radius * 0.6))
    halo_a = np.asarray(m).astype(float) / 255 * strength
    src_a = frame[..., 3].astype(float) / 255
    out_a = src_a + halo_a * (1 - src_a)
    out = frame.astype(float).copy()
    safe = np.where(out_a > 0, out_a, 1)
    for i, c in enumerate(colour):
        out[..., i] = (frame[..., i] * src_a + c * halo_a * (1 - src_a)) / safe
    out[..., 3] = out_a * 255
    return np.clip(out.round(), 0, 255).astype(np.uint8)


def split(strip: np.ndarray, frames: int, w: int) -> list[np.ndarray]:
    return [strip[:, i * w : (i + 1) * w].copy() for i in range(frames)]


def join(frames: list[np.ndarray]) -> np.ndarray:
    return np.concatenate(frames, axis=1)



# ---------------------------------------------------------------------------------------------------
# Any key colour, any creature (creature-cut.py and creature-qc.py). The penguin's own tools above
# key on green by dominance and know its colours; what follows measures the key from the sheet, keys
# soft glows without a fringe, and finds components and anchors from masks the caller describes.

GLOW_DEPTH = 48  # px a glow may be followed inwards from its tinted part
GLOW_MATCH = 50  # summed RGB difference allowed between neighbouring glow pixels, unmixed
GLOW_FLAT = 2  # px a glow may go on without thickening before it counts as paint
EDGE_BAND = 6  # px inside the outline that despill reaches (2 px of a strip is up to 5 of a sheet)
SPILL_HUES = {"green": (85, 170), "magenta": (270, 345)}  # the hues that count as the key's (key_spill)
DESPILL_HUES = {"green": (80, 170), "magenta": (265, 350)}  # what despill_key touches: a little wider, but never the cyan above 170


def key_family(key: np.ndarray) -> str:
    return "green" if key[1] > max(key[0], key[2]) else "magenta"


def measure_key(rgb: np.ndarray, ring: int = 12) -> tuple[np.ndarray, float]:
    """A sheet's key colour (the median of its border pixels) and how far the border strays from it
    (the 99.9th percentile of the RGB distance)."""
    a = rgb[..., :3].astype(float)
    edge = np.concatenate([a[:ring].reshape(-1, 3), a[-ring:].reshape(-1, 3), a[:, :ring].reshape(-1, 3), a[:, -ring:].reshape(-1, 3)])
    key = np.median(edge, axis=0)
    return key, float(np.percentile(np.sqrt(((edge - key) ** 2).sum(-1)), 99.9))


def keyness(rgb: np.ndarray, key: np.ndarray) -> np.ndarray:
    """How much of the key's tint a colour carries: on green, green above the larger of red and blue;
    on magenta, the smaller of red and blue above green. The key itself scores highest; the creatures'
    own colours score about zero or below."""
    high = key > 128
    p = rgb[..., :3].astype(float)
    return p[..., high].min(-1) - p[..., ~high].max(-1)


def least_alpha(rgb: np.ndarray, key: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The smallest alpha each pixel can have over the key and still be a real colour, and that colour.
    Exact for light (a glow, a sparkle, white) and for black, which sit on the edge of the colour
    cube; too low for mid-tones, so only blends are given it."""
    p = rgb[..., :3].astype(float)
    k = key.astype(float)
    up = np.where((p > k) & (255 - k >= 20), (p - k) / np.maximum(255 - k, 1), 0)
    down = np.where((p < k) & (k >= 20), (k - p) / np.maximum(k, 1), 0)
    a = np.clip(np.maximum(up, down).max(-1), 0, 1)
    # Nothing drawn is key-coloured, so a pixel tinted as much as the key holds no foreground at all
    # (the sheets have patches of slightly brighter key around some shapes).
    a = np.minimum(a, np.clip(1 - keyness(p, k) / keyness(k, k), 0, 1))
    colour = np.clip(k + (p - k) / np.maximum(a, 1e-3)[..., None], 0, 255)
    return a, colour


def grow(mask: np.ndarray, steps: int = 1, diagonal: bool = False) -> np.ndarray:
    """The mask, widened by `steps` pixels."""
    m = mask
    for _ in range(steps):
        n = m.copy()
        n[1:] |= m[:-1]
        n[:-1] |= m[1:]
        n[:, 1:] |= m[:, :-1]
        n[:, :-1] |= m[:, 1:]
        if diagonal:
            n[1:, 1:] |= m[:-1, :-1]
            n[1:, :-1] |= m[:-1, 1:]
            n[:-1, 1:] |= m[1:, :-1]
            n[:-1, :-1] |= m[1:, 1:]
        m = n
    return m


def label(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The mask's 4-connected components: an array of labels (0 where the mask is clear) and each
    label's area. Works on runs of pixels, so it is quick without scipy."""
    h, w = mask.shape
    padded = np.zeros((h, w + 2), bool)
    padded[:, 1:-1] = mask
    d = np.diff(padded.astype(np.int8), axis=1)
    ys, starts = np.nonzero(d == 1)
    ends = np.nonzero(d == -1)[1]  # row-major like the starts: one end for each
    n = len(ys)
    parent = list(range(n + 1))

    def find(i: int) -> int:
        root = i
        while parent[root] != root:
            root = parent[root]
        while parent[i] != root:
            parent[i], i = root, parent[i]
        return root

    first = np.searchsorted(ys, np.arange(h + 1))
    s, e = starts.tolist(), ends.tolist()
    for y in range(1, h):
        i, i_end, j, j_end = int(first[y - 1]), int(first[y]), int(first[y]), int(first[y + 1])
        while i < i_end and j < j_end:
            if s[i] < e[j] and s[j] < e[i]:
                a, b = find(i + 1), find(j + 1)
                if a != b:
                    parent[max(a, b)] = min(a, b)
            if e[i] < e[j]:
                i += 1
            else:
                j += 1
    roots = np.array([find(i) for i in range(n + 1)])
    compact = np.unique(roots, return_inverse=True)[1]
    labels = np.zeros((h, w), np.int32)
    areas = np.zeros(int(compact.max()) + 1, np.int64)
    for i in range(n):
        labels[ys[i], s[i] : e[i]] = compact[i + 1]
        areas[compact[i + 1]] += e[i] - s[i]
    return labels, areas


def chroma_key(rgb: np.ndarray, key: np.ndarray, spread: float, soft: bool = True, tint: float = 6.0) -> tuple[np.ndarray, np.ndarray]:
    """A sheet on a flat key colour, as RGBA, and the mask of the pixels it had to work out.

    Every pixel is background, paint (opaque, its colour kept) or a blend of the two. Blends are found
    from the outside in: pixels that still carry the key's tint and connect to the background (the
    anti-aliased edges and the outer part of every glow) and, with `soft`, whatever continues a glow
    uphill from there. A blend beside paint that lies on the line from the key to that paint is an
    anti-aliased edge of it: it gets the paint's colour and the alpha the line gives. Any other blend
    is light over the key (a glow, a sparkle, mist): the least alpha it can have, its colour unmixed.
    A glow is never cut at a threshold (its faintest tenth fades out, with what is only the sheet's
    background wavering), and no blend keeps any of the key in its colour.
    """
    p = rgb[..., :3].astype(float)
    k = key.astype(float)
    bg = np.sqrt(((p - k) ** 2).sum(-1)) <= spread + 8
    a_min, light = least_alpha(p, k)

    tinted = (keyness(p, k) > tint) & ~bg
    labels, _ = label(tinted)
    is_blend = np.zeros(int(labels.max()) + 1, bool)
    is_blend[np.unique(labels[grow(bg) & tinted])] = True
    # a tinted patch shut in by outlines (the notch between two ears) is the background showing
    # through, unless it is dense enough to be paint (cyan wings are tinted a little, and bright)
    density = np.bincount(labels.ravel(), a_min.ravel()) / np.maximum(np.bincount(labels.ravel()), 1)
    is_blend |= density < 0.6
    is_blend[0] = False
    blend = is_blend[labels]

    glow = np.zeros_like(bg)
    shallow = blend
    if soft:
        # A glow thickens steadily towards whatever it surrounds, in one colour: follow it uphill from
        # its tinted part. Paint is flat, so the walk dies within GLOW_FLAT pixels of entering any.
        glow = blend & (a_min >= 0.1)
        shallow = blend | glow
        peak = np.where(glow, a_min, 0.0)
        flat = np.zeros(bg.shape, np.int16)
        steps = ((1, 0), (-1, 0), (0, 1), (0, -1))
        alike = [~bg & (np.abs(light - np.roll(light, step, (0, 1))).sum(-1) < GLOW_MATCH) for step in steps]
        for depth in range(1, GLOW_DEPTH + 1):
            added = np.zeros_like(glow)
            for step, same in zip(steps, alike, strict=True):
                src = np.roll(glow & (a_min < 0.9), step, (0, 1))
                src_peak = np.roll(peak, step, (0, 1))
                src_flat = np.roll(flat, step, (0, 1))
                rises = a_min >= src_peak + 0.01
                new = src & ~glow & ~added & same & (a_min >= src_peak - 0.02) & (rises | (src_flat < GLOW_FLAT))
                peak[new] = np.maximum(src_peak, a_min)[new]
                flat[new] = np.where(rises, 0, src_flat + 1)[new]
                added |= new
            if not added.any():
                break
            glow |= added
            if depth == GLOW_FLAT:
                shallow = glow.copy()
    mixed = blend | glow
    # tinted pixels the walk passed round (a pocket of mist inside a glow) are blends too
    labels, _ = label(tinted & ~mixed)
    touching = np.unique(labels[grow(mixed) & tinted & ~mixed])
    mixed |= np.isin(labels, touching[touching > 0]) & tinted
    solid = ~bg & ~mixed
    rim = solid & grow(mixed | bg)  # paint's outermost pixel: it may hold a little of the key
    core = solid & ~rim

    # the nearest paint colour, carried a few pixels outwards from the core
    paint = np.where(core[..., None], p, 0.0)
    known = core.copy()
    for _ in range(4):
        total = np.zeros_like(paint)
        count = np.zeros(known.shape, float)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            src = np.roll(known, (dy, dx), (0, 1))
            total += np.where(src[..., None], np.roll(paint, (dy, dx), (0, 1)), 0)
            count += src
        fill = ~known & (count > 0)
        paint[fill] = total[fill] / count[fill][:, None]
        known |= fill
    line = paint - k
    length2 = np.maximum((line**2).sum(-1), 1.0)
    along = ((p - k) * line).sum(-1) / length2
    off = np.sqrt((((p - k) - along[..., None] * line) ** 2).sum(-1))
    on_line = known & (along > 0) & (off < np.minimum(30.0, 0.16 * np.sqrt(length2)))
    # a rim pixel that looks like paint nearby is that paint; so is one too dense to be a blend
    nearest = np.full(bg.shape, 1e9)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dy or dx:
                d = np.abs(p - np.roll(p, (dy, dx), (0, 1))).sum(-1)
                nearest = np.minimum(nearest, np.where(np.roll(core, (dy, dx), (0, 1)), d, 1e9))
    kept = rim & ((nearest < 48) | ((a_min >= 0.8) & ~on_line))
    edge = on_line & (shallow | (rim & ~kept))
    light_px = (mixed | rim) & ~edge & ~kept

    alpha = np.where(bg, 0.0, 1.0)
    colour = p.copy()
    # light this dense is as good as opaque (a dark outline measures 0.9): close the last tenth
    a = a_min[light_px]
    a = np.minimum(1.0, a + np.clip(a - 0.8, 0, None))
    alpha[light_px] = a
    colour[light_px] = np.clip(k + (p[light_px] - k) / np.maximum(a, 1e-3)[:, None], 0, 255)
    # Light that comes out the key's own colour is the sheet's background wavering, not something
    # drawn. So is light with none of the channel the key lacks (on green: no red at all, a pure
    # cyan; every glow, spark and highlight drawn has some) or, where it is faint, with little of
    # it; and so is a faint dark veil (glows are bright, and the sheets have no shadows).
    alpha[light_px] *= np.clip(1 - (keyness(colour[light_px], k) - 10) / 30, 0, 1)
    veil = light_px & (colour.max(-1) < 140)
    bright = light_px & ~veil
    lacking = colour[bright][:, int(np.argmin(k))]
    alpha[bright] *= np.clip((lacking - 30) / 40, 0, 1)
    little = np.clip((lacking / colour[bright].max(-1) - 0.35) / 0.25, 0, 1)
    alpha[bright] *= 1 - (1 - little) * np.clip((0.4 - alpha[bright]) / 0.1, 0, 1)
    alpha[veil] *= np.clip((alpha[veil] - 0.1) / 0.15, 0, 1)
    alpha[edge] = np.clip(along[edge], 0, 1)
    colour[edge] = paint[edge]
    # the faintest blends fade out rather than being cut off: the sheet's own noise ends here
    t = np.clip((alpha - 0.04) / 0.08, 0, 1)
    alpha = np.where(alpha < 0.12, alpha * t * t * (3 - 2 * t), alpha)
    out = np.dstack([colour, alpha * 255])
    out[alpha == 0] = 0
    worked_out = (mixed | rim) & (alpha > 0)
    # The sheet's colour also bleeds a few pixels into dark outlines and white highlights: take the
    # key's tint out of those along the whole edge. Bright, saturated paint there (cyan wings) is colour, not spill.
    plain = (p.max(-1) < 110) | (p.max(-1) - p.min(-1) < 60)
    near_edge = grow(bg | mixed, EDGE_BAND, diagonal=True) & (alpha > 0) & plain
    return despill_key(np.clip(out.round(), 0, 255).astype(np.uint8), key, worked_out | near_edge), worked_out


def despill_key(frame: np.ndarray, key: np.ndarray, where: np.ndarray | None = None) -> np.ndarray:
    """despill() for either key: pixels (all, or those in `where`) whose hue is the key's and that are
    tinted like it lose the excess. On green, green comes down to the larger of red and blue; on
    magenta, red and blue come down to green. Other hues (a gold star, cyan wings) are left alone.
    Near-black pixels have no hue to speak of, so any tint the key's way goes."""
    out = frame.copy()
    rgb = out[..., :3].astype(int)
    lo, hi = DESPILL_HUES[key_family(key)]
    h = _hue(rgb)
    excess = keyness(rgb, key).astype(int)
    m = (out[..., 3] > 0) & (excess > 0) & (((h >= lo) & (h <= hi)) | (rgb.max(-1) < 64))
    if where is not None:
        m &= where
    high = key > 128
    for c in range(3):
        if high[c]:
            out[..., c] = np.where(m, rgb[..., c] - excess, rgb[..., c]).clip(0, 255).astype(np.uint8)
    return out


def despill_edge(frame: np.ndarray, key: np.ndarray, band: int = 3, min_alpha: int = 32) -> np.ndarray:
    """despill_key for a frame that has been scaled: averaging two clean colours can make a third that
    leans the key's way (a yellow and a cyan highlight make a greenish white). Along the edge (within
    `band` px of a pixel at or below `min_alpha`), plain pixels (dark, or nearly grey) lose that tint."""
    rgb = frame[..., :3].astype(int)
    shown = frame[..., 3] > min_alpha
    plain = (rgb.max(-1) < 110) | (rgb.max(-1) - rgb.min(-1) < 60)
    return despill_key(frame, key, grow(~shown, band, diagonal=True) & plain)


def key_spill(frame: np.ndarray, key: np.ndarray, band: int = 2, min_alpha: int = 32) -> np.ndarray:
    """The edge pixels (within `band` px of a pixel at or below `min_alpha`) that still look keyed:
    within 100 RGB levels of the key colour, or of the key's hue and tinted more than 10 levels its way."""
    rgb = frame[..., :3].astype(int)
    shown = frame[..., 3] > min_alpha
    edge = shown & grow(~shown, band, diagonal=True)
    lo, hi = SPILL_HUES[key_family(key)]
    h = _hue(rgb)
    near = np.sqrt(((rgb - key) ** 2).sum(-1)) < 100
    tinted = (keyness(rgb, key) > 10) & (h >= lo) & (h <= hi)
    return edge & (near | tinted)


def resize_rgba(frame: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Resample an RGBA frame to (width, height) with colour weighted by alpha, in floating point, so
    see-through pixels neither darken the edge nor lose their colour. Inside the drawing it is a
    Lanczos resample; at the edge, where Lanczos overshoots and would turn a faint pixel some colour
    its neighbours never had, the colour comes from a filter that only averages (Hamming)."""
    f = frame.astype(np.float32)
    a = f[..., 3] / 255

    def planes(kernel) -> list[np.ndarray]:
        return [np.asarray(Image.fromarray(f[..., c] * a).resize(size, kernel), np.float32) for c in range(3)] + [np.asarray(Image.fromarray(a * 255).resize(size, kernel), np.float32)]

    sharp, smooth = planes(Image.LANCZOS), planes(Image.HAMMING)
    alpha = np.where(smooth[3] > 0.5, np.clip(sharp[3], 0, 255), 0)
    alpha = np.where(smooth[3] < 64, np.minimum(alpha, smooth[3]), alpha)  # nor may the overshoot thicken what is faint
    inside = ~grow(alpha < 250, 2, diagonal=True)
    out = np.zeros((size[1], size[0], 4), np.float32)
    for c in range(3):
        out[..., c] = np.where(inside, sharp[c] / np.maximum(sharp[3] / 255, 1e-4), smooth[c] / np.maximum(smooth[3] / 255, 1e-4))
    out[..., 3] = alpha
    out[alpha < 0.5] = 0
    return np.clip(out.round(), 0, 255).astype(np.uint8)


def colour_mask(frame: np.ndarray, rules: list[str]) -> np.ndarray:
    """Pixels matching any of `rules`, each a few comparisons on r, g, b (and a, alpha) joined by "and",
    such as "r>205 and b-g<48". An empty list matches every pixel."""
    if not rules:
        return np.ones(frame.shape[:2], bool)
    names = {n: frame[..., i].astype(int) for i, n in enumerate("rgba")}
    out = np.zeros(frame.shape[:2], bool)
    for rule in rules:
        m = np.ones(frame.shape[:2], bool)
        for part in rule.split(" and "):
            left, op, right = re.fullmatch(r"\s*([rgba0-9+\- ]+?)\s*([<>])\s*(-?\d+)\s*", part).groups()
            value = sum((-1 if sign == "-" else 1) * (names[term] if term in names else int(term)) for sign, term in re.findall(r"([+-]?)\s*([rgba]|\d+)", left))
            m &= (value > int(right)) if op == ">" else (value < int(right))
        out |= m
    return out


def main_part(mask: np.ndarray) -> np.ndarray:
    """The largest connected piece of a mask (the creature, without loose leaves, orbs and sparkles)."""
    labels, areas = label(mask)
    return labels == int(areas[1:].argmax()) + 1 if len(areas) > 1 else mask


def overlap_shift(ref: np.ndarray, mask: np.ndarray) -> int:
    """How far right to move `mask` for the best overlap with `ref` (as frame_shifts does for "body")."""
    return _best_overlap(ref, mask)
