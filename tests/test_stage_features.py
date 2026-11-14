"""What the stage offers the app beyond drawing the chatmon: an agents badge, reduced motion, and following the
pointer to another screen. The recording surface and fake clock are test_stage_timer's."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QPointF, QRect  # noqa: E402
from PyQt6.QtGui import QImage, QPainter, QRegion  # noqa: E402
from PyQt6.QtWidgets import QMenu  # noqa: E402

from chatmon import penguin  # noqa: E402
from test_stage_timer import follow_the_clock, make_stage  # noqa: E402


@pytest.fixture
def stage(qapp):
    s, clock = make_stage()
    follow_the_clock(s, clock, 3, check=False)  # past the greeting
    s.behavior.set_attending(True, clock.t)  # standing still
    s._tick()
    yield s, clock
    s.close_stage()


def picture(s) -> QImage:
    img = QImage(s._geo.width(), s._geo.height(), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    s.paint(p, QRegion(0, 0, img.width(), img.height()))
    p.end()
    return img


def close_to(colour, wanted, slack=24):
    return all(abs(a - b) <= slack for a, b in zip(colour.getRgb()[:3], wanted.getRgb()[:3], strict=True))


def test_the_badge_counts_agents_by_state_with_a_shape_for_each(stage):
    s, clock = stage
    assert s._badges == () and s.badge_description() == ""
    s.set_badge(working=2, needs_you=1)
    assert s._timer.remainingTime() <= 17  # drawn within a frame
    s._tick()
    (waiting, rw, figure_w), (working, rk, figure_k) = s._badges
    assert (waiting, figure_w, working, figure_k) == ("needs-you", "1", "working", "2")
    assert s.badge_description() == "1 agent needs you, 2 agents working"
    sprite = s.sprites.frame(s._frame.anim, s._frame.index, s._frame.mirror)
    right = max(x + w for x, y, w, h in sprite.rects) + s._penguin.x()
    top = min(y for x, y, w, h in sprite.rects) + s._penguin.y()
    assert abs(rw.center().x() - right) <= penguin.BADGE and abs(rw.center().y() - top) <= penguin.BADGE  # at its top right
    assert rk.right() < rw.left()  # working beside it, never on top of it
    img = picture(s)
    for state, r in (("needs-you", rw), ("working", rk)):
        fill, _ink = penguin.BADGE_COLOURS[state]
        beside = QPointF(r.left() + r.width() * 0.15, r.center().y()).toPoint()  # inside, left of the figure
        assert close_to(img.pixelColor(beside), fill), state
        # The shape says which, not the colour alone: a fifth in from the corner is in a circle, not a diamond.
        corner = QPointF(r.left() + r.width() * 0.2, r.top() + r.height() * 0.2)
        assert penguin.Stage._badge_path(state, r).contains(corner) == (state == "working"), state
    s.set_badge(working=12, needs_you=0)
    s._tick()
    assert [(state, figure) for state, _, figure in s._badges] == [("working", "9+")]
    s.surface.damaged = QRegion()
    old = s._badges[0][1]
    s.set_badge(0, 0)
    s._tick()
    assert s._badges == () and s.surface.damaged.contains(old.center().toPoint())  # its place drawn again, empty
    assert not close_to(picture(s).pixelColor(old.center().toPoint()), penguin.BADGE_COLOURS["working"][0])


def test_a_needs_you_badge_pulses_unless_motion_is_reduced(stage):
    s, clock = stage
    s.set_badge(needs_you=1)
    ticks = follow_the_clock(s, clock, 2, check=False)
    assert max(wait for _, _, wait in ticks) <= penguin.PULSE_STEP + 0.01  # it ticks for the ring
    pulses = set()
    for _ in range(8):
        s._tick()
        pulses.add(s._pulse)
        clock.t += s.next_tick_in
    assert pulses == {0, 1, 2, 3}
    s.set_reduced_motion(True)
    looks = set()
    for _ in range(5):
        s._tick()
        looks.add(s._key[4])
        clock.t += s.next_tick_in
    assert len(looks) == 1 and s._pulse == -1 and s.next_tick_in == pytest.approx(penguin.IDLE_FLOOR)  # still: nothing to tick for


def test_reduced_motion_stills_the_creature_and_its_zs(qapp):
    s, clock = make_stage(sleep_after=5)
    follow_the_clock(s, clock, 30, check=False)
    assert s._frame.anim == "sleep"
    s.set_reduced_motion(True)
    assert s.behavior.reduced_motion
    seen = set()
    for _ in range(20):
        s._tick()
        seen.add((s._frame.anim, s._frame.index, s._z_phase))
        clock.t += s.next_tick_in
    assert seen == {("sleep", 3, 2)}  # asleep, one pose, all three z's, still
    s.set_reduced_motion(False)
    phases = set()
    for _ in range(40):
        s._tick()
        phases.add(s._z_phase)
        clock.t += s.next_tick_in
    assert {0, 1, 2} <= phases  # counting up again (after nodding off once more)
    s.close_stage()


class Screen:
    """A monitor, as much of one as the stage asks about."""

    def __init__(self, name, x, y, w, h):
        self._name, self._geo = name, QRect(x, y, w, h)

    def name(self):
        return self._name

    def geometry(self):
        return QRect(self._geo)

    def availableGeometry(self):
        return QRect(self._geo)

    def devicePixelRatio(self):
        return 1.0

    def refreshRate(self):
        return 60.0


@pytest.fixture
def two_screens(stage):
    s, clock = stage
    left, right = Screen("left", 0, 0, 1920, 1080), Screen("right", 1920, 0, 1280, 800)
    s._screen_at = lambda point: left if point.x() < 1920 else right
    s._use_screen(left)
    s._tick()
    s._pointer_known = lambda: True
    return s, clock, left, right


def tick_for(s, clock, seconds, step=0.25):
    end = clock.t + seconds
    while clock.t < end:
        s._tick()
        clock.t += min(step, s.next_tick_in)


def test_it_follows_the_pointer_to_its_screen_only_when_asked_and_after_a_second(two_screens):
    s, clock, left, right = two_screens
    s._cursor_pos = lambda: QPoint(2500, 300)  # on the right-hand screen
    tick_for(s, clock, 3)
    assert s.screen() is left  # off by default
    assert s.follow_pointer_screen(True)
    tick_for(s, clock, 0.75)
    assert s.screen() is left  # not for a pointer passing through
    tick_for(s, clock, 0.75)
    assert s.screen() is right
    floor = right.availableGeometry()
    assert floor.left() + penguin.EDGE <= s.behavior.x <= floor.right() - penguin.EDGE
    assert s.behavior.x == pytest.approx(1920 + penguin.EDGE + 400 / 1920 * (1280 - 2 * penguin.EDGE), abs=1)  # as far along
    tick_for(s, clock, 2)
    assert s._frame.lift == 0 and s.screen() is right  # landed, and stays
    s._cursor_pos = lambda: QPoint(100, 100)
    menu = QMenu()
    menu.addAction("Ask")
    s.open_menu(menu, QPoint(2000, 100))  # you're using it: it stays where it is
    tick_for(s, clock, 3)
    assert s.screen() is right
    s.close_menu()
    tick_for(s, clock, 2)
    assert s.screen() is left
    assert not s.follow_pointer_screen(False)
    s._cursor_pos = lambda: QPoint(2500, 300)
    tick_for(s, clock, 3)
    assert s.screen() is left
    menu.deleteLater()


def test_where_the_pointer_isnt_known_it_cant_follow(stage):
    s, clock = stage
    s._pointer_known = lambda: False  # a Wayland desktop
    assert not s.follow_pointer_screen(True) and not s._follow
