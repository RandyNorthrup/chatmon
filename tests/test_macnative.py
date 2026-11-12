"""macOS: what Chatmon tells AppKit itself. Run where Qt's cocoa platform is (CI's macOS runner has a desktop
session): `QT_QPA_PLATFORM=cocoa python -m pytest tests/test_macnative.py`."""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


@pytest.fixture
def cocoa(qapp):
    from PyQt6.QtGui import QGuiApplication

    if QGuiApplication.platformName() != "cocoa":
        pytest.skip("needs Qt's cocoa platform (QT_QPA_PLATFORM=cocoa)")
    return qapp


def test_the_stage_floats_on_every_space_but_not_in_full_screen_apps(cocoa):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QWidget

    from chatmon import clickthrough, macnative

    window = QWidget(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
    window.resize(200, 200)
    window.show()
    cocoa.processEvents()
    assert macnative.float_everywhere(window)
    toggle = clickthrough.for_window(window)
    assert type(toggle) is clickthrough.MacPointerToggle
    for i in range(50):  # the pointer crossing the chatmon: the window's Spaces must survive it
        toggle._accept(i % 2 == 0)
    behavior = macnative.collection_behavior(window)
    assert behavior & macnative.OVERLAY == macnative.OVERLAY
    assert not behavior & (macnative.FULL_SCREEN_AUXILIARY | macnative.FULL_SCREEN_PRIMARY | macnative.MOVE_TO_ACTIVE_SPACE)
    macnative.activate()  # never raises
    window.close()


def _until(app, check, seconds: float) -> bool:
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if check():
            return True
        time.sleep(0.2)
    return False


def test_a_full_screen_app_over_the_chatmon_is_seen(cocoa):
    """Another app goes full screen on the chatmon's screen, as a real full-screen Space (macOS animates into
    it): the stage is seen to be under it, and out from under it again once that app has gone."""
    import os
    import subprocess

    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QWidget

    from chatmon import macnative

    stage = QWidget(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
    stage.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    stage.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    stage.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)  # as the stage: shown while another app is active
    stage.setGeometry(QGuiApplication.primaryScreen().geometry())
    stage.show()
    cocoa.processEvents()
    assert macnative.float_everywhere(stage)
    view = int(stage.winId())
    assert not macnative.full_screen_over(view) and not macnative.full_screen_over(0)
    script = ("from PyQt6.QtCore import QTimer\nfrom PyQt6.QtWidgets import QApplication, QLabel\napp = QApplication([])\n"
              "w = QLabel('A full-screen app')\nw.showFullScreen()\nQTimer.singleShot(30000, app.quit)\napp.exec()\n")
    other = subprocess.Popen([sys.executable, "-c", script], env=dict(os.environ, QT_QPA_PLATFORM="cocoa"))
    try:
        assert _until(cocoa, lambda: macnative.full_screen_over(view), 12)
    finally:
        other.terminate()
        other.wait(10)
    assert _until(cocoa, lambda: not macnative.full_screen_over(view), 12)
    stage.close()
