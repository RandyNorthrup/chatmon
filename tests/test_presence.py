"""The platform's own readings, called for real on each CI runner: they answer, or say they can't (None),
and never raise."""

import os
import sys
from pathlib import Path

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


# -- Linux: the portal's settings, GNOME's, Qt's, and each server's Do Not Disturb, without waiting (M4A-01, -04, -05)


def _portal_says(desk, key: str, value: int) -> None:
    """The portal's SettingChanged signal, as linuxsession.PortalSettings hears it from the bus."""
    from PyQt6.QtDBus import QDBusMessage, QDBusVariant

    from chatmon import linuxsession

    signal = QDBusMessage.createSignal(linuxsession.PORTAL[1], linuxsession.PORTAL[2], "SettingChanged")
    signal.setArguments([linuxsession.APPEARANCE, key, QDBusVariant(value)])
    desk._portal._setting_changed(signal)


@pytest.fixture
def linux_desk(qapp, monkeypatch):
    pytest.importorskip("PyQt6.QtDBus")
    monkeypatch.setattr(presence.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    which = presence.shutil.which  # GNOME's settings are told here, not read from this machine's gsettings
    monkeypatch.setattr(presence.shutil, "which", lambda name, *args, **kwargs: None if name == "gsettings" else which(name, *args, **kwargs))
    desk = presence.Desk("wayland")
    changes = []
    desk.settings_changed.connect(lambda: changes.append(True))
    yield desk, changes
    from PyQt6 import sip

    if not sip.isdeleted(desk):
        desk.close()


def test_the_portals_contrast_decides_and_says_when_it_changes(linux_desk):
    desk, changes = linux_desk
    desk._gsetting("org.gnome.desktop.a11y.interface", "high-contrast")  # asked, as high_contrast() does
    gnome = desk._gnome[("org.gnome.desktop.a11y.interface", "high-contrast")]
    gnome._set("true")  # GNOME says high contrast...
    changes.clear()
    desk.high_contrast()  # the first reading starts the portal's listener
    _portal_says(desk, "contrast", 0)  # ...but the portal, asked first, has no preference
    assert desk.high_contrast() is False and changes == [True]
    _portal_says(desk, "contrast", 1)
    assert desk.high_contrast() is True and changes == [True, True]
    _portal_says(desk, "contrast", 1)  # the same again: no news
    assert changes == [True, True]
    _portal_says(desk, "reduced-motion", 1)
    assert desk.reduce_motion() is True and changes == [True, True, True]
    _portal_says(desk, "contrast", 7)  # not a value the portal defines: not known, so GNOME's word counts
    assert desk.high_contrast() is True


def test_without_the_portal_gnome_then_qt_say_whether_contrast_is_high(linux_desk, monkeypatch):
    desk, changes = linux_desk
    assert desk.high_contrast() is False  # nothing known yet: no portal on this bus, no gsettings, Qt's no preference
    gnome = desk._gnome[("org.gnome.desktop.a11y.interface", "high-contrast")]
    gnome._set("true")  # `gsettings get` answers, or `gsettings monitor` hears a change
    assert desk.high_contrast() is True and changes == [True]
    gnome._set("false")
    assert desk.high_contrast() is False and changes == [True, True]
    monkeypatch.setattr(presence, "_qt_high_contrast", lambda: True)  # Qt 6.10's word, from the platform theme
    assert desk.high_contrast() is False  # GNOME said no: its word comes before Qt's
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "Hyprland")
    assert presence.Desk("wayland").high_contrast() is True  # no portal answer and no GNOME: Qt's word


def test_macos_high_contrast_is_appkits_increase_contrast(monkeypatch):
    seen = []
    monkeypatch.setattr(presence, "_mac_increase_contrast", lambda: seen.append(True) or True)
    monkeypatch.setattr(presence.sys, "platform", "darwin")
    assert presence.Desk("cocoa").high_contrast() is True and seen == [True]


@macos
def test_macos_reads_increase_contrast():
    assert presence._mac_increase_contrast() in (True, False)
    assert presence.Desk("cocoa").high_contrast() == presence._mac_increase_contrast()


def test_qts_contrast_change_is_passed_on(qapp):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QGuiApplication

    from PyQt6.QtCore import pyqtBoundSignal

    hints = QGuiApplication.styleHints().accessibility()
    if not isinstance(getattr(hints, "contrastPreferenceChanged", None), pyqtBoundSignal):
        pytest.skip("Qt before 6.10, or PyQt6 6.11, which wraps contrastPreferenceChanged as a method, not a signal")
    desk = presence.Desk("offscreen")
    changes = []
    desk.settings_changed.connect(lambda: changes.append(True))
    hints.contrastPreferenceChanged.emit(Qt.ContrastPreference.HighContrast)
    assert changes == [True]


