"""The platform's own readings, called for real on each CI runner: they answer, or say they can't (None),
and never raise."""

import sys

import pytest

from chatmon import presence

windows = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
macos = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


@windows
def test_windows_readings():
    idle = presence._win_idle()
    assert isinstance(idle, float) and idle >= 0
    assert presence._win_quiet() in (None, *presence._QUNS.values())
    assert presence._win_setting(presence._SPI_GETCLIENTAREAANIMATION) in (0, 1)
    assert presence._win_high_contrast() in (True, False)
    assert presence._win_covered(0) is False  # no stage window: nothing to cover
    desk = presence.Desk("windows")
    assert desk.quiet() in (None, *presence._QUNS.values()) and isinstance(desk.reduce_motion(), bool)


@macos
def test_macos_readings():
    idle = presence._mac_idle()
    assert isinstance(idle, float) and idle >= 0
    assert presence._mac_reduce_motion() in (True, False, None)
    desk = presence.Desk("cocoa")
    assert desk.quiet() is None and isinstance(desk.reduce_motion(), bool)


def test_every_reading_answers_or_says_it_cant(qapp):
    desk = presence.Desk("offscreen")
    idle = desk.idle_seconds()
    assert idle is None or idle >= 0
    assert desk.quiet() in (None, "Do Not Disturb", "a full-screen app", *presence._QUNS.values())
    assert desk.covered(0) in (True, False)
    assert isinstance(desk.reduce_motion(), bool) and isinstance(desk.high_contrast(), bool)


def test_the_overlay_tells_when_youre_away(qapp, monkeypatch):
    monkeypatch.setattr(presence.sys, "platform", "linux")
    desk = presence.Desk("wayland")
    desk.overlay_idle_since = presence.time.monotonic() - 60  # the compositor said so a minute ago
    assert desk.idle_seconds() == pytest.approx(presence.AWAY_AFTER + 60, abs=1)
