"""The stage window (X11, Windows, macOS) keeping up with its screen: unplugged, resized, rescaled."""

import pytest
from PyQt6.QtCore import QPoint, QRect
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


def test_a_screen_that_moves_under_it_is_covered_where_it_is_now(stage):
    """Another screen unplugged: KDE Plasma and sway move the one left (to 0,0), and the chatmon's place, on the old
    spot, is on no screen. The stage covers its own screen where it is now, on its next tick (tests/test_compositors.py
    sees KWin do it)."""
    now = stage.screen().geometry()
    stage._geo = now.translated(now.width(), 0)  # where it was: right of the screen that went
    stage.behavior.x = stage._geo.x() + 600  # walking there, on the old spot
    assert stage._screen_at(QPoint(int(stage.behavior.x), stage._geo.center().y())) is None
    stage._tick()
    assert stage._geo == now and now.contains(int(stage.behavior.x), now.center().y())


def test_a_screen_that_moves_wakes_the_stage_within_a_frame(stage):
    """Not at its next idle tick (up to IDLE_FLOOR, a second, away): the screen's own word that it moved."""
    stage._tick()
    stage._timer.start(1000)  # idle
    stage.screen().geometryChanged.emit(stage.screen().geometry())
    assert stage._timer.remainingTime() <= 1000 / 60 + 1


def test_a_closed_stage_hears_no_more_of_its_screen(stage):
    screen = stage.screen()
    stage.close_stage()
    assert stage._watched is None
    stage._timer.stop()
    screen.geometryChanged.emit(screen.geometry())
    assert not stage._timer.isActive()
