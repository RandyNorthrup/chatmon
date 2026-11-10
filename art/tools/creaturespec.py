"""What creature-cut.py and creature-qc.py share: the table in creatures.json and the measurements
made on a frame (where the body is, where it stands, where its anchor is, which specks are stray).

Frames are RGBA numpy arrays, as in spritefix.py. Needs Pillow and numpy.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import spritefix

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "creatures.json"
ANIM_ROOT = HERE.parent.parent / "chatmon" / "anim"
SOLID = 200  # alpha above which a pixel is part of the drawing itself, not of a glow or an edge
SHOWN = 32  # alpha above which a pixel shows at all (the limit the QC counts from)
SPECK = 12  # strip px: a loose piece smaller than this is a speck
FAR = 6  # strip px: a speck further than this from the creature is on its own
KEYS = {"green": np.array([2.0, 174.0, 61.0]), "magenta": np.array([251.0, 6.0, 250.0])}  # the sheets' keys, as measured


def load(path: Path = SPEC_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def anim_spec(spec: dict, creature: str, anim: str) -> dict:
    """One animation's entry with the creature's defaults filled in."""
    c = spec["creatures"][creature]
    return {**c.get("defaults", {}), **c["anims"][anim]}


def body(frame: np.ndarray, colours: dict, band: list[float] | None = None, part: str = "body") -> np.ndarray:
    """The creature in a frame: its largest solid piece (loose leaves, orbs and sparkles drop out),
    narrowed to the colours the table lists under `part` and without those it lists as "effect"
    (flames, mist). `band` keeps only that share of its height, top to bottom, such as [0.3, 0.78]."""
    solid = frame[..., 3] > SOLID
    if not solid.any():
        return solid
    whole = spritefix.main_part(solid)
    m = whole.copy()
    if colours.get(part):
        m &= spritefix.colour_mask(frame, colours[part])
    if part == "body" and colours.get("effect"):
        m &= ~spritefix.colour_mask(frame, colours["effect"])
    if band is not None:
        rows = np.nonzero(whole.any(1))[0]
        top, height = rows.min(), rows.max() - rows.min() + 1
        keep = np.zeros_like(m)
        keep[top + int(height * band[0]) : top + int(np.ceil(height * band[1]))] = True
        m &= keep
    return m


def floor_row(frame: np.ndarray, colours: dict) -> float | None:
    """The row the creature stands on (or, floating, the tip of its tail): the lowest row its largest
    solid piece reaches, effects left out (flames lick below the paws), read off the alpha so a frame
    scaled down still gives a fraction of a pixel."""
    m = body(frame, {"effect": colours.get("effect")})
    rows = np.nonzero(m.any(1))[0]
    if len(rows) == 0:
        return None
    last = rows.max()
    cols = m[last]
    below = frame[min(last + 1, frame.shape[0] - 1), :, 3][cols].max() / 255 if last + 1 < frame.shape[0] else 0.0
    return float(last + below)


def anchor_x(frame: np.ndarray, colours: dict, how: dict) -> float | None:
    """Where a frame's anchor is, left to right. `how["by"]` picks it:
    centre  the middle of the body (its mean x), within how["band"] if given
    feet    the mean x of the body's lowest how["rows"] rows (default: the bottom eighth)
    mark    the mean x of the colours the table lists under how["part"] (a belly, a charm), or of
            the how["top"] largest patches of them
    cut     the middle of what shows at the bottom edge (peek)
    """
    by = how["by"]
    if by == "cut":
        return float(spritefix._cut_x(frame))
    if by == "mark":
        m = body(frame, colours, how.get("band"), how.get("part", "mark"))
        if how.get("top") and m.any():  # only its largest pieces: a belly, not every patch of that colour
            labels, areas = spritefix.label(m)
            m = np.isin(labels, np.argsort(areas[1:])[::-1][: how["top"]] + 1)
    else:
        m = body(frame, colours, how.get("band"))
        if by == "feet" and m.any():
            rows = np.nonzero(m.any(1))[0]
            height = rows.max() - rows.min() + 1
            keep = np.zeros_like(m)
            keep[rows.max() + 1 - int(how.get("rows", max(4, height // 8))) : rows.max() + 1] = True
            m &= keep
    if not m.any():
        return None
    weight = m.sum(0)
    return float((weight * np.arange(m.shape[1])).sum() / weight.sum())


def shift_between(ref: np.ndarray, frame: np.ndarray, colours: dict, how: dict) -> float | None:
    """How far right `frame` has to move for its anchor to sit where `ref`'s does."""
    if how["by"] == "none":
        return 0.0
    if how["by"] == "overlap":
        return float(spritefix.overlap_shift(body(ref, colours, how.get("band")), body(frame, colours, how.get("band"))))
    a, b = anchor_x(ref, colours, how), anchor_x(frame, colours, how)
    return None if a is None or b is None else a - b


def stray_specks(frame: np.ndarray, loose: bool) -> tuple[np.ndarray, int, int]:
    """A strip frame's specks that are not meant, as a mask and a count, and the count of loose
    pieces that are. A speck is a loose piece of under SPECK showing pixels, more than FAR px from
    the creature. It is unmeant if the animation has no loose effects at all, or if it is faint (no
    pixel above half alpha): at half this size on screen, that is noise, not a sparkle."""
    labels, areas = spritefix.label(frame[..., 3] > SHOWN)
    if len(areas) < 3:
        return np.zeros(frame.shape[:2], bool), 0, 0
    main = int(areas[1:].argmax()) + 1
    close = np.zeros(len(areas), bool)
    close[np.unique(labels[spritefix.grow(labels == main, FAR, diagonal=True)])] = True
    peak = np.zeros(len(areas), np.uint8)
    np.maximum.at(peak, labels.ravel(), frame[..., 3].ravel())
    stray = (areas < SPECK) & ~close & ((peak < 128) | (not loose))
    stray[0] = False
    pieces = np.ones(len(areas), bool)
    pieces[[0, main]] = False
    return stray[labels], int(stray.sum()), int((pieces & ~stray).sum())


def frames_of(strip: np.ndarray, entry: dict) -> list[np.ndarray]:
    return spritefix.split(strip, entry["frames"], entry["w"])


def screen_factor(entry: dict, size: float) -> float:
    """Strip pixels to pixels on screen at the app's `size` setting (as sprites.py scales them)."""
    return entry.get("scale", 1.0) * size / entry["h"]
