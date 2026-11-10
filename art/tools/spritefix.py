"""Pixel fixes and per-frame alignment shared by penguin-slice.py and penguin-touchup.py.

Frames are RGBA numpy arrays (height x width x 4, uint8). Needs Pillow and numpy.
"""

from __future__ import annotations

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