def test_windows_setting_changes_are_passed_on(qapp):
    desk = presence.Desk("windows")
    settings, readers = [], []
    desk.settings_changed.connect(lambda: settings.append(True))
    desk.screen_reader_changed.connect(lambda: readers.append(True))
    for action in (presence.SPI_SETHIGHCONTRAST, presence.SPI_SETCLIENTAREAANIMATION, presence.SPI_SETMESSAGEDURATION):
        desk.windows_setting_changed(action)
    desk.windows_setting_changed(0x0014)  # SPI_SETDESKWALLPAPER: not ours
    desk.windows_setting_changed(0)  # no action named (a theme or policy change)
    assert settings == [True] * 3 and readers == []
    desk.windows_setting_changed(presence.SPI_SETSCREENREADER)
    assert readers == [True] and len(settings) == 3


def test_a_full_screen_window_counts_only_on_the_stages_screen():
    left, right = (0, 0, 1920, 1080), (1920, 0, 2560, 1440)  # two monitors side by side
    assert presence.covers(left, left) and presence.covers(right, right)
    assert not presence.covers(right, left) and not presence.covers(left, right)
    assert not presence.covers((1920, 0, 1, 1), (0, 0, 3840, 1080))  # the stage's middle is past its edge
    assert presence.covers((1920, 0, 1920, 1080), (1920, 0, 1920, 1080))


def test_covered_on_x11_asks_where_the_full_screen_window_is(monkeypatch):
    class X:  # an X server's answers: a full-screen video in front, on the right monitor
        ok = True
        rects = {7: (1920, 0, 2560, 1440), 100: (0, 0, 1920, 1080), 200: (1920, 0, 2560, 1440)}

        def fullscreen_window(self):
            return 7

        def rect(self, window):
            return self.rects.get(window)

    monkeypatch.setattr(presence.sys, "platform", "linux")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    desk = presence.Desk("xcb")
    desk._x11 = X()
    assert desk.covered(200) and not desk.covered(100)  # the stage on the right monitor, then on the left
    assert desk.covered(0)  # where the stage is can't be told: as before, any full-screen window counts
    assert desk.quiet(100) == "a full-screen app"  # bubbles still wait, as Windows' notification state has it


@pytest.mark.parametrize("server, on, off", [
    ("dunst", True, False),
    ("Plasma", True, False),
    ("SwayNotificationCenter", True, False),
    ("Xfce Notify Daemon", True, False),
    ("mako", ["default", "do-not-disturb"], ["default"]),
])
def test_each_notification_servers_do_not_disturb_holds_bubbles(linux_desk, server, on, off):
    from chatmon import linuxsession

    desk, _ = linux_desk
    assert desk.quiet() is None  # nothing known yet (no bus here): not quiet
    dnd = desk._dnd
    dnd.server = server
    dnd.heard(on)
    assert desk.quiet() == "Do Not Disturb"
    dnd.heard(off)
    assert desk.quiet() is None
    dnd.heard("an answer of the wrong kind")
    assert dnd.state is None and desk.quiet() is None
    assert server in linuxsession.DND_QUESTIONS


def test_the_linux_listeners_go_with_their_desk(linux_desk):
    """What they hear after the Desk has gone (an answer still on its way) must reach nothing: they belong to it."""
    from PyQt6 import sip

    desk, _ = linux_desk
    portal, dnd = desk._linux("portal"), desk._linux("dnd")
    desk._gsetting("org.gnome.desktop.interface", "enable-animations")
    gnome = desk._gnome[("org.gnome.desktop.interface", "enable-animations")]
    assert portal.parent() is desk and dnd.parent() is desk and gnome.parent() is desk
    sip.delete(desk)
    assert sip.isdeleted(portal) and sip.isdeleted(dnd) and sip.isdeleted(gnome)


X11_CLIENT = r"""
import sys, time
sys.path.insert(0, sys.argv[1])
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget
app = QApplication([])
from chatmon import presence
window = QWidget(None, Qt.WindowType.FramelessWindowHint)
window.setGeometry(120, 80, 320, 200)
window.show()
end = time.monotonic() + 1.5
while time.monotonic() < end:
    app.processEvents()
    time.sleep(0.02)
x = presence._X11()
g = window.geometry()
print("qt", g.x(), g.y(), g.width(), g.height())
print("x11", *(x.rect(int(window.winId())) or ("none",)))
print("root", *(x.rect(x.root) or ("none",))[2:])
"""


@pytest.mark.skipif(not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"), reason="Linux with an X display")
def test_x11_says_where_a_window_is():
    """The X server's own answer (XGetGeometry, XTranslateCoordinates), which covered() compares: a window's place on
    the whole X screen, as Qt put it there."""
    import subprocess

    env = dict(os.environ, QT_QPA_PLATFORM="xcb", QT_ENABLE_HIGHDPI_SCALING="0", QT_SCALE_FACTOR="1")
    env.pop("WAYLAND_DISPLAY", None)
    out = subprocess.run([sys.executable, "-c", X11_CLIENT, str(Path(__file__).resolve().parent.parent)], capture_output=True, text=True,
                         timeout=60, env=env)
    lines = dict(line.split(" ", 1) for line in out.stdout.splitlines() if " " in line)
    assert "qt" in lines and lines.get("x11") == lines["qt"], out.stdout + out.stderr
    width, height = map(int, lines["root"].split())
    assert width >= 440 and height >= 280  # the root window spans the screen the window is on
