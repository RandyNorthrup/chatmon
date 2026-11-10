"""The animation strips themselves: sizes match the manifest, and the penguin doesn't slide about."""

import json
from pathlib import Path

import pytest
from PyQt6.QtGui import QImage

ANIM = Path(__file__).resolve().parent.parent / "penguin_companion" / "anim"
MANIFEST = json.loads((ANIM / "manifest.json").read_text(encoding="utf-8"))
# Front views keep the white penguin mark on the belly in every frame: it should stay put.
FRONT = ["idle", "talk", "wave", "think", "hop", "sleep", "alert"]
MAX_DRIFT = 4  # px, at the strips' 240 px height


def _rgba(name: str) -> tuple[bytes, int, int, int]:
    img = QImage(str(ANIM / f"{name}.png")).convertToFormat(QImage.Format.Format_RGBA8888)
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    return bytes(ptr), img.width(), img.height(), img.bytesPerLine()


def _belly_x(data: bytes, bpl: int, x0: int, w: int, h: int) -> float:
    total = count = 0
    for y in range(0, h, 2):
        row = y * bpl
        for x in range(x0, x0 + w, 2):
            i = row + 4 * x
            if data[i + 3] > 200 and data[i] > 245 and data[i + 1] > 245 and data[i + 2] > 245:
                total += x - x0
                count += 1
    assert count, "no belly mark found"
    return total / count


@pytest.mark.parametrize("name", sorted(MANIFEST))
def test_strip_matches_its_manifest_entry(name):
    m = MANIFEST[name]
    _, width, height, _ = _rgba(name)
    assert (width, height) == (m["frames"] * m["w"], m["h"])


@pytest.mark.parametrize("name", FRONT)
def test_front_view_frames_keep_the_body_in_place(name):
    m = MANIFEST[name]
    data, _, height, bpl = _rgba(name)
    xs = [_belly_x(data, bpl, i * m["w"], m["w"], height) for i in range(m["frames"])]
    assert max(xs) - min(xs) <= MAX_DRIFT, f"{name} belly mark wanders {[round(x - xs[0]) for x in xs]}"
