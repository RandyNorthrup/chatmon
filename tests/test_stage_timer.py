"""The stage's clock: asleep until the next change it can see, awake within a frame of anything it's told, at the
screen's refresh rate while something moves, and drawing on the device pixel grid. A recording surface stands in
for the window or the compositor; the stage, its behaviour and its sprites are the real ones."""

import copy
import math
import os
import random
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEventLoop, QPoint, QPointF, Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QGuiApplication, QRegion  # noqa: E402

from chatmon import paths, penguin  # noqa: E402
from chatmon.behavior import Behavior  # noqa: E402
from chatmon.penguin import Stage  # noqa: E402
from chatmon.sprites import Sprites  # noqa: E402


def spin(seconds: float) -> None:
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec()


class Surface:
    """Records what the stage asks of its surface."""

    hosts_windows = draws_menus = False
    polls_pointer = False
    scale = 1.0

    def __init__(self, stage):
        self.inputs: tuple = ()
        self.damaged = QRegion()
        self.follows = 0

    def set_screen(self, screen, geometry):
        pass

    def damage(self, region):
        self.damaged = self.damaged.united(region)

    def set_input(self, rects):
        self.inputs = tuple(rects)

    def follow_pointer(self, hit):
        self.follows += 1

    def device_scale(self):
        return self.scale

    def close(self):
        pass


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Screen:
    """The real screen, saying it refreshes `hz` times a second."""

    def __init__(self, hz):
        self._real, self.hz = QGuiApplication.primaryScreen(), hz

    def refreshRate(self):
        return self.hz

    def __getattr__(self, name):
        return getattr(self._real, name)


def make_stage(surface=Surface, clock=None, **behaviour):
    sprites = Sprites(paths.anim_dir(), 120)
    clock = clock or Clock()
    b = Behavior(sprites.anims(), now=clock(), x=400, rng=random.Random(1), **{"walk": False, "sleep_after": 0, **behaviour})
    s = Stage(sprites, b, surface_factory=surface)
    s._clock = clock
    return s, clock


@pytest.fixture
def stage(qapp):
    s, clock = make_stage()
    yield s, clock
    s.close_stage()


def on_screen(f):
    return (f.anim, f.index, f.mirror, round(f.x), round(f.lift))


def follow_the_clock(s, clock, seconds, check=True):
    """Run the stage as its own timer would, each tick at the delay it last asked for. With `check`, a copy of
    the behaviour ticked 1000 times a second shows nothing new until a frame before that tick: whatever changes
    is drawn within a frame of changing. Return the ticks."""
    ticks, end = [], clock.t + seconds
    while clock.t < end:
        s.behavior.on_change, told = None, s.behavior.on_change
        twin = copy.deepcopy(s.behavior)
        s.behavior.on_change = told
        s.surface.damaged = QRegion()
        before, where = s._frame, s._penguin.toAlignedRect()
        s._tick()
        drawn, wait = s._frame, s.next_tick_in
        if before is not None and on_screen(before) != on_screen(drawn):
            assert s.surface.damaged.intersects(where.united(s._penguin.toAlignedRect())), "a new frame, not drawn"
        ticks.append((clock.t, drawn, wait))
        if check:
            twin.set_floor(s.behavior.left, s.behavior.right)
            twin.tick(clock.t)
            u, frame = clock.t + 0.001, s._frame_interval()
            while u < clock.t + wait - frame:
                assert on_screen(twin.tick(u)) == on_screen(drawn), f"changed at {u:.3f}; the stage slept until {clock.t + wait:.3f}"
                u += 0.001
        clock.t += wait
    return ticks


def test_standing_idle_it_sleeps_until_the_next_frame_and_misses_none(stage):
    s, clock = stage
    follow_the_clock(s, clock, 5, check=False)  # the greeting wave
    s.behavior.set_attending(True, clock.t)  # idle: still, blinking every 3-5 s
    ticks = follow_the_clock(s, clock, 60)
    assert len(ticks) < 60 + 16 * 4  # a second at most while still, and each blink's frames: the old clock ticked 1800 times
    assert max(wait for _, _, wait in ticks) == pytest.approx(penguin.IDLE_FLOOR)
    blinks = sum(1 for (_, a, _), (_, b, _) in zip(ticks, ticks[1:], strict=False) if (a.index, b.index) == (0, 2))
    assert blinks >= 11  # still blinking, on time


def test_asleep_it_ticks_for_the_frames_and_the_zs_only(qapp):
    s, clock = make_stage(sleep_after=8)
    ticks = follow_the_clock(s, clock, 40)
    asleep = [t for t in ticks if t[1].anim == "sleep" and t[1].index >= 3]
    assert asleep and len(ticks) < 40 * 6
    phases = {0, 1, 2}
    assert {int(t / penguin.Z_STEP) % 3 for t, _, _ in asleep} == phases  # the z's still count up
    s.close_stage()


def test_covered_hidden_or_not_drawing_it_hardly_ticks_or_stops(stage):
    s, clock = stage
    follow_the_clock(s, clock, 3, check=False)
    s.set_covered(True)
    s._tick()
    assert s.next_tick_in == penguin.COVERED_TICK
    s.set_covered(False)
    s.behavior.set_hidden(True, clock.t)
    ticks = follow_the_clock(s, clock, 15)
    gone = [wait for (_, f, wait), (_, g, _) in zip(ticks, ticks[1:], strict=False) if f.anim is None and g.anim is None]
    assert gone and all(wait == pytest.approx(penguin.IDLE_FLOOR) for wait in gone)  # nothing shown: once a second
    s.set_drawing(False)
    assert not s._timer.isActive()
    s.behavior.set_alert(True, clock.t)
    s.show_message("Reminder", "stretch")
    assert not s._timer.isActive()  # nothing is drawn while nothing can be seen
    s.set_drawing(True)
    assert s._timer.isActive()


