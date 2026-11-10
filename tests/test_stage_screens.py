"""The stage window (X11, Windows, macOS) keeping up with its screen: unplugged, resized, rescaled."""

import pytest
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QGuiApplication

from chatmon import paths
from chatmon.behavior import Behavior
from chatmon.penguin import Stage, StageWindow
from chatmon.sprites import Sprites


@pytest.fixture
def stage(qapp):
    sprites = Sprites(paths.anim_dir(), 120)
    s = Stage(sprites, Behavior(sprites.anims(), now=0, x=400), surface_factory=StageWindow)
    yield s
    s.close_stage()


class Unplugged:
    """A screen Qt has let go of: anything asked of it fails, as a deleted QScreen's wrapper does."""

    def __getattr__(self, name):
        raise RuntimeError("wrapped C/C++ object of type QScreen has been deleted")


def test_losing_its_screen_takes_it_to_one_still_there(stage):
    gone = Unplugged()
    stage._screen = gone
    stage._screen_removed(gone)
    assert stage.screen() is QGuiApplication.primaryScreen()
    stage._tick()  # draws again, on the screen it has now


def test_a_screen_that_changes_size_is_covered_again(stage):
    stage._geo = QRect(0, 0, 10, 10)  # as it was before the resolution or the scale setting changed
    stage._tick()
    assert stage._geo == stage.screen().geometry()


def test_a_screen_of_another_scale_gets_sprites_drawn_for_it(stage):
    scales = []
    stage.scale_changed_to.connect(scales.append)
    stage._use_screen(stage.screen(), again=True)
    assert scales == [stage.screen().devicePixelRatio()]
