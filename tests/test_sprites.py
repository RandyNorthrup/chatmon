"""The frames the stage draws: kept once each, hit-tested by a mask, and kept for the screen before."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from chatmon import paths, sprites  # noqa: E402
from chatmon.sprites import Sprites  # noqa: E402


@pytest.fixture
def fresh(qapp):
    """No frames left over from other tests: each Sprites here cuts its own."""
    sprites._CUT.clear()
    yield
    sprites._CUT.clear()


def test_a_frame_is_kept_once_with_a_mask_that_agrees_with_its_pixels(fresh):
    frame = Sprites(paths.anim_dir(), 120, 2.0).frame("wave", 2, False)
    assert frame.pixmap.devicePixelRatio() == 2.0
    assert not any(isinstance(v, type(frame.image)) for v in vars(frame).values())  # no QImage beside the pixmap
    pixels = frame.pixmap.toImage()  # the oracle: the pixmap's own alpha
    w, h = pixels.width(), pixels.height()
    assert len(frame.mask) == w * h
    solid = 0
    for dy in range(h):
        for dx in range(w):
            expected = pixels.pixelColor(dx, dy).alpha() > sprites.OPAQUE
            assert frame.mask[dy * w + dx] == expected, (dx, dy)
            solid += expected
    assert 0 < solid < w * h  # the fixture has both: penguin and the clear space round it
    # Logical coordinates: half the device pixels on a 2x screen.
    centre = next((dx // 2, dy // 2) for dy in range(0, h, 2) for dx in range(0, w, 2) if pixels.pixelColor(dx, dy).alpha() > 200)
    assert frame.hit(*centre)
    assert not frame.hit(-1, 0) and not frame.hit(0, frame.height() + 1)
    assert frame.width() == round(w / 2) and frame.height() == round(h / 2)


def test_the_menu_bar_icon_still_has_the_frames_shape(fresh):
    frame = Sprites(paths.anim_dir(), 120, 1.0).frame("idle", 0, False)
    icon = sprites.silhouette(frame)
    assert not icon.isNull() and icon.width() <= frame.pixmap.width() and icon.height() <= frame.pixmap.height()


def test_the_previous_screens_frames_are_kept_for_a_drag_back(fresh):
    first = Sprites(paths.anim_dir(), 120, 1.0).frame("idle", 0, False)
    second = Sprites(paths.anim_dir(), 120, 2.0).frame("idle", 0, False)
    assert second is not first and second.scale == 2.0
    again = Sprites(paths.anim_dir(), 120, 1.0)
    assert again.frame("idle", 0, False) is first  # not cut again
    Sprites(paths.anim_dir(), 120, 1.5).frame("idle", 0, False)  # a third screen: the oldest (2x) goes
    assert Sprites(paths.anim_dir(), 120, 1.0).frame("idle", 0, False) is first
    assert Sprites(paths.anim_dir(), 120, 2.0).frame("idle", 0, False) is not second