def test_anything_it_is_told_wakes_it_within_a_frame(stage):
    s, clock = stage
    follow_the_clock(s, clock, 3, check=False)
    s.behavior.set_attending(True, clock.t)
    follow_the_clock(s, clock, 2, check=False)
    frame_ms = math.ceil(s._frame_interval() * 1000)
    s._tick()
    assert s._timer.remainingTime() > 5 * frame_ms  # asleep for a while
    s.move(QPointF(5, 5), QPointF(5, 5))
    assert s._timer.remainingTime() <= frame_ms
    s._tick()
    s.behavior.set_alert(True, clock.t)  # the app, changing the behaviour
    assert s._timer.remainingTime() <= frame_ms
    s._tick()
    s.show_message("Hello", "")
    assert s._timer.remainingTime() <= frame_ms


def test_the_pointer_is_polled_every_frame_only_near_the_chatmon(qapp):
    class Polling(Surface):
        polls_pointer = True

    s, clock = make_stage(Polling)
    s._tick()
    x, y, w, h = s._inputs[0]
    origin = s.origin()
    s._cursor_pos = lambda: QPoint(x + w // 2, y + h // 2) + origin
    s._poll_pointer()
    assert s._pointer_timer.interval() == math.ceil(s._frame_interval() * 1000)
    s._cursor_pos = lambda: QPoint(x + w + penguin.NEAR + 300, y) + origin
    s._poll_pointer()
    assert s._pointer_timer.interval() == round(penguin.FAR_POLL * 1000)
    follows = s.surface.follows
    s.set_covered(True)
    assert not s._pointer_timer.isActive()
    s._poll_pointer()
    assert s.surface.follows == follows  # covered: nothing to click, nothing polled
    s.set_covered(False)
    assert s._pointer_timer.isActive()
    s.set_drawing(False)
    assert not s._pointer_timer.isActive()
    s.close_stage()


def test_a_surface_that_needs_no_polling_is_never_polled(stage):
    s, clock = stage
    s._tick()
    s._poll_pointer()
    assert s.surface.follows == 0 and not s._pointer_timer.isActive()


def test_while_it_moves_it_ticks_at_the_screens_refresh_rate(stage):
    s, clock = stage
    for hz, saving, expected in ((144, False, 1 / 144), (50, False, 1 / 50), (144, True, 1 / penguin.SAVER_FPS), (0, False, 1 / penguin.DEFAULT_HZ)):
        screen = Screen(hz)
        s._screen, s._screen_at = screen, lambda _point, screen=screen: screen
        s.power_saving = saving
        s.behavior.hold(400, 300, clock.t)
        s.behavior.release(clock.t)  # falling: every frame
        clock.t += 0.01
        s._tick()
        assert s.behavior.falling and s.next_tick_in == pytest.approx(expected), (hz, saving)
        assert s._timer.interval() == math.ceil(expected * 1000)
        follow_the_clock(s, clock, 2, check=False)  # landed


def test_the_sprite_sits_on_the_device_pixel_grid(stage):
    s, clock = stage
    follow_the_clock(s, clock, 3, check=False)
    s.behavior.set_attending(True, clock.t)
    s.surface.scale = 2.0
    halves = 0
    for x in (400.0, 400.3, 400.6, 401.2, 401.7):
        s.behavior.x = x
        s._tick()
        left, top = s._penguin.x(), s._penguin.y()
        assert (left * 2).is_integer() and (top * 2).is_integer()
        halves += not left.is_integer()
        sprite = s.sprites.frame(s._frame.anim, s._frame.index, s._frame.mirror)
        for (rx, ry, rw, rh), (ix, iy, iw, ih) in zip(sprite.rects, s.surface.inputs, strict=False):
            # what takes clicks covers the outline wherever the half-pixel puts it
            assert ix <= rx + left and ix + iw >= rx + rw + left and iy <= ry + top and iy + ih >= ry + rh + top
    assert halves >= 2  # not rounded to whole stage pixels
    s.surface.scale = 1.0
    s.behavior.x = 400.6
    s._tick()
    assert s._penguin.x().is_integer()


def test_a_drag_redraws_on_the_pointer_moving_not_on_a_clock(qapp):
    s, _clock = make_stage(clock=time.monotonic)
    spin(0.3)
    x, y, w, h = s.surface.inputs[len(s.surface.inputs) // 2]
    grab = QPointF(x + w / 2, y + h / 2)
    assert s._target_at(grab.toPoint()) == "penguin"
    origin = QPointF(s.origin())
    s.press(grab, grab + origin, Qt.MouseButton.LeftButton)
    spin(0.05)
    s._timer.stop()  # nothing else would bring a tick: only the move may
    start = s._frame.x
    to = grab + QPointF(40, -20)
    s.move(to, to + origin)
    assert s._timer.isActive() and s._timer.remainingTime() <= math.ceil(s._frame_interval() * 1000)
    spin(0.05)
    assert s._frame.anim == "hop" and s._frame.x == pytest.approx(start + 40)  # held up, where the pointer took it
    assert s.surface.damaged.intersects(s._penguin.toAlignedRect())
    s.release(to, to + origin, Qt.MouseButton.LeftButton)
    s.close_stage()
