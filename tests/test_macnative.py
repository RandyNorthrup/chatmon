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
