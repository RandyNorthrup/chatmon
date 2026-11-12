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
    try:
        assert desk.quiet() in (None, "Focus", *presence._QUNS.values()) and isinstance(desk.reduce_motion(), bool)
    finally:
        desk.close()


@windows
def test_windows_11s_focus_is_read_off_the_screens_thread():
    """FocusSessionManager, from WinRT through ctypes, on a thread of its own: Windows 11 answers True or
    False; a Windows without Focus (Windows 10, Windows Server) says it can't tell."""
    import time

    from chatmon import winfocus

    focus = winfocus.Focus(every=0.2)
    try:
        has_focus = sys.getwindowsversion().build >= 23504 and sys.getwindowsversion().product_type == 1  # a workstation
        deadline = time.monotonic() + 10
        # it answers, or (finding no Focus) its thread ends
        while focus.active is None and focus._thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert focus.active in ((True, False) if has_focus else (True, False, None))
        assert focus._thread.is_alive() == (focus.active is not None)
    finally:
        focus.close()
    assert focus.active is None and not focus._thread.is_alive()


@windows
def test_focus_holds_bubbles_on_windows(monkeypatch):
    desk = presence.Desk("windows")
    monkeypatch.setattr(presence, "_win_quiet", lambda: None)

    class On:
        active = True

        def close(self):
            pass

    desk._focus = On()
    assert desk.quiet() == "Focus"
    desk._focus.active = None  # can't tell: not quiet
    assert desk.quiet() is None
    monkeypatch.setattr(presence, "_win_quiet", lambda: "a presentation")
    assert desk.quiet() == "a presentation"  # what SHQueryUserNotificationState says comes first


@macos
def test_macos_readings():
    idle = presence._mac_idle()
    assert isinstance(idle, float) and idle >= 0
    assert presence._mac_reduce_motion() in (True, False, None)
    desk = presence.Desk("cocoa")
    assert desk.quiet() is None and isinstance(desk.reduce_motion(), bool)


def test_a_full_screen_app_fills_the_chatmons_screen_from_its_top_edge():
    """As macOS's window list has it: a full-screen app's window, or either half of Split View, starts at the
    screen's very top (no menu bar); every other window starts below the menu bar."""
    from chatmon.macnative import Window, fills_from_top

    screen = (0.0, 0.0, 1280.0, 1024.0)
    full = Window(pid=7, layer=0, on_screen=True, bounds=(0.0, 0.0, 1280.0, 1024.0))
    left_half = Window(7, 0, True, (0.0, 0.0, 636.0, 1024.0))
    maximized = Window(7, 0, True, (0.0, 25.0, 1280.0, 920.0))  # below the menu bar
    title_strip = Window(7, 0, True, (0.0, -44.0, 1280.0, 44.0))  # a full-screen app's hidden title bar
    menu_bar = Window(9, 24, True, (0.0, 0.0, 1280.0, 25.0))  # not an app's window
    elsewhere = Window(7, 0, True, (1280.0, 0.0, 1920.0, 1080.0))  # full screen, on the other monitor
    assert fills_from_top(screen, [maximized, full]) and fills_from_top(screen, [left_half])
    assert not fills_from_top(screen, [maximized, title_strip, menu_bar, elsewhere])
    assert fills_from_top((1280.0, 0.0, 1920.0, 1080.0), [elsewhere])


def test_bubbles_wait_on_macos_while_a_full_screen_app_is_over_the_chatmon(monkeypatch):
    from chatmon import macnative

    over = []
    monkeypatch.setattr(macnative, "full_screen_over", lambda view: view in over)
    monkeypatch.setattr(presence.sys, "platform", "darwin")
    desk = presence.Desk("cocoa")
    assert desk.quiet(1234) is None and not desk.covered(1234)
    over.append(1234)
    assert desk.quiet(1234) == "a full-screen app" and desk.covered(1234)
    assert presence.Desk("offscreen").quiet(1234) is None  # only Qt's cocoa windows are NSViews to ask about


def test_every_reading_answers_or_says_it_cant(qapp):
    desk = presence.Desk("offscreen")
    try:
        idle = desk.idle_seconds()
        assert idle is None or idle >= 0
        assert desk.quiet() in (None, "Do Not Disturb", "a full-screen app", "Focus", *presence._QUNS.values())
        assert desk.covered(0) in (True, False)
        assert isinstance(desk.reduce_motion(), bool) and isinstance(desk.high_contrast(), bool)
    finally:
        desk.close()  # on Windows, the Focus thread its quiet() started


def test_the_overlay_tells_when_youre_away(qapp, monkeypatch):
    monkeypatch.setattr(presence.sys, "platform", "linux")
    desk = presence.Desk("wayland")
    desk.overlay_idle_since = presence.time.monotonic() - 60  # the compositor said so a minute ago
    assert desk.idle_seconds() == pytest.approx(presence.AWAY_AFTER + 60, abs=1)


def test_gnome_says_how_long_youve_been_away(qapp, monkeypatch):
    """Against a real Mutter (tests/gnome-session.sh): its IdleMonitor, where Chatmon reads it."""
    import os

    from chatmon import presence

    bus = presence._session_bus()
    path, iface = "/org/gnome/Mutter/IdleMonitor/Core", "org.gnome.Mutter.IdleMonitor"
    if not bus or presence._dbus_call(bus, iface, path, iface, "GetIdletime") is None:
        if os.environ.get("CHATMON_GNOME_SESSION"):
            pytest.fail("Mutter's IdleMonitor didn't answer")
        pytest.skip("no GNOME session here")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    seconds = presence.Desk("wayland").idle_seconds()
    assert isinstance(seconds, float) and 0 <= seconds < 3600
